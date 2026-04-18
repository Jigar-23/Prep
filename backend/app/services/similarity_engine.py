from __future__ import annotations

import json
import math
import re

from google.genai import types

from app.config import settings
from app.database import db
from app.services.cache_service import cache_service
from app.services.error_handler import error_handler
from app.services.llm_service import llm_service
from app.utils.common import new_id, normalize_text, sha256_text, split_sentences, utc_now_iso


class SimilarityEngine:
    def generate_embedding(self, text: str) -> list[float]:
        normalized = self._normalize(text)
        embeddings = self.generate_embeddings([normalized])
        return embeddings[normalized]

    def generate_embeddings(self, texts: list[str]) -> dict[str, list[float]]:
        normalized_texts = [self._normalize(text) for text in texts if self._normalize(text)]
        unique_texts = list(dict.fromkeys(normalized_texts))
        if not unique_texts:
            return {}

        resolved: dict[str, list[float]] = {}
        missing: list[str] = []
        for text in unique_texts:
            text_hash = sha256_text(text)
            cached = cache_service.get_embedding(text_hash)
            if cached is not None:
                resolved[text] = cached
                continue
            missing.append(text)

        if missing:
            rows = self._fetch_db_embeddings(missing)
            for row in rows:
                text = row["raw_text"]
                vector = json.loads(row["vector_json"])
                cache_service.set_embedding(row["text_hash"], vector)
                resolved[text] = vector
            missing = [text for text in missing if text not in resolved]

        for chunk in self._chunks(missing, settings.embedding_batch_size):
            if not chunk:
                continue
            vectors = self._embed_batch(chunk)
            now = utc_now_iso()
            for text, vector in zip(chunk, vectors, strict=True):
                text_hash = sha256_text(text)
                cache_service.set_embedding(text_hash, vector)
                db.execute(
                    """
                    INSERT OR REPLACE INTO text_embeddings
                    (id, text_hash, raw_text, vector_json, provider, model, dimension, created_at, updated_at)
                    VALUES (
                        COALESCE((SELECT id FROM text_embeddings WHERE text_hash = ?), ?),
                        ?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM text_embeddings WHERE text_hash = ?), ?), ?
                    )
                    """,
                    [
                        text_hash,
                        new_id("emb"),
                        text_hash,
                        text,
                        json.dumps(vector, separators=(",", ":")),
                        "gemini" if llm_service.enabled else "local-fallback",
                        settings.gemini_embedding_model if llm_service.enabled else "local-semantic-fallback",
                        len(vector),
                        text_hash,
                        now,
                        now,
                    ],
                )
                resolved[text] = vector
        return resolved

    @staticmethod
    def cosine_similarity(left: list[float], right: list[float]) -> float:
        if not left or not right:
            return 0.0
        numerator = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(item * item for item in left))
        right_norm = math.sqrt(sum(item * item for item in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        raw = numerator / (left_norm * right_norm)
        return max(0.0, min(1.0, (raw + 1) / 2))

    def compute_similarity(self, *, student_answer: str, model_answer: str) -> float:
        student_vector = self.generate_embedding(student_answer)
        model_vector = self.generate_embedding(model_answer)
        return round(self.cosine_similarity(student_vector, model_vector), 3)

    def compare(self, *, student_answer: str, model_answer: dict, analysis: dict) -> dict:
        model_answer_text = " ".join(model_answer.get("full_answer", []))
        similarity_score = self.compute_similarity(student_answer=student_answer, model_answer=model_answer_text)
        segments = self._answer_segments(student_answer)
        segment_vectors = self.generate_embeddings(segments)

        must_have_present = self._semantic_hits(
            analysis.get("must_have_points", []),
            segments,
            segment_vectors,
            threshold=settings.semantic_point_threshold,
        )
        good_to_have_present = self._semantic_hits(
            analysis.get("good_to_have_points", []),
            segments,
            segment_vectors,
            threshold=settings.semantic_point_threshold,
        )
        extra_edge_present = self._semantic_hits(
            analysis.get("extra_edge_points", []),
            segments,
            segment_vectors,
            threshold=settings.semantic_point_threshold,
        )

        core_concepts = model_answer.get("core_concepts") or analysis.get("must_have_points", [])
        covered_concepts = self._semantic_hits(
            core_concepts,
            segments,
            segment_vectors,
            threshold=settings.concept_similarity_threshold,
        )
        missing_concepts = [concept for concept in core_concepts if concept not in covered_concepts]
        coverage_denominator = max(1, len(core_concepts))
        coverage_score = round(len(covered_concepts) / coverage_denominator, 3)
        return {
            "similarity_score": similarity_score,
            "coverage_score": coverage_score,
            "must_have_points_present": must_have_present,
            "good_to_have_points_present": good_to_have_present,
            "extra_edge_points_present": extra_edge_present,
            "covered_concepts": covered_concepts,
            "missing_concepts": missing_concepts,
            "key_concept_hits": covered_concepts,
        }

    def _semantic_hits(
        self,
        concepts: list[str],
        segments: list[str],
        segment_vectors: dict[str, list[float]],
        *,
        threshold: float,
    ) -> list[str]:
        if not concepts or not segments:
            return []
        concept_vectors = self.generate_embeddings(concepts)
        hits: list[str] = []
        for concept in concepts:
            concept_vector = concept_vectors.get(self._normalize(concept))
            if concept_vector is None:
                continue
            best = 0.0
            for segment in segments:
                segment_vector = segment_vectors.get(segment)
                if segment_vector is None:
                    continue
                best = max(best, self.cosine_similarity(concept_vector, segment_vector))
            if best >= threshold:
                hits.append(concept)
        return hits

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        if llm_service.enabled and llm_service._client is not None:
            def _call() -> list[list[float]]:
                response = llm_service._client.models.embed_content(
                    model=settings.gemini_embedding_model,
                    contents=texts,
                    config=types.EmbedContentConfig(
                        task_type="SEMANTIC_SIMILARITY",
                        output_dimensionality=settings.embedding_dimensions,
                        auto_truncate=True,
                    ),
                )
                embeddings = response.embeddings or []
                vectors = [item.values or [] for item in embeddings]
                if len(vectors) != len(texts):
                    raise ValueError("Embedding response size mismatch.")
                return [self._normalize_vector(vector) for vector in vectors]

            return error_handler.with_retries(
                "Embedding generation",
                _call,
                retries=2,
                fallback=lambda: [self._local_embedding(text) for text in texts],
            )

        return [self._local_embedding(text) for text in texts]

    def _fetch_db_embeddings(self, texts: list[str]) -> list[dict]:
        if not texts:
            return []
        hashes = [sha256_text(text) for text in texts]
        placeholders = ",".join(["?"] * len(hashes))
        return db.fetch_all(f"SELECT * FROM text_embeddings WHERE text_hash IN ({placeholders})", hashes)

    @staticmethod
    def _normalize(text: str) -> str:
        return normalize_text(text)

    def _answer_segments(self, answer: str) -> list[str]:
        sentences = split_sentences(answer)
        if not sentences:
            return []
        segments: list[str] = []
        for index, sentence in enumerate(sentences):
            if sentence not in segments:
                segments.append(sentence)
            if index + 1 < len(sentences):
                combined = f"{sentence} {sentences[index + 1]}".strip()
                if combined not in segments:
                    segments.append(combined)
        full_answer = self._normalize(answer)
        if full_answer and full_answer not in segments:
            segments.append(full_answer)
        return segments

    @staticmethod
    def _chunks(items: list[str], size: int) -> list[list[str]]:
        return [items[index:index + size] for index in range(0, len(items), size)]

    @staticmethod
    def _normalize_vector(vector: list[float]) -> list[float]:
        norm = math.sqrt(sum(item * item for item in vector))
        if norm == 0:
            return vector
        return [item / norm for item in vector]

    def _local_embedding(self, text: str) -> list[float]:
        normalized = self._normalize(text).lower()
        tokens = re.findall(r"[a-z0-9]+", normalized)
        if not tokens:
            return [0.0] * settings.embedding_dimensions
        alphabet = "abcdefghijklmnopqrstuvwxyz"
        vector = [0.0] * settings.embedding_dimensions
        for token in tokens:
            for character in token:
                if character in alphabet:
                    vector[alphabet.index(character) % settings.embedding_dimensions] += 1.0
            vector[min(len(token), settings.embedding_dimensions) - 1] += 0.5
        for phrase, offset in [
            ("because", 32),
            ("however", 33),
            ("article", 34),
            ("court", 35),
            ("scheme", 36),
            ("rights", 37),
            ("federal", 38),
            ("inflation", 39),
            ("accountability", 40),
        ]:
            if phrase in normalized and offset < settings.embedding_dimensions:
                vector[offset] += 2.0
        return self._normalize_vector(vector)


similarity_engine = SimilarityEngine()
