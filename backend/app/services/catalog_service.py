from __future__ import annotations

import json

from app.database import db
from app.errors import ApiError
from app.seed_data import (
    SEED_CATALOG,
    STUDY_SEED_SOURCE,
    build_product_note,
    build_seed_questions,
)
from app.services.cache_service import catalog_cache
from app.utils.common import sha256_json, utc_now_iso


ACTIVE_EXAM_CODES = {exam["code"] for exam in SEED_CATALOG}
DEFAULT_PRACTICE_COUNTS = {"mcq": 0, "mains": 0}


def _seed_topic_note_id(topic_id: str) -> str:
    return f"tnote_{topic_id}"


def _parse_metadata(raw: str | None) -> dict:
    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}


def _is_seeded_study_question(metadata_raw: str | None) -> bool:
    return _parse_metadata(metadata_raw).get("seed_source") == STUDY_SEED_SOURCE


def _subtopics_by_topic() -> dict[str, list[dict]]:
    rows = db.fetch_all("SELECT * FROM subtopics ORDER BY topic_id ASC, display_order ASC")
    mapped: dict[str, list[dict]] = {}
    for row in rows:
        mapped.setdefault(row["topic_id"], []).append(
            {
                "id": row["id"],
                "topic_id": row["topic_id"],
                "name": row["name"],
                "display_order": row["display_order"],
            }
        )
    return mapped


def _study_question_counts() -> dict[str, dict[str, int]]:
    rows = db.fetch_all("SELECT topic_id, type, metadata_json FROM questions WHERE is_deleted = 0")
    counts: dict[str, dict[str, int]] = {}
    for row in rows:
        if not _is_seeded_study_question(row.get("metadata_json")):
            continue
        bucket = counts.setdefault(row["topic_id"], dict(DEFAULT_PRACTICE_COUNTS))
        if row["type"] == "mcq":
            bucket["mcq"] += 1
        else:
            bucket["mains"] += 1
    return counts


def seed_catalog() -> None:
    now = utc_now_iso()
    seeded_question_ids: set[str] = set()
    seeded_subtopic_ids: set[str] = set()
    seeded_topic_note_ids: set[str] = set()

    with db.session(write=True) as conn:
        for exam in SEED_CATALOG:
            exam_payload = {key: exam[key] for key in ["code", "name", "description"]}
            conn.execute(
                """
                INSERT OR REPLACE INTO exams (id, code, name, description, version, content_hash, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    exam["id"],
                    exam["code"],
                    exam["name"],
                    exam["description"],
                    1,
                    sha256_json(exam_payload),
                    now,
                ],
            )
            for subject in exam["subjects"]:
                subject_payload = {key: subject[key] for key in ["code", "name", "description", "display_order"]}
                conn.execute(
                    """
                    INSERT OR REPLACE INTO subjects
                    (id, exam_id, code, name, description, display_order, version, content_hash, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        subject["id"],
                        exam["id"],
                        subject["code"],
                        subject["name"],
                        subject["description"],
                        subject["display_order"],
                        1,
                        sha256_json(subject_payload),
                        now,
                    ],
                )

                for topic_order, topic in enumerate(subject["topics"], start=1):
                    topic_payload = {
                        "code": topic["code"],
                        "name": topic["name"],
                        "description": topic["description"],
                        "parent_topic_id": None,
                        "display_order": topic_order,
                        "learning_objectives": topic["learning_objectives"],
                        "difficulty": topic["difficulty"],
                        "estimated_minutes": topic["estimated_minutes"],
                        "knowledge": topic["knowledge"],
                    }
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO topics
                        (id, exam_id, subject_id, code, name, description, parent_topic_id, display_order,
                         learning_objectives_json, difficulty, estimated_minutes, knowledge_json,
                         version, content_hash, updated_at, is_deleted)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                        """,
                        [
                            topic["id"],
                            exam["id"],
                            subject["id"],
                            topic["code"],
                            topic["name"],
                            topic["description"],
                            None,
                            topic_order,
                            json.dumps(topic["learning_objectives"]),
                            topic["difficulty"],
                            topic["estimated_minutes"],
                            json.dumps(topic["knowledge"]),
                            1,
                            sha256_json(topic_payload),
                            now,
                        ],
                    )

                    for subtopic_order, subtopic_name in enumerate(topic.get("subtopics", []), start=1):
                        subtopic_id = f"subtopic_{topic['id']}_{subtopic_order}"
                        seeded_subtopic_ids.add(subtopic_id)
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO subtopics
                            (id, topic_id, name, display_order, updated_at)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            [subtopic_id, topic["id"], subtopic_name, subtopic_order, now],
                        )

                    topic_note_id = _seed_topic_note_id(topic["id"])
                    seeded_topic_note_ids.add(topic_note_id)
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO topic_notes
                        (id, topic_id, content_json, updated_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        [topic_note_id, topic["id"], json.dumps(build_product_note(topic)), now],
                    )

                    bundle = build_seed_questions(exam, subject, topic)
                    bundle_hash = sha256_json(bundle)
                    for question in bundle:
                        seeded_question_ids.add(question["id"])
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO questions
                            (id, exam_id, subject_id, topic_id, type, prompt, options_json, answer_key,
                             explanation, explanation_hint, difficulty, metadata_json, version, bundle_hash,
                             content_hash, updated_at, is_deleted)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                            """,
                            [
                                question["id"],
                                exam["id"],
                                subject["id"],
                                topic["id"],
                                question["type"],
                                question["prompt"],
                                json.dumps(question["options"]) if question["options"] else None,
                                question["correct_option_id"],
                                question["explanation"],
                                question["explanation_hint"],
                                question["difficulty"],
                                json.dumps(question["metadata"]),
                                1,
                                bundle_hash,
                                sha256_json(question),
                                now,
                            ],
                        )

        existing_subtopics = conn.execute("SELECT id FROM subtopics").fetchall()
        for row in existing_subtopics:
            if row[0] not in seeded_subtopic_ids:
                conn.execute("DELETE FROM subtopics WHERE id = ?", [row[0]])

        existing_topic_notes = conn.execute("SELECT id FROM topic_notes").fetchall()
        for row in existing_topic_notes:
            if row[0] not in seeded_topic_note_ids:
                conn.execute("DELETE FROM topic_notes WHERE id = ?", [row[0]])

        existing_questions = conn.execute("SELECT id, metadata_json FROM questions").fetchall()
        for row in existing_questions:
            question_id, metadata_raw = row
            if _is_seeded_study_question(metadata_raw) and question_id not in seeded_question_ids:
                conn.execute("DELETE FROM questions WHERE id = ?", [question_id])

    catalog_cache.clear()


def get_catalog_tree(exam_id: str | None = None) -> list[dict]:
    cache_key = f"tree:{exam_id or 'all'}"
    cached = catalog_cache.get(cache_key)
    if cached is not None:
        return cached

    exams = db.fetch_all("SELECT * FROM exams ORDER BY name ASC")
    exams = [exam for exam in exams if exam["code"] in ACTIVE_EXAM_CODES and (exam_id is None or exam["id"] == exam_id)]
    active_exam_ids = {exam["id"] for exam in exams}
    subjects = db.fetch_all("SELECT * FROM subjects ORDER BY exam_id ASC, display_order ASC")
    subjects = [subject for subject in subjects if subject["exam_id"] in active_exam_ids]
    active_subject_ids = {subject["id"] for subject in subjects}
    topics = db.fetch_all("SELECT * FROM topics WHERE is_deleted = 0 ORDER BY subject_id ASC, display_order ASC, name ASC")
    topics = [topic for topic in topics if topic["subject_id"] in active_subject_ids]
    subtopics_map = _subtopics_by_topic()
    question_counts = _study_question_counts()

    topic_map: dict[str, list[dict]] = {}
    for topic in topics:
        entry = dict(topic)
        entry["learning_objectives"] = json.loads(entry["learning_objectives_json"])
        entry["knowledge"] = json.loads(entry.get("knowledge_json") or "{}")
        entry["practice_counts"] = question_counts.get(topic["id"], dict(DEFAULT_PRACTICE_COUNTS))
        entry["subtopics"] = subtopics_map.get(topic["id"], [])
        entry.pop("learning_objectives_json", None)
        entry.pop("knowledge_json", None)
        topic_map.setdefault(topic["subject_id"], []).append(entry)

    subject_map: dict[str, list[dict]] = {}
    for subject in subjects:
        entry = dict(subject)
        entry["topics"] = topic_map.get(subject["id"], [])
        subject_map.setdefault(subject["exam_id"], []).append(entry)

    tree: list[dict] = []
    for exam in exams:
        entry = dict(exam)
        entry["subjects"] = subject_map.get(exam["id"], [])
        tree.append(entry)

    catalog_cache[cache_key] = tree
    return tree


def get_topic_context(topic_id: str) -> tuple[dict, dict, dict]:
    topic = db.fetch_one("SELECT * FROM topics WHERE id = ? AND is_deleted = 0", [topic_id])
    if not topic:
        raise ApiError(404, "TOPIC_NOT_FOUND", "Topic not found.")
    subject = db.fetch_one("SELECT * FROM subjects WHERE id = ?", [topic["subject_id"]])
    exam = db.fetch_one("SELECT * FROM exams WHERE id = ?", [topic["exam_id"]])
    if not subject or not exam:
        raise ApiError(500, "TOPIC_CONTEXT_INCOMPLETE", "Topic context is incomplete.")
    parsed = dict(topic)
    parsed["learning_objectives"] = json.loads(parsed["learning_objectives_json"])
    parsed["knowledge"] = json.loads(parsed.get("knowledge_json") or "{}")
    parsed["subtopics"] = _subtopics_by_topic().get(topic_id, [])
    return exam, subject, parsed
