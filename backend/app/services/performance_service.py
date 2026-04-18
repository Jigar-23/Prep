from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean

from app.database import db
from app.services.cache_service import performance_cache
from app.utils.common import new_id, utc_now_iso


def _iso_to_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _legacy_attempts(user_id: str) -> list[dict]:
    rows = db.fetch_all(
        """
        SELECT a.exam_id, a.subject_id, a.topic_id, a.score, a.is_correct, a.submitted_at, e.max_score
        FROM attempts a
        LEFT JOIN evaluations e ON e.attempt_id = a.id
        WHERE a.user_id = ?
        ORDER BY a.submitted_at DESC
        """,
        [user_id],
    )
    attempts: list[dict] = []
    for row in rows:
        max_score = float(row["max_score"] or 10.0)
        normalized_score = float(row["score"]) / max(max_score, 1.0)
        attempts.append(
            {
                "exam_id": row["exam_id"],
                "subject_id": row["subject_id"],
                "topic_id": row["topic_id"],
                "normalized_score": normalized_score,
                "is_correct": 1 if row["is_correct"] == 1 else 0,
                "submitted_at": row["submitted_at"],
            }
        )
    return attempts


def _upsc_attempts(user_id: str) -> list[dict]:
    rows = db.fetch_all(
        """
        SELECT eh.topic_id, eh.score, eh.created_at AS submitted_at, eh.scoring_json, a.max_marks, t.exam_id, t.subject_id
        FROM evaluation_history eh
        JOIN answers a ON a.id = eh.answer_id
        JOIN topics t ON t.id = eh.topic_id
        WHERE eh.user_id = ?
        ORDER BY eh.created_at DESC
        """,
        [user_id],
    )
    attempts: list[dict] = []
    for row in rows:
        scoring = json.loads(row["scoring_json"])
        scaled_score = float(scoring.get("scaled_score", row["score"]))
        max_marks = float(row["max_marks"] or 10.0)
        normalized_score = scaled_score / max(max_marks, 1.0)
        attempts.append(
            {
                "exam_id": row["exam_id"],
                "subject_id": row["subject_id"],
                "topic_id": row["topic_id"],
                "normalized_score": normalized_score,
                "is_correct": 1 if normalized_score >= 0.55 else 0,
                "submitted_at": row["submitted_at"],
            }
        )
    return attempts


def _combined_attempts(user_id: str) -> list[dict]:
    attempts = _legacy_attempts(user_id) + _upsc_attempts(user_id)
    return sorted(attempts, key=lambda item: item["submitted_at"], reverse=True)


def _trend_delta(items: list[dict]) -> float:
    if len(items) < 2:
        return 0.0

    scores = [item["normalized_score"] for item in items]
    recent_window = scores[: min(5, len(scores))]
    previous_window = scores[1 : 1 + min(5, max(0, len(scores) - 1))]
    if not previous_window:
        return 0.0

    recent_average = mean(recent_window)
    previous_average = mean(previous_window)
    if previous_average <= 0:
        return 0.0
    return round(((recent_average - previous_average) / previous_average) * 100, 2)


def refresh_user_performance(user_id: str) -> None:
    attempts = _combined_attempts(user_id)
    revisions = db.fetch_all("SELECT * FROM revision_schedule WHERE user_id = ?", [user_id])
    now = datetime.now(timezone.utc)

    def build_row(scope_type: str, items: list[dict], exam_id=None, subject_id=None, topic_id=None) -> dict:
        scoped_items = sorted(items, key=lambda item: item["submitted_at"], reverse=True)
        total_attempts = len(scoped_items)
        correct_attempts = sum(1 for item in scoped_items if item["is_correct"] == 1)
        average_score = round(mean(item["normalized_score"] for item in scoped_items) * 10, 2) if scoped_items else 0.0
        accuracy = round((correct_attempts / total_attempts) * 100, 2) if total_attempts else 0.0
        scope_revisions = [
            revision
            for revision in revisions
            if (exam_id is None or revision["exam_id"] == exam_id)
            and (subject_id is None or revision["subject_id"] == subject_id)
            and (topic_id is None or revision["topic_id"] == topic_id)
        ]
        due = 0
        completed = 0
        next_due = None
        for revision in scope_revisions:
            due_at = _iso_to_dt(revision["due_at"])
            if revision["status"] == "completed":
                completed += 1
            elif due_at and due_at <= now:
                due += 1
            if due_at and revision["status"] == "pending":
                next_due = min(next_due, due_at) if next_due else due_at
        last_activity = scoped_items[0]["submitted_at"] if scoped_items else None
        return {
            "id": new_id("perf"),
            "user_id": user_id,
            "scope_type": scope_type,
            "exam_id": exam_id,
            "subject_id": subject_id,
            "topic_id": topic_id,
            "accuracy": accuracy,
            "average_score": average_score,
            "trend_delta": _trend_delta(scoped_items),
            "total_attempts": total_attempts,
            "correct_attempts": correct_attempts,
            "revisions_due": due,
            "revisions_completed": completed,
            "next_review_at": next_due.replace(microsecond=0).isoformat().replace("+00:00", "Z") if next_due else None,
            "last_activity_at": last_activity,
            "updated_at": utc_now_iso(),
        }

    by_exam = defaultdict(list)
    by_subject = defaultdict(list)
    by_topic = defaultdict(list)
    for attempt in attempts:
        by_exam[attempt["exam_id"]].append(attempt)
        by_subject[(attempt["exam_id"], attempt["subject_id"])].append(attempt)
        by_topic[(attempt["exam_id"], attempt["subject_id"], attempt["topic_id"])].append(attempt)

    rows = [build_row("overall", attempts)]
    rows.extend(build_row("exam", items, exam_id=exam_id) for exam_id, items in by_exam.items())
    rows.extend(
        build_row("subject", items, exam_id=exam_id, subject_id=subject_id)
        for (exam_id, subject_id), items in by_subject.items()
    )
    rows.extend(
        build_row("topic", items, exam_id=exam_id, subject_id=subject_id, topic_id=topic_id)
        for (exam_id, subject_id, topic_id), items in by_topic.items()
    )

    with db.session(write=True) as conn:
        conn.execute("DELETE FROM performance WHERE user_id = ?", [user_id])
        for row in rows:
            conn.execute(
                """
                INSERT INTO performance
                (id, user_id, scope_type, exam_id, subject_id, topic_id, accuracy, average_score, trend_delta,
                 total_attempts, correct_attempts, revisions_due, revisions_completed, next_review_at,
                 last_activity_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    row["id"],
                    row["user_id"],
                    row["scope_type"],
                    row["exam_id"],
                    row["subject_id"],
                    row["topic_id"],
                    row["accuracy"],
                    row["average_score"],
                    row["trend_delta"],
                    row["total_attempts"],
                    row["correct_attempts"],
                    row["revisions_due"],
                    row["revisions_completed"],
                    row["next_review_at"],
                    row["last_activity_at"],
                    row["updated_at"],
                ],
            )
    performance_cache.pop(user_id, None)


def get_performance_snapshot(user_id: str) -> dict:
    cached = performance_cache.get(user_id)
    if cached is not None:
        return cached

    rows = db.fetch_all("SELECT * FROM performance WHERE user_id = ? ORDER BY scope_type ASC", [user_id])
    revisions = db.fetch_all(
        "SELECT exam_id, subject_id, topic_id, stage, due_at, status FROM revision_schedule WHERE user_id = ? ORDER BY due_at ASC",
        [user_id],
    )
    overall = next((row for row in rows if row["scope_type"] == "overall"), None)
    snapshot = {
        "summary": {
            "overall_accuracy": overall["accuracy"] if overall else 0.0,
            "average_score": overall["average_score"] if overall else 0.0,
            "total_attempts": overall["total_attempts"] if overall else 0,
            "due_revisions": overall["revisions_due"] if overall else 0,
            "improvement_trend": overall["trend_delta"] if overall else 0.0,
        },
        "exam_breakdown": [row for row in rows if row["scope_type"] == "exam"],
        "subject_breakdown": [row for row in rows if row["scope_type"] == "subject"],
        "topic_breakdown": [row for row in rows if row["scope_type"] == "topic"],
        "revision_queue": revisions,
    }
    performance_cache[user_id] = snapshot
    return snapshot
