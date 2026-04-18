from __future__ import annotations

import re

from app.database import db
from app.utils.common import utc_now_iso


DIMENSIONS = ("structure", "relevance", "content")


def _normalize_mistake(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", (value or "").strip().lower())
    cleaned = re.sub(r"[^a-z0-9\s%.-]", "", cleaned)
    return cleaned[:180]


def _weakest_dimension(*, structure_score: float, relevance_score: float, content_score: float) -> str:
    items = {
        "structure": float(structure_score),
        "relevance": float(relevance_score),
        "content": float(content_score),
    }
    return min(items, key=items.get)


class ImprovementService:
    def record_evaluation(
        self,
        *,
        user_id: str,
        topic_id: str,
        structure_score: float,
        relevance_score: float,
        content_score: float,
        biggest_mistake: str,
    ) -> dict:
        weakest = _weakest_dimension(
            structure_score=structure_score,
            relevance_score=relevance_score,
            content_score=content_score,
        )
        mistake_key = _normalize_mistake(biggest_mistake)
        now = utc_now_iso()

        existing = db.fetch_one(
            """
            SELECT *
            FROM user_topic_weakness
            WHERE user_id = ? AND topic_id = ?
            """,
            [user_id, topic_id],
        )

        structure_count = int(existing["structure_weak_count"]) if existing else 0
        relevance_count = int(existing["relevance_weak_count"]) if existing else 0
        content_count = int(existing["content_weak_count"]) if existing else 0
        most_repeated = (existing["most_repeated_mistake"] or "") if existing else ""
        most_repeated_count = int(existing["most_repeated_mistake_count"]) if existing else 0
        last_mistake = (existing["last_mistake"] or "") if existing else ""
        consecutive = int(existing["consecutive_mistake_count"]) if existing else 0

        if weakest == "structure":
            structure_count += 1
        elif weakest == "relevance":
            relevance_count += 1
        else:
            content_count += 1

        if mistake_key and mistake_key == last_mistake:
            consecutive += 1
        else:
            consecutive = 1 if mistake_key else 0

        if mistake_key:
            if mistake_key == most_repeated:
                most_repeated_count += 1
            elif most_repeated_count <= 0:
                most_repeated = mistake_key
                most_repeated_count = 1
            else:
                # keep existing "most repeated" unless the new streak overtakes it
                if consecutive >= most_repeated_count:
                    most_repeated = mistake_key
                    most_repeated_count = consecutive

        db.execute(
            """
            INSERT INTO user_topic_weakness
            (user_id, topic_id, structure_weak_count, relevance_weak_count, content_weak_count,
             most_repeated_mistake, most_repeated_mistake_count, last_mistake, consecutive_mistake_count,
             last_weakest_dimension, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, topic_id) DO UPDATE SET
              structure_weak_count = excluded.structure_weak_count,
              relevance_weak_count = excluded.relevance_weak_count,
              content_weak_count = excluded.content_weak_count,
              most_repeated_mistake = excluded.most_repeated_mistake,
              most_repeated_mistake_count = excluded.most_repeated_mistake_count,
              last_mistake = excluded.last_mistake,
              consecutive_mistake_count = excluded.consecutive_mistake_count,
              last_weakest_dimension = excluded.last_weakest_dimension,
              updated_at = excluded.updated_at
            """,
            [
                user_id,
                topic_id,
                structure_count,
                relevance_count,
                content_count,
                most_repeated,
                most_repeated_count,
                mistake_key,
                consecutive,
                weakest,
                now,
            ],
        )

        consistent_dimension = max(
            {"structure": structure_count, "relevance": relevance_count, "content": content_count},
            key=lambda key: {"structure": structure_count, "relevance": relevance_count, "content": content_count}[key],
        )

        pressure = ""
        if consecutive >= 2 and mistake_key:
            pressure = "You are repeating the same mistake. Fix this before moving on."

        return {
            "weakest_dimension": weakest,
            "consistent_weakness": consistent_dimension,
            "repeated_mistake": most_repeated,
            "repeated_mistake_count": most_repeated_count,
            "consecutive_mistake_count": consecutive,
            "pressure_message": pressure,
        }

    def get_user_focus(self, *, user_id: str, exam_id: str | None = None) -> dict | None:
        rows = db.fetch_all(
            """
            SELECT utw.*, t.exam_id, t.name as topic_name
            FROM user_topic_weakness utw
            JOIN topics t ON t.id = utw.topic_id
            WHERE utw.user_id = ? AND t.is_deleted = 0
            """,
            [user_id],
        )
        if exam_id:
            rows = [row for row in rows if row.get("exam_id") == exam_id]
        if not rows:
            return None

        def score_row(row: dict) -> tuple:
            total = int(row["structure_weak_count"]) + int(row["relevance_weak_count"]) + int(row["content_weak_count"])
            return (
                -int(row.get("consecutive_mistake_count") or 0),
                -int(row.get("most_repeated_mistake_count") or 0),
                -total,
                str(row.get("topic_id") or ""),
            )

        rows.sort(key=score_row)
        top = rows[0]
        counts = {
            "structure": int(top["structure_weak_count"]),
            "relevance": int(top["relevance_weak_count"]),
            "content": int(top["content_weak_count"]),
        }
        weakest_area = max(counts, key=counts.get)
        return {
            "topic_id": top["topic_id"],
            "topic_name": top.get("topic_name") or "",
            "weakest_area": weakest_area,
            "most_repeated_mistake": top.get("most_repeated_mistake") or "",
            "most_repeated_mistake_count": int(top.get("most_repeated_mistake_count") or 0),
        }

    def get_user_summary(self, *, user_id: str, exam_id: str | None = None) -> dict:
        focus = self.get_user_focus(user_id=user_id, exam_id=exam_id)
        if not focus:
            return {"weakest_area": "", "most_repeated_mistake": ""}
        return {
            "weakest_area": focus["weakest_area"],
            "most_repeated_mistake": focus["most_repeated_mistake"],
        }

    def record_subtopic_attempt(
        self,
        *,
        user_id: str,
        subtopic_id: str,
        topic_id: str,
        weakest_dimension: str,
        repeated_mistake: str,
        repeated_mistake_count: int,
        consecutive_mistake_count: int,
    ) -> None:
        db.execute(
            """
            INSERT INTO user_subtopic_weakness
            (user_id, subtopic_id, topic_id, weakest_dimension, repeated_mistake, repeated_mistake_count, consecutive_mistake_count, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, subtopic_id) DO UPDATE SET
              weakest_dimension = excluded.weakest_dimension,
              repeated_mistake = excluded.repeated_mistake,
              repeated_mistake_count = excluded.repeated_mistake_count,
              consecutive_mistake_count = excluded.consecutive_mistake_count,
              updated_at = excluded.updated_at
            """,
            [
                user_id,
                subtopic_id,
                topic_id,
                weakest_dimension,
                repeated_mistake or "",
                int(repeated_mistake_count or 0),
                int(consecutive_mistake_count or 0),
                utc_now_iso(),
            ],
        )


improvement_service = ImprovementService()

