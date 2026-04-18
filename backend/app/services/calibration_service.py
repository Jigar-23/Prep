from __future__ import annotations

import json
from math import sqrt

from app.config import settings
from app.database import db
from app.errors import ApiError
from app.utils.common import new_id, stable_json_dumps, utc_now_iso


DEFAULT_PROFILE_ID = "default"


class CalibrationService:
    def _default_weights(self) -> dict[str, float]:
        return {
            "must_weight": settings.default_must_weight,
            "good_weight": settings.default_good_weight,
            "similarity_weight": settings.default_similarity_weight,
            "coverage_weight": settings.default_coverage_weight,
            "depth_weight": settings.default_depth_weight,
            "directive_weight": settings.default_directive_weight,
            "extra_weight": settings.default_extra_weight,
            "fact_weight": settings.default_fact_weight,
            "maturity_weight": settings.default_maturity_weight,
            "impression_weight": settings.default_impression_weight,
        }

    def bootstrap(self) -> None:
        if db.fetch_one("SELECT id FROM calibration_weights WHERE id = ?", [DEFAULT_PROFILE_ID]):
            return
        now = utc_now_iso()
        weights = self._default_weights()
        db.execute(
            """
            INSERT INTO calibration_weights
            (id, must_weight, good_weight, similarity_weight, coverage_weight, depth_weight, directive_weight,
             extra_weight, fact_weight, maturity_weight, impression_weight, impression_score_correlation,
             impression_score_mismatch, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, 0.0, ?)
            """,
            [
                DEFAULT_PROFILE_ID,
                weights["must_weight"],
                weights["good_weight"],
                weights["similarity_weight"],
                weights["coverage_weight"],
                weights["depth_weight"],
                weights["directive_weight"],
                weights["extra_weight"],
                weights["fact_weight"],
                weights["maturity_weight"],
                weights["impression_weight"],
                now,
            ],
        )

    def get_weights(self) -> dict[str, float]:
        self.bootstrap()
        row = db.fetch_one("SELECT * FROM calibration_weights WHERE id = ?", [DEFAULT_PROFILE_ID])
        if not row:
            raise ApiError(500, "CALIBRATION_UNAVAILABLE", "Calibration weights are unavailable.")
        return {
            "must_weight": float(row["must_weight"]),
            "good_weight": float(row["good_weight"]),
            "similarity_weight": float(row["similarity_weight"]),
            "coverage_weight": float(row["coverage_weight"]),
            "depth_weight": float(row["depth_weight"]),
            "directive_weight": float(row["directive_weight"]),
            "extra_weight": float(row["extra_weight"]),
            "fact_weight": float(row["fact_weight"]),
            "maturity_weight": float(row["maturity_weight"]),
            "impression_weight": float(row["impression_weight"]),
        }

    def update_weights(self, new_weights: dict[str, float]) -> dict[str, float]:
        allowed = set(self._default_weights())
        unknown = set(new_weights) - allowed
        if unknown:
            raise ApiError(400, "INVALID_CALIBRATION_WEIGHTS", "Unsupported calibration weight keys.", {"keys": sorted(unknown)})
        weights = self.get_weights() | {key: float(value) for key, value in new_weights.items()}
        if any(value <= 0 for value in weights.values()):
            raise ApiError(400, "INVALID_CALIBRATION_WEIGHTS", "Calibration weights must be positive.")
        db.execute(
            """
            UPDATE calibration_weights
            SET must_weight = ?, good_weight = ?, similarity_weight = ?, coverage_weight = ?, depth_weight = ?,
                directive_weight = ?, extra_weight = ?, fact_weight = ?, maturity_weight = ?, impression_weight = ?, updated_at = ?
            WHERE id = ?
            """,
            [
                weights["must_weight"],
                weights["good_weight"],
                weights["similarity_weight"],
                weights["coverage_weight"],
                weights["depth_weight"],
                weights["directive_weight"],
                weights["extra_weight"],
                weights["fact_weight"],
                weights["maturity_weight"],
                weights["impression_weight"],
                utc_now_iso(),
                DEFAULT_PROFILE_ID,
            ],
        )
        return weights

    def record_sample(
        self,
        *,
        evaluation_history_id: str,
        user_id: str,
        topic_id: str,
        features: dict,
        predicted_score: float,
        manual_score: float | None = None,
    ) -> None:
        weights = self.get_weights()
        payload = {
            "features": features,
            "predicted_score": predicted_score,
            "manual_score": manual_score,
        }
        now = utc_now_iso()
        db.execute(
            """
            INSERT OR REPLACE INTO calibration_samples
            (id, evaluation_history_id, user_id, topic_id, features_json, predicted_score, manual_score, weights_json, created_at, updated_at)
            VALUES (
                COALESCE((SELECT id FROM calibration_samples WHERE evaluation_history_id = ?), ?),
                ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM calibration_samples WHERE evaluation_history_id = ?), ?), ?
            )
            """,
            [
                evaluation_history_id,
                new_id("cal"),
                evaluation_history_id,
                user_id,
                topic_id,
                stable_json_dumps(payload),
                float(predicted_score),
                manual_score,
                json.dumps(weights, sort_keys=True),
                evaluation_history_id,
                now,
                now,
            ],
        )
        self._sync_impression_calibration()

    def _sync_impression_calibration(self) -> None:
        rows = db.fetch_all(
            """
            SELECT features_json, predicted_score
            FROM calibration_samples
            ORDER BY updated_at DESC
            LIMIT 24
            """
        )
        if not rows:
            return

        impression_values: list[float] = []
        normalized_scores: list[float] = []
        for row in rows:
            payload = json.loads(row["features_json"])
            scoring = payload.get("features", {}).get("scoring", {})
            impression_score = scoring.get("impression_score")
            if impression_score is None:
                continue
            impression_values.append(float(impression_score))
            normalized_scores.append(float(row["predicted_score"]) / 9.0)

        if not impression_values:
            return

        correlation = round(self._pearson(impression_values, normalized_scores), 3)
        mismatch = round(
            sum(abs(impression - predicted) for impression, predicted in zip(impression_values, normalized_scores, strict=False))
            / len(impression_values),
            3,
        )
        current_weight = self.get_weights()["impression_weight"]
        adjusted_weight = current_weight
        if len(impression_values) >= 8 and mismatch > 0.18:
            direction = -0.02 if sum(impression_values) > sum(normalized_scores) else 0.02
            adjusted_weight = max(0.35, min(0.75, round(current_weight + direction, 3)))

        db.execute(
            """
            UPDATE calibration_weights
            SET impression_weight = ?, impression_score_correlation = ?, impression_score_mismatch = ?, updated_at = ?
            WHERE id = ?
            """,
            [adjusted_weight, correlation, mismatch, utc_now_iso(), DEFAULT_PROFILE_ID],
        )

    @staticmethod
    def _pearson(left: list[float], right: list[float]) -> float:
        if len(left) != len(right) or len(left) < 2:
            return 0.0
        left_mean = sum(left) / len(left)
        right_mean = sum(right) / len(right)
        numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right, strict=False))
        left_denominator = sqrt(sum((x - left_mean) ** 2 for x in left))
        right_denominator = sqrt(sum((y - right_mean) ** 2 for y in right))
        denominator = left_denominator * right_denominator
        if denominator == 0:
            return 0.0
        return numerator / denominator


calibration_service = CalibrationService()
