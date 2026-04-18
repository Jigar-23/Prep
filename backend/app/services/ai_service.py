from __future__ import annotations

import base64
import json
import textwrap
import time
from typing import Any

from google import genai
from google.genai import types

from app.config import settings
from app.errors import ApiError
from app.schemas import AIEvaluationBundle, AIGenerationBundle
from app.utils.common import sha256_text, stable_json_dumps


GENERATION_PROMPT = textwrap.dedent(
    """
    You are generating structured exam-preparation content.
    Return JSON only.
    Generate:
    - structured notes with summary, detailed sections, examples, traps, diagrams
    - exactly 5 MCQs
    - exactly 1 mains question
    Keep explanations crisp, factual, and exam oriented.
    """
).strip()


EVALUATION_PROMPT = textwrap.dedent(
    """
    Evaluate the learner answer against the question.
    Return JSON only.
    Score out of 10.
    Judge accuracy, structure, depth, and exam relevance.
    If image text is unclear, extract the readable parts and state that uncertainty inside reasoning_summary.
    """
).strip()


def _demo_generation(topic: dict) -> dict:
    name = topic["name"]
    objectives = topic["learning_objectives"]
    summary = [
        f"{name} is a recurring scoring area; start with definition, scope, and why examiners ask it.",
        f"Anchor revision around these objectives: {', '.join(objectives[:2])}.",
        "Use one constitutional, economic, or procedural reference whenever the answer format allows it.",
    ]
    detailed = [
        {
            "heading": "Core Idea",
            "body": [
                f"{name} should be understood through definition, structure, and practical application.",
                f"In exam settings, connect {name} with the broader subject context instead of memorizing isolated facts.",
            ],
        },
        {
            "heading": "Answer Framing",
            "body": [
                "Begin with a one-line definition or context setter.",
                "Use 3 to 4 points with cause-effect or feature-function logic.",
                "Close with relevance, challenge, or way forward.",
            ],
        },
    ]
    examples = [
        f"Use {name} in a short note with definition, significance, and one example.",
        "Convert factual recall into elimination logic for prelim-style MCQs.",
    ]
    traps = [
        "Do not confuse definitions with consequences.",
        "Avoid writing generic introductions that ignore the exact keyword in the prompt.",
    ]
    diagrams = [
        {
            "title": f"{name} quick flow",
            "steps": ["Definition", "Key features", "Application", "Common pitfalls", "Exam usage"],
        }
    ]
    mcqs = []
    for index in range(5):
        option_ids = ["A", "B", "C", "D"]
        mcqs.append(
            {
                "type": "mcq",
                "prompt": f"{name}: choose the most accurate exam-oriented statement for concept check {index + 1}.",
                "options": [
                    {"id": "A", "text": f"{name} is only theoretical and has no applied relevance."},
                    {"id": "B", "text": f"{name} should be understood with definition, application, and common exceptions."},
                    {"id": "C", "text": f"{name} can be solved only through rote memorization."},
                    {"id": "D", "text": f"{name} is unrelated to the parent subject."},
                ],
                "correct_option_id": "B",
                "explanation": "The strongest answers connect concept, application, and exceptions.",
                "explanation_hint": "Look for the balanced option.",
                "difficulty": "medium",
                "metadata": {"objective": objectives[index % len(objectives)]},
            }
        )
    mains = {
        "type": "mains",
        "prompt": f"Discuss {name} with conceptual clarity, applied relevance, and exam-ready structure.",
        "options": None,
        "correct_option_id": None,
        "explanation": "A complete answer defines the concept, explains mechanics, and ends with relevance or reform.",
        "explanation_hint": "Use intro-body-conclusion with one example.",
        "difficulty": "medium",
        "metadata": {"recommended_word_limit": 180},
    }
    return {
        "notes": {
            "summary": summary,
            "detailed": detailed,
            "examples": examples,
            "traps": traps,
            "diagrams": diagrams,
        },
        "questions": mcqs + [mains],
    }


def _demo_evaluation(question: dict, answer_text: str | None, extracted_text: str | None) -> dict:
    text = (answer_text or extracted_text or "").strip()
    lowered = text.lower()
    signal_words = max(1, sum(1 for token in ["define", "because", "therefore", "example", "article", "policy"] if token in lowered))
    score = min(9.0, 3.5 + signal_words)
    verdict = "good" if score >= 7 else "needs_improvement"
    return {
        "score": round(score, 1),
        "max_score": 10,
        "verdict": verdict,
        "rubric": {
            "accuracy": round(min(3.5, score * 0.35), 1),
            "structure": round(min(3.0, score * 0.3), 1),
            "depth": round(min(3.5, score * 0.35), 1),
        },
        "strengths": [
            "The answer attempts concept explanation instead of giving only isolated facts.",
            "There is enough signal for topic relevance.",
        ],
        "improvements": [
            "Add one sharper example or official term.",
            "Use a cleaner intro-body-conclusion structure.",
        ],
        "extracted_text": extracted_text,
        "reasoning_summary": f"Demo evaluation based on answer coverage for the question: {question['prompt'][:80]}",
    }


class AIService:
    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.gemini_api_key) if settings.gemini_api_key else None

    def _run_with_retry(self, call):
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                return call()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                time.sleep(1 + attempt)
        raise ApiError(503, "AI_UNAVAILABLE", "AI provider request failed.", {"reason": str(last_error)})

    def generate_bundle(self, exam: dict, subject: dict, topic: dict) -> tuple[dict, str]:
        if not self._client:
            if settings.allow_demo_ai_fallback:
                return _demo_generation(topic), "demo"
            raise ApiError(503, "AI_UNAVAILABLE", "Gemini is not configured.")

        prompt = stable_json_dumps(
            {
                "instruction": GENERATION_PROMPT,
                "exam": {"name": exam["name"], "description": exam["description"]},
                "subject": {"name": subject["name"], "description": subject["description"]},
                "topic": {
                    "name": topic["name"],
                    "description": topic["description"],
                    "learning_objectives": topic["learning_objectives"],
                    "difficulty": topic["difficulty"],
                },
            }
        )

        def _call():
            response = self._client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_json_schema": AIGenerationBundle.model_json_schema(),
                    "temperature": 0,
                },
            )
            return AIGenerationBundle.model_validate_json(response.text).model_dump()

        return self._run_with_retry(_call), "ai"

    def evaluate_answer(
        self,
        question: dict,
        answer_text: str | None,
        image_base64: str | None,
        image_mime_type: str | None,
    ) -> tuple[dict, str]:
        extracted_text = None
        if image_base64:
            try:
                image_bytes = base64.b64decode(image_base64)
                extracted_text = f"Image provided ({image_mime_type}, sha={sha256_text(image_base64)[:12]})"
            except Exception as exc:  # noqa: BLE001
                raise ApiError(400, "INVALID_ANSWER", "Could not decode uploaded image.", {"reason": str(exc)}) from exc
        else:
            image_bytes = None

        if not self._client:
            if settings.allow_demo_ai_fallback:
                return _demo_evaluation(question, answer_text, extracted_text), "demo"
            raise ApiError(503, "AI_UNAVAILABLE", "Gemini is not configured.")

        parts: list[Any] = [
            {
                "text": stable_json_dumps(
                    {
                        "instruction": EVALUATION_PROMPT,
                        "question": question["prompt"],
                        "question_type": question["type"],
                        "answer_text": answer_text,
                        "expected_reference": question.get("explanation", ""),
                    }
                )
            }
        ]
        if image_bytes and image_mime_type:
            parts.append(types.Part.from_bytes(data=image_bytes, mime_type=image_mime_type))

        def _call():
            response = self._client.models.generate_content(
                model=settings.gemini_model,
                contents=[{"role": "user", "parts": parts}],
                config={
                    "response_mime_type": "application/json",
                    "response_json_schema": AIEvaluationBundle.model_json_schema(),
                    "temperature": 0,
                },
            )
            result = AIEvaluationBundle.model_validate_json(response.text).model_dump()
            if extracted_text and not result.get("extracted_text"):
                result["extracted_text"] = extracted_text
            return result

        return self._run_with_retry(_call), "ai"


ai_service = AIService()
