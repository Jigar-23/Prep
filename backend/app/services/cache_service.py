from __future__ import annotations

from cachetools import TTLCache

from app.config import settings


catalog_cache: TTLCache[str, object] = TTLCache(maxsize=4, ttl=300)
performance_cache: TTLCache[str, object] = TTLCache(maxsize=128, ttl=300)


class CacheService:
    def __init__(self) -> None:
        ttl = settings.cache_ttl_seconds
        self.notes_cache: TTLCache[str, dict] = TTLCache(maxsize=128, ttl=ttl)
        self.flashcards_cache: TTLCache[str, list[dict]] = TTLCache(maxsize=128, ttl=ttl)
        self.model_answer_cache: TTLCache[str, dict] = TTLCache(maxsize=256, ttl=ttl)
        self.concept_universe_cache: TTLCache[str, list[dict]] = TTLCache(maxsize=256, ttl=ttl)
        self.evaluation_result_cache: TTLCache[str, dict] = TTLCache(maxsize=256, ttl=ttl)
        self.learning_bundle_cache: TTLCache[str, dict] = TTLCache(maxsize=128, ttl=ttl)
        self.review_cache: TTLCache[str, list[dict]] = TTLCache(maxsize=128, ttl=60)
        self.embedding_cache: TTLCache[str, list[float]] = TTLCache(maxsize=4096, ttl=ttl)

    @staticmethod
    def _key(*parts: str) -> str:
        return "::".join(parts)

    def get_notes(self, topic_id: str) -> dict | None:
        return self.notes_cache.get(self._key("notes", topic_id))

    def set_notes(self, topic_id: str, payload: dict) -> None:
        self.notes_cache[self._key("notes", topic_id)] = payload

    def get_flashcards(self, topic_id: str) -> list[dict] | None:
        return self.flashcards_cache.get(self._key("flashcards", topic_id))

    def set_flashcards(self, topic_id: str, payload: list[dict]) -> None:
        self.flashcards_cache[self._key("flashcards", topic_id)] = payload

    def get_model_answer(self, topic_id: str, question_hash: str) -> dict | None:
        return self.model_answer_cache.get(self._key("model_answer", topic_id, question_hash))

    def set_model_answer(self, topic_id: str, question_hash: str, payload: dict) -> None:
        self.model_answer_cache[self._key("model_answer", topic_id, question_hash)] = payload

    def get_concept_universe(self, question_id: str) -> list[dict] | None:
        return self.concept_universe_cache.get(self._key("concept_universe", question_id))

    def set_concept_universe(self, question_id: str, payload: list[dict]) -> None:
        self.concept_universe_cache[self._key("concept_universe", question_id)] = payload

    def get_evaluation_result(self, cache_key: str) -> dict | None:
        return self.evaluation_result_cache.get(self._key("evaluation_result", cache_key))

    def set_evaluation_result(self, cache_key: str, payload: dict) -> None:
        self.evaluation_result_cache[self._key("evaluation_result", cache_key)] = payload

    def get_learning_bundle(self, topic_id: str) -> dict | None:
        return self.learning_bundle_cache.get(self._key("learning_bundle", topic_id))

    def set_learning_bundle(self, topic_id: str, payload: dict) -> None:
        self.learning_bundle_cache[self._key("learning_bundle", topic_id)] = payload

    def get_review_cards(self, user_id: str) -> list[dict] | None:
        return self.review_cache.get(self._key("review", user_id))

    def set_review_cards(self, user_id: str, payload: list[dict]) -> None:
        self.review_cache[self._key("review", user_id)] = payload

    def get_embedding(self, text_hash: str) -> list[float] | None:
        return self.embedding_cache.get(self._key("embedding", text_hash))

    def set_embedding(self, text_hash: str, payload: list[float]) -> None:
        self.embedding_cache[self._key("embedding", text_hash)] = payload

    def invalidate_topic(self, topic_id: str) -> None:
        for cache, key in [
            (self.notes_cache, self._key("notes", topic_id)),
            (self.flashcards_cache, self._key("flashcards", topic_id)),
            (self.learning_bundle_cache, self._key("learning_bundle", topic_id)),
        ]:
            cache.pop(key, None)

    def invalidate_user(self, user_id: str) -> None:
        self.review_cache.pop(self._key("review", user_id), None)
        performance_cache.pop(user_id, None)


cache_service = CacheService()
