from __future__ import annotations

import json
import re
import threading

from app.config import settings
from app.database import db
from app.errors import ApiError
from app.services.cache_service import cache_service
from app.services.catalog_service import get_topic_context
from app.services.llm_service import llm_service
from app.utils.common import new_id, sha256_json, stable_json_dumps, utc_now_iso


_topic_locks: dict[str, threading.Lock] = {}


def _lock(topic_id: str) -> threading.Lock:
    if topic_id not in _topic_locks:
        _topic_locks[topic_id] = threading.Lock()
    return _topic_locks[topic_id]


class NotesEngine:
    def _note_from_row(self, row: dict) -> dict:
        payload = json.loads(row["content_json"])
        return {
            "topic_id": row["topic_id"],
            "version": row["version"],
            "content_hash": row["content_hash"],
            "source": "database",
            "updated_at": row["updated_at"],
            **payload,
        }

    def _flashcards_from_rows(self, rows: list[dict]) -> list[dict]:
        return [
            {
                "id": row["id"],
                "topic_id": row["topic_id"],
                "card_type": row["card_type"],
                "front": row["question_text"],
                "back": row["answer_text"],
                "explanation": row["explanation"],
                "difficulty": row["difficulty"],
                "source": "database",
            }
            for row in rows
        ]

    def _fetch_note_row(self, topic_id: str) -> dict | None:
        return db.fetch_one("SELECT * FROM notes WHERE topic_id = ? AND is_deleted = 0", [topic_id])

    def _fetch_flashcard_rows(self, topic_id: str) -> list[dict]:
        return db.fetch_all("SELECT * FROM flashcards WHERE topic_id = ? AND is_deleted = 0 ORDER BY card_type ASC, created_at ASC", [topic_id])

    def _persist_learning_bundle(self, *, exam_id: str, subject_id: str, topic_id: str, bundle: dict, source: str) -> None:
        now = utc_now_iso()
        notes_payload = bundle["notes"]
        note_hash = sha256_json(notes_payload)
        note_id = new_id("note")
        with db.session(write=True) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO notes
                (id, exam_id, subject_id, topic_id, content_json, version, content_hash, source_prompt_hash, ai_model, updated_at, is_deleted)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, 0)
                """,
                [
                    note_id,
                    exam_id,
                    subject_id,
                    topic_id,
                    stable_json_dumps(notes_payload),
                    note_hash,
                    sha256_json({"topic_id": topic_id, "bundle": bundle}),
                    "demo" if source == "demo" else "gemini",
                    now,
                ],
            )
            conn.execute("DELETE FROM flashcards WHERE topic_id = ?", [topic_id])
            for card in bundle["flashcards"]:
                card_hash = sha256_json(card)
                conn.execute(
                    """
                    INSERT INTO flashcards
                    (id, topic_id, card_type, question_text, answer_text, explanation, difficulty,
                     source_hash, content_hash, created_at, updated_at, is_deleted)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    [
                        new_id("card"),
                        topic_id,
                        card["card_type"],
                        card["front"],
                        card["back"],
                        card["explanation"],
                        card["difficulty"],
                        sha256_json({"topic_id": topic_id, "source": source}),
                        card_hash,
                        now,
                        now,
                    ],
                )

    def ensure_learning_bundle(self, topic_id: str) -> tuple[dict, list[dict], str]:
        exam, subject, topic = get_topic_context(topic_id)
        cached_note = cache_service.get_notes(topic_id)
        cached_cards = cache_service.get_flashcards(topic_id)
        if cached_note and cached_cards and self._bundle_valid(topic, cached_note, cached_cards):
            return cached_note | {"source": "cache"}, cached_cards, "cache"

        note_row = self._fetch_note_row(topic_id)
        card_rows = self._fetch_flashcard_rows(topic_id)
        if note_row and card_rows:
            note_payload = self._note_from_row(note_row)
            flashcards = self._flashcards_from_rows(card_rows)
            if self._bundle_valid(topic, note_payload, flashcards):
                cache_service.set_notes(topic_id, note_payload)
                cache_service.set_flashcards(topic_id, flashcards)
                return note_payload, flashcards, "database"
            cache_service.invalidate_topic(topic_id)

        lock = _lock(topic_id)
        with lock:
            note_row = self._fetch_note_row(topic_id)
            card_rows = self._fetch_flashcard_rows(topic_id)
            if note_row and card_rows:
                note_payload = self._note_from_row(note_row)
                flashcards = self._flashcards_from_rows(card_rows)
                if self._bundle_valid(topic, note_payload, flashcards):
                    cache_service.set_notes(topic_id, note_payload)
                    cache_service.set_flashcards(topic_id, flashcards)
                    return note_payload, flashcards, "database"

            source = "cache"
            validation_feedback: str | None = None
            bundle = cache_service.get_learning_bundle(topic_id)
            for attempt in range(settings.note_validation_retries + 1):
                if bundle is None or attempt > 0:
                    bundle = llm_service.generate_learning_bundle(topic=topic, validation_feedback=validation_feedback)
                    cache_service.set_learning_bundle(topic_id, bundle)
                    source = "demo" if not llm_service.enabled else "ai"
                valid, errors = self._validate_bundle(topic, bundle)
                if valid:
                    break
                validation_feedback = " | ".join(errors)
                bundle = None
            else:
                raise ApiError(500, "NOTES_VALIDATION_FAILED", "Generated notes did not satisfy validation rules.")

            self._persist_learning_bundle(
                exam_id=exam["id"],
                subject_id=subject["id"],
                topic_id=topic_id,
                bundle=bundle,
                source=source,
            )
            note_row = self._fetch_note_row(topic_id)
            card_rows = self._fetch_flashcard_rows(topic_id)
            if not note_row or not card_rows:
                raise ApiError(500, "LEARNING_BUNDLE_FAILED", "Could not persist notes and flashcards.")
            note_payload = self._note_from_row(note_row)
            flashcards = self._flashcards_from_rows(card_rows)
            cache_service.set_notes(topic_id, note_payload)
            cache_service.set_flashcards(topic_id, flashcards)
            return note_payload | {"source": source}, flashcards, source

    def get_or_generate_notes(self, topic_id: str) -> dict:
        note, _, _ = self.ensure_learning_bundle(topic_id)
        return note

    def _bundle_valid(self, topic: dict, notes: dict, flashcards: list[dict]) -> bool:
        valid, _ = self._validate_bundle(topic, {"notes": self._notes_for_validation(notes), "flashcards": flashcards})
        return valid

    @staticmethod
    def _notes_for_validation(notes: dict) -> dict:
        return {
            "thirty_second_revision": notes.get("thirty_second_revision", []),
            "core_facts": notes.get("core_facts", []),
            "classification": notes.get("classification", []),
            "case_laws": notes.get("case_laws", []),
            "current_affairs": notes.get("current_affairs", []),
            "prelim_traps": notes.get("prelim_traps", []),
            "mains_answer_structure": notes.get("mains_answer_structure", {"intro": [], "body": [], "conclusion": []}),
            "value_addition": notes.get("value_addition", []),
            "pyq": notes.get("pyq", []),
        }

    def _validate_bundle(self, topic: dict, bundle: dict) -> tuple[bool, list[str]]:
        notes = bundle["notes"]
        flashcards = bundle["flashcards"]
        errors: list[str] = []
        if len(flashcards) != 12:
            errors.append("Flashcard bundle must contain exactly 12 cards.")
        card_types = [card["card_type"] for card in flashcards]
        expected = {"FACTUAL": 5, "CONCEPTUAL": 3, "TRAP": 2, "MAINS": 2}
        for card_type, count in expected.items():
            if card_types.count(card_type) != count:
                errors.append(f"{card_type} count must be {count}.")
        note_errors = self._validate_notes(topic, notes)
        errors.extend(note_errors)
        return not errors, errors

    def _validate_notes(self, topic: dict, notes: dict) -> list[str]:
        errors: list[str] = []
        knowledge = topic.get("knowledge", {})
        all_note_lines = notes.get("thirty_second_revision", []) + notes.get("core_facts", []) + notes.get("case_laws", [])
        mains = notes.get("mains_answer_structure", {})
        all_note_lines.extend(mains.get("intro", []))
        all_note_lines.extend(mains.get("body", []))
        all_note_lines.extend(mains.get("conclusion", []))
        combined = " ".join(all_note_lines)
        requires_articles = bool(knowledge.get("case_laws")) or any("Article" in item for item in knowledge.get("core_facts", []))
        requires_current_affairs = bool(knowledge.get("current_affairs_seed")) and not requires_articles

        if requires_articles and not re.search(r"\bArticle(?:s)?\s+\d+\b|\bPart\s+[IVX]+\b", combined, re.IGNORECASE):
            errors.append("Static legal topics must include Article references.")
        if requires_articles and len(notes.get("case_laws", [])) < settings.minimum_static_case_laws:
            errors.append(f"Static legal topics must include at least {settings.minimum_static_case_laws} case laws.")
        if requires_current_affairs and len(notes.get("current_affairs", [])) == 0:
            errors.append("Dynamic topics must include a current affairs linkage.")
        if not notes.get("thirty_second_revision"):
            errors.append("Notes must include a 30-second revision block.")
        if not notes.get("core_facts"):
            errors.append("Notes must include core facts.")
        return errors


notes_engine = NotesEngine()
