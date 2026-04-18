from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from app.database import db
from app.services.catalog_service import get_catalog_tree, get_topic_context
from app.services.improvement_service import improvement_service
from app.services.performance_service import get_performance_snapshot
from app.utils.common import sha256_text, utc_now_iso


def _date_from_iso(value: str) -> datetime.date:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def _today_utc() -> datetime.date:
    return datetime.now(timezone.utc).date()


def _gs_label(subject_code: str) -> str:
    return subject_code.split("_")[0] if "_" in subject_code else subject_code


def update_answer_streak(user_id: str, answered_at: str) -> int:
    answer_date = _date_from_iso(answered_at)
    record = db.fetch_one("SELECT daily_answer_streak, last_answer_date FROM user_continuity WHERE user_id = ?", [user_id])
    if not record:
        streak = 1
    else:
        last_answer_date = _date_from_iso(record["last_answer_date"]) if record["last_answer_date"] else None
        if last_answer_date == answer_date:
            streak = int(record["daily_answer_streak"])
        elif last_answer_date == answer_date - timedelta(days=1):
            streak = int(record["daily_answer_streak"]) + 1
        else:
            streak = 1

    db.execute(
        """
        INSERT INTO user_continuity (user_id, daily_answer_streak, last_answer_date, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            daily_answer_streak = excluded.daily_answer_streak,
            last_answer_date = excluded.last_answer_date,
            updated_at = excluded.updated_at
        """,
        [user_id, streak, answer_date.isoformat(), utc_now_iso()],
    )
    return streak


def get_answer_streak(user_id: str) -> int:
    record = db.fetch_one("SELECT daily_answer_streak, last_answer_date FROM user_continuity WHERE user_id = ?", [user_id])
    if not record or not record["last_answer_date"]:
        return 0
    last_answer_date = _date_from_iso(record["last_answer_date"])
    if last_answer_date == _today_utc():
        return int(record["daily_answer_streak"])
    if last_answer_date < _today_utc() - timedelta(days=1):
        return 0
    return int(record["daily_answer_streak"])


def build_next_action(*, subject: dict, topic: dict, analysis: dict, similarity: dict, progress_snapshot: dict) -> str:
    gs_label = _gs_label(subject["code"])
    missing_concepts = similarity.get("missing_concepts", [])
    if missing_concepts:
        return f"Practice {gs_label} {topic['name']} question focusing on {missing_concepts[0]}."

    weak_rows = [
        row
        for row in progress_snapshot.get("topic_breakdown", [])
        if row["topic_id"] != topic["id"] and row["subject_id"] == subject["id"]
    ]
    if weak_rows:
        weak_rows.sort(key=lambda row: (row["average_score"], row.get("trend_delta", 0.0), -row["total_attempts"]))
        _, _, weak_topic = get_topic_context(weak_rows[0]["topic_id"])
        return f"Practice {gs_label} {weak_topic['name']} question."

    if analysis.get("structure") == "WEAK":
        return f"Rewrite this {gs_label} {topic['name']} answer with sharper structure."

    return f"Practice one more {gs_label} {topic['name']} answer with tighter evidence."


def _sorted_active_topics(snapshot: dict, topic_index: dict[str, tuple[dict, dict, dict]]) -> list[dict]:
    rows = [row for row in snapshot.get("topic_breakdown", []) if row["topic_id"] in topic_index and row["total_attempts"] > 0]
    rows.sort(key=lambda row: (row["average_score"], row.get("trend_delta", 0.0), -row["total_attempts"], row["topic_id"]))
    return rows


def _deterministic_mix_mode(user_id: str) -> str:
    bucket = int(sha256_text(f"{user_id}|{_today_utc().isoformat()}")[:8], 16) % 10
    if bucket < 7:
        return "weak"
    if bucket < 9:
        return "moderate"
    return "random"


def _pool_index(seed: str, length: int) -> int:
    if length <= 1:
        return 0
    return int(sha256_text(seed)[:8], 16) % length


def get_daily_question(user_id: str, exam_id: str | None = None) -> dict:
    catalog = get_catalog_tree(exam_id=exam_id)
    snapshot = get_performance_snapshot(user_id)
    streak = get_answer_streak(user_id)
    focus = improvement_service.get_user_focus(user_id=user_id, exam_id=exam_id)
    focus_subtopic = None
    if focus and focus.get("topic_id"):
        row = db.fetch_one(
            """
            SELECT usw.*, s.name AS subtopic_name
            FROM user_subtopic_weakness usw
            JOIN subtopics s ON s.id = usw.subtopic_id
            WHERE usw.user_id = ? AND usw.topic_id = ?
            ORDER BY consecutive_mistake_count DESC, repeated_mistake_count DESC, updated_at DESC
            LIMIT 1
            """,
            [user_id, focus["topic_id"]],
        )
        if row:
            focus_subtopic = {"id": row["subtopic_id"], "name": row.get("subtopic_name") or ""}

    topic_index: dict[str, tuple[dict, dict, dict]] = {}
    for exam in catalog:
        for subject in exam["subjects"]:
            for topic in subject["topics"]:
                topic_index[topic["id"]] = (exam, subject, topic)

    ordered_topics = list(topic_index.values())
    if not ordered_topics:
        return {
            "topic_id": "",
            "topic_name": "Workspace unavailable",
            "subject_name": "UPSC",
            "subject_code": "UPSC",
            "question": "Seed the UPSC catalog to unlock the daily question.",
            "reason": "No topics are available yet.",
            "average_score": float(snapshot.get("summary", {}).get("average_score", 0.0)),
            "progress_trend": float(snapshot.get("summary", {}).get("improvement_trend", 0.0)),
            "streak": streak,
        }

    active_topics = [
        row
        for row in _sorted_active_topics(snapshot, topic_index)
        if row["topic_id"] in topic_index and (exam_id is None or row["exam_id"] == exam_id)
    ]
    active_by_id = {row["topic_id"]: row for row in active_topics}

    selected_row = None
    if len(active_topics) < 3 and active_topics and (
        active_topics[0]["average_score"] < 6.5 or active_topics[0].get("trend_delta", 0.0) < 0
    ):
        selected_row = active_topics[0]
        exam, subject, topic = topic_index[selected_row["topic_id"]]
        reason = "Picked from your weakest active topic."
    elif active_topics:
        weak_cutoff = max(1, math.ceil(len(active_topics) * 0.4))
        moderate_start = weak_cutoff
        moderate_end = max(moderate_start + 1, math.ceil(len(active_topics) * 0.8))
        weak_pool = active_topics[:weak_cutoff]
        moderate_pool = active_topics[moderate_start:moderate_end] or active_topics[weak_cutoff:] or weak_pool
        random_pool = [{"topic_id": item[2]["id"]} for item in ordered_topics]

        mix_mode = _deterministic_mix_mode(user_id)
        if mix_mode == "weak":
            selected_row = weak_pool[_pool_index(f"{user_id}|weak|{_today_utc().isoformat()}", len(weak_pool))]
            reason = "Picked from your weak-topic repair cycle."
        elif mix_mode == "moderate":
            selected_row = moderate_pool[_pool_index(f"{user_id}|moderate|{_today_utc().isoformat()}", len(moderate_pool))]
            reason = "Picked from your consolidation cycle."
        else:
            selected_row = random_pool[_pool_index(f"{user_id}|random|{_today_utc().isoformat()}", len(random_pool))]
            reason = "Picked from your rotation cycle."

        exam, subject, topic = topic_index[selected_row["topic_id"]]
    else:
        selected_index = _pool_index(f"{user_id}|rotation|{_today_utc().isoformat()}", len(ordered_topics))
        exam, subject, topic = ordered_topics[selected_index]
        reason = "Rotating topic to keep continuity alive."

    if focus and focus.get("topic_id") == topic["id"] and focus.get("weakest_area"):
        label = focus_subtopic["name"] if focus_subtopic and focus_subtopic.get("name") else topic["name"]
        reason = f"Today's focus: {focus['weakest_area']} · {label}"

    selected_progress = active_by_id.get(topic["id"])
    trend = float(selected_progress.get("trend_delta", 0.0)) if selected_progress else float(snapshot.get("summary", {}).get("improvement_trend", 0.0))
    average_score = (
        float(selected_progress.get("average_score", 0.0))
        if selected_progress
        else float(snapshot.get("summary", {}).get("average_score", 0.0))
    )

    prompt_pool = topic.get("knowledge", {}).get("pyq", [])
    if prompt_pool:
        question_index = int(sha256_text(f"{topic['id']}|{_today_utc().isoformat()}")[:8], 16) % len(prompt_pool)
        question = prompt_pool[question_index]
    else:
        question = f"Discuss {topic['name']} with conceptual clarity, structure, and one value-addition point."

    return {
        "topic_id": topic["id"],
        "topic_name": topic["name"],
        "subtopic_id": (focus_subtopic or {}).get("id"),
        "subtopic_name": (focus_subtopic or {}).get("name"),
        "subject_name": subject["name"],
        "subject_code": subject["code"],
        "question": question,
        "reason": reason,
        "average_score": average_score,
        "progress_trend": trend,
        "streak": streak,
    }
