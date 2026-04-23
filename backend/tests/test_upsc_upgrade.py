from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.database import db
from app.errors import ApiError
from app.services.calibration_service import calibration_service
from app.services.catalog_service import get_catalog_tree, get_topic_context, seed_catalog
from app.services.continuity_service import get_daily_question, get_answer_streak
from app.services.evaluation_engine import evaluation_engine
from app.services.notes_engine import notes_engine
from app.services.performance_service import _trend_delta
from app.services.scoring_engine import scoring_engine
from app.services.similarity_engine import similarity_engine
from app.services.study_service import get_dashboard, get_topic_page
from app.services.subtopic_notes_service import subtopic_notes_service
from app.utils.common import new_id, utc_now_iso


TOPIC_ID = "topic_upsc_polity_fundamental_rights"
UPSC_EXAM_ID = "exam_upsc"


class UPSCUpgradeTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        db.init_db()
        calibration_service.bootstrap()
        seed_catalog()

    def _ensure_user(self) -> str:
        user_id = new_id("user")
        now = utc_now_iso()
        db.execute(
            """
            INSERT OR REPLACE INTO users (id, name, email, password_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [user_id, "Test User", f"{user_id}@example.com", "not-used", now, now],
        )
        return user_id

    def test_similarity_engine_semantic_coverage(self) -> None:
        _, _, topic = get_topic_context(TOPIC_ID)
        model_answer = {
            "full_answer": [
                "Fundamental Rights limit arbitrary state power.",
                "Articles 14, 19 and 21 form the liberty triangle.",
                "Article 32 enables constitutional remedies.",
            ],
            "core_concepts": [
                "Liberty and equality are protected against arbitrary state action",
                "Articles 14, 19 and 21 form the core liberty triangle",
                "Article 32 and writ remedies make rights enforceable",
            ],
        }
        content_eval = {
            "must_have_points": topic["knowledge"]["must_have_points"],
            "good_to_have_points": topic["knowledge"]["good_to_have_points"],
            "extra_edge_points": topic["knowledge"]["extra_edge_points"],
        }
        student_answer = (
            "Fundamental Rights prevent arbitrary state action. The liberty triangle of Articles 14, 19 and 21 "
            "protects equality, freedoms and dignity, while Article 32 lets citizens seek writ remedies."
        )
        result = similarity_engine.compare(student_answer=student_answer, model_answer=model_answer, analysis=content_eval)
        self.assertGreaterEqual(result["coverage_score"], 0.66)
        self.assertGreaterEqual(result["similarity_score"], 0.5)
        self.assertTrue(result["must_have_points_present"])

    def test_scoring_engine_applies_examiner_caps(self) -> None:
        features = scoring_engine.extract_features(
            cleaned_answer="This is important for development and helps society in many ways.",
            sentence_list=["This is important for development and helps society in many ways."],
            topic=get_topic_context(TOPIC_ID)[2],
        )
        analysis = {
            "relevance": "PARTIAL",
            "domain": "CORRECT",
            "must_have_points": [],
            "good_to_have_points": [],
            "extra_edge_points": [],
            "missing_points": ["Article 32"],
            "incorrect_points": [],
            "depth": "SURFACE",
            "thinking": "DESCRIPTIVE",
            "directive": "PARTIAL",
            "structure": "WEAK",
            "vagueness": "HIGH",
            "alternative_valid": False,
        }
        similarity = {
            "similarity_score": 0.28,
            "coverage_score": 0.1,
            "must_have_points_present": [],
            "good_to_have_points_present": [],
            "extra_edge_points_present": [],
            "covered_concepts": [],
            "missing_concepts": ["Article 32"],
            "key_concept_hits": [],
        }
        scoring = scoring_engine.score(analysis=analysis, similarity=similarity, features=features, max_marks=10)
        self.assertEqual(scoring["max_score_cap"], 4)
        self.assertIn("no_must_have_cap_4", scoring["applied_caps"])
        self.assertIn("high_vagueness_penalty", scoring["applied_penalties"])

    def test_scoring_engine_adds_impression_and_overwriting_penalty(self) -> None:
        weak_features = scoring_engine.extract_features(
            cleaned_answer=(
                "This is very important for development and helps society in many ways. " * 60
            ).strip(),
            sentence_list=[
                ("This is very important for development and helps society in many ways. " * 10).strip(),
            ]
            * 6,
            topic=get_topic_context(TOPIC_ID)[2],
        )
        strong_features = scoring_engine.extract_features(
            cleaned_answer=(
                "Fundamental Rights protect liberty against arbitrary state action. "
                "Articles 14, 19 and 21 create a structured liberty triangle. "
                "Article 32 keeps rights enforceable through constitutional remedies. "
                "Therefore, rights feel credible because remedies and structure move together."
            ),
            sentence_list=[
                "Fundamental Rights protect liberty against arbitrary state action.",
                "Articles 14, 19 and 21 create a structured liberty triangle.",
                "Article 32 keeps rights enforceable through constitutional remedies.",
                "Therefore, rights feel credible because remedies and structure move together.",
            ],
            topic=get_topic_context(TOPIC_ID)[2],
        )
        weak_analysis = {
            "relevance": "PARTIAL",
            "domain": "CORRECT",
            "must_have_points": [],
            "good_to_have_points": [],
            "extra_edge_points": [],
            "missing_points": ["Article 32"],
            "incorrect_points": [],
            "depth": "SURFACE",
            "thinking": "DESCRIPTIVE",
            "directive": "PARTIAL",
            "structure": "WEAK",
            "vagueness": "HIGH",
            "alternative_valid": False,
        }
        weak_similarity = {
            "similarity_score": 0.22,
            "coverage_score": 0.18,
            "must_have_points_present": [],
            "good_to_have_points_present": [],
            "extra_edge_points_present": [],
            "covered_concepts": [],
            "missing_concepts": ["Article 32"],
            "key_concept_hits": [],
        }
        strong_analysis = {
            "relevance": "FULL",
            "domain": "CORRECT",
            "must_have_points": get_topic_context(TOPIC_ID)[2]["knowledge"]["must_have_points"],
            "good_to_have_points": get_topic_context(TOPIC_ID)[2]["knowledge"]["good_to_have_points"],
            "extra_edge_points": [],
            "missing_points": [],
            "incorrect_points": [],
            "depth": "MODERATE",
            "thinking": "ANALYTICAL",
            "directive": "FULL",
            "structure": "STRONG",
            "vagueness": "LOW",
            "alternative_valid": False,
        }
        strong_similarity = {
            "similarity_score": 0.74,
            "coverage_score": 0.72,
            "must_have_points_present": get_topic_context(TOPIC_ID)[2]["knowledge"]["must_have_points"][:2],
            "good_to_have_points_present": get_topic_context(TOPIC_ID)[2]["knowledge"]["good_to_have_points"][:1],
            "extra_edge_points_present": [],
            "covered_concepts": [],
            "missing_concepts": [],
            "key_concept_hits": [],
        }

        weak_scoring = scoring_engine.score(analysis=weak_analysis, similarity=weak_similarity, features=weak_features, max_marks=10)
        strong_scoring = scoring_engine.score(
            analysis=strong_analysis,
            similarity=strong_similarity,
            features=strong_features,
            max_marks=10,
        )

        self.assertIn("overwriting_irrelevance_penalty", weak_scoring["applied_penalties"])
        self.assertGreater(strong_scoring["impression_score"], weak_scoring["impression_score"])
        self.assertGreaterEqual(strong_scoring["impression_score"], round(strong_scoring["structure_score"] * 0.75, 3))
        self.assertGreater(strong_scoring["final_score"], weak_scoring["final_score"])

    def test_signal_strategy_scoring_applies_caps(self) -> None:
        strategy = scoring_engine.score_from_signal_strategy(
            signals={
                "core_coverage_ratio": 0.3,
                "core_depth_ratio": 0.1,
                "directive_coverage_ratio": 0.2,
                "clarity_score": 3,
                "value_additions": {"data_or_report": 1, "example": 1, "generic": 1},
                "vague_ratio": 0.7,
                "factual_error_present": False,
                "contradiction_present": False,
                "penalty_flags": [
                    {"type": "missing_conclusion", "severity": "medium"},
                    {"flag": "poor_structure", "severity": "high"},
                    {"flag": "weak_core_coverage", "severity": "high"},
                    {"flag": "excessive_vagueness", "severity": "high"},
                ],
                "structure": {"introduction": "weak", "body": "unstructured", "conclusion": "missing"},
                "confidence": "low",
                "extra_valid_concepts": ["strong outside-universe concept"],
            },
            max_marks=10,
        )
        self.assertEqual(strategy["confidence"], "low")
        self.assertIn("weak_core_coverage_cap_0.4", strategy["applied_caps"])
        self.assertIn("unstructured_body_cap_0.6", strategy["applied_caps"])
        self.assertIn("low_directive_coverage_cap_0.5", strategy["applied_caps"])
        self.assertLessEqual(strategy["final_normalized_score"], 0.4)
        self.assertLessEqual(strategy["estimated_marks"], 4.0)
        self.assertGreater(strategy["extra_bonus"], 0.0)
        self.assertLessEqual(strategy["raw_score"], 0.25)
        self.assertTrue(any(item.startswith("missing_conclusion:") for item in strategy["applied_penalties"]))
        self.assertIn("confidence_adjustment_0.90", strategy["applied_penalties"])
        self.assertTrue(isinstance(strategy["marks_range"], list) and len(strategy["marks_range"]) == 2)

    def test_signal_strategy_calibration_is_deterministic_with_seed(self) -> None:
        signals = {
            "core_coverage_ratio": 0.72,
            "core_depth_ratio": 0.61,
            "directive_coverage_ratio": 0.75,
            "clarity_score": 4,
            "value_additions": {"data_or_report": 1, "example": 1, "generic": 0},
            "vague_ratio": 0.22,
            "factual_error_present": False,
            "contradiction_present": False,
            "penalty_flags": [],
            "structure": {"introduction": "present", "body": "structured", "conclusion": "present"},
            "dimension_balance": "good",
            "confidence": "medium",
            "fundamental_weakness": False,
            "extra_valid_concepts": ["useful extra concept"],
        }
        calibrated_one = scoring_engine.score_from_signal_strategy(
            signals=signals,
            max_marks=10,
            calibration_enabled=True,
            calibration_mode="lenient",
            calibration_seed=1234,
        )
        calibrated_two = scoring_engine.score_from_signal_strategy(
            signals=signals,
            max_marks=10,
            calibration_enabled=True,
            calibration_mode="lenient",
            calibration_seed=1234,
        )
        self.assertEqual(calibrated_one["final_normalized_score"], calibrated_two["final_normalized_score"])
        self.assertEqual(calibrated_one["estimated_marks"], calibrated_two["estimated_marks"])
        self.assertEqual(calibrated_one["calibration"]["variation"], calibrated_two["calibration"]["variation"])
        self.assertEqual(calibrated_one["calibration"]["applied_profile"], "lenient")
        self.assertIn("presentation_boost", calibrated_one["calibration"]["applied_adjustments"])
        self.assertIn("balance_bonus", calibrated_one["calibration"]["applied_adjustments"])
        self.assertIn("profile_adjustment", calibrated_one["calibration"]["applied_adjustments"])
        self.assertIn("variation", calibrated_one["calibration"]["applied_adjustments"])

    def test_signal_strategy_calibration_disables_variation_for_fundamental_weakness(self) -> None:
        calibrated = scoring_engine.score_from_signal_strategy(
            signals={
                "core_coverage_ratio": 0.2,
                "core_depth_ratio": 0.1,
                "directive_coverage_ratio": 0.4,
                "clarity_score": 2,
                "value_additions": {"data_or_report": 0, "example": 0, "generic": 0},
                "vague_ratio": 0.6,
                "factual_error_present": False,
                "contradiction_present": False,
                "penalty_flags": [],
                "structure": {"introduction": "weak", "body": "semi", "conclusion": "missing"},
                "dimension_balance": "poor",
                "confidence": "low",
                "fundamental_weakness": True,
                "extra_valid_concepts": [],
            },
            max_marks=10,
            calibration_enabled=True,
            calibration_mode="strict",
            calibration_seed=7,
        )
        self.assertEqual(calibrated["calibration"]["variation"], 0.0)
        self.assertEqual(calibrated["calibration"]["applied_profile"], "strict")

    def test_calibration_weights_can_be_updated(self) -> None:
        original = calibration_service.get_weights()
        try:
            updated = calibration_service.update_weights({"must_weight": 2.3, "coverage_weight": 2.4, "impression_weight": 0.55})
            self.assertEqual(updated["must_weight"], 2.3)
            self.assertEqual(updated["coverage_weight"], 2.4)
            self.assertEqual(updated["impression_weight"], 0.55)
            current = calibration_service.get_weights()
            self.assertEqual(current["must_weight"], 2.3)
            self.assertEqual(current["coverage_weight"], 2.4)
            self.assertEqual(current["impression_weight"], 0.55)
        finally:
            calibration_service.update_weights(original)

    def test_notes_engine_enforces_validation(self) -> None:
        notes = notes_engine.get_or_generate_notes(TOPIC_ID)
        validation_errors = notes_engine._validate_notes(get_topic_context(TOPIC_ID)[2], notes_engine._notes_for_validation(notes))
        self.assertEqual(validation_errors, [])

    def test_progress_delta_uses_smoothed_moving_average(self) -> None:
        delta = _trend_delta(
            [
                {"normalized_score": 0.78, "submitted_at": "2026-04-16T10:00:00Z"},
                {"normalized_score": 0.52, "submitted_at": "2026-04-15T10:00:00Z"},
                {"normalized_score": 0.74, "submitted_at": "2026-04-14T10:00:00Z"},
                {"normalized_score": 0.5, "submitted_at": "2026-04-13T10:00:00Z"},
                {"normalized_score": 0.7, "submitted_at": "2026-04-12T10:00:00Z"},
                {"normalized_score": 0.48, "submitted_at": "2026-04-11T10:00:00Z"},
            ]
        )
        self.assertAlmostEqual(delta, 10.2, places=2)

    def test_evaluation_engine_returns_upgraded_fields(self) -> None:
        user_id = self._ensure_user()
        response = evaluation_engine.evaluate(
            user_id=user_id,
            payload={
                "topic_id": TOPIC_ID,
                "question": "Discuss the significance of Fundamental Rights in Indian democracy.",
                "student_answer": (
                    "Fundamental Rights limit arbitrary state action and preserve democratic liberty. "
                    "Articles 14, 19 and 21 together protect equality, freedom and dignity, while Article 32 "
                    "allows remedies through writs. Judicial interpretation in Maneka Gandhi expanded fairness "
                    "and due process, which keeps rights relevant in contemporary governance."
                ),
                "max_marks": 10,
                "include_learning_assets": True,
            },
        )
        self.assertIn("confidence", response["evaluation"])
        self.assertIn("maturity", response["evaluation"])
        self.assertIn("missing_concepts", response["evaluation"])
        self.assertIn("applied_caps", response["evaluation"])
        self.assertIn("applied_penalties", response["evaluation"])
        self.assertIn("penalty_reasons", response["evaluation"])
        self.assertIn("relevance_score", response["evaluation"])
        self.assertIn("structure_score", response["evaluation"])
        self.assertIn("efficiency_score", response["evaluation"])
        self.assertIn("impression_score", response["evaluation"])
        self.assertIn("examiner_variance", response["evaluation"])
        self.assertIn("score_band", response["evaluation"])
        self.assertIn("answer_gap_summary", response["evaluation"])
        self.assertEqual(len(response["evaluation"]["top_improvements"]), 3)
        self.assertGreaterEqual(len(response["evaluation"]["strengths"]), 2)
        self.assertEqual(len(response["evaluation"]["ideal_answer_directions"]), 3)
        self.assertIn("progress_delta", response["evaluation"])
        self.assertIn("next_action", response["evaluation"])
        self.assertIn("streak", response["evaluation"])
        self.assertIn(response["evaluation"]["score_band"], {"Poor", "Average", "Good", "Topper-level"})
        self.assertIsInstance(response["evaluation"]["penalty_reasons"], list)
        self.assertTrue(response["evaluation"]["answer_gap_summary"].startswith("Your answer"))
        self.assertIn("weights", response["scoring"])
        self.assertIn("impression_weight", response["scoring"]["weights"])
        self.assertIn("structure", response["analysis"])
        self.assertIn("depth_signals", response["features"])
        self.assertIn("alternative_valid", response["analysis"])

    def test_catalog_tree_exposes_practice_counts(self) -> None:
        exams = get_catalog_tree()
        topic = next(
            row
            for exam in exams
            for subject in exam["subjects"]
            for row in subject["topics"]
            if row["id"] == TOPIC_ID
        )
        self.assertEqual(topic["practice_counts"]["mcq"], 5)
        self.assertEqual(topic["practice_counts"]["mains"], 2)

    def test_unreadable_input_returns_structured_error(self) -> None:
        user_id = self._ensure_user()
        with self.assertRaises(ApiError) as caught:
            evaluation_engine.evaluate(
                user_id=user_id,
                payload={
                    "topic_id": TOPIC_ID,
                    "question": "Discuss the significance of Fundamental Rights in Indian democracy.",
                    "student_answer": "Too short",
                    "max_marks": 10,
                    "include_learning_assets": False,
                },
            )

        self.assertEqual(caught.exception.code, "INVALID_ANSWER")
        self.assertEqual(caught.exception.details["error_type"], "INPUT_INVALID")
        self.assertEqual(caught.exception.details["reason"], "empty_or_unreadable")
        self.assertGreaterEqual(len(caught.exception.details["suggestions"]), 3)

    def test_daily_question_and_streak_follow_recent_weak_topic(self) -> None:
        user_id = self._ensure_user()
        evaluation_engine.evaluate(
            user_id=user_id,
            payload={
                "topic_id": TOPIC_ID,
                "question": "Discuss the significance of Fundamental Rights in Indian democracy.",
                "student_answer": "Rights are important for development and help society in many ways.",
                "max_marks": 10,
                "include_learning_assets": False,
            },
        )

        daily_question = get_daily_question(user_id)
        self.assertEqual(daily_question["topic_id"], TOPIC_ID)
        self.assertEqual(get_answer_streak(user_id), 1)
        self.assertIn("question", daily_question)
        self.assertIn("streak", daily_question)
        self.assertIn("reason", daily_question)

    def test_study_contract_exposes_action_and_external_notes(self) -> None:
        user_id = self._ensure_user()
        dashboard = get_dashboard(user_id=user_id, exam_id=UPSC_EXAM_ID)
        self.assertIn("recommended_action", dashboard["summary"])
        self.assertIn("today_plan", dashboard["summary"])
        self.assertIsNotNone(dashboard["summary"]["today_plan"])

        topic_data = get_topic_page(user_id=user_id, topic_id=TOPIC_ID)
        self.assertIn("next_best_action", topic_data)
        self.assertGreaterEqual(len(topic_data["trusted_notes"]), 1)
        self.assertGreater(topic_data["chapter_progress"]["total_subtopics"], 0)

        first_subtopic_id = topic_data["topic"]["subtopics"][0]["id"]
        notes = subtopic_notes_service.ensure_notes(subtopic_id=first_subtopic_id)
        self.assertGreaterEqual(len(notes["external_notes"]), 1)
        self.assertIn("directive", notes["writing_brief"])
        self.assertGreaterEqual(len(notes["writing_brief"]["keywords"]), 1)


if __name__ == "__main__":
    unittest.main()
