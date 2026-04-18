from __future__ import annotations

import base64
import re
import textwrap
from typing import Any

from google import genai
from google.genai import types

from app.config import settings
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
)
from app.services.error_handler import error_handler
from app.utils.common import normalize_text, split_sentences, stable_json_dumps


class LLMService:
    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.gemini_api_key) if settings.gemini_api_key else None

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def _generate_json(
        self,
        *,
        model: str,
        instruction: str,
        schema: type,
        contents: list[Any] | str,
        fallback: callable,
    ) -> dict:
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

    def clean_input(
        self,
        answer_text: str | None,
        ocr_text: str | None = None,
        handwritten_image_base64: str | None = None,
        handwritten_image_mime_type: str | None = None,
    ) -> dict:
        raw = normalize_text((ocr_text or answer_text or "").strip())
        if not raw and handwritten_image_base64 and self._client:
            raw = self._extract_text_from_image(handwritten_image_base64, handwritten_image_mime_type)
        cleaned = self._local_clean(raw)
        should_use_model = self._client is not None and (len(cleaned) > 1200 or self._looks_like_ocr_noise(cleaned))
        if not should_use_model:
            return self._local_normalization_payload(cleaned)

        prompt = stable_json_dumps(
            {
                "task": "Normalize OCR or raw UPSC answer text without changing meaning.",
                "text": cleaned,
            }
        )
        return self._generate_json(
            model=settings.gemini_small_model,
            instruction="Return strict JSON only with cleaned_answer and sentence_list. Preserve meaning exactly.",
            schema=NormalizationPayload,
            contents=prompt,
            fallback=lambda: self._local_normalization_payload(cleaned),
        )

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

    def _extract_text_from_image(self, image_base64: str, image_mime_type: str | None) -> str:
        if not self._client:
            return ""

        image_bytes = base64.b64decode(image_base64)

        def _call() -> dict:
            response = self._client.models.generate_content(
                model=settings.gemini_small_model,
                contents=[
                    {
                        "role": "user",
                        "parts": [
                            {"text": "Extract only the readable handwritten UPSC answer text and return strict JSON with extracted_text."},
                            types.Part.from_bytes(data=image_bytes, mime_type=image_mime_type or "image/png"),
                        ],
                    }
                ],
                config={
                    "response_mime_type": "application/json",
                    "response_json_schema": ExtractedTextPayload.model_json_schema(),
                    "temperature": 0,
                },
            )
            return ExtractedTextPayload.model_validate_json(response.text).model_dump()

        payload = error_handler.with_retries(
            "Image text extraction",
            _call,
            retries=2,
            fallback=lambda: {"extracted_text": ""},
        )
        return normalize_text(payload.get("extracted_text", ""))

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
        return bool(value) and noise_tokens / max(len(value), 1) > 0.05

    @staticmethod
    def _local_clean(value: str) -> str:
        cleaned = value.replace("•", ". ").replace("|", " ").replace("  ", " ")
        cleaned = re.sub(r"[^\S\r\n]+", " ", cleaned)
        cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
        return normalize_text(cleaned)

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
            for fallback in topic.get("knowledge", {}).get("pyq", []) + topic.get("knowledge", {}).get("core_facts", []):
                hint = self._directional_hint(fallback)
                if hint and hint not in directions:
                    directions.append(hint)
                if len(directions) == 3:
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
