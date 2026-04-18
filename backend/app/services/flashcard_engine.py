from __future__ import annotations

from app.services.notes_engine import notes_engine
from app.services.revision_engine import revision_engine


class FlashcardEngine:
    def get_or_generate_flashcards(self, *, topic_id: str, user_id: str | None = None) -> tuple[list[dict], dict]:
        _, flashcards, _ = notes_engine.ensure_learning_bundle(topic_id)
        revision = revision_engine.seed_revision_queue(user_id=user_id, flashcards=flashcards) if user_id else revision_engine.empty_summary()
        return flashcards, revision


flashcard_engine = FlashcardEngine()
