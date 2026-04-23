from __future__ import annotations

import json

from app.config import ROOT_DIR, settings
from app.database import db
from app.errors import input_invalid_error
from app.schemas import TopicNormalizationPayload
from app.services.llm_service import llm_service
from app.services.scoring_engine import scoring_engine
from app.services.similarity_engine import similarity_engine
from app.utils.common import new_id, normalize_text, stable_json_dumps, utc_now_iso


class AnswerEvaluationEngine:
    @staticmethod
    def _concept_universe_from_model_answer(model_answer: dict) -> list[dict[str, str]]:
        concept_universe: list[dict[str, str]] = []
        seen: set[str] = set()
        for concept in model_answer.get("core_concepts", []) or []:
            normalized = normalize_text(str(concept or ""))
            if normalized and normalized.lower() not in seen:
                seen.add(normalized.lower())
                concept_universe.append({"concept": normalized, "importance": "core"})
        for concept in model_answer.get("must_have_points", []) or []:
            normalized = normalize_text(str(concept or ""))
            if normalized and normalized.lower() not in seen:
                seen.add(normalized.lower())
                concept_universe.append({"concept": normalized, "importance": "core"})
        for concept in (model_answer.get("good_to_have_points", []) or []) + (model_answer.get("extra_edge_points", []) or []):
            normalized = normalize_text(str(concept or ""))
            if normalized and normalized.lower() not in seen:
                seen.add(normalized.lower())
                concept_universe.append({"concept": normalized, "importance": "secondary"})
        return concept_universe

    @staticmethod
    def _raise_ocr_unavailable_if_needed(
        *,
        student_answer: str | None,
        ocr_text: str | None,
        handwritten_image_base64: str | None,
    ) -> None:
        has_image = bool((handwritten_image_base64 or "").strip())
        has_text = bool(normalize_text(student_answer or "") or normalize_text(ocr_text or ""))
        has_ocr_engine = llm_service.enabled or llm_service.local_ocr_available
        if has_image and not has_text and not has_ocr_engine:
            if llm_service.key_configured and llm_service.auth_failed:
                raise input_invalid_error(
                    reason="ocr_auth_failed",
                    message="Gemini OCR authentication failed. Replace GEMINI_API_KEY with a valid key and restart backend.",
                    suggestions=[
                        f"Set GEMINI_API_KEY in {ROOT_DIR / '.env'}",
                        f"Or set GEMINI_API_KEY in {ROOT_DIR / 'backend' / '.env'}",
                        "Use an AI Studio Gemini API key (not OAuth/access token)",
                    ],
                )
            raise input_invalid_error(
                reason="ocr_engine_unavailable",
                message="OCR is unavailable in demo mode. Add GEMINI_API_KEY or paste the answer text manually.",
                suggestions=[
                    f"Set GEMINI_API_KEY in {ROOT_DIR / '.env'}",
                    f"Or set GEMINI_API_KEY in {ROOT_DIR / 'backend' / '.env'}",
                    "Check /health and confirm ai_mode is gemini",
                    "Paste typed answer or OCR text manually",
                ],
            )

    @staticmethod
    def _safe_json_loads(value: str | None) -> dict:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:  # noqa: BLE001
            return {}

    def _normalize_question_topic(self, question: str) -> TopicNormalizationPayload:
        fallback = TopicNormalizationPayload(
            subject="General Studies",
            core_topic=normalize_text(question)[:120] or "UPSC Topic",
            subtopics=[
                "Core demand of the question",
                "Constitutional and governance relevance",
                "Critical analysis and balance",
                "Way forward and conclusion",
            ],
        )
        payload = llm_service._generate_json(
            model=settings.gemini_small_model,
            instruction=(
                "Return strict JSON only with subject, core_topic, subtopics for UPSC mains evaluation context. "
                "Do not add any extra keys."
            ),
            schema=TopicNormalizationPayload,
            contents=stable_json_dumps({"question": question, "exam": "UPSC"}),
            fallback=lambda: fallback.model_dump(),
        )
        validated = TopicNormalizationPayload.model_validate(payload)
        if not validated.subtopics:
            validated.subtopics = fallback.subtopics
        return validated

    @staticmethod
    def _topic_payload(normalized: TopicNormalizationPayload) -> dict:
        keyword_bank = [normalized.core_topic, *normalized.subtopics]
        keywords = [normalize_text(item) for item in keyword_bank if normalize_text(item)]
        must_have = normalized.subtopics[:4]
        good_to_have = normalized.subtopics[4:8]
        return {
            "id": "topic_dynamic_upsc",
            "name": normalized.core_topic,
            "description": f"Dynamic UPSC evaluation context for {normalized.core_topic}",
            "learning_objectives": normalized.subtopics,
            "knowledge": {
                "keywords": keywords,
                "must_have_points": must_have,
                "good_to_have_points": good_to_have,
                "extra_edge_points": [],
                "core_facts": [],
                "case_laws": [],
                "value_addition": [],
                "current_affairs_seed": [],
                "mains_frame": {},
                "pyq": [],
            },
        }

    @staticmethod
    def _input_mode(*, student_answer: str | None, ocr_text: str | None, image_base64: str | None) -> str:
        has_image = bool(image_base64)
        has_text = bool((student_answer or "").strip() or (ocr_text or "").strip())
        if has_image and has_text:
            return "hybrid"
        if has_image:
            return "image"
        return "typed"

    def preview_ocr(
        self,
        *,
        student_answer: str | None,
        ocr_text: str | None,
        handwritten_image_base64: str | None,
        handwritten_image_mime_type: str | None,
    ) -> dict:
        self._raise_ocr_unavailable_if_needed(
            student_answer=student_answer,
            ocr_text=ocr_text,
            handwritten_image_base64=handwritten_image_base64,
        )
        normalized = llm_service.clean_input(
            answer_text=student_answer,
            ocr_text=ocr_text,
            handwritten_image_base64=handwritten_image_base64,
            handwritten_image_mime_type=handwritten_image_mime_type,
        )
        cleaned = normalize_text(normalized.get("cleaned_answer", ""))
        merged = normalize_text(normalized.get("source_text", {}).get("merged_text", cleaned))
        extracted = normalize_text(normalized.get("source_text", {}).get("image_text", ""))
        if len(cleaned) < 20:
            partial = merged or extracted or cleaned
            # Surface partial OCR output for manual correction instead of hard-failing.
            if partial:
                return {
                    "extracted_text": extracted or partial,
                    "cleaned_text": cleaned or partial,
                    "merged_text": partial,
                }
            raise input_invalid_error(
                reason="empty_or_unreadable",
                message="We couldn’t read your handwriting clearly. Try a cleaner image or edit the preview text.",
                suggestions=["Retry upload", "Edit OCR preview", "Paste clearer text manually"],
            )
        return {
            "extracted_text": extracted or cleaned,
            "cleaned_text": cleaned,
            "merged_text": merged or cleaned,
        }

    def get_history(self, *, user_id: str, limit: int = 20) -> dict:
        rows = db.fetch_all(
            """
            SELECT id, question_text, input_mode, evaluation_json, created_at
            FROM answer_evaluation_history
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            [user_id, max(1, min(100, limit))],
        )

        items: list[dict] = []
        for row in rows:
            evaluation = self._safe_json_loads(row.get("evaluation_json"))
            subscores_raw = evaluation.get("subscores") if isinstance(evaluation.get("subscores"), dict) else {}
            items.append(
                {
                    "id": str(row.get("id") or ""),
                    "question_text": normalize_text(str(row.get("question_text") or "")),
                    "input_mode": normalize_text(str(row.get("input_mode") or "typed")) or "typed",
                    "score": round(float(evaluation.get("score") or 0.0), 2),
                    "subscores": {
                        "content_accuracy": round(float(subscores_raw.get("content_accuracy") or 0.0), 2),
                        "structure": round(float(subscores_raw.get("structure") or 0.0), 2),
                        "depth": round(float(subscores_raw.get("depth") or 0.0), 2),
                        "keywords": round(float(subscores_raw.get("keywords") or 0.0), 2),
                        "conclusion": round(float(subscores_raw.get("conclusion") or 0.0), 2),
                    },
                    "strengths": [str(item) for item in (evaluation.get("strengths") or [])[:3]],
                    "missing_points": [str(item) for item in (evaluation.get("missing_points") or [])[:4]],
                    "improvements": [str(item) for item in (evaluation.get("improvements") or [])[:3]],
                    "created_at": str(row.get("created_at") or ""),
                }
            )

        return {"count": len(items), "items": items}

    def evaluate(
        self,
        *,
        user_id: str,
        question: str,
        student_answer: str | None,
        ocr_text: str | None,
        handwritten_image_base64: str | None,
        handwritten_image_mime_type: str | None,
        concept_universe: list[dict[str, str] | str] | None = None,
        max_marks: int = 10,
        calibration_enabled: bool = True,
        examiner_mode: str = "balanced",
        calibration_seed: int | None = None,
    ) -> dict:
        question = normalize_text(question)
        self._raise_ocr_unavailable_if_needed(
            student_answer=student_answer,
            ocr_text=ocr_text,
            handwritten_image_base64=handwritten_image_base64,
        )
        normalized_input = llm_service.clean_input(
            answer_text=student_answer,
            ocr_text=ocr_text,
            handwritten_image_base64=handwritten_image_base64,
            handwritten_image_mime_type=handwritten_image_mime_type,
        )
        cleaned_answer = normalize_text(normalized_input.get("cleaned_answer", ""))
        if len(cleaned_answer) < 20:
            raise input_invalid_error(
                reason="empty_or_unreadable",
                message="We could not derive a readable answer from the submitted text or image.",
            )

        normalized_topic = self._normalize_question_topic(question)
        topic = self._topic_payload(normalized_topic)

        model_answer = llm_service.generate_model_answer(question=question, topic=topic)
        effective_concept_universe = llm_service._normalize_concept_universe(concept_universe) or self._concept_universe_from_model_answer(model_answer)
        evaluation_signals = llm_service.analyze_answer_signals(
            question=question,
            cleaned_answer=cleaned_answer,
            concept_universe=effective_concept_universe,
        )
        features = scoring_engine.extract_features(
            cleaned_answer=cleaned_answer,
            sentence_list=normalized_input.get("sentence_list", []),
            topic=topic,
        )
        similarity = similarity_engine.compare(
            student_answer=cleaned_answer,
            model_answer=model_answer,
            analysis={"must_have_points": evaluation_signals.get("concepts_expected", [])[:6]},
        )
        analysis = scoring_engine.merge_analysis_from_signals(
            signals=evaluation_signals,
            features=features,
            similarity=similarity,
        )
        scoring = scoring_engine.score(
            analysis=analysis,
            similarity=similarity,
            features=features,
            max_marks=max_marks,
        )
        normalized_scoring = scoring_engine.score_from_signal_strategy(
            signals=evaluation_signals,
            max_marks=max_marks,
            calibration_enabled=calibration_enabled,
            calibration_mode=examiner_mode,
            calibration_seed=calibration_seed,
        )
        guidance = llm_service.generate_evaluation_guidance(
            question=question,
            cleaned_answer=cleaned_answer,
            topic=topic,
            model_answer=model_answer,
            analysis=analysis,
            similarity=similarity,
            scoring=scoring,
            features=features,
        )

        subscores = {
            "content_accuracy": round(float(normalized_scoring.get("core_score", 0.0)) * 10.0, 2),
            "structure": round(float(normalized_scoring.get("structure_score", 0.0)) * 10.0, 2),
            "depth": round(float(evaluation_signals.get("core_depth_ratio", 0.0)) * 10.0, 2),
            "keywords": round(float(evaluation_signals.get("core_coverage_ratio", 0.0)) * 10.0, 2),
            "conclusion": round(
                10.0
                if str((evaluation_signals.get("structure", {}) or {}).get("conclusion") or "") == "present"
                else 5.0
                if str((evaluation_signals.get("structure", {}) or {}).get("conclusion") or "") == "weak"
                else 0.0,
                2,
            ),
        }
        penalty_reasons = scoring_engine.penalty_reasons(
            analysis=analysis,
            similarity=similarity,
            features=features,
            scoring=scoring,
        )
        mistakes = list(dict.fromkeys(analysis.get("incorrect_points", []) + penalty_reasons))[:8]
        improvements = guidance.get("top_improvements", [])[:3]

        evaluation = {
            "score": round(float(normalized_scoring.get("estimated_marks", 0.0)), 2),
            "subscores": subscores,
            "missing_points": analysis.get("missing_points", [])[:10],
            "mistakes": mistakes,
            "improvements": improvements,
            "strengths": guidance.get("strengths", [])[:3],
            "applied_caps": normalized_scoring.get("applied_caps", []),
            "applied_penalties": normalized_scoring.get("applied_penalties", []),
            "marks_range": normalized_scoring.get("marks_range", [0.0, 0.0]),
            "normalized_score": normalized_scoring.get("final_normalized_score", 0.0),
            "component_scores": {
                "core_score": normalized_scoring.get("core_score", 0.0),
                "directive_score": normalized_scoring.get("directive_score", 0.0),
                "structure_score": normalized_scoring.get("structure_score", 0.0),
                "value_score": normalized_scoring.get("value_score", 0.0),
                "expression_score": normalized_scoring.get("expression_score", 0.0),
                "raw_score": normalized_scoring.get("raw_score", 0.0),
            },
            "confidence": normalized_scoring.get("confidence", evaluation_signals.get("confidence", "medium")),
            "calibration": normalized_scoring.get("calibration", {}),
        }

        raw_merged_text = normalize_text(normalized_input.get("source_text", {}).get("merged_text", ""))
        now = utc_now_iso()
        db.execute(
            """
            INSERT INTO answer_evaluation_history
            (id, user_id, question_text, raw_answer_text, cleaned_answer_text, ocr_text, input_mode, analysis_json, scoring_json, evaluation_json, model_answer_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                new_id("aneval"),
                user_id,
                question,
                raw_merged_text or cleaned_answer,
                cleaned_answer,
                ocr_text,
                self._input_mode(student_answer=student_answer, ocr_text=ocr_text, image_base64=handwritten_image_base64),
                stable_json_dumps({"analysis": analysis, "similarity": similarity, "features": features, "normalized_scoring": normalized_scoring}),
                stable_json_dumps({"legacy_scoring": scoring, "normalized_scoring": normalized_scoring}),
                stable_json_dumps(evaluation),
                stable_json_dumps(model_answer),
                now,
            ],
        )

        return {
            "evaluation": evaluation,
            "analysis": {
                "evaluation_signals": evaluation_signals,
                "merged": analysis,
                "normalized_scoring": normalized_scoring,
                "legacy_scoring": scoring,
            },
            "cleaned_answer": cleaned_answer,
            "score": round(float(normalized_scoring.get("estimated_marks", 0.0)), 2),
            "improvements": improvements,
            "model_answer": model_answer,
            "subscores": subscores,
        }


answer_evaluation_engine = AnswerEvaluationEngine()
