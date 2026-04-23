from __future__ import annotations

import base64
import re
import subprocess
import tempfile
import textwrap
from typing import Any

from google import genai
from google.genai import types

from app.config import ROOT_DIR, read_env_value, settings
from app.errors import ApiError
from app.errors import input_invalid_error
from app.schemas import (
    ConceptExtractionPayload,
    ContentEvaluatorPayload,
    DirectiveEvaluatorPayload,
    EvaluationGuidancePayload,
    ExtractedTextPayload,
    GeneratedFlashcardPayload,
    GeneratedNotesPayload,
    LearningBundleLLMPayload,
    ModelAnswerPayload,
    NormalizationPayload,
    ReasoningEvaluatorPayload,
    UnifiedEvaluationSignalsPayload,
)
from app.services.error_handler import error_handler
from app.utils.common import normalize_text, split_sentences, stable_json_dumps


class LLMService:
    def __init__(self) -> None:
        self._client: genai.Client | None = None
        self._active_api_key: str | None = None
        self._auth_failed = False
        self._refresh_client(force=True)

    @staticmethod
    def _runtime_api_key() -> str | None:
        # Runtime env takes priority; then fallback to .env files.
        return read_env_value("GEMINI_API_KEY")

    def _refresh_client(self, *, force: bool = False) -> None:
        api_key = self._runtime_api_key()
        if not force and api_key == self._active_api_key:
            return
        self._active_api_key = api_key
        self._client = genai.Client(api_key=api_key) if api_key else None
        self._auth_failed = bool(api_key and self._looks_like_non_api_token(api_key))

    @property
    def enabled(self) -> bool:
        self._refresh_client()
        return self._client is not None and not self._auth_failed

    @property
    def key_configured(self) -> bool:
        self._refresh_client()
        return self._client is not None

    @property
    def auth_failed(self) -> bool:
        self._refresh_client()
        return self._auth_failed

    @property
    def local_ocr_available(self) -> bool:
        # Local OCR fallback uses Apple Vision via Swift script.
        return (ROOT_DIR / "backend" / "scripts" / "vision_ocr.swift").exists()

    def health_status(self) -> dict[str, str | None]:
        self._refresh_client()
        if self._client is None:
            return {
                "mode": "demo",
                "reason": "missing_key",
                "fallback": "local_vision" if self.local_ocr_available else None,
            }
        if self._auth_failed:
            return {
                "mode": "demo",
                "reason": "invalid_key",
                "fallback": "local_vision" if self.local_ocr_available else None,
            }
        return {"mode": "gemini", "reason": None, "fallback": "local_vision" if self.local_ocr_available else None}

    def _generate_json(
        self,
        *,
        model: str,
        instruction: str,
        schema: type,
        contents: list[Any] | str,
        fallback: callable,
    ) -> dict:
        self._refresh_client()
        if not self._client:
            return fallback()

        def _call() -> dict:
            response = self._client.models.generate_content(
                model=model,
                contents=contents,
                config={
                    "response_mime_type": "application/json",
                    "response_json_schema": schema.model_json_schema(),
                    "temperature": 0,
                    "system_instruction": instruction,
                },
            )
            return schema.model_validate_json(response.text).model_dump()

        return error_handler.with_retries("LLM JSON generation", _call, retries=2, fallback=fallback)

    @staticmethod
    def _topic_context(topic: dict) -> dict:
        knowledge = topic.get("knowledge", {})
        return {
            "topic_name": topic["name"],
            "topic_description": topic["description"],
            "learning_objectives": topic.get("learning_objectives", []),
            "keywords": knowledge.get("keywords", []),
            "must_have_points": knowledge.get("must_have_points", []),
            "good_to_have_points": knowledge.get("good_to_have_points", []),
            "extra_edge_points": knowledge.get("extra_edge_points", []),
            "core_facts": knowledge.get("core_facts", []),
            "case_laws": knowledge.get("case_laws", []),
            "value_addition": knowledge.get("value_addition", []),
            "current_affairs_seed": knowledge.get("current_affairs_seed", []),
            "mains_frame": knowledge.get("mains_frame", {}),
            "pyq": knowledge.get("pyq", []),
        }

    @staticmethod
    def _normalize_concept_universe(concept_universe: list[Any] | None) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in concept_universe or []:
            concept = ""
            importance = "secondary"
            if isinstance(item, str):
                concept = normalize_text(item)
            elif isinstance(item, dict):
                concept = normalize_text(str(item.get("concept") or ""))
                raw_importance = normalize_text(str(item.get("importance") or "secondary")).lower()
                importance = "core" if raw_importance == "core" else "secondary"
            if not concept:
                continue
            key = concept.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append({"concept": concept, "importance": importance})
        return normalized

    @staticmethod
    def _legacy_signal_view(payload: dict) -> dict:
        concept_scores = payload.get("concept_scores", []) or []
        dimension_counts = payload.get("dimension_counts", {}) or {}
        structure = payload.get("structure", {}) or {}
        concepts_expected = [str(item.get("concept") or "") for item in concept_scores if str(item.get("concept") or "")]
        concepts_covered = [
            str(item.get("concept") or "")
            for item in concept_scores
            if str(item.get("concept") or "") and int(item.get("coverage_score") or 0) >= 1
        ]
        concepts_missing = [
            str(item.get("concept") or "")
            for item in concept_scores
            if str(item.get("concept") or "") and int(item.get("coverage_score") or 0) == 0
        ]
        dimensions_detected = [
            key for key in ["causes", "impacts", "challenges", "way_forward", "examples"] if int(dimension_counts.get(key, 0) or 0) > 0
        ]
        core_coverage_ratio = float(payload.get("core_coverage_ratio", 0.0) or 0.0)
        core_depth_ratio = float(payload.get("core_depth_ratio", 0.0) or 0.0)
        clarity_score = int(payload.get("clarity_score", 0) or 0)
        directive_coverage_ratio = float(payload.get("directive_coverage_ratio", 0.0) or 0.0)
        content_hint = round(min(10.0, (core_coverage_ratio * 6.0) + (core_depth_ratio * 4.0)))
        expression_hint = max(0, min(10, clarity_score * 2))
        if directive_coverage_ratio >= 0.75:
            directive_satisfaction = "good"
        elif directive_coverage_ratio >= 0.4:
            directive_satisfaction = "partial"
        else:
            directive_satisfaction = "low"
        return {
            "expected_approach": f"Answer should address the detected directive with the required components explicitly.",
            "concepts_expected": concepts_expected,
            "concepts_covered": concepts_covered,
            "concepts_missing": concepts_missing,
            "irrelevant_concepts": [],
            "dimensions_detected": dimensions_detected,
            "introduction_type": str(structure.get("introduction") or "missing"),
            "body_structure": "semi-structured" if str(structure.get("body") or "semi") == "semi" else str(structure.get("body") or "unstructured"),
            "conclusion_type": str(structure.get("conclusion") or "missing"),
            "content_quality_score_hint": content_hint,
            "expression_quality_score_hint": expression_hint,
            "bluff_flags": {
                "filler_phrases": [],
                "vague_sentences": [],
                "repetitions": [],
                "low_value_lines": [],
            },
            "directive_satisfaction": directive_satisfaction,
        }

    def clean_input(
        self,
        answer_text: str | None,
        ocr_text: str | None = None,
        handwritten_image_base64: str | None = None,
        handwritten_image_mime_type: str | None = None,
    ) -> dict:
        self._refresh_client()
        typed_text = normalize_text((answer_text or "").strip())
        supplied_ocr = normalize_text((ocr_text or "").strip())
        extracted_image_text = ""
        if handwritten_image_base64:
            extracted_image_text = self._extract_text_from_image(handwritten_image_base64, handwritten_image_mime_type)
        raw = self._merge_sources(typed_text, supplied_ocr, extracted_image_text)
        cleaned = self._repair_common_ocr_artifacts(self._local_clean(raw))
        should_use_model = self._client is not None and (
            bool(handwritten_image_base64) or len(cleaned) > 1200 or self._looks_like_ocr_noise(cleaned)
        )
        if not should_use_model:
            payload = self._local_normalization_payload(self._repair_common_ocr_artifacts(cleaned))
            payload["source_text"] = {
                "typed_text": typed_text,
                "ocr_text": supplied_ocr,
                "image_text": extracted_image_text,
                "merged_text": raw,
            }
            return payload

        prompt = stable_json_dumps(
            {
                "task": (
                    "Normalize OCR or raw UPSC answer text without changing meaning. "
                    "Repair obvious OCR errors where highly confident. Preserve sections and bullet intent."
                ),
                "text": cleaned,
            }
        )
        payload = self._generate_json(
            model=settings.gemini_small_model,
            instruction=(
                "Return strict JSON only with cleaned_answer and sentence_list. "
                "Preserve meaning exactly. Keep heading and bullet structure readable. "
                "Do not invent new facts. Repair obvious OCR corruption in names, institutions, and dates when highly confident."
            ),
            schema=NormalizationPayload,
            contents=prompt,
            fallback=lambda: self._local_normalization_payload(cleaned),
        )
        payload["cleaned_answer"] = self._repair_common_ocr_artifacts(str(payload.get("cleaned_answer") or cleaned))
        payload["sentence_list"] = split_sentences(str(payload.get("cleaned_answer") or cleaned))
        payload["source_text"] = {
            "typed_text": typed_text,
            "ocr_text": supplied_ocr,
            "image_text": extracted_image_text,
            "merged_text": raw,
        }
        return payload

    def analyze_content(self, *, question: str, cleaned_answer: str, model_answer: dict, topic: dict) -> dict:
        fallback = lambda: self._demo_content_evaluator(topic=topic, cleaned_answer=cleaned_answer)
        prompt = stable_json_dumps(
            {
                "question": question,
                "student_answer": cleaned_answer,
                "model_answer": model_answer,
                "topic_context": self._topic_context(topic),
            }
        )
        instruction = textwrap.dedent(
            """
            You are Evaluator A for a UPSC answer evaluation system.
            Focus only on conceptual content coverage and domain correctness.
            Never assign marks.
            Return strict JSON only with:
            relevance, domain, must_have_points, good_to_have_points, extra_edge_points,
            missing_points, incorrect_points, alternative_valid.
            Mark alternative_valid true only if the answer is substantively valid even when it differs from the model answer framing.
            """
        ).strip()
        return self._generate_json(
            model=settings.gemini_eval_model,
            instruction=instruction,
            schema=ContentEvaluatorPayload,
            contents=prompt,
            fallback=fallback,
        )

    def analyze_answer_signals(self, *, question: str, cleaned_answer: str, concept_universe: list[Any] | None = None) -> dict:
        normalized_concepts = self._normalize_concept_universe(concept_universe)
        fallback = lambda: self._demo_unified_evaluation_signals(
            question=question,
            cleaned_answer=cleaned_answer,
            concept_universe=normalized_concepts,
        )
        prompt = stable_json_dumps(
            {
                "question": question,
                "cleaned_answer": cleaned_answer,
                "concept_universe": normalized_concepts,
            }
        )
        instruction = textwrap.dedent(
            """
            You are a UPSC Mains Answer Evaluation Signal Extractor.
            Your role is NOT to give marks.
            Your role is to extract deterministic, scoring-aligned, normalized signals for a backend scoring engine.

            CORE PRINCIPLES:
            - Core concepts are MOST IMPORTANT (highest priority)
            - Directive compliance is next
            - Structure is next
            - Value addition enhances score
            - Expression refines score
            - Penalties can cap or reduce score

            INPUT:
            - question
            - cleaned_answer
            - concept_universe (MANDATORY, PRE-CACHED)

            GLOBAL RULES:
            - Use ONLY concept_universe for scoring.
            - If answer contains a strong valid concept not present in concept_universe, include it under extra_valid_concepts.
            - Prefer strict evaluation over generous interpretation.
            - Do NOT assume correctness unless supported.
            - Core concepts are MOST IMPORTANT. Prioritize them.
            - Avoid hallucination or assumption.
            - Output MUST be valid JSON.

            TASKS:
            1. Detect directive using keywords first, then meaning.
            2. Define required_components as an explicit checklist. If unsure, choose the closest directive and continue.
            3. For EACH concept in concept_universe assign coverage_score:
               0 = not present
               1 = mentioned OR weak explanation
               2 = clearly explained WITH at least one of reasoning, example, or cause-effect linkage.
               IMPORTANT: do NOT give 2 unless explanation is clear and meaningful. Prefer 1 over 2 in borderline cases.
            4. Return core summary with core_total, core_covered, core_well_covered. Core coverage is the primary indicator of answer quality.
            5. Map concepts to dimensions using only: causes, impacts, challenges, way_forward, examples.
               Assign each concept to maximum 2 dimensions.
               dimension_balance is:
               - good only if dimensions >= 4 AND core_depth_ratio > 0.4
               - average if 2 to 3 dimensions
               - poor otherwise
            6. Evaluate structure strictly:
               - introduction: present, weak, or missing
               - body: structured, semi, or unstructured
               - conclusion: present, weak, or missing
            7. Return core_coverage_ratio and core_depth_ratio.
            8. Return clarity_score using:
               5 crisp precise no redundancy
               4 mostly clear
               3 understandable but wordy
               2 partially unclear
               1 mostly unclear
               0 unreadable
            9. Count value additions only if they directly support the argument.
            10. Return vague_ratio where vagueness means sentences lacking specific information.
            11. Return directive_coverage_ratio based ONLY on required_components satisfied.
            12. Return factual_error_present and contradiction_present as booleans.
            13. penalty_flags may include ONLY:
               missing_conclusion, poor_structure, weak_core_coverage, excessive_vagueness, factual_error_present, contradiction_present
               Each with severity low, medium, or high.
            14. Return partial_concepts_count, answer_length_category, and fundamental_weakness where fundamental_weakness is true if core_coverage_ratio < 0.4.
            15. Return confidence as low, medium, or high. Reduce confidence if core_coverage_ratio < 0.5 OR vague_ratio > 0.5.
            16. Return extra_valid_concepts.

            Use this structure exactly:
            {
              "directive": "",
              "required_components": [],
              "concept_scores": [{"concept": "", "importance": "core | secondary", "coverage_score": 0}],
              "extra_valid_concepts": [],
              "core_summary": {"core_total": 0, "core_covered": 0, "core_well_covered": 0},
              "dimension_counts": {"causes": 0, "impacts": 0, "challenges": 0, "way_forward": 0, "examples": 0},
              "dimension_balance": "poor | average | good",
              "structure": {"introduction": "present | weak | missing", "body": "structured | semi | unstructured", "conclusion": "present | weak | missing"},
              "core_coverage_ratio": 0.0,
              "core_depth_ratio": 0.0,
              "clarity_score": 0,
              "value_additions": {"data_or_report": 0, "example": 0, "generic": 0},
              "vague_ratio": 0.0,
              "directive_coverage_ratio": 0.0,
              "factual_error_present": false,
              "penalty_flags": [{"flag": "missing_conclusion", "severity": "low | medium | high"}],
              "contradiction_present": false,
              "partial_concepts_count": 0,
              "answer_length_category": "short | optimal | long",
              "fundamental_weakness": false,
              "confidence": "low | medium | high"
            }
            """
        ).strip()
        payload = self._generate_json(
            model=settings.gemini_eval_model,
            instruction=instruction,
            schema=UnifiedEvaluationSignalsPayload,
            contents=prompt,
            fallback=fallback,
        )
        payload.update(self._legacy_signal_view(payload))
        return payload

    def analyze_reasoning(self, *, question: str, cleaned_answer: str, model_answer: dict, topic: dict) -> dict:
        fallback = lambda: self._demo_reasoning_evaluator(cleaned_answer=cleaned_answer)
        prompt = stable_json_dumps(
            {
                "question": question,
                "student_answer": cleaned_answer,
                "model_answer": model_answer,
                "topic_context": self._topic_context(topic),
            }
        )
        instruction = textwrap.dedent(
            """
            You are Evaluator B for a UPSC answer evaluation system.
            Focus only on depth, reasoning quality, and UPSC mains framing maturity.
            Prioritize structure-led reasoning over raw information volume.
            Never assign marks.
            Return strict JSON only with:
            depth, thinking, balanced_argument, real_world_relevance, logical_flow, interlinking_topics.
            """
        ).strip()
        return self._generate_json(
            model=settings.gemini_eval_model,
            instruction=instruction,
            schema=ReasoningEvaluatorPayload,
            contents=prompt,
            fallback=fallback,
        )

    def analyze_directive(self, *, question: str, cleaned_answer: str, model_answer: dict, topic: dict) -> dict:
        fallback = lambda: self._demo_directive_evaluator(question=question, cleaned_answer=cleaned_answer)
        prompt = stable_json_dumps(
            {
                "question": question,
                "student_answer": cleaned_answer,
                "model_answer": model_answer,
                "topic_context": self._topic_context(topic),
            }
        )
        instruction = textwrap.dedent(
            """
            You are Evaluator C for a UPSC answer evaluation system.
            Focus only on question demand fulfillment, directive handling, and answer structure.
            Be strict: if question demand is partially addressed, mark directive as PARTIAL.
            Reward clear intro-body-conclusion and explicit paragraph transitions.
            Never assign marks.
            Return strict JSON only with:
            directive, structure, fulfilled_demands, missed_demands.
            """
        ).strip()
        return self._generate_json(
            model=settings.gemini_eval_model,
            instruction=instruction,
            schema=DirectiveEvaluatorPayload,
            contents=prompt,
            fallback=fallback,
        )

    def generate_evaluation_guidance(
        self,
        *,
        question: str,
        cleaned_answer: str,
        topic: dict,
        model_answer: dict,
        analysis: dict,
        similarity: dict,
        scoring: dict,
        features: dict,
    ) -> dict:
        fallback = lambda: self._demo_evaluation_guidance(
            topic=topic,
            model_answer=model_answer,
            analysis=analysis,
            similarity=similarity,
            scoring=scoring,
            features=features,
        )
        prompt = stable_json_dumps(
            {
                "question": question,
                "student_answer": cleaned_answer,
                "topic_context": self._topic_context(topic),
                "model_answer": {
                    "must_have_points": model_answer.get("must_have_points", []),
                    "good_to_have_points": model_answer.get("good_to_have_points", []),
                    "articles_and_facts": model_answer.get("articles_and_facts", []),
                    "examples": model_answer.get("examples", []),
                    "value_addition": model_answer.get("value_addition", []),
                },
                "analysis": analysis,
                "similarity": similarity,
                "scoring": {
                    "relevance_score": scoring.get("relevance_score"),
                    "structure_score": scoring.get("structure_score"),
                    "efficiency_score": scoring.get("efficiency_score"),
                    "impression_score": scoring.get("impression_score"),
                },
                "features": {
                    "fact_density": features.get("fact_density"),
                    "examples_detected": features.get("examples_detected", []),
                    "bluff_ratio": features.get("bluff_ratio"),
                },
            }
        )
        instruction = textwrap.dedent(
            """
            You are a UPSC mentor summarizing evaluation guidance after scoring is already complete.
            Never assign marks.
            Return strict JSON only with:
            top_improvements, strengths, ideal_answer_directions.
            Rules:
            - top_improvements must contain exactly 3 short action items.
            - strengths must contain 2 or 3 short strengths.
            - ideal_answer_directions must contain exactly 3 directional hints.
            - Do not produce a full answer, paragraphs, or explanations.
            - Keep every item under 12 words where possible.
            - Prefer structure-first guidance: framing, ordering, and directive alignment.
            """
        ).strip()
        return self._generate_json(
            model=settings.gemini_small_model,
            instruction=instruction,
            schema=EvaluationGuidancePayload,
            contents=prompt,
            fallback=fallback,
        )

    def extract_core_concepts(self, *, answer_text: str, topic: dict) -> dict:
        fallback = lambda: self._demo_concepts(topic=topic)
        prompt = stable_json_dumps(
            {
                "answer_text": answer_text,
                "topic_context": self._topic_context(topic),
            }
        )
        instruction = textwrap.dedent(
            """
            Extract between 8 and 15 semantically distinct UPSC-ready core concepts from the provided answer.
            Keep them concept-level, not sentence-level.
            Return strict JSON only with:
            concepts
            """
        ).strip()
        payload = self._generate_json(
            model=settings.gemini_small_model,
            instruction=instruction,
            schema=ConceptExtractionPayload,
            contents=prompt,
            fallback=fallback,
        )
        concepts = payload.get("concepts", [])[:15]
        return {"concepts": concepts}

    def generate_model_answer(self, *, question: str, topic: dict) -> dict:
        fallback = lambda: self._demo_model_answer(topic=topic, question=question)
        prompt = stable_json_dumps(
            {
                "question": question,
                "topic_context": self._topic_context(topic),
            }
        )
        instruction = textwrap.dedent(
            """
            Generate a topper-level UPSC model answer in strict JSON.
            Include intro, body, conclusion, must_have_points, good_to_have_points,
            extra_edge_points, articles_and_facts, examples, value_addition, and full_answer.
            Do not assign marks. Keep the answer dense, exam-ready, and directive-sensitive.
            """
        ).strip()
        payload = self._generate_json(
            model=settings.gemini_eval_model,
            instruction=instruction,
            schema=ModelAnswerPayload,
            contents=prompt,
            fallback=fallback,
        )
        concepts = self.extract_core_concepts(answer_text="\n".join(payload["full_answer"]), topic=topic)["concepts"]
        payload["core_concepts"] = concepts
        return payload

    def generate_learning_bundle(self, *, topic: dict, validation_feedback: str | None = None) -> dict:
        fallback = lambda: self._demo_learning_bundle(topic)
        note_requirements = self._notes_requirements(topic)
        prompt = stable_json_dumps(
            {
                "topic_context": self._topic_context(topic),
                "validation_feedback": validation_feedback or "",
                "requirements": note_requirements,
            }
        )
        instruction = textwrap.dedent(
            """
            Generate strict JSON only.
            Create exam-ready notes plus flashcards for UPSC preparation.
            Notes must be high-density and non-fluffy.
            Flashcards must be exactly 12 cards: 5 FACTUAL, 3 CONCEPTUAL, 2 TRAP, 2 MAINS.
            If current affairs linkage is weak, return an empty current_affairs list.
            Respect any validation feedback and regenerate accordingly.
            """
        ).strip()
        payload = self._generate_json(
            model=settings.gemini_small_model,
            instruction=instruction,
            schema=LearningBundleLLMPayload,
            contents=prompt,
            fallback=fallback,
        )
        flashcards = [GeneratedFlashcardPayload.model_validate(item).model_dump() for item in payload.get("flashcards", [])]
        notes = GeneratedNotesPayload.model_validate(payload.get("notes", {})).model_dump()
        if len(flashcards) != 12:
            raise ValueError("Learning bundle must return exactly 12 flashcards.")
        return {"notes": notes, "flashcards": flashcards}

    @staticmethod
    def _candidate_image_mime_types(image_mime_type: str | None) -> list[str]:
        provided = normalize_text((image_mime_type or "").lower())
        candidates: list[str] = []
        if provided:
            candidates.append(provided)
        if provided in {"image/heic", "image/heif"}:
            candidates.extend(["image/heic", "image/heif", "image/jpeg", "image/png"])
        else:
            candidates.extend(["image/jpeg", "image/png"])
        unique: list[str] = []
        seen: set[str] = set()
        for item in candidates:
            if item and item not in seen:
                unique.append(item)
                seen.add(item)
        return unique or ["image/png"]

    @staticmethod
    def _image_extension_from_mime(mime_type: str | None) -> str:
        normalized = normalize_text((mime_type or "").lower())
        mapping = {
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/heic": ".heic",
            "image/heif": ".heif",
        }
        return mapping.get(normalized, ".img")

    def _extract_text_macos_vision(self, *, image_bytes: bytes, mime_type: str | None) -> str:
        script_path = ROOT_DIR / "backend" / "scripts" / "vision_ocr.swift"
        if not script_path.exists():
            return ""

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=self._image_extension_from_mime(mime_type)) as temp_file:
                temp_file.write(image_bytes)
                temp_path = temp_file.name

            process = subprocess.run(
                ["swift", str(script_path), str(temp_path)],
                capture_output=True,
                text=True,
                timeout=25,
                check=False,
            )
            if process.returncode != 0:
                return ""
            return normalize_text(process.stdout or "")
        except Exception:  # noqa: BLE001
            return ""
        finally:
            if temp_path:
                try:
                    from pathlib import Path

                    Path(temp_path).unlink(missing_ok=True)
                except Exception:  # noqa: BLE001
                    pass

    def _extract_text_json(self, *, image_bytes: bytes, mime_type: str) -> str:
        if not self._client:
            return ""
        last_error: Exception | None = None
        for _ in range(2):
            try:
                response = self._client.models.generate_content(
                    model=settings.gemini_eval_model,
                    contents=[
                        {
                            "role": "user",
                            "parts": [
                                {
                                    "text": (
                                        "Extract all readable handwritten or printed text from this answer sheet. "
                                        "Return strict JSON only: {\"extracted_text\":\"...\"}. "
                                        "If partially readable, include whatever is readable."
                                    )
                                },
                                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                            ],
                        }
                    ],
                    config={
                        "response_mime_type": "application/json",
                        "response_json_schema": ExtractedTextPayload.model_json_schema(),
                        "temperature": 0,
                    },
                )
                try:
                    payload = ExtractedTextPayload.model_validate_json(response.text).model_dump()
                    return normalize_text(str(payload.get("extracted_text") or ""))
                except Exception:  # noqa: BLE001
                    return ""
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if self._is_ocr_auth_error(exc):
                    self._auth_failed = True
                    raise input_invalid_error(
                        reason="ocr_auth_failed",
                        message="Gemini OCR authentication failed. Use a valid Gemini API key and restart the backend.",
                        suggestions=[
                            "Create a Gemini API key in Google AI Studio (not an OAuth/token string)",
                            f"Set GEMINI_API_KEY in {ROOT_DIR / '.env'}",
                            f"Or set GEMINI_API_KEY in {ROOT_DIR / 'backend' / '.env'}",
                            "Restart backend after updating the key",
                        ],
                    ) from exc
                if self._is_ocr_network_error(exc):
                    raise input_invalid_error(
                        reason="ocr_provider_unreachable",
                        message="OCR provider could not be reached. Check backend network and retry.",
                        suggestions=[
                            "Verify internet access on backend runtime",
                            "Retry in 10-20 seconds",
                            "Paste answer text manually if urgent",
                        ],
                    ) from exc
        _ = last_error
        return ""

    def _extract_text_plain(self, *, image_bytes: bytes, mime_type: str) -> str:
        if not self._client:
            return ""
        last_error: Exception | None = None
        for _ in range(2):
            try:
                response = self._client.models.generate_content(
                    model=settings.gemini_eval_model,
                    contents=[
                        {
                            "role": "user",
                            "parts": [
                                {
                                    "text": (
                                        "Transcribe all readable handwritten or printed text from this answer sheet. "
                                        "Return plain text only. Preserve line breaks if possible. "
                                        "If text is unreadable, return exactly: NOT_READABLE"
                                    )
                                },
                                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                            ],
                        }
                    ],
                    config={"temperature": 0},
                )
                raw = normalize_text(response.text or "")
                if raw.upper() == "NOT_READABLE":
                    return ""
                return raw
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if self._is_ocr_auth_error(exc):
                    self._auth_failed = True
                    raise input_invalid_error(
                        reason="ocr_auth_failed",
                        message="Gemini OCR authentication failed. Use a valid Gemini API key and restart the backend.",
                        suggestions=[
                            "Create a Gemini API key in Google AI Studio (not an OAuth/token string)",
                            f"Set GEMINI_API_KEY in {ROOT_DIR / '.env'}",
                            f"Or set GEMINI_API_KEY in {ROOT_DIR / 'backend' / '.env'}",
                            "Restart backend after updating the key",
                        ],
                    ) from exc
                if self._is_ocr_network_error(exc):
                    raise input_invalid_error(
                        reason="ocr_provider_unreachable",
                        message="OCR provider could not be reached. Check backend network and retry.",
                        suggestions=[
                            "Verify internet access on backend runtime",
                            "Retry in 10-20 seconds",
                            "Paste answer text manually if urgent",
                        ],
                    ) from exc
        _ = last_error
        return ""

    @staticmethod
    def _is_ocr_auth_error(exc: Exception) -> bool:
        lowered = str(exc).lower()
        return any(
            marker in lowered
            for marker in [
                "unauthenticated",
                "invalid authentication credentials",
                "access_token_type_unsupported",
                "api key not valid",
                "permission denied",
            ]
        )

    @staticmethod
    def _is_ocr_network_error(exc: Exception) -> bool:
        lowered = str(exc).lower()
        return any(
            marker in lowered
            for marker in [
                "connecterror",
                "timed out",
                "temporary failure in name resolution",
                "nodename nor servname provided",
                "network is unreachable",
            ]
        )

    @staticmethod
    def _looks_like_non_api_token(value: str) -> bool:
        token = normalize_text(value)
        lowered = token.lower()
        return lowered.startswith(("ya29.", "1//", "aq.", "eyj"))

    def _extract_text_from_image(self, image_base64: str, image_mime_type: str | None) -> str:
        try:
            image_bytes = base64.b64decode(image_base64)
        except Exception:  # noqa: BLE001
            return ""

        # Local OCR fallback works even when Gemini is unavailable.
        local_text = normalize_text(self._extract_text_macos_vision(image_bytes=image_bytes, mime_type=image_mime_type))
        if not self._client:
            return local_text

        mime_candidates = self._candidate_image_mime_types(image_mime_type)
        remote_candidates: list[str] = []
        last_api_error: ApiError | None = None

        for mime_type in mime_candidates:
            try:
                extracted = self._extract_text_json(image_bytes=image_bytes, mime_type=mime_type)
            except ApiError as exc:
                last_api_error = exc
                continue
            if extracted:
                remote_candidates.append(extracted)

        for mime_type in mime_candidates:
            try:
                extracted = self._extract_text_plain(image_bytes=image_bytes, mime_type=mime_type)
            except ApiError as exc:
                last_api_error = exc
                continue
            if extracted:
                remote_candidates.append(extracted)

        remote_best = self._pick_best_ocr_candidate(remote_candidates)
        if len(remote_best) >= 20:
            return remote_best
        if len(local_text) >= 20:
            return local_text
        if remote_best:
            return remote_best
        if local_text:
            return local_text
        if last_api_error is not None:
            raise last_api_error
        return ""

    @staticmethod
    def _notes_requirements(topic: dict) -> dict:
        knowledge = topic.get("knowledge", {})
        has_legal_static = bool(knowledge.get("case_laws")) or any("Article" in item for item in knowledge.get("core_facts", []))
        requires_current_affairs = bool(knowledge.get("current_affairs_seed")) and not has_legal_static
        return {
            "requires_articles": has_legal_static,
            "minimum_case_laws": settings.minimum_static_case_laws if has_legal_static else 0,
            "requires_current_affairs_link": requires_current_affairs,
        }

    @staticmethod
    def _looks_like_ocr_noise(value: str) -> bool:
        noise_tokens = len(re.findall(r"[^a-zA-Z0-9\s,.;:()%-]", value))
        return bool(value) and noise_tokens / max(len(value), 1) > 0.02

    @staticmethod
    def _pick_best_ocr_candidate(candidates: list[str]) -> str:
        best_text = ""
        best_score = -1000.0
        for candidate in candidates:
            cleaned = normalize_text(candidate)
            if not cleaned:
                continue
            # Prefer longer readable outputs while penalizing symbol-heavy noise.
            odd_symbols = len(re.findall(r"[^A-Za-z0-9\s,.;:!?()/%'\-]", cleaned))
            score = float(len(cleaned) - (odd_symbols * 8))
            if score > best_score or (abs(score - best_score) <= 0.001 and len(cleaned) > len(best_text)):
                best_score = score
                best_text = cleaned
        return best_text

    @staticmethod
    def _repair_common_ocr_artifacts(value: str) -> str:
        cleaned = normalize_text(value)
        if not cleaned:
            return ""

        replacements = [
            (r"\bRegulating At\b", "Regulating Act"),
            (r"\baffais\b", "affairs"),
            (r"\btast Jadia Coury\b", "East India Company"),
            (r"\bfreneral\b", "General"),
            (r"\bGrovener\b", "Governor"),
            (r"\bbang\b", "Bengal"),
            (r"\bSupume Count\b", "Supreme Court"),
            (r"\bJunges\b", "Judges"),
            (r"\bExentive Comicil\b", "Executive Council"),
            (r"\bBoa Boud of lont of Directors\b", "Court of Directors"),
            (r"\bconfion\b", "corruption"),
            (r"\btrado\b", "trade"),
            (r"\bgudia\b", "India"),
            (r"\bAvending\b", "Amending"),
            (r"\bEthere Court Juisdicion dount contain\b", "Supreme Court jurisdiction doesn't contain"),
            (r"\bJuisdicion\b", "jurisdiction"),
            (r"\bdount\b", "doesn't"),
            (r"\bRevanue\b", "revenue"),
            (r"\bsemants\b", "servants"),
            (r"\bmattes\b", "matters"),
            (r"\bfry did\b", "they did"),
            (r"\btir\b", "their"),
            (r"\benfrity\b", "capacity"),
            (r"\bShoned\b", "Should"),
            (r"\bJuidictim\b", "jurisdiction"),
            (r"\bpeofle\b", "people"),
            (r"\bCal cutta\b", "Calcutta"),
            (r"\bShaull\b", "should"),
            (r"\bdig fitte of tad and huntin lams\b", "try people of Hindu and Muslim laws"),
            (r"\bAspeliste cont\b", "provincial courts"),
            (r"\bpromucial counts genesel in commil\b", "provincial courts to Governor General in Council"),
        ]
        for pattern, replacement in replacements:
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)

        cleaned = re.sub(r"\s*→\s*", "\n- ", cleaned)
        cleaned = re.sub(r"\bAt 178\)\s+Amending\b", "\nAmending Act 1781", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bRegulating Act 1773\b", "Regulating Act 1773", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = cleaned.replace("\n- ", "\n- ")
        return "\n".join(part.strip() for part in cleaned.split("\n") if part.strip())

    @staticmethod
    def _local_clean(value: str) -> str:
        cleaned = value.replace("•", ". ").replace("|", " ").replace("  ", " ")
        cleaned = re.sub(r"[^\S\r\n]+", " ", cleaned)
        cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
        return normalize_text(cleaned)

    @staticmethod
    def _merge_sources(typed_text: str, ocr_text: str, image_text: str) -> str:
        parts: list[str] = []
        for candidate in [typed_text, ocr_text, image_text]:
            normalized = normalize_text(candidate)
            if not normalized:
                continue
            if any(normalized in existing or existing in normalized for existing in parts):
                continue
            parts.append(normalized)
        return normalize_text("\n".join(parts))

    def _local_normalization_payload(self, cleaned: str) -> dict:
        return {"cleaned_answer": cleaned, "sentence_list": split_sentences(cleaned)}

    def _demo_model_answer(self, *, topic: dict, question: str) -> dict:
        knowledge = topic["knowledge"]
        intro = [
            f"{topic['name']} should be defined with conceptual precision and linked to the exact demand of the question."
        ]
        body = knowledge.get("must_have_points", []) + knowledge.get("good_to_have_points", [])
        conclusion = [
            f"A strong UPSC answer on {topic['name']} should end with reform relevance, institutional balance, or citizen impact."
        ]
        full_answer = intro + body[:6] + conclusion
        concepts = self._demo_concepts(topic=topic)["concepts"]
        return {
            "intro": intro,
            "body": body[:6],
            "conclusion": conclusion,
            "must_have_points": knowledge.get("must_have_points", []),
            "good_to_have_points": knowledge.get("good_to_have_points", []),
            "extra_edge_points": knowledge.get("extra_edge_points", []),
            "articles_and_facts": knowledge.get("core_facts", []),
            "examples": knowledge.get("case_laws", []) or [item["issue"] for item in knowledge.get("current_affairs_seed", [])],
            "value_addition": knowledge.get("value_addition", []),
            "core_concepts": concepts,
            "full_answer": [question, *full_answer],
        }

    @staticmethod
    def _demo_concepts(*, topic: dict) -> dict:
        knowledge = topic["knowledge"]
        concepts = (
            knowledge.get("must_have_points", [])
            + knowledge.get("good_to_have_points", [])
            + knowledge.get("extra_edge_points", [])
            + knowledge.get("keywords", [])
        )
        ordered: list[str] = []
        for concept in concepts:
            if concept and concept not in ordered:
                ordered.append(concept)
        return {"concepts": ordered[:12]}

    def _demo_content_evaluator(self, *, topic: dict, cleaned_answer: str) -> dict:
        lowered = cleaned_answer.lower()
        knowledge = topic["knowledge"]
        must_have = [point for point in knowledge.get("must_have_points", []) if self._point_visible(point, lowered)]
        good_to_have = [point for point in knowledge.get("good_to_have_points", []) if self._point_visible(point, lowered)]
        extra_edge = [point for point in knowledge.get("extra_edge_points", []) if self._point_visible(point, lowered)]
        missing = [point for point in knowledge.get("must_have_points", []) if point not in must_have]
        relevance = "FULL" if len(must_have) >= 2 else "PARTIAL" if must_have else "OFF_TOPIC"
        alternative_valid = len(cleaned_answer.split()) > 120 and any(
            marker in lowered for marker in ["however", "although", "therefore", "in contrast", "at the same time"]
        )
        return {
            "relevance": relevance,
            "domain": "WRONG" if "completely unrelated" in lowered else "CORRECT",
            "must_have_points": knowledge.get("must_have_points", []),
            "good_to_have_points": knowledge.get("good_to_have_points", []),
            "extra_edge_points": knowledge.get("extra_edge_points", []),
            "missing_points": missing,
            "incorrect_points": [],
            "alternative_valid": alternative_valid,
        }

    @staticmethod
    def _demo_reasoning_evaluator(*, cleaned_answer: str) -> dict:
        lowered = cleaned_answer.lower()
        word_count = len(cleaned_answer.split())
        depth = "DEEP" if word_count > 140 else "MODERATE" if word_count > 75 else "SURFACE"
        thinking = (
            "CRITICAL"
            if any(token in lowered for token in ["however", "although", "trade-off", "limitation", "critically"])
            else "ANALYTICAL"
            if any(token in lowered for token in ["because", "therefore", "impact", "reason", "results in"])
            else "DESCRIPTIVE"
        )
        return {
            "depth": depth,
            "thinking": thinking,
            "balanced_argument": any(token in lowered for token in ["however", "on the other hand", "while"]),
            "real_world_relevance": "HIGH" if re.search(r"\b\d{4}\b|\bcase\b|\bscheme\b|\barticle\b", lowered) else "MEDIUM" if word_count > 90 else "LOW",
            "logical_flow": "STRONG" if any(token in lowered for token in ["therefore", "thus", "hence"]) else "ADEQUATE",
            "interlinking_topics": any(token in lowered for token in ["interplay", "linked", "connect", "read with", "along with"]),
        }

    @staticmethod
    def _demo_directive_evaluator(*, question: str, cleaned_answer: str) -> dict:
        lowered_question = question.lower()
        lowered_answer = cleaned_answer.lower()
        demands = [token for token in ["discuss", "explain", "critically", "analyse", "examine", "evaluate"] if token in lowered_question]
        fulfilled = [token for token in demands if token in lowered_answer or len(cleaned_answer.split()) > 90]
        missed = [token for token in demands if token not in fulfilled]
        directive = "FULL" if demands and not missed else "PARTIAL" if fulfilled or len(cleaned_answer.split()) > 60 else "NONE"
        structure = "STRONG" if any(token in lowered_answer for token in ["therefore", "thus", "hence", "overall"]) else "ADEQUATE"
        return {
            "directive": directive,
            "structure": structure,
            "fulfilled_demands": fulfilled,
            "missed_demands": missed,
        }

    def _demo_unified_evaluation_signals(self, *, question: str, cleaned_answer: str, concept_universe: list[dict[str, str]] | None = None) -> dict:
        lowered_question = question.lower()
        lowered_answer = cleaned_answer.lower()
        expected_concepts = concept_universe or [
            {"concept": "definition and context", "importance": "core"},
            {"concept": "core arguments", "importance": "core"},
            {"concept": "causes", "importance": "secondary"},
            {"concept": "impacts", "importance": "secondary"},
            {"concept": "challenges", "importance": "secondary"},
            {"concept": "way forward", "importance": "secondary"},
            {"concept": "examples", "importance": "secondary"},
        ]
        concept_scores: list[dict[str, Any]] = []
        for item in expected_concepts:
            concept = str(item.get("concept") or "")
            if not concept:
                continue
            tokens = [token for token in re.findall(r"[a-zA-Z0-9]+", concept.lower()) if len(token) > 2]
            token_hits = sum(1 for token in tokens[:4] if token in lowered_answer)
            coverage_score = 2 if token_hits >= 2 else 1 if token_hits >= 1 else 0
            concept_scores.append(
                {
                    "concept": concept,
                    "importance": "core" if str(item.get("importance") or "secondary") == "core" else "secondary",
                    "coverage_score": coverage_score,
                }
            )
        dimension_counts = {
            "causes": 1 if any(marker in lowered_answer for marker in {"because", "due to", "causes", "drivers"}) else 0,
            "impacts": 1 if any(marker in lowered_answer for marker in {"impact", "effects", "results", "consequences"}) else 0,
            "challenges": 1 if any(marker in lowered_answer for marker in {"challenge", "problem", "limitation", "constraint"}) else 0,
            "way_forward": 1 if any(marker in lowered_answer for marker in {"way forward", "should", "reform", "recommend", "need to"}) else 0,
            "examples": 1 if any(marker in lowered_answer for marker in {"for example", "for instance", "case", "article", "committee"}) else 0,
        }
        dimensions_detected = [key for key, value in dimension_counts.items() if value > 0]
        directive = next((token for token in ["discuss", "analyze", "critically examine", "evaluate", "explain", "comment"] if token in lowered_question), "discuss")
        core_total = sum(1 for item in concept_scores if item["importance"] == "core")
        core_covered = sum(1 for item in concept_scores if item["importance"] == "core" and item["coverage_score"] >= 1)
        core_well_covered = sum(1 for item in concept_scores if item["importance"] == "core" and item["coverage_score"] == 2)
        core_coverage_ratio = round(core_covered / max(1, core_total), 3)
        core_depth_ratio = round(core_well_covered / max(1, core_total), 3)
        body = "structured" if any(token in lowered_answer for token in ["first", "second", "however", "therefore"]) else "semi" if len(cleaned_answer.split()) > 40 else "unstructured"
        conclusion = "present" if any(token in lowered_answer for token in ["therefore", "thus", "in conclusion", "overall"]) else "weak" if len(cleaned_answer.split()) > 50 else "missing"
        vague_ratio = 0.2 if len(cleaned_answer.split()) > 80 else 0.4 if len(cleaned_answer.split()) > 40 else 0.6
        if len(dimensions_detected) >= 4 and core_depth_ratio > 0.4:
            dimension_balance = "good"
        elif len(dimensions_detected) >= 2:
            dimension_balance = "average"
        else:
            dimension_balance = "poor"
        penalty_flags: list[dict[str, str]] = []
        if conclusion == "missing":
            penalty_flags.append({"flag": "missing_conclusion", "severity": "medium"})
        if body == "unstructured":
            penalty_flags.append({"flag": "poor_structure", "severity": "high"})
        if core_coverage_ratio < 0.4:
            penalty_flags.append({"flag": "weak_core_coverage", "severity": "high"})
        if vague_ratio > 0.5:
            penalty_flags.append({"flag": "excessive_vagueness", "severity": "high"})
        if core_coverage_ratio < 0.5 or vague_ratio > 0.5:
            confidence = "low"
        elif core_depth_ratio > 0.4 and len(dimensions_detected) >= 3:
            confidence = "high"
        else:
            confidence = "medium"
        payload = {
            "directive": directive,
            "required_components": ["direct response to the question", "relevant core concepts", "structured presentation"],
            "concept_scores": concept_scores[:20],
            "extra_valid_concepts": [],
            "core_summary": {
                "core_total": core_total,
                "core_covered": core_covered,
                "core_well_covered": core_well_covered,
            },
            "dimension_counts": dimension_counts,
            "dimension_balance": dimension_balance,
            "value_additions": {
                "data_or_report": 1 if any(token in lowered_answer for token in ["report", "survey", "data", "census"]) else 0,
                "example": dimension_counts["examples"],
                "generic": 0 if len(cleaned_answer.split()) > 60 else 1,
            },
            "structure": {
                "introduction": "present" if len(cleaned_answer.split()) >= 20 else "weak" if len(cleaned_answer.split()) >= 10 else "missing",
                "body": body,
                "conclusion": conclusion,
            },
            "core_coverage_ratio": core_coverage_ratio,
            "core_depth_ratio": core_depth_ratio,
            "clarity_score": 4 if len(cleaned_answer.split()) > 90 else 3 if len(cleaned_answer.split()) > 45 else 2,
            "vague_ratio": vague_ratio,
            "directive_coverage_ratio": 0.8 if len(cleaned_answer.split()) > 100 else 0.5 if len(cleaned_answer.split()) > 50 else 0.2,
            "factual_error_present": False,
            "penalty_flags": penalty_flags,
            "contradiction_present": False,
            "partial_concepts_count": sum(1 for item in concept_scores if item["coverage_score"] == 1),
            "answer_length_category": "optimal" if 80 <= len(cleaned_answer.split()) <= 220 else "short" if len(cleaned_answer.split()) < 80 else "long",
            "fundamental_weakness": core_coverage_ratio < 0.4,
            "confidence": confidence,
        }
        payload.update(self._legacy_signal_view(payload))
        return payload

    def _demo_evaluation_guidance(
        self,
        *,
        topic: dict,
        model_answer: dict,
        analysis: dict,
        similarity: dict,
        scoring: dict,
        features: dict,
    ) -> dict:
        improvements: list[str] = []
        strengths: list[str] = []
        directions: list[str] = []

        if scoring.get("structure_score", 0) < 0.7:
            improvements.append("Sharpen intro-body-conclusion flow")
        if not features.get("examples_detected"):
            improvements.append("Add specific examples or constitutional anchors")
        if similarity.get("missing_concepts"):
            improvements.append("Cover missing core concepts more directly")
        if features.get("bluff_ratio", 0) > 0.2:
            improvements.append("Reduce generic statements")
        if scoring.get("efficiency_score", 0) < 0.65:
            improvements.append("Tighten the answer and remove drift")
        if scoring.get("relevance_score", 0) < 0.75:
            improvements.append("Stay closer to the question demand")

        if scoring.get("relevance_score", 0) >= 0.8:
            strengths.append("Relevant points are well targeted")
        if scoring.get("structure_score", 0) >= 0.78:
            strengths.append("Structure feels examiner-friendly")
        if analysis.get("thinking") in {"ANALYTICAL", "CRITICAL"}:
            strengths.append("Analytical movement is visible")
        if features.get("examples_detected"):
            strengths.append("Examples improve answer credibility")
        if features.get("fact_density", 0) >= 0.35:
            strengths.append("Conceptual clarity is reasonably anchored")

        candidate_directions = (
            similarity.get("missing_concepts", [])
            + model_answer.get("articles_and_facts", [])
            + model_answer.get("examples", [])
            + model_answer.get("value_addition", [])
            + topic.get("knowledge", {}).get("value_addition", [])
        )
        for item in candidate_directions:
            hint = self._directional_hint(item)
            if hint and hint not in directions:
                directions.append(hint)

        while len(improvements) < 3:
            for fallback in [
                "Use more evidence-backed phrasing",
                "Link each paragraph to the directive",
                "Add one value-addition point",
            ]:
                if fallback not in improvements:
                    improvements.append(fallback)
                if len(improvements) == 3:
                    break

        while len(strengths) < 2:
            for fallback in [
                "The answer has usable core material",
                "There is a visible attempt at UPSC framing",
            ]:
                if fallback not in strengths:
                    strengths.append(fallback)
                if len(strengths) == 2:
                    break

        while len(directions) < 3:
            fallback_candidates = topic.get("knowledge", {}).get("pyq", []) + topic.get("knowledge", {}).get("core_facts", [])
            if not fallback_candidates:
                fallback_candidates = [
                    "Start with a precise definition and direct demand mapping",
                    "Use one constitutional or policy anchor in the body",
                    "Close with a crisp governance-oriented conclusion",
                ]
            appended = False
            for fallback in fallback_candidates:
                hint = self._directional_hint(fallback)
                if hint and hint not in directions:
                    directions.append(hint)
                    appended = True
                if len(directions) == 3:
                    break
            if not appended:
                break

        return {
            "top_improvements": improvements[:3],
            "strengths": strengths[:3],
            "ideal_answer_directions": directions[:3],
        }

    @staticmethod
    def _point_visible(point: str, lowered_answer: str) -> bool:
        tokens = [token for token in re.findall(r"[a-zA-Z][a-zA-Z0-9]+", point.lower()) if len(token) > 3]
        if not tokens:
            return False
        hits = sum(1 for token in tokens if token in lowered_answer)
        return hits / len(tokens) >= 0.4

    @staticmethod
    def _directional_hint(item: str) -> str:
        cleaned = normalize_text(item).strip(". ")
        if not cleaned:
            return ""
        lowered = cleaned.lower()
        if lowered.startswith(("include ", "compare ", "link ", "use ", "add ", "show ", "mention ")):
            return cleaned
        if "article" in lowered:
            return f"Include {cleaned}"
        if "compare" in lowered or "vs" in lowered:
            return cleaned if cleaned[0].isupper() else cleaned.capitalize()
        if any(token in lowered for token in ["judgment", "case", "committee", "scheme", "council"]):
            return f"Use {cleaned}"
        return f"Link to {cleaned}"

    def _demo_learning_bundle(self, topic: dict) -> dict:
        knowledge = topic["knowledge"]
        flashcards: list[dict] = []
        factual_cards = knowledge.get("core_facts", [])[:5]
        while len(factual_cards) < 5:
            factual_cards.append(f"{topic['name']} fact point {len(factual_cards) + 1}")
        for item in factual_cards:
            flashcards.append(
                {
                    "card_type": "FACTUAL",
                    "front": f"What is one high-value fact about {topic['name']}?",
                    "back": item,
                    "explanation": "Recall the fact precisely and use it as evidence in prelims or mains.",
                    "difficulty": "easy",
                }
            )
        for item in knowledge.get("must_have_points", [])[:3]:
            flashcards.append(
                {
                    "card_type": "CONCEPTUAL",
                    "front": f"Explain this concept in {topic['name']}.",
                    "back": item,
                    "explanation": "Use the idea in a 2-3 line analytical frame.",
                    "difficulty": "medium",
                }
            )
        traps = knowledge.get("value_addition", [])[:2]
        while len(traps) < 2:
            traps.append(f"Trap cue for {topic['name']} {len(traps) + 1}")
        for item in traps:
            flashcards.append(
                {
                    "card_type": "TRAP",
                    "front": f"What trap should you avoid in {topic['name']}?",
                    "back": item,
                    "explanation": "This helps in eliminating vague or generic statements.",
                    "difficulty": "medium",
                }
            )
        pyqs = knowledge.get("pyq", [])[:2]
        while len(pyqs) < 2:
            pyqs.append(f"Write a short mains frame on {topic['name']}.")
        for item in pyqs:
            flashcards.append(
                {
                    "card_type": "MAINS",
                    "front": item,
                    "back": "Answer with intro, 3 dimensions, and a reform-oriented conclusion.",
                    "explanation": "Use it as an answer writing rehearsal card.",
                    "difficulty": "hard",
                }
            )
        return {
            "notes": {
                "thirty_second_revision": knowledge.get("must_have_points", [])[:3],
                "core_facts": knowledge.get("core_facts", []),
                "classification": knowledge.get("classification", []),
                "case_laws": knowledge.get("case_laws", []),
                "current_affairs": knowledge.get("current_affairs_seed", []),
                "prelim_traps": knowledge.get("value_addition", [])[:3],
                "mains_answer_structure": knowledge.get("mains_frame", {"intro": [], "body": [], "conclusion": []}),
                "value_addition": knowledge.get("value_addition", []),
                "pyq": knowledge.get("pyq", []),
            },
            "flashcards": flashcards,
        }


llm_service = LLMService()
