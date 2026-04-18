from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.database import db
from app.services.cache_service import cache_service
from app.utils.common import iso_after_days, new_id, utc_now_iso


SCHEDULE_DAYS = [1, 2, 4, 7, 15, 30]


def _next_schedule(raw_days: float) -> int:
    rounded = max(1, int(round(raw_days)))
    for day in SCHEDULE_DAYS:
        if rounded <= day:
            return day
    return SCHEDULE_DAYS[-1]


class RevisionEngine:
    def empty_summary(self) -> dict:
        return {
            "cards_added": 0,
            "due_today": 0,
            "next_review_dates": [],
            "schedule_days": SCHEDULE_DAYS,
        }

    def seed_revision_queue(self, *, user_id: str | None, flashcards: list[dict]) -> dict:
        if not user_id:
            return self.empty_summary()
        now = utc_now_iso()
        cards_added = 0
        next_dates: list[str] = []
        with db.session(write=True) as conn:
            for card in flashcards:
                existing = conn.execute(
                    "SELECT id, next_review FROM revision_progress WHERE user_id = ? AND flashcard_id = ?",
                    [user_id, card["id"]],
                ).fetchone()
                if existing:
                    next_dates.append(existing[1])
                    continue
                next_review = iso_after_days(1)
                conn.execute(
                    """
                    INSERT INTO revision_progress
                    (id, user_id, flashcard_id, ease_factor, interval_days, next_review,
                     correct_count, incorrect_count, last_result, last_reviewed_at, created_at, updated_at)
                    VALUES (?, ?, ?, 2.5, 1, ?, 0, 0, NULL, NULL, ?, ?)
                    """,
                    [new_id("revp"), user_id, card["id"], next_review, now, now],
                )
                cards_added += 1
                next_dates.append(next_review)
        cache_service.invalidate_user(user_id)
        due_today = len(self.get_due_cards(user_id=user_id, limit=200)["cards"])
        return {
            "cards_added": cards_added,
            "due_today": due_today,
            "next_review_dates": sorted(next_dates)[:6],
            "schedule_days": SCHEDULE_DAYS,
        }

    def get_due_cards(self, *, user_id: str, limit: int = 20) -> dict:
        cached = cache_service.get_review_cards(user_id)
        if cached is not None:
            return {"cards": cached[:limit], "due_today": len(cached)}

        rows = db.fetch_all(
            """
            SELECT f.id, f.topic_id, t.name AS topic_name, f.card_type, f.question_text, f.answer_text, f.explanation, f.difficulty,
                   rp.ease_factor, rp.interval_days, rp.next_review, rp.correct_count, rp.incorrect_count, rp.last_result
            FROM revision_progress rp
            JOIN flashcards f ON f.id = rp.flashcard_id
            JOIN topics t ON t.id = f.topic_id
            WHERE rp.user_id = ? AND rp.next_review <= ? AND f.is_deleted = 0
            ORDER BY rp.next_review ASC
            LIMIT 200
            """,
            [user_id, utc_now_iso()],
        )
        cards = [
            {
                "id": row["id"],
                "topic_id": row["topic_id"],
                "topic_name": row["topic_name"],
                "card_type": row["card_type"],
                "front": row["question_text"],
                "back": row["answer_text"],
                "explanation": row["explanation"],
                "difficulty": row["difficulty"],
                "progress": {
                    "card_id": row["id"],
                    "ease_factor": round(row["ease_factor"], 2),
                    "interval_days": round(row["interval_days"], 2),
                    "next_review": row["next_review"],
                    "correct_count": row["correct_count"],
                    "incorrect_count": row["incorrect_count"],
                    "last_result": row["last_result"],
                },
            }
            for row in rows
        ]
        cache_service.set_review_cards(user_id, cards)
        return {"cards": cards[:limit], "due_today": len(cards)}

    def update_progress(self, *, user_id: str, card_id: str, correct: bool) -> dict:
        progress = db.fetch_one(
            """
            SELECT * FROM revision_progress
            WHERE user_id = ? AND flashcard_id = ?
            """,
            [user_id, card_id],
        )
        if not progress:
            raise ValueError("Revision progress not found.")
        ease_factor = float(progress["ease_factor"])
        interval_days = float(progress["interval_days"])
        if correct:
            ease_factor += 0.1
            raw_interval = interval_days * ease_factor
            interval_days = _next_schedule(raw_interval)
            correct_count = progress["correct_count"] + 1
            incorrect_count = progress["incorrect_count"]
            last_result = "correct"
        else:
            ease_factor = max(1.3, ease_factor - 0.2)
            interval_days = 1
            correct_count = progress["correct_count"]
            incorrect_count = progress["incorrect_count"] + 1
            last_result = "wrong"
        next_review = (datetime.now(timezone.utc) + timedelta(days=interval_days)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        now = utc_now_iso()
        db.execute(
            """
            UPDATE revision_progress
            SET ease_factor = ?, interval_days = ?, next_review = ?, correct_count = ?, incorrect_count = ?,
                last_result = ?, last_reviewed_at = ?, updated_at = ?
            WHERE user_id = ? AND flashcard_id = ?
            """,
            [ease_factor, interval_days, next_review, correct_count, incorrect_count, last_result, now, now, user_id, card_id],
        )
        cache_service.invalidate_user(user_id)
        return {
            "progress": {
                "card_id": card_id,
                "ease_factor": round(ease_factor, 2),
                "interval_days": float(interval_days),
                "next_review": next_review,
                "correct_count": correct_count,
                "incorrect_count": incorrect_count,
                "last_result": last_result,
            },
            "revision": {
                "cards_added": 0,
                "due_today": self.get_due_cards(user_id=user_id, limit=200)["due_today"],
                "next_review_dates": [next_review],
                "schedule_days": SCHEDULE_DAYS,
            },
        }


revision_engine = RevisionEngine()
