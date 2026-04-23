from __future__ import annotations

import json

from app.database import db
from app.errors import input_invalid_error
from app.services.cache_service import cache_service
from app.services.calibration_service import calibration_service
from app.services.catalog_service import get_topic_context
from app.services.continuity_service import build_next_action, update_answer_streak
from app.services.feedback_engine import feedback_engine
from app.services.flashcard_engine import flashcard_engine
from app.services.llm_service import llm_service
from app.services.notes_engine import notes_engine
from app.services.performance_service import get_performance_snapshot, refresh_user_performance
from app.services.revision_engine import revision_engine
from app.services.scoring_engine import scoring_engine
from app.services.similarity_engine import similarity_engine
from app.services.improvement_service import improvement_service
from app.utils.common import new_id, sha256_json, sha256_text, stable_json_dumps, utc_now_iso


class EvaluationEngine:
    """UPSC topic-aware evaluation flow with deterministic replay support."""

    @staticmethod
    def _concept_universe_from_model_answer(model_answer: dict) -> list[dict[str, str]]:
        concept_universe: list[dict[str, str]] = []
        seen: set[str] = set()
        for concept in model_answer.get("core_concepts", []) or []:
            normalized = str(concept or "").strip()
            if normalized and normalized.lower() not in seen:
                seen.add(normalized.lower())
                concept_universe.append({"concept": normalized, "importance": "core"})
        for concept in model_answer.get("must_have_points", []) or []:
            normalized = str(concept or "").strip()
            if normalized and normalized.lower() not in seen:
                seen.add(normalized.lower())
                concept_universe.append({"concept": normalized, "importance": "core"})
        for concept in (model_answer.get("good_to_have_points", []) or []) + (model_answer.get("extra_edge_points", []) or []):
            normalized = str(concept or "").strip()
            if normalized and normalized.lower() not in seen:
                seen.add(normalized.lower())
                concept_universe.append({"concept": normalized, "importance": "secondary"})
        return concept_universe

    @staticmethod
    def _biggest_mistake(*, penalty_reasons: list[str], mistakes: list[str], top_improvements: list[str]) -> str:
        if penalty_reasons:
            return penalty_reasons[0]
        if mistakes:
            return mistakes[0]
        if top_improvements:
            return top_improvements[0]
        return "Not addressed: core demand."

    def _smart_next_action(self, *, topic_id: str, question: str, weakest_dimension: str) -> str:
        # pressure loop prioritizes retrying the same demand framing
        if weakest_dimension in {"structure", "relevance"}:
            return "Retry same question."
        # content weakness: try a different prompt from same topic if available
        other = db.fetch_one(
            """
            SELECT prompt
            FROM questions
            WHERE topic_id = ? AND is_deleted = 0 AND type = 'mains' AND prompt != ?
            ORDER BY id ASC
            LIMIT 1
            """,
            [topic_id, question],
        )
        return "Similar question from same topic." if other else "Retry same question."

    def _get_model_answer(self, *, topic: dict, question: str) -> tuple[dict, str]:
        question_hash = sha256_text(question.lower().strip())
        cached = cache_service.get_model_answer(topic["id"], question_hash)
        if cached:
            cache_service.set_concept_universe(question_hash, self._concept_universe_from_model_answer(cached))
            return cached, "cache"

        row = db.fetch_one("SELECT * FROM model_answers WHERE topic_id = ? AND question_hash = ?", [topic["id"], question_hash])
        if row:
            payload = json.loads(row["content_json"])
            if not payload.get("core_concepts"):
                payload["core_concepts"] = llm_service.extract_core_concepts(
                    answer_text="\n".join(payload.get("full_answer", [])),
                    topic=topic,
                )["concepts"]
                db.execute(
                    "UPDATE model_answers SET content_json = ?, content_hash = ?, updated_at = ? WHERE id = ?",
                    [stable_json_dumps(payload), sha256_json(payload), utc_now_iso(), row["id"]],
                )
            cache_service.set_model_answer(topic["id"], question_hash, payload)
            cache_service.set_concept_universe(question_hash, self._concept_universe_from_model_answer(payload))
            return payload, "database"

        payload = llm_service.generate_model_answer(question=question, topic=topic)
        now = utc_now_iso()
        db.execute(
            """
            INSERT OR REPLACE INTO model_answers
            (id, topic_id, question_hash, question_text, content_json, content_hash, ai_model, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                new_id("model"),
                topic["id"],
                question_hash,
                question,
                stable_json_dumps(payload),
                sha256_json(payload),
                "demo" if not llm_service.enabled else "gemini",
                now,
                now,
            ],
        )
        cache_service.set_model_answer(topic["id"], question_hash, payload)
        cache_service.set_concept_universe(question_hash, self._concept_universe_from_model_answer(payload))
        return payload, "ai"

    @staticmethod
    def _compute_percentile(*, topic_scores: list[float], score: int) -> float:
        population = topic_scores + [score]
        if not topic_scores:
            return round((score / 9) * 100, 2)
        average = sum(population) / max(1, len(population))
        normalized_population = [item / average for item in population]
        current = score / average
        below_or_equal = sum(1 for item in normalized_population if item <= current)
        return round((below_or_equal / len(normalized_population)) * 100, 2)

    def evaluate(self, *, user_id: str, payload: dict) -> dict:
        exam, subject, topic = get_topic_context(payload["topic_id"])
        question = payload["question"].strip()
        normalized = llm_service.clean_input(
            answer_text=payload.get("student_answer"),
            ocr_text=payload.get("ocr_text"),
            handwritten_image_base64=payload.get("handwritten_image_base64"),
            handwritten_image_mime_type=payload.get("handwritten_image_mime_type"),
        )
        if not normalized["cleaned_answer"] or len(normalized["cleaned_answer"].strip()) < 20:
            raise input_invalid_error(
                reason="empty_or_unreadable",
                message="We could not derive a readable answer from the submitted text or image.",
            )
        question_id = sha256_text(question.lower().strip())
        answer_id = sha256_text(f"{question}|{normalized['cleaned_answer']}")
        evaluation_cache_key = sha256_text(
            stable_json_dumps(
                {
                    "user_id": user_id,
                    "topic_id": topic["id"],
                    "question_id": question_id,
                    "answer_id": answer_id,
                    "max_marks": payload["max_marks"],
                    "calibration_enabled": bool(payload.get("calibration_enabled", True)),
                    "examiner_mode": str(payload.get("examiner_mode") or "balanced"),
                    "calibration_seed": payload.get("calibration_seed"),
                    "safe_mode": payload.get("safe_mode"),
                    "gs_paper": payload.get("gs_paper"),
                }
            )
        )
        cached_result = cache_service.get_evaluation_result(evaluation_cache_key)
        if cached_result:
            return cached_result

        model_answer, _ = self._get_model_answer(topic=topic, question=question)
        concept_universe = cache_service.get_concept_universe(question_id) or self._concept_universe_from_model_answer(model_answer)
        cache_service.set_concept_universe(question_id, concept_universe)
        evaluation_signals = llm_service.analyze_answer_signals(
            question=question,
            cleaned_answer=normalized["cleaned_answer"],
            concept_universe=concept_universe,
        )
        features = scoring_engine.extract_features(
            cleaned_answer=normalized["cleaned_answer"],
            sentence_list=normalized["sentence_list"],
            topic=topic,
        )
        similarity = similarity_engine.compare(
            student_answer=normalized["cleaned_answer"],
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
            max_marks=payload["max_marks"],
        )
        normalized_scoring = scoring_engine.score_from_signal_strategy(
            signals=evaluation_signals,
            max_marks=payload["max_marks"],
            calibration_enabled=bool(payload.get("calibration_enabled", True)),
            calibration_mode=str(payload.get("examiner_mode") or "balanced"),
            calibration_seed=payload.get("calibration_seed"),
            question_id=question_id,
            answer_id=answer_id,
            safe_mode=payload.get("safe_mode"),
            gs_paper=payload.get("gs_paper"),
        )
        feedback = feedback_engine.generate_feedback(
            {
                **evaluation_signals,
                "directive_score": normalized_scoring.get("directive_score", 0.0),
                "value_score": normalized_scoring.get("value_score", 0.0),
            }
        )
        guidance = llm_service.generate_evaluation_guidance(
            question=question,
            cleaned_answer=normalized["cleaned_answer"],
            topic=topic,
            model_answer=model_answer,
            analysis=analysis,
            similarity=similarity,
            scoring=scoring,
            features=features,
        )
        historical = db.fetch_all("SELECT score FROM evaluation_history WHERE topic_id = ?", [topic["id"]])
        percentile = self._compute_percentile(
            topic_scores=[float(row["score"]) for row in historical],
            score=scoring["final_score"],
        )
        performance_band = scoring_engine.performance_band(percentile)
        score_band = scoring_engine.score_band(scaled_score=scoring["scaled_score"], max_marks=payload["max_marks"])
        verdict = scoring_engine.verdict(scoring["final_score"], features["maturity"]["level"])
        mistakes = list(dict.fromkeys(analysis["missing_points"] + analysis["incorrect_points"]))
        penalty_reasons = scoring_engine.penalty_reasons(
            analysis=analysis,
            similarity=similarity,
            features=features,
            scoring=scoring,
        )
        answer_gap_summary = scoring_engine.answer_gap_summary(
            analysis=analysis,
            similarity=similarity,
            features=features,
            scoring=scoring,
        )

        answer_id = new_id("ans")
        now = utc_now_iso()
        has_image = bool(payload.get("handwritten_image_base64"))
        has_text = bool((payload.get("student_answer") or "").strip() or (payload.get("ocr_text") or "").strip())
        input_mode = "hybrid" if has_image and has_text else "image" if has_image else "typed"
        raw_answer_text = (
            normalized.get("source_text", {}).get("merged_text")
            or payload.get("student_answer")
            or payload.get("ocr_text")
            or ""
        )
        db.execute(
            """
            INSERT INTO answers
            (id, user_id, topic_id, question_text, raw_answer_text, cleaned_answer_text, sentence_list_json, input_mode, ocr_text, max_marks, answer_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                answer_id,
                user_id,
                topic["id"],
                question,
                raw_answer_text,
                normalized["cleaned_answer"],
                stable_json_dumps(normalized["sentence_list"]),
                input_mode,
                payload.get("ocr_text"),
                payload["max_marks"],
                sha256_text(f"{question}|{normalized['cleaned_answer']}"),
                now,
            ],
        )
        model_row = db.fetch_one("SELECT id FROM model_answers WHERE topic_id = ? AND question_hash = ?", [topic["id"], sha256_text(question.lower().strip())])
        evaluation_history_id = new_id("evalh")
        stored_analysis = {
            "analysis": analysis,
            "evaluation_signals": evaluation_signals,
            "normalized_scoring": normalized_scoring,
            "feedback": feedback,
        }
        db.execute(
            """
            INSERT INTO evaluation_history
            (id, answer_id, user_id, topic_id, question_hash, model_answer_id, score, percentile, performance_band,
             analysis_json, similarity_json, feature_json, scoring_json, mistakes_json, ideal_answer_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                evaluation_history_id,
                answer_id,
                user_id,
                topic["id"],
                sha256_text(question.lower().strip()),
                model_row["id"] if model_row else None,
                scoring["final_score"],
                percentile,
                performance_band,
                stable_json_dumps(stored_analysis),
                stable_json_dumps(similarity),
                stable_json_dumps(features),
                stable_json_dumps(scoring),
                stable_json_dumps(mistakes),
                stable_json_dumps(model_answer),
                now,
                now,
            ],
        )
        calibration_service.record_sample(
            evaluation_history_id=evaluation_history_id,
            user_id=user_id,
            topic_id=topic["id"],
            features={
                "analysis": analysis,
                "similarity": similarity,
                "features": features,
                "scoring": scoring,
            },
            predicted_score=scoring["final_score"],
        )
        streak = update_answer_streak(user_id, now)
        refresh_user_performance(user_id)
        progress_snapshot = get_performance_snapshot(user_id)
        topic_progress = next(
            (row for row in progress_snapshot["topic_breakdown"] if row["topic_id"] == topic["id"]),
            None,
        )
        progress_delta = float(topic_progress["trend_delta"]) if topic_progress else 0.0
        next_action = build_next_action(
            subject=subject,
            topic=topic,
            analysis=analysis,
            similarity=similarity,
            progress_snapshot=progress_snapshot,
        )

        biggest_mistake = self._biggest_mistake(
            penalty_reasons=penalty_reasons,
            mistakes=mistakes,
            top_improvements=guidance["top_improvements"],
        )
        loop = improvement_service.record_evaluation(
            user_id=user_id,
            topic_id=topic["id"],
            structure_score=float(scoring.get("structure_score", 0.0)),
            relevance_score=float(scoring.get("relevance_score", 0.0)),
            content_score=float(similarity.get("coverage_score", 0.0)),
            biggest_mistake=biggest_mistake,
        )
        smart_next = self._smart_next_action(topic_id=topic["id"], question=question, weakest_dimension=loop["weakest_dimension"])
        if loop.get("pressure_message"):
            smart_next = "Retry same question."

        subtopic_id = payload.get("subtopic_id")
        if isinstance(subtopic_id, str) and subtopic_id:
            improvement_service.record_subtopic_attempt(
                user_id=user_id,
                subtopic_id=subtopic_id,
                topic_id=topic["id"],
                weakest_dimension=str(loop.get("weakest_dimension") or ""),
                repeated_mistake=str(loop.get("repeated_mistake") or ""),
                repeated_mistake_count=int(loop.get("repeated_mistake_count") or 0),
                consecutive_mistake_count=int(loop.get("consecutive_mistake_count") or 0),
            )
            # progress update: mark attempted and flag weakness if pressure loop hit
            db.execute(
                """
                INSERT INTO user_subtopic_progress
                (user_id, subtopic_id, topic_id, status, weakness_flag, last_attempted_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, subtopic_id) DO UPDATE SET
                  status = excluded.status,
                  weakness_flag = excluded.weakness_flag,
                  last_attempted_at = excluded.last_attempted_at,
                  updated_at = excluded.updated_at
                """,
                [
                    user_id,
                    subtopic_id,
                    topic["id"],
                    "done" if score_band in {"Good", "Topper-level"} else "in_progress",
                    1 if loop.get("pressure_message") else 0,
                    now,
                    now,
                ],
            )

        notes = notes_engine.get_or_generate_notes(topic["id"])
        flashcards, revision = flashcard_engine.get_or_generate_flashcards(topic_id=topic["id"], user_id=user_id)
        if not payload.get("include_learning_assets", True):
            flashcards = []
            revision = revision_engine.empty_summary()

        result = {
            "evaluation": {
                "score": scoring["final_score"],
                "scaled_score": scoring["scaled_score"],
                "percentile": percentile,
                "performance_band": performance_band,
                "score_band": score_band,
                "verdict": verdict,
                "mistakes": mistakes,
                "ideal_answer": model_answer,
                "confidence": scoring["confidence"],
                "normalized_scoring": normalized_scoring,
                "maturity": features["maturity"]["level"],
                "bluff_ratio": features["bluff_ratio"],
                "coverage_score": similarity["coverage_score"],
                "similarity_score": similarity["similarity_score"],
                "relevance_score": scoring["relevance_score"],
                "structure_score": scoring["structure_score"],
                "efficiency_score": scoring["efficiency_score"],
                "impression_score": scoring["impression_score"],
                "examiner_variance": scoring["examiner_variance"],
                "alternative_valid": analysis["alternative_valid"],
                "applied_caps": scoring["applied_caps"],
                "applied_penalties": scoring["applied_penalties"],
                "penalty_reasons": penalty_reasons,
                "missing_concepts": similarity["missing_concepts"],
                "answer_gap_summary": answer_gap_summary,
                "top_improvements": guidance["top_improvements"],
                "strengths": guidance["strengths"],
                "ideal_answer_directions": guidance["ideal_answer_directions"],
                "progress_delta": progress_delta,
                "next_action": smart_next,
                "streak": streak,
                "weakest_dimension": loop.get("weakest_dimension"),
                "consistent_weakness": loop.get("consistent_weakness"),
                "repeated_mistake": loop.get("repeated_mistake"),
                "repeated_mistake_count": loop.get("repeated_mistake_count"),
                "pressure_message": loop.get("pressure_message"),
                "normalized_scoring": normalized_scoring,
                "score_breakdown": normalized_scoring.get("score_breakdown", {}),
                "feedback": feedback,
                "scoring_version": normalized_scoring.get("scoring_version"),
            },
            "analysis": analysis,
            "notes": notes,
            "flashcards": flashcards,
            "revision": revision,
            "normalized_answer": normalized,
            "similarity": similarity,
            "features": features,
            "scoring": scoring,
            "normalized_scoring": normalized_scoring,
            "feedback": feedback,
        }
        cache_service.set_evaluation_result(evaluation_cache_key, result)
        return result


evaluation_engine = EvaluationEngine()
