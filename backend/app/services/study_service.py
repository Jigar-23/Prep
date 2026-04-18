from __future__ import annotations

import json
import threading

from app.database import db
from app.errors import ApiError
from app.seed_data import STUDY_SEED_SOURCE
from app.services.ai_service import ai_service
from app.services.catalog_service import get_catalog_tree, get_topic_context
from app.services.continuity_service import get_answer_streak, get_daily_question
from app.services.evaluation_service import evaluate_submission
from app.services.llm_service import llm_service
from app.services.performance_service import get_performance_snapshot
from app.services.revision_engine import revision_engine
from app.services.improvement_service import improvement_service
from app.utils.common import new_id, stable_json_dumps, utc_now_iso


_topic_note_locks: dict[str, threading.Lock] = {}


def _parse_json(raw: str | None, default):
    try:
        return json.loads(raw) if raw else default
    except json.JSONDecodeError:
        return default


def _seeded_metadata(metadata_raw: str | None) -> dict:
    metadata = _parse_json(metadata_raw, {})
    return metadata if metadata.get("seed_source") == STUDY_SEED_SOURCE else {}


def _dashboard_exam_list(catalog: list[dict]) -> list[dict]:
    return [{"id": exam["id"], "code": exam["code"], "name": exam["name"], "description": exam["description"]} for exam in catalog]


def _find_exam(catalog: list[dict], exam_id: str | None = None) -> dict:
    if exam_id:
        match = next((exam for exam in catalog if exam["id"] == exam_id), None)
        if match:
            return match
    if not catalog:
        raise ApiError(404, "EXAM_NOT_FOUND", "Exam context is unavailable.")
    return catalog[0]


def _find_subject(exam: dict, subject_id: str) -> dict:
    subject = next((item for item in exam["subjects"] if item["id"] == subject_id), None)
    if not subject:
        raise ApiError(404, "SUBJECT_NOT_FOUND", "Subject not found for the selected exam.")
    return subject


def _find_exam_and_subject(catalog: list[dict], subject_id: str, exam_id: str | None = None) -> tuple[dict, dict]:
    if exam_id:
        exam = _find_exam(catalog, exam_id)
        subject = next((item for item in exam["subjects"] if item["id"] == subject_id), None)
        if subject:
            return exam, subject
    for exam in catalog:
        subject = next((item for item in exam["subjects"] if item["id"] == subject_id), None)
        if subject:
            return exam, subject
    raise ApiError(404, "SUBJECT_NOT_FOUND", "Subject not found.")


def _find_topic(exam: dict, topic_id: str) -> tuple[dict, dict]:
    for subject in exam["subjects"]:
        for topic in subject["topics"]:
            if topic["id"] == topic_id:
                return subject, topic
    raise ApiError(404, "TOPIC_NOT_FOUND", "Topic not found for the selected exam.")


def _last_score_for_exam(user_id: str, exam_id: str) -> float | None:
    upsc_row = db.fetch_one(
        """
        SELECT eh.created_at AS submitted_at, eh.scoring_json
        FROM evaluation_history eh
        JOIN topics t ON t.id = eh.topic_id
        WHERE eh.user_id = ? AND t.exam_id = ?
        ORDER BY eh.created_at DESC
        LIMIT 1
        """,
        [user_id, exam_id],
    )
    legacy_row = db.fetch_one(
        """
        SELECT a.submitted_at, a.score, e.max_score
        FROM attempts a
        LEFT JOIN evaluations e ON e.attempt_id = a.id
        WHERE a.user_id = ? AND a.exam_id = ?
        ORDER BY a.submitted_at DESC
        LIMIT 1
        """,
        [user_id, exam_id],
    )
    if not upsc_row and not legacy_row:
        return None
    if upsc_row and (not legacy_row or upsc_row["submitted_at"] >= legacy_row["submitted_at"]):
        scoring = _parse_json(upsc_row["scoring_json"], {})
        return round(float(scoring.get("scaled_score", 0.0)), 2)
    max_score = float((legacy_row or {}).get("max_score") or 10.0)
    return round((float(legacy_row["score"]) / max(max_score, 1.0)) * 10, 2)


def _performance_rows(snapshot: dict, *, scope: str, exam_id: str | None = None, subject_id: str | None = None) -> list[dict]:
    row_map = {
        "exam": snapshot.get("exam_breakdown", []),
        "subject": snapshot.get("subject_breakdown", []),
        "topic": snapshot.get("topic_breakdown", []),
    }
    rows = row_map.get(scope, [])
    return [
        row
        for row in rows
        if (exam_id is None or row.get("exam_id") == exam_id) and (subject_id is None or row.get("subject_id") == subject_id)
    ]


def _sorted_topics_for_exam(snapshot: dict, exam: dict) -> list[dict]:
    topic_rows = _performance_rows(snapshot, scope="topic", exam_id=exam["id"])
    topic_rows.sort(key=lambda row: (row["average_score"], row["trend_delta"], -row["total_attempts"], row["topic_id"]))
    return topic_rows


def _seeded_questions_for_topic(topic_id: str) -> list[dict]:
    rows = db.fetch_all(
        """
        SELECT id, topic_id, type, prompt, options_json, explanation_hint, difficulty, metadata_json
        FROM questions
        WHERE topic_id = ? AND is_deleted = 0
        ORDER BY type ASC, id ASC
        """,
        [topic_id],
    )
    questions: list[dict] = []
    for row in rows:
        metadata = _seeded_metadata(row.get("metadata_json"))
        if not metadata:
            continue
        questions.append(
            {
                "id": row["id"],
                "topic_id": row["topic_id"],
                "type": row["type"],
                "kind": metadata.get("kind", "mcq"),
                "prompt": row["prompt"],
                "options": _parse_json(row.get("options_json"), None),
                "difficulty": row["difficulty"],
                "explanation_hint": row["explanation_hint"],
                "recommended_word_limit": metadata.get("recommended_word_limit"),
            }
        )
    return questions


def _question_counts_for_topic(topic_id: str) -> dict[str, int]:
    counts = {"mcq": 0, "practice": 0, "pyq": 0}
    for question in _seeded_questions_for_topic(topic_id):
        counts[question["kind"]] = counts.get(question["kind"], 0) + 1
    return counts


def _topic_note(topic_id: str) -> dict | None:
    row = db.fetch_one("SELECT content_json FROM topic_notes WHERE topic_id = ?", [topic_id])
    if not row:
        return None
    return _parse_json(row["content_json"], None)


def _topic_note_lock(topic_id: str) -> threading.Lock:
    if topic_id not in _topic_note_locks:
        _topic_note_locks[topic_id] = threading.Lock()
    return _topic_note_locks[topic_id]


def _topic_note_is_usable(note: dict | None) -> bool:
    if not note:
        return False
    required = ["core_idea", "framework", "key_anchors", "answer_direction", "linkages"]
    for key in required:
        value = note.get(key)
        if key == "core_idea":
            if not isinstance(value, str) or len(value.strip()) < 20:
                return False
        else:
            if not isinstance(value, list) or len(value) == 0:
                return False
    return True


def _framework_note_from_bundle(*, topic: dict, bundle_notes: dict | None) -> dict:
    knowledge = topic.get("knowledge", {})
    summary = (bundle_notes or {}).get("summary", [])
    detailed = (bundle_notes or {}).get("detailed", [])
    framework = [section.get("heading", "").strip() for section in detailed if section.get("heading")]
    if not framework:
        framework = topic.get("subtopics", [])[:5] or knowledge.get("must_have_points", [])[:5] or [topic["name"]]
    key_anchors = (
        knowledge.get("core_facts", [])[:2]
        + knowledge.get("case_laws", [])[:2]
        + knowledge.get("value_addition", [])[:2]
    )
    if not key_anchors:
        key_anchors = [item for item in summary[:3] if isinstance(item, str) and item.strip()] or [f"{topic['name']} anchor"]
    answer_direction = [
        "Not addressed: question demand line in introduction.",
        "Weak: body without 3-5 structured dimensions.",
        "Missing: analytical closure with implication or reform.",
    ]
    linkages = [
        f"Link {topic['name']} with polity-governance outcomes.",
        f"Link {topic['name']} with current affairs evidence.",
    ] + knowledge.get("pyq", [])[:2]
    return {
        "core_idea": (summary[0] if summary else topic["description"])[:220],
        "framework": framework[:5],
        "key_anchors": key_anchors[:6],
        "answer_direction": answer_direction,
        "linkages": linkages[:5],
    }


def _ensure_topic_note(*, exam: dict, subject: dict, topic: dict) -> dict:
    existing = _topic_note(topic["id"])
    if _topic_note_is_usable(existing):
        return existing

    lock = _topic_note_lock(topic["id"])
    with lock:
        existing = _topic_note(topic["id"])
        if _topic_note_is_usable(existing):
            return existing

        bundle_notes = None
        try:
            bundle, _source = ai_service.generate_bundle(exam, subject, topic)
            bundle_notes = bundle.get("notes")
        except Exception:
            bundle_notes = None

        note_payload = _framework_note_from_bundle(topic=topic, bundle_notes=bundle_notes)
        db.execute(
            """
            INSERT OR REPLACE INTO topic_notes (id, topic_id, content_json, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            [new_id("tnote"), topic["id"], stable_json_dumps(note_payload), utc_now_iso()],
        )
        return note_payload


def _topic_preview(topic: dict, progress_rows: dict[str, dict]) -> dict:
    counts = _question_counts_for_topic(topic["id"])
    exam = db.fetch_one("SELECT * FROM exams WHERE id = ?", [topic["exam_id"]]) or {}
    subject = db.fetch_one("SELECT * FROM subjects WHERE id = ?", [topic["subject_id"]]) or {}
    note = _ensure_topic_note(exam=exam, subject=subject, topic=topic)
    progress = progress_rows.get(topic["id"])
    return {
        "topic_id": topic["id"],
        "topic_name": topic["name"],
        "description": topic["description"],
        "note_ready": note is not None,
        "note_preview": note["core_idea"] if note else "UPSC framework pending",
        "mcq_count": counts["mcq"],
        "practice_count": counts["practice"],
        "pyq_count": counts["pyq"],
        "progress_average_score": progress["average_score"] if progress else None,
        "progress_trend": progress["trend_delta"] if progress else None,
    }


def get_dashboard(*, user_id: str, exam_id: str | None = None) -> dict:
    catalog = get_catalog_tree()
    exam = _find_exam(catalog, exam_id)
    snapshot = get_performance_snapshot(user_id)
    streak = get_answer_streak(user_id)
    exam_row = next((row for row in snapshot.get("exam_breakdown", []) if row["exam_id"] == exam["id"]), None)
    subject_rows = {row["subject_id"]: row for row in _performance_rows(snapshot, scope="subject", exam_id=exam["id"])}
    improvement_summary = improvement_service.get_user_summary(user_id=user_id, exam_id=exam["id"])
    focus = improvement_service.get_user_focus(user_id=user_id, exam_id=exam["id"])

    recommended_action = None
    if focus and focus.get("topic_id"):
        # pick the weakest/most-pressured subtopic within the focus topic (if any)
        rows = db.fetch_all(
            """
            SELECT usw.*, s.name AS subtopic_name
            FROM user_subtopic_weakness usw
            JOIN subtopics s ON s.id = usw.subtopic_id
            WHERE usw.user_id = ? AND usw.topic_id = ?
            """,
            [user_id, focus["topic_id"]],
        )
        rows.sort(
            key=lambda row: (
                -int(row.get("consecutive_mistake_count") or 0),
                -int(row.get("repeated_mistake_count") or 0),
                str(row.get("updated_at") or ""),
            ),
            reverse=False,
        )
        if rows:
            top = rows[0]
            label = f"Fix {focus.get('weakest_area') or 'weakness'}: {top.get('subtopic_name') or 'subtopic'}"
            recommended_action = {
                "type": "retry_subtopic",
                "topic_id": focus["topic_id"],
                "subtopic_id": top["subtopic_id"],
                "label": label,
                "href": f"/topic/{focus['topic_id']}/subtopic/{top['subtopic_id']}",
            }

    subjects = [
        {
            "id": subject["id"],
            "exam_id": subject["exam_id"],
            "code": subject["code"],
            "name": subject["name"],
            "description": subject["description"],
            "topic_count": len(subject["topics"]),
            "href": f"/subject/{subject['id']}",
            "progress_average_score": subject_rows.get(subject["id"], {}).get("average_score"),
            "progress_trend": subject_rows.get(subject["id"], {}).get("trend_delta"),
            "due_revisions": int(subject_rows.get(subject["id"], {}).get("revisions_due", 0)),
        }
        for subject in exam["subjects"]
    ]

    topic_rows = [
        row
        for row in snapshot.get("topic_breakdown", [])
        if row["exam_id"] == exam["id"] and row.get("last_activity_at")
    ]
    topic_rows.sort(key=lambda row: row["last_activity_at"], reverse=True)
    continue_target = None
    if topic_rows:
        subject, topic = _find_topic(exam, topic_rows[0]["topic_id"])
        continue_target = {
            "subject_id": subject["id"],
            "topic_id": topic["id"],
            "subject_name": subject["name"],
            "topic_name": topic["name"],
            "href": f"/topic/{topic['id']}",
            "reason": "Continue where you last practiced.",
        }
    else:
        daily = get_daily_question(user_id, exam["id"])
        if daily.get("topic_id"):
            subject, topic = _find_topic(exam, daily["topic_id"])
            continue_target = {
                "subject_id": subject["id"],
                "topic_id": topic["id"],
                "subject_name": subject["name"],
                "topic_name": topic["name"],
                "href": f"/topic/{topic['id']}",
                "reason": daily["reason"],
            }

    return {
        "selected_exam_id": exam["id"],
        "selected_exam_code": exam["code"],
        "exams": _dashboard_exam_list(catalog),
        "summary": {
            "average_score": float(exam_row["average_score"]) if exam_row else 0.0,
            "due_revisions": int(exam_row["revisions_due"]) if exam_row else 0,
            "improvement_trend": float(exam_row["trend_delta"]) if exam_row else 0.0,
            "total_attempts": int(exam_row["total_attempts"]) if exam_row else 0,
            "streak": streak,
            "last_score": _last_score_for_exam(user_id, exam["id"]),
            "weakest_area": improvement_summary.get("weakest_area") or None,
            "most_repeated_mistake": improvement_summary.get("most_repeated_mistake") or None,
            "recommended_action": recommended_action,
        },
        "continue_target": continue_target,
        "subjects": subjects,
    }


def get_subject_page(*, user_id: str, subject_id: str, exam_id: str | None = None) -> dict:
    catalog = get_catalog_tree()
    exam, subject = _find_exam_and_subject(catalog, subject_id, exam_id)
    snapshot = get_performance_snapshot(user_id)
    topic_progress_rows = {row["topic_id"]: row for row in _performance_rows(snapshot, scope="topic", exam_id=exam["id"], subject_id=subject_id)}
    subject_row = next(
        (row for row in snapshot.get("subject_breakdown", []) if row["exam_id"] == exam["id"] and row["subject_id"] == subject_id),
        None,
    )

    previews = [_topic_preview(topic, topic_progress_rows) for topic in subject["topics"]]
    weak_topics = sorted(
        subject["topics"],
        key=lambda topic: (
            topic_progress_rows.get(topic["id"], {}).get("average_score", 0.0),
            topic_progress_rows.get(topic["id"], {}).get("trend_delta", 0.0),
            topic["display_order"],
        ),
    )[:4]

    return {
        "exam": {key: exam[key] for key in ["id", "code", "name", "description", "version", "content_hash", "updated_at"]},
        "subject": {key: subject[key] for key in ["id", "exam_id", "code", "name", "description", "display_order", "version", "content_hash", "updated_at"]},
        "syllabus": subject["topics"],
        "notes_topics": previews,
        "question_topics": previews,
        "mcq_topics": previews,
        "progress": {
            "average_score": float(subject_row["average_score"]) if subject_row else 0.0,
            "trend_delta": float(subject_row["trend_delta"]) if subject_row else 0.0,
            "total_attempts": int(subject_row["total_attempts"]) if subject_row else 0,
            "due_revisions": int(subject_row["revisions_due"]) if subject_row else 0,
            "weak_topics": [topic["name"] for topic in weak_topics],
        },
    }


def get_topic_page(*, user_id: str, topic_id: str) -> dict:
    exam, subject, topic = get_topic_context(topic_id)
    snapshot = get_performance_snapshot(user_id)
    progress_row = next(
        (row for row in snapshot.get("topic_breakdown", []) if row["topic_id"] == topic_id),
        None,
    )
    questions = _seeded_questions_for_topic(topic_id)
    notes = _ensure_topic_note(exam=exam, subject=subject, topic=topic)
    flashcard_row = db.fetch_one(
        "SELECT COUNT(*) AS total FROM flashcards WHERE topic_id = ? AND is_deleted = 0",
        [topic_id],
    )
    due_cards = revision_engine.get_due_cards(user_id=user_id, limit=200)
    due_count = sum(1 for card in due_cards["cards"] if card["topic_id"] == topic_id)
    next_review = next((card["progress"]["next_review"] for card in due_cards["cards"] if card["topic_id"] == topic_id), None)

    subtopics = topic.get("subtopics") or []
    progress_rows = db.fetch_all(
        """
        SELECT * FROM user_subtopic_progress
        WHERE user_id = ? AND topic_id = ?
        """,
        [user_id, topic_id],
    )
    progress_by_subtopic = {row["subtopic_id"]: row for row in progress_rows}

    weakness_rows = db.fetch_all(
        """
        SELECT * FROM user_subtopic_weakness
        WHERE user_id = ? AND topic_id = ?
        """,
        [user_id, topic_id],
    )
    weakness_by_subtopic = {row["subtopic_id"]: row for row in weakness_rows}

    completed_subtopics = [
        sub_id for sub_id, row in progress_by_subtopic.items() if (row.get("status") or "") == "done"
    ]

    def status_for(subtopic_id: str) -> str:
        progress = progress_by_subtopic.get(subtopic_id)
        if not progress:
            return "not_started"
        if int(progress.get("weakness_flag") or 0) == 1:
            return "weak"
        return str(progress.get("status") or "in_progress")

    def group_for(title: str) -> str:
        lowered = title.lower()
        if "act" in lowered or "charter" in lowered or "regulating" in lowered or "pitt" in lowered or "goi" in lowered:
            return "British Acts"
        if "company" in lowered:
            return "Company rule"
        if "movement" in lowered or "national" in lowered:
            return "National movement influence"
        return "Core subtopics"

    sections_map: dict[str, list[dict]] = {}
    weak_subtopics: list[dict] = []
    last_attempt = None
    for sub in subtopics:
        sub_id = sub["id"]
        title = sub["name"]
        status = status_for(sub_id)
        item = {"id": sub_id, "title": title, "status": status}
        sections_map.setdefault(group_for(title), []).append(item)
        if status == "weak":
            weak_subtopics.append(item)
        attempted_at = progress_by_subtopic.get(sub_id, {}).get("last_attempted_at")
        if attempted_at and (last_attempt is None or str(attempted_at) > str(last_attempt.get("at") or "")):
            last_attempt = {"subtopic_id": sub_id, "at": attempted_at}

    sections = [{"name": name, "items": items} for name, items in sections_map.items()]
    sections.sort(key=lambda s: s["name"])

    chapter_progress = {
        "total_subtopics": len(subtopics),
        "completed_count": len(completed_subtopics),
        "weak_count": len(weak_subtopics),
        "continue_subtopic_id": (last_attempt or {}).get("subtopic_id"),
    }

    return {
        "exam": exam,
        "subject": subject,
        "topic": {
            **topic,
            "practice_counts": topic.get("practice_counts")
            or {
                "mcq": sum(1 for item in questions if item["kind"] == "mcq"),
                "mains": sum(1 for item in questions if item["kind"] in {"practice", "pyq"}),
            },
        },
        "notes": notes,
        "notes_status": "ready" if _topic_note_is_usable(notes) else "coming_soon",
        "practice_mode": "answer_writing" if exam["code"] == "UPSC" else "mcq_only",
        "practice_questions": [item for item in questions if item["kind"] == "practice"],
        "pyqs": [item for item in questions if item["kind"] == "pyq"],
        "mcqs": [item for item in questions if item["kind"] == "mcq"],
        "flashcards": {
            "generated_count": int(flashcard_row["total"]) if flashcard_row else 0,
            "due_count": due_count,
            "next_review": next_review,
        },
        "progress": progress_row,
        "chapter_progress": chapter_progress,
        "weak_subtopics": weak_subtopics,
        "completed_subtopics": completed_subtopics,
        "sections": sections,
    }


def get_practice_page(*, user_id: str, exam_id: str | None = None) -> dict:
    catalog = get_catalog_tree()
    exam = _find_exam(catalog, exam_id)
    daily_question = get_daily_question(user_id, exam["id"])
    snapshot = get_performance_snapshot(user_id)
    topic_rows = _sorted_topics_for_exam(snapshot, exam)

    topic_lookup: dict[str, tuple[dict, dict]] = {}
    for subject in exam["subjects"]:
        for topic in subject["topics"]:
            topic_lookup[topic["id"]] = (subject, topic)

    weak_rows = topic_rows[:4]
    moderate_rows = topic_rows[4:8]
    weak_topics = []
    for row in weak_rows:
        if row["topic_id"] not in topic_lookup:
            continue
        subject, topic = topic_lookup[row["topic_id"]]
        weak_topics.append(
            {
                "topic_id": topic["id"],
                "topic_name": topic["name"],
                "subject_name": subject["name"],
                "href": f"/topic/{topic['id']}",
                "reason": "Weak-topic repair",
                "average_score": row["average_score"],
            }
        )
    moderate_topics = []
    for row in moderate_rows:
        if row["topic_id"] not in topic_lookup:
            continue
        subject, topic = topic_lookup[row["topic_id"]]
        moderate_topics.append(
            {
                "topic_id": topic["id"],
                "topic_name": topic["name"],
                "subject_name": subject["name"],
                "href": f"/topic/{topic['id']}",
                "reason": "Consolidation cycle",
                "average_score": row["average_score"],
            }
        )

    mixed_mcqs: list[dict] = []
    for row in weak_rows + moderate_rows:
        if row["topic_id"] not in topic_lookup:
            continue
        question = next((item for item in _seeded_questions_for_topic(row["topic_id"]) if item["kind"] == "mcq"), None)
        if question:
            mixed_mcqs.append(question)
        if len(mixed_mcqs) >= 6:
            break

    return {
        "exam": {"id": exam["id"], "code": exam["code"], "name": exam["name"], "description": exam["description"]},
        "daily_question": daily_question if daily_question.get("topic_id") else None,
        "weak_topics": weak_topics,
        "moderate_topics": moderate_topics,
        "mixed_mcqs": mixed_mcqs,
    }


def get_revision_page(*, user_id: str, exam_id: str | None = None) -> dict:
    catalog = get_catalog_tree()
    exam = _find_exam(catalog, exam_id)
    topic_ids = {topic["id"] for subject in exam["subjects"] for topic in subject["topics"]}
    topic_subject_lookup = {
        topic["id"]: subject["name"]
        for subject in exam["subjects"]
        for topic in subject["topics"]
    }
    review_cards = [
        card
        for card in revision_engine.get_due_cards(user_id=user_id, limit=200)["cards"]
        if card["topic_id"] in topic_ids
    ]
    snapshot = get_performance_snapshot(user_id)
    streak = get_answer_streak(user_id)
    exam_row = next((row for row in snapshot.get("exam_breakdown", []) if row["exam_id"] == exam["id"]), None)
    weak_topics = []
    for row in _sorted_topics_for_exam(snapshot, exam)[:6]:
        if row["topic_id"] not in topic_ids:
            continue
        _, topic = _find_topic(exam, row["topic_id"])
        weak_topics.append(
            {
                "topic_id": topic["id"],
                "topic_name": topic["name"],
                "subject_name": topic_subject_lookup[topic["id"]],
                "href": f"/topic/{topic['id']}",
                "average_score": row["average_score"],
                "trend_delta": row["trend_delta"],
            }
        )

    return {
        "exam": {"id": exam["id"], "code": exam["code"], "name": exam["name"], "description": exam["description"]},
        "summary": {
            "average_score": float(exam_row["average_score"]) if exam_row else 0.0,
            "due_revisions": len(review_cards),
            "improvement_trend": float(exam_row["trend_delta"]) if exam_row else 0.0,
            "total_attempts": int(exam_row["total_attempts"]) if exam_row else 0,
            "streak": streak,
            "last_score": _last_score_for_exam(user_id, exam["id"]),
        },
        "review_cards": review_cards[:40],
        "weak_topics": weak_topics,
    }


def preview_ocr(*, answer_text: str | None, handwritten_image_base64: str | None, handwritten_image_mime_type: str | None) -> dict:
    normalized = llm_service.clean_input(
        answer_text=answer_text,
        handwritten_image_base64=handwritten_image_base64,
        handwritten_image_mime_type=handwritten_image_mime_type,
    )
    cleaned = normalized.get("cleaned_answer", "").strip()
    if len(cleaned) < 20:
        raise ApiError(
            400,
            "INVALID_ANSWER",
            "We couldn’t read your handwriting clearly. Try a clearer image or paste text.",
            {
                "error_type": "INPUT_INVALID",
                "reason": "empty_or_unreadable",
                "partial_text": cleaned,
                "suggestions": ["Retry upload", "Paste text manually", "Use a clearer image"],
            },
        )
    return {"extracted_text": cleaned, "cleaned_text": cleaned}


def submit_mcq_attempt(*, user_id: str, payload: dict) -> dict:
    exam, subject, topic = get_topic_context(payload["topic_id"])
    if exam["id"] != payload["exam_id"] or subject["id"] != payload["subject_id"]:
        raise ApiError(400, "INVALID_ATTEMPT", "Exam or subject does not match the topic context.")
    return evaluate_submission(
        user_id,
        {
            "exam_id": payload["exam_id"],
            "subject_id": payload["subject_id"],
            "topic_id": payload["topic_id"],
            "question_id": payload["question_id"],
            "selected_option": payload["selected_option"],
        },
    )
