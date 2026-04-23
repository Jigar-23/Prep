from __future__ import annotations

from app.utils.common import clamp


class FeedbackEngine:
    """Rule-based feedback generator for deterministic UPSC answer guidance."""

    @staticmethod
    def _weighted_value_score(value_additions: dict | None) -> float:
        payload = value_additions if isinstance(value_additions, dict) else {}
        return clamp(
            (
                (2.0 * float(payload.get("data_or_report", 0) or 0.0))
                + (1.0 * float(payload.get("example", 0) or 0.0))
                + (0.5 * float(payload.get("generic", 0) or 0.0))
            )
            / 5.0,
            0.0,
            1.0,
        )

    def generate_feedback(self, evaluation_json: dict | None) -> dict:
        """Create deterministic strengths, weaknesses, and improvements from evaluation signals."""
        payload = evaluation_json if isinstance(evaluation_json, dict) else {}
        structure = payload.get("structure", {}) if isinstance(payload.get("structure"), dict) else {}
        core_coverage_ratio = float(payload.get("core_coverage_ratio", 0.0) or 0.0)
        directive_score = float(
            payload.get("directive_score", payload.get("directive_coverage_ratio", 0.0)) or 0.0
        )
        vague_ratio = float(payload.get("vague_ratio", 0.0) or 0.0)
        value_score = float(payload.get("value_score", self._weighted_value_score(payload.get("value_additions"))) or 0.0)
        clarity_score = int(payload.get("clarity_score", 0) or 0)
        body_structure = str(structure.get("body") or "unstructured").lower()

        strengths: list[str] = []
        weaknesses: list[str] = []
        improvements: list[str] = []

        if core_coverage_ratio >= 0.6:
            strengths.append("Covers a meaningful share of the core concepts.")
        else:
            weaknesses.append("Core concept coverage is thin for the question demand.")
            improvements.append("Add more core concepts from the concept universe.")

        if directive_score >= 0.6:
            strengths.append("Responds to the directive with reasonable focus.")
        else:
            weaknesses.append("Directive handling is partial or indirect.")
            improvements.append("Answer the directive more directly.")

        if body_structure == "structured":
            strengths.append("The body is organized into clear thematic blocks.")
        else:
            weaknesses.append("The answer structure is not strong enough.")
            improvements.append("Improve intro, body grouping, and conclusion flow.")

        if vague_ratio > 0.4:
            weaknesses.append("Too many statements stay generic instead of specific.")
            improvements.append("Reduce vague statements and add concrete linkage.")

        if value_score >= 0.4:
            strengths.append("Uses supportive examples or value additions.")
        else:
            improvements.append("Include examples, data, or reports to support the argument.")

        if clarity_score >= 4:
            strengths.append("Expression is clear and easy to follow.")
        elif clarity_score <= 2:
            weaknesses.append("Expression is reducing the sharpness of the answer.")

        return {
            "strengths": strengths[:3],
            "weaknesses": weaknesses[:3],
            "improvements": improvements[:3],
        }


feedback_engine = FeedbackEngine()
