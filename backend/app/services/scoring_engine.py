from __future__ import annotations

import hashlib
import logging
import re

from app.services.calibration_service import calibration_service
from app.utils.common import clamp


CAUSE_EFFECT_MARKERS = {
    "because",
    "therefore",
    "thus",
    "hence",
    "leads to",
    "results in",
    "causes",
    "due to",
    "as a result",
    "consequently",
}
DIMENSION_TERMS = {
    "economic": {"economic", "economy", "income", "growth", "inflation", "fiscal"},
    "social": {"social", "society", "equity", "justice", "welfare", "citizen"},
    "political": {"political", "democratic", "parliament", "executive", "representation"},
    "legal": {"legal", "constitutional", "article", "rights", "court", "judicial"},
    "ethical": {"ethical", "ethics", "integrity", "probity", "fairness"},
    "environmental": {"environmental", "ecology", "sustainability", "climate"},
    "administrative": {"administrative", "governance", "bureaucracy", "implementation"},
    "institutional": {"institutional", "commission", "committee", "council", "federal"},
}
EXAMPLE_PATTERNS = [
    r"\bfor example\b",
    r"\bfor instance\b",
    r"\bsuch as\b",
    r"\barticle\s+\d+\b",
    r"\bv\.\b",
    r"\bcase\b",
    r"\bjudgment\b",
    r"\bscheme\b",
    r"\bcommittee\b",
    r"\bcommission\b",
]
BLUFF_PHRASES = {
    "important for development",
    "plays a vital role",
    "plays vital role",
    "helps society",
    "good for the country",
    "very important",
    "helps the nation",
}
FACTUAL_ANCHOR_PATTERN = re.compile(
    r"\b(article|articles|part|section|court|commission|committee|scheme|act|msp|gdp|cpi|repo|frbm|gst|rights)\b|\d{2,4}",
    re.IGNORECASE,
)
BALANCE_MARKERS = {"however", "on the other hand", "while", "yet", "although", "but", "trade-off"}
INTERLINK_MARKERS = {"interplay", "linked", "connect", "read with", "along with", "combined with", "in relation to"}
REAL_WORLD_MARKERS = {"scheme", "budget", "policy", "judgment", "court", "governor", "gst", "data", "survey", "committee"}
TRANSITION_MARKERS = {"first", "second", "third", "further", "moreover", "however", "therefore", "thus", "overall", "finally"}
THINKING_ORDER = {"DESCRIPTIVE": 1, "ANALYTICAL": 2, "CRITICAL": 3}
DEPTH_ORDER = {"SURFACE": 1, "MODERATE": 2, "DEEP": 3}
VAGUENESS_ORDER = {"LOW": 1, "MODERATE": 2, "HIGH": 3}
logger = logging.getLogger(__name__)


class ScoringEngine:
    @staticmethod
    def _nearest_half(value: float) -> float:
        return round(value * 2) / 2

    @staticmethod
    def _structure_component_score(value: str, *, body: bool = False) -> float:
        lowered = str(value or "").lower()
        if body:
            return 1.0 if lowered == "structured" else 0.5 if lowered == "semi" else 0.0
        return 1.0 if lowered == "present" else 0.5 if lowered == "weak" else 0.0

    def score_from_signal_strategy(self, *, signals: dict, max_marks: int) -> dict:
        max_marks = max(1, int(max_marks or 10))
        core_coverage_ratio = float(signals.get("core_coverage_ratio", 0.0) or 0.0)
        core_depth_ratio = float(signals.get("core_depth_ratio", 0.0) or 0.0)
        directive_coverage_ratio = float(signals.get("directive_coverage_ratio", 0.0) or 0.0)
        clarity_score = int(signals.get("clarity_score", 0) or 0)
        vague_ratio = float(signals.get("vague_ratio", 0.0) or 0.0)
        value_additions = signals.get("value_additions", {}) if isinstance(signals.get("value_additions"), dict) else {}
        structure = signals.get("structure", {}) if isinstance(signals.get("structure"), dict) else {}
        confidence = str(signals.get("confidence", "medium") or "medium").lower()
        penalty_flags = signals.get("penalty_flags", []) if isinstance(signals.get("penalty_flags"), list) else []
        fundamental_weakness = bool(signals.get("fundamental_weakness", False))

        intro_score = self._structure_component_score(str(structure.get("introduction") or "missing"))
        body_score = self._structure_component_score(str(structure.get("body") or "unstructured"), body=True)
        conclusion_score = self._structure_component_score(str(structure.get("conclusion") or "missing"))

        core_score = clamp((0.7 * core_coverage_ratio) + (0.3 * core_depth_ratio), 0.0, 1.0)
        directive_score = clamp(directive_coverage_ratio, 0.0, 1.0)
        structure_score = clamp((intro_score * 0.3) + (body_score * 0.4) + (conclusion_score * 0.3), 0.0, 1.0)
        value_score = clamp(
            (
                (2.0 * float(value_additions.get("data_or_report", 0) or 0))
                + (1.0 * float(value_additions.get("example", 0) or 0))
                + (0.5 * float(value_additions.get("generic", 0) or 0))
            )
            / 5.0,
            0.0,
            1.0,
        )
        expression_score = clamp(clarity_score / 5.0, 0.0, 1.0)

        raw_score_before_penalty = clamp(
            (core_score * 0.40)
            + (directive_score * 0.20)
            + (structure_score * 0.15)
            + (value_score * 0.10)
            + (expression_score * 0.10),
            0.0,
            1.0,
        )
        logger.debug(
            "Signal scoring normalization: core_score=%.3f directive_score=%.3f structure_score=%.3f value_score=%.3f expression_score=%.3f",
            core_score,
            directive_score,
            structure_score,
            value_score,
            expression_score,
        )
        logger.debug("Signal scoring raw score before penalties: %.3f", raw_score_before_penalty)

        applied_penalties: list[str] = []
        base_penalty_map = {
            "missing_conclusion": 0.05,
            "poor_structure": 0.07,
            "excessive_vagueness": 0.05,
            "factual_error_present": 0.10,
            "contradiction_present": 0.08,
        }
        severity_penalty_map = {
            "low": 0.02,
            "medium": 0.05,
            "high": 0.10,
        }
        penalties_to_apply: dict[str, float] = {}
        for item in penalty_flags:
            if not isinstance(item, dict):
                continue
            flag = str(item.get("flag") or item.get("type") or "")
            severity = str(item.get("severity") or "").lower()
            if flag in base_penalty_map:
                penalties_to_apply[flag] = base_penalty_map[flag]
            elif severity in severity_penalty_map:
                penalties_to_apply[flag] = severity_penalty_map[severity]
            else:
                continue
        if bool(signals.get("factual_error_present", False)):
            penalties_to_apply["factual_error_present"] = base_penalty_map["factual_error_present"]
        if bool(signals.get("contradiction_present", False)):
            penalties_to_apply["contradiction_present"] = base_penalty_map["contradiction_present"]

        total_penalty = round(min(0.25, sum(penalties_to_apply.values())), 3)
        penalized_score = clamp(raw_score_before_penalty - total_penalty, 0.0, 1.0)
        for flag, deduction in penalties_to_apply.items():
            applied_penalties.append(f"{flag}:{deduction:.2f}")
        logger.debug(
            "Signal scoring penalties: penalties=%s total_penalty=%.3f penalized_score=%.3f",
            penalties_to_apply,
            total_penalty,
            penalized_score,
        )

        cap_score = 1.0
        applied_caps: list[str] = []
        if core_coverage_ratio < 0.4:
            cap_score = min(cap_score, 0.4)
            applied_caps.append("weak_core_coverage_cap_0.4")
        if str(structure.get("body") or "").lower() == "unstructured":
            cap_score = min(cap_score, 0.6)
            applied_caps.append("unstructured_body_cap_0.6")
        if directive_coverage_ratio < 0.3:
            cap_score = min(cap_score, 0.5)
            applied_caps.append("low_directive_coverage_cap_0.5")

        capped_score = min(penalized_score, cap_score)
        extra_bonus = min(0.1, len(signals.get("extra_valid_concepts", []) or []) * 0.02)
        adjusted_score = capped_score + extra_bonus
        logger.debug(
            "Signal scoring caps and bonus: cap_score=%.3f capped_score=%.3f extra_bonus=%.3f adjusted_pre_confidence=%.3f",
            cap_score,
            capped_score,
            extra_bonus,
            adjusted_score,
        )

        if confidence == "low":
            adjusted_score *= 0.90
            applied_penalties.append("confidence_adjustment_0.90")
        elif confidence == "medium":
            adjusted_score *= 0.97
            applied_penalties.append("confidence_adjustment_0.97")

        if core_coverage_ratio > 0.6 and adjusted_score < 0.4 and not fundamental_weakness:
            adjusted_score = 0.4
            applied_caps.append("core_strength_floor_0.4")

        final_normalized_score = round(clamp(adjusted_score, 0.0, 1.0), 3)
        adjusted_marks = clamp(final_normalized_score * max_marks, 0.0, float(max_marks))
        estimated_marks = self._nearest_half(adjusted_marks)
        marks_range = [
            round(estimated_marks - 0.5, 1),
            round(estimated_marks + 0.5, 1),
        ]
        logger.debug(
            "Signal scoring final: final_normalized_score=%.3f estimated_marks=%.1f marks_range=%s confidence=%s",
            final_normalized_score,
            estimated_marks,
            marks_range,
            confidence,
        )

        return {
            "core_score": round(core_score, 3),
            "directive_score": round(directive_score, 3),
            "structure_score": round(structure_score, 3),
            "value_score": round(value_score, 3),
            "expression_score": round(expression_score, 3),
            "raw_score": round(penalized_score, 3),
            "final_normalized_score": final_normalized_score,
            "estimated_marks": round(estimated_marks, 1),
            "marks_range": marks_range,
            "applied_penalties": applied_penalties,
            "applied_caps": applied_caps,
            "extra_bonus": round(extra_bonus, 3),
            "confidence": confidence,
        }

    def extract_features(self, *, cleaned_answer: str, sentence_list: list[str], topic: dict) -> dict:
        total_sentences = max(1, len(sentence_list))
        word_count = len(re.findall(r"[a-zA-Z0-9]+", cleaned_answer))
        sentence_lengths = [len(re.findall(r"[a-zA-Z0-9]+", sentence)) for sentence in sentence_list] or [word_count]
        factual_statements = 0
        factual_anchor_sentences = 0
        reasoning_signals = 0
        transition_markers = 0
        examples_detected: list[str] = []
        dimensions: list[str] = []
        bluff_hits: list[str] = []
        interlinking_examples: list[str] = []
        real_world_references: list[str] = []
        vague_sentences = 0
        topic_keywords = [item.lower() for item in topic.get("knowledge", {}).get("keywords", [])]

        for sentence in sentence_list:
            lowered = sentence.lower()
            has_factual_anchor = bool(FACTUAL_ANCHOR_PATTERN.search(lowered))
            if has_factual_anchor:
                factual_anchor_sentences += 1
                factual_statements += 1
            if any(marker in lowered for marker in CAUSE_EFFECT_MARKERS):
                reasoning_signals += 1
            if any(marker in lowered for marker in TRANSITION_MARKERS):
                transition_markers += 1
            for bucket, keywords in DIMENSION_TERMS.items():
                if any(keyword in lowered for keyword in keywords) and bucket not in dimensions:
                    dimensions.append(bucket)
            if any(re.search(pattern, lowered) for pattern in EXAMPLE_PATTERNS) and sentence not in examples_detected:
                examples_detected.append(sentence)
            if self._is_interlinking_sentence(lowered, topic_keywords) and sentence not in interlinking_examples:
                interlinking_examples.append(sentence)
            if self._is_real_world_reference(lowered) and sentence not in real_world_references:
                real_world_references.append(sentence)
            sentence_bluff_hits = [phrase for phrase in BLUFF_PHRASES if phrase in lowered]
            for phrase in sentence_bluff_hits:
                if phrase not in bluff_hits:
                    bluff_hits.append(phrase)
            if self._is_vague_sentence(lowered, has_factual_anchor):
                vague_sentences += 1

        fact_density = round(factual_statements / total_sentences, 3)
        average_sentence_length = round(sum(sentence_lengths) / max(1, len(sentence_lengths)), 2)
        long_sentence_ratio = round(sum(1 for length in sentence_lengths if length >= 28) / total_sentences, 3)
        balance_detected = any(marker in cleaned_answer.lower() for marker in BALANCE_MARKERS)
        structure_intro_present = total_sentences > 0 and len(sentence_list[0].split()) >= 6
        structure_conclusion_present = total_sentences > 1 and any(
            marker in sentence_list[-1].lower() for marker in ["therefore", "thus", "hence", "overall", "in conclusion"]
        )
        depth_signals = self.detect_depth_features(
            answer=cleaned_answer,
            dimensions=dimensions,
            examples_detected=examples_detected,
            interlinking_examples=interlinking_examples,
        )
        bluff_ratio = round(vague_sentences / total_sentences, 3)
        vagueness_from_signals = self.detect_bluff(bluff_ratio=bluff_ratio)
        maturity = self.compute_maturity(
            answer=cleaned_answer,
            balance_detected=balance_detected,
            interlinking=depth_signals["interlinking"],
            real_world_references=real_world_references,
        )
        return {
            "fact_density": fact_density,
            "factual_statements": factual_statements,
            "factual_anchor_sentences": factual_anchor_sentences,
            "total_sentences": total_sentences,
            "word_count": word_count,
            "average_sentence_length": average_sentence_length,
            "long_sentence_ratio": long_sentence_ratio,
            "transition_markers": transition_markers,
            "reasoning_signals": reasoning_signals,
            "multidimensional_terms": dimensions,
            "balance_detected": balance_detected,
            "examples_detected": examples_detected[:5],
            "bluff_phrases_detected": bluff_hits,
            "structure_intro_present": structure_intro_present,
            "structure_conclusion_present": structure_conclusion_present,
            "vague_sentences": vague_sentences,
            "bluff_ratio": bluff_ratio,
            "vagueness_from_signals": vagueness_from_signals,
            "depth_signals": depth_signals,
            "maturity": maturity,
            "interlinking_examples": interlinking_examples[:5],
            "real_world_references": real_world_references[:5],
        }

    def detect_depth_features(
        self,
        *,
        answer: str,
        dimensions: list[str],
        examples_detected: list[str],
        interlinking_examples: list[str],
    ) -> dict:
        lowered = answer.lower()
        cause_effect = any(marker in lowered for marker in CAUSE_EFFECT_MARKERS)
        multi_dimension = len(dimensions) >= 2
        examples = bool(examples_detected)
        interlinking = bool(interlinking_examples)
        positive_signals = sum([cause_effect, multi_dimension, examples, interlinking])
        if cause_effect and multi_dimension and examples:
            depth = "DEEP"
        elif positive_signals >= 2:
            depth = "MODERATE"
        else:
            depth = "SURFACE"
        return {
            "cause_effect": cause_effect,
            "multi_dimension": multi_dimension,
            "examples": examples,
            "interlinking": interlinking,
            "depth_from_signals": depth,
        }

    @staticmethod
    def detect_bluff(*, bluff_ratio: float) -> str:
        if bluff_ratio > 0.4:
            return "HIGH"
        if bluff_ratio > 0.2:
            return "MODERATE"
        return "LOW"

    def compute_maturity(
        self,
        *,
        answer: str,
        balance_detected: bool,
        interlinking: bool,
        real_world_references: list[str],
    ) -> dict:
        lowered = answer.lower()
        critical_evaluation = any(token in lowered for token in ["however", "although", "trade-off", "limitation", "critically"])
        real_world = bool(real_world_references)
        score = sum([balance_detected, critical_evaluation, interlinking, real_world])
        if score >= 3:
            return {"level": "HIGH", "bonus": 1.0}
        if score >= 2:
            return {"level": "MEDIUM", "bonus": 0.5}
        return {"level": "LOW", "bonus": 0.0}

    def compute_impression(
        self,
        *,
        analysis: dict,
        features: dict,
        structure_score: float,
        relevance_score: float,
        max_marks: int,
    ) -> float:
        ideal_word_count = self._ideal_word_count(max_marks)
        word_delta = abs(features["word_count"] - ideal_word_count) / max(ideal_word_count, 1)

        readability_score = clamp(
            0.62
            + (0.14 if 10 <= features["average_sentence_length"] <= 22 else 0.06 if features["average_sentence_length"] <= 26 else -0.12)
            - min(0.2, features["long_sentence_ratio"] * 0.32)
            - min(0.16, features["bluff_ratio"] * 0.26),
            0.05,
            1.0,
        )
        coherence = clamp(
            0.42
            + min(0.2, features["transition_markers"] * 0.04)
            + min(0.16, features["reasoning_signals"] * 0.05)
            + (0.1 if analysis["thinking"] in {"ANALYTICAL", "CRITICAL"} else 0.04)
            + (0.06 if features["balance_detected"] else 0.0)
            - min(0.16, features["bluff_ratio"] * 0.22),
            0.05,
            1.0,
        )
        conciseness = clamp(
            0.62
            - min(0.22, word_delta * 0.34)
            + (0.1 if features["word_count"] <= ideal_word_count * 1.05 else 0.0)
            - (0.12 if features["word_count"] > ideal_word_count * 1.5 else 0.0),
            0.05,
            1.0,
        )
        impression_score = clamp(
            (readability_score * 0.3)
            + (structure_score * 0.25)
            + (relevance_score * 0.2)
            + (conciseness * 0.15)
            + (coherence * 0.1),
            0.0,
            1.0,
        )
        if structure_score >= 0.8:
            alignment_floor = clamp((structure_score * 0.55) + (relevance_score * 0.25) + (coherence * 0.1), 0.05, 1.0)
            impression_score = max(impression_score, alignment_floor)
        return round(clamp(impression_score, 0.0, 1.0), 3)

    def merge_analysis(self, *, content: dict, reasoning: dict, directive: dict, features: dict, similarity: dict) -> dict:
        depth = self._stronger_level(reasoning["depth"], features["depth_signals"]["depth_from_signals"], DEPTH_ORDER)
        vagueness = self._stronger_level(features["vagueness_from_signals"], features["vagueness_from_signals"], VAGUENESS_ORDER)
        missing_points = list(dict.fromkeys(content["missing_points"] + ([] if content["alternative_valid"] else similarity["missing_concepts"])))
        incorrect_points = list(dict.fromkeys(content["incorrect_points"]))
        return {
            "relevance": content["relevance"],
            "domain": content["domain"],
            "must_have_points": content["must_have_points"],
            "good_to_have_points": content["good_to_have_points"],
            "extra_edge_points": content["extra_edge_points"],
            "missing_points": missing_points,
            "incorrect_points": incorrect_points,
            "depth": depth,
            "thinking": reasoning["thinking"],
            "directive": directive["directive"],
            "structure": directive["structure"],
            "vagueness": vagueness,
            "alternative_valid": content["alternative_valid"],
        }

    def merge_analysis_from_signals(self, *, signals: dict, features: dict, similarity: dict) -> dict:
        content_hint = float(signals.get("content_quality_score_hint", 0) or 0)
        expression_hint = float(signals.get("expression_quality_score_hint", 0) or 0)
        directive_satisfaction = str(signals.get("directive_satisfaction", "partial")).lower()
        balance = str(signals.get("dimension_balance", "average")).lower()
        body_structure = str(signals.get("body_structure", "semi-structured")).lower()
        conclusion_type = str(signals.get("conclusion_type", "missing")).lower()
        factual_error_present = bool(signals.get("factual_error_present", False))
        contradiction_present = bool(signals.get("contradiction_present", False))

        relevance = "FULL" if directive_satisfaction == "good" and len(similarity["covered_concepts"]) >= 3 else "PARTIAL" if similarity["covered_concepts"] else "OFF_TOPIC"
        depth = "DEEP" if content_hint >= 8 or balance == "good" else "MODERATE" if content_hint >= 5 or balance == "average" else "SURFACE"
        thinking = "CRITICAL" if balance == "good" and expression_hint >= 7 else "ANALYTICAL" if content_hint >= 5 else "DESCRIPTIVE"
        directive = "FULL" if directive_satisfaction == "good" else "PARTIAL" if directive_satisfaction == "partial" else "NONE"
        structure = "STRONG" if body_structure == "structured" and conclusion_type == "present" else "ADEQUATE" if body_structure in {"structured", "semi-structured"} else "WEAK"
        vagueness = self._stronger_level(features["vagueness_from_signals"], features["vagueness_from_signals"], VAGUENESS_ORDER)
        missing_points = list(dict.fromkeys(list(signals.get("concepts_missing", [])) + similarity["missing_concepts"]))
        incorrect_points = [str(item) for item in signals.get("irrelevant_concepts", [])]
        if contradiction_present:
            incorrect_points.append("Internal contradiction present")
        if factual_error_present:
            incorrect_points.append("Factual error present")
        concept_scores = [item for item in signals.get("concept_scores", []) if isinstance(item, dict)]
        core_points = [str(item.get("concept") or "") for item in concept_scores if str(item.get("importance") or "") == "core"]
        secondary_points = [str(item.get("concept") or "") for item in concept_scores if str(item.get("importance") or "") != "core"]
        return {
            "relevance": relevance,
            "domain": "WRONG" if factual_error_present else "CORRECT",
            "must_have_points": core_points[:6] or [str(item) for item in signals.get("concepts_expected", [])[:6]],
            "good_to_have_points": secondary_points[:6] or [str(item) for item in signals.get("concepts_expected", [])[6:12]],
            "extra_edge_points": [],
            "missing_points": missing_points,
            "incorrect_points": incorrect_points,
            "depth": depth,
            "thinking": thinking,
            "directive": directive,
            "structure": structure,
            "vagueness": vagueness,
            "alternative_valid": True,
        }

    def score(
        self,
        *,
        analysis: dict,
        similarity: dict,
        features: dict,
        max_marks: int,
    ) -> dict:
        weights = calibration_service.get_weights()
        if analysis["relevance"] == "OFF_TOPIC":
            return self._finalize_fixed(
                score=1,
                max_marks=max_marks,
                weights=weights,
                applied_caps=["off_topic"],
                applied_penalties=["off_topic_stop"],
            )
        if analysis["domain"] == "WRONG":
            return self._finalize_fixed(
                score=2,
                max_marks=max_marks,
                weights=weights,
                applied_caps=["wrong_domain"],
                applied_penalties=["wrong_domain_stop"],
            )

        point_score = (
            len(similarity["must_have_points_present"]) * weights["must_weight"]
            + len(similarity["good_to_have_points_present"]) * weights["good_weight"]
            + len(similarity["extra_edge_points_present"]) * weights["extra_weight"]
        )
        depth_bonus = (
            weights["depth_weight"]
            if analysis["depth"] == "DEEP"
            else weights["depth_weight"] * 0.5
            if analysis["depth"] == "MODERATE"
            else 0.0
        )
        directive_bonus = (
            weights["directive_weight"]
            if analysis["directive"] == "FULL"
            else weights["directive_weight"] * 0.5
            if analysis["directive"] == "PARTIAL"
            else 0.0
        )
        similarity_bonus = similarity["similarity_score"] * weights["similarity_weight"]
        fact_bonus = (
            weights["fact_weight"]
            if features["fact_density"] > 0.45
            else weights["fact_weight"] * 0.5
            if features["fact_density"] > 0.3
            else 0.0
        )
        vagueness_penalty = 2.0 if analysis["vagueness"] == "HIGH" else 1.0 if analysis["vagueness"] == "MODERATE" else 0.0
        missing_penalty = 0.0 if analysis["alternative_valid"] else min(2.0, len(similarity["missing_concepts"]) * 0.35)
        relevance_score = self._relevance_score(analysis=analysis, similarity=similarity)
        structure_score = self._structure_score(analysis=analysis, features=features)
        efficiency_score = self._efficiency_score(features=features, max_marks=max_marks, relevance_score=relevance_score)
        impression_score = self.compute_impression(
            analysis=analysis,
            features=features,
            structure_score=structure_score,
            relevance_score=relevance_score,
            max_marks=max_marks,
        )
        effective_coverage_weight = weights["coverage_weight"] if relevance_score >= 0.7 else weights["coverage_weight"] * 0.05
        coverage_bonus = similarity["coverage_score"] * effective_coverage_weight
        relevance_override_penalty = 1.6 if relevance_score < 0.7 else 0.0
        irrelevance_penalty = 2.2 if relevance_score < 0.55 else 1.2 if relevance_score < 0.7 else 0.0
        structure_modifier = 0.85 if structure_score > 0.78 else -1.2 if structure_score < 0.55 else 0.0
        structure_priority_bonus = (
            0.45
            if structure_score >= 0.78 and analysis["directive"] == "FULL" and analysis["thinking"] in {"ANALYTICAL", "CRITICAL"}
            else 0.0
        )
        concise_high_relevance_bonus = (
            0.25
            if features["word_count"] <= self._ideal_word_count(max_marks) * 1.05
            and relevance_score >= 0.82
            and features["bluff_ratio"] < 0.18
            else 0.0
        )
        overwrite_multiplier = (
            0.6
            if features["word_count"] > self._ideal_word_count(max_marks) * 1.5 and relevance_score < 0.7
            else 1.0
        )
        applied_penalties = self._applied_penalties(
            analysis=analysis,
            features=features,
            missing_penalty=missing_penalty,
            vagueness_penalty=vagueness_penalty,
            relevance_score=relevance_score,
            structure_score=structure_score,
            overwrite_multiplier=overwrite_multiplier,
            irrelevance_penalty=irrelevance_penalty,
        )

        base_formula_score = clamp(
            point_score
            + depth_bonus
            + directive_bonus
            + similarity_bonus
            + coverage_bonus
            + fact_bonus
            - vagueness_penalty
            - missing_penalty
            - relevance_override_penalty
            - irrelevance_penalty,
            1,
            9,
        )

        content_score = clamp(
            1
            + point_score
            + coverage_bonus
            + (relevance_score * 1.15)
            + (similarity_bonus * 0.75 if analysis["alternative_valid"] else 0.0)
            - (0 if analysis["alternative_valid"] else len(similarity["missing_concepts"]) * 0.25)
            - (relevance_override_penalty * 0.35),
            1,
            9,
        )
        depth_score = clamp(
            1
            + (2.5 if analysis["depth"] == "DEEP" else 1.5 if analysis["depth"] == "MODERATE" else 0)
            + (1.0 if features["depth_signals"]["cause_effect"] else 0)
            + (1.0 if features["depth_signals"]["multi_dimension"] else 0)
            + (1.0 if features["depth_signals"]["examples"] else 0)
            + (0.75 if features["depth_signals"]["interlinking"] else 0)
            + (0.5 if features["balance_detected"] else 0)
            + (0.5 if analysis["thinking"] in {"ANALYTICAL", "CRITICAL"} else 0),
            1,
            9,
        )
        similarity_component = clamp(
            1
            + similarity["similarity_score"] * 4.25
            + (similarity["coverage_score"] * (1.2 if relevance_score < 0.7 else 3.2 if not analysis["alternative_valid"] else 1.8)),
            1,
            9,
        )
        directive_score = clamp(
            1
            + (3.1 if analysis["directive"] == "FULL" else 1.45 if analysis["directive"] == "PARTIAL" else 0)
            + (structure_score * 2.8)
            + (1.0 if features["structure_intro_present"] else 0)
            + (1.0 if features["structure_conclusion_present"] else 0)
            + (0.75 if analysis["thinking"] in {"ANALYTICAL", "CRITICAL"} else 0),
            1,
            9,
        )

        ensemble_score = (0.26 * content_score) + (0.14 * depth_score) + (0.12 * similarity_component) + (0.48 * directive_score)
        maturity_bonus = features["maturity"]["bonus"] * weights["maturity_weight"]
        seeded_examiner_variance = self._examiner_variance(analysis=analysis, similarity=similarity, features=features)
        raw_score = clamp(
            (
                ensemble_score
                + maturity_bonus
                + fact_bonus
                + structure_modifier
                + structure_priority_bonus
                + concise_high_relevance_bonus
                + (impression_score * weights["impression_weight"])
                - vagueness_penalty
                - (missing_penalty * 0.5)
                - relevance_override_penalty
                - irrelevance_penalty
                + seeded_examiner_variance
            )
            * overwrite_multiplier,
            1,
            9,
        )

        max_score_cap, applied_caps = self._apply_caps(
            analysis=analysis,
            similarity=similarity,
            relevance_score=relevance_score,
        )
        capped_score = min(raw_score, max_score_cap)
        final_score = round(clamp(capped_score, 1, 9))
        confidence = self._confidence(
            analysis=analysis,
            features=features,
            component_scores=[content_score, depth_score, similarity_component, directive_score],
        )
        scaled_score = self._compressed_scaled_score(
            final_score=final_score,
            max_marks=max_marks,
            relevance_score=relevance_score,
            examiner_variance=seeded_examiner_variance,
        )
        return {
            "content_score": round(content_score, 2),
            "depth_score": round(depth_score, 2),
            "similarity_component": round(similarity_component, 2),
            "directive_score": round(directive_score, 2),
            "impression_score": round(impression_score, 3),
            "relevance_score": round(relevance_score, 3),
            "structure_score": round(structure_score, 3),
            "efficiency_score": round(efficiency_score, 3),
            "base_formula_score": round(base_formula_score, 2),
            "ensemble_score": round(ensemble_score, 2),
            "raw_score": round(raw_score, 2),
            "final_score": final_score,
            "scaled_score": scaled_score,
            "examiner_variance": round(seeded_examiner_variance, 3),
            "max_score_cap": max_score_cap,
            "applied_caps": applied_caps,
            "applied_penalties": applied_penalties,
            "confidence": confidence,
            "weights": weights,
        }

    @staticmethod
    def verdict(score: int, maturity: str = "LOW") -> str:
        if score >= 8:
            return "Topper-level direction with strong examiner appeal"
        if score >= 6:
            return "Competitive answer with visible gaps"
        if score >= 4 and maturity == "HIGH":
            return "Reasoned answer, but content coverage still limits marks"
        if score >= 4:
            return "Recoverable answer but below UPSC edge"
        return "Weak answer requiring topic rebuild"

    @staticmethod
    def performance_band(percentile: float) -> str:
        if percentile >= 90:
            return "Top 10%"
        if percentile >= 75:
            return "Top 25%"
        if percentile >= 40:
            return "Average"
        return "Below Average"

    @staticmethod
    def score_band(*, scaled_score: float, max_marks: int) -> str:
        normalized_score = (scaled_score / max(max_marks, 1)) * 10
        if normalized_score < 4:
            return "Poor"
        if normalized_score < 5.5:
            return "Average"
        if normalized_score <= 6.5:
            return "Good"
        return "Topper-level"

    @classmethod
    def penalty_reasons(cls, *, analysis: dict, similarity: dict, features: dict, scoring: dict) -> list[str]:
        reasons: list[str] = []
        for penalty in scoring.get("applied_penalties", []):
            if penalty == "off_topic_stop":
                reasons.append("Off-topic response")
            elif penalty == "wrong_domain_stop":
                reasons.append("Wrong domain framing")
            elif penalty == "high_vagueness_penalty":
                reasons.append("High vagueness reduced answer precision")
            elif penalty == "moderate_vagueness_penalty":
                reasons.append("Moderate vagueness reduced answer precision")
            elif penalty == "missing_concepts_penalty":
                missing_label = cls._missing_dimension_label(similarity.get("missing_concepts", []))
                reasons.append(f"Missing key dimension: {missing_label}")
            elif penalty == "bluff_density_penalty":
                reasons.append("Generic phrasing lowered value density")
            elif penalty == "directive_miss_penalty":
                reasons.append("Directive not addressed directly")
            elif penalty == "relevance_override_penalty":
                reasons.append(f"Low relevance ({scoring.get('relevance_score', 0.0):.2f})")
            elif penalty == "severe_irrelevance_penalty":
                reasons.append("Severe irrelevance to question demand")
            elif penalty == "weak_structure_penalty":
                reasons.append(f"Weak structure ({scoring.get('structure_score', 0.0):.2f})")
            elif penalty == "overwriting_irrelevance_penalty":
                reasons.append("Overwriting with low value density")

        return reasons[:5]

    @classmethod
    def answer_gap_summary(cls, *, analysis: dict, similarity: dict, features: dict, scoring: dict) -> str:
        gaps: list[str] = []
        if scoring.get("relevance_score", 0.0) < 0.7:
            gaps.append("drifts from the core demand")
        if similarity.get("missing_concepts"):
            gaps.append(f"misses key dimensions like {cls._missing_dimension_label(similarity['missing_concepts'])}")
        if analysis.get("structure") == "WEAK" or not features.get("structure_intro_present") or not features.get("structure_conclusion_present"):
            gaps.append("needs clearer answer structure")
        if not features.get("examples_detected"):
            gaps.append("lacks concrete examples")
        if features.get("bluff_ratio", 0.0) > 0.2:
            gaps.append("leans on generic phrasing")
        if analysis.get("thinking") == "DESCRIPTIVE" and not features.get("balance_detected"):
            gaps.append("needs sharper comparison and analysis")

        if not gaps:
            return "Your answer is broadly sound, but tighter evidence and smoother transitions can lift it further."
        if len(gaps) == 1:
            return f"Your answer {gaps[0]}."
        return f"Your answer {gaps[0]} and {gaps[1]}."

    @staticmethod
    def stronger_thinking(left: str, right: str) -> str:
        return left if THINKING_ORDER[left] >= THINKING_ORDER[right] else right

    @staticmethod
    def _stronger_level(left: str, right: str, ordering: dict[str, int]) -> str:
        return left if ordering[left] >= ordering[right] else right

    @staticmethod
    def _is_vague_sentence(lowered: str, has_factual_anchor: bool) -> bool:
        if any(phrase in lowered for phrase in BLUFF_PHRASES):
            return True
        generic_adjectives = {"important", "useful", "helpful", "vital", "good", "significant"}
        if has_factual_anchor:
            return False
        tokens = set(re.findall(r"[a-zA-Z]+", lowered))
        return bool(tokens & generic_adjectives) and len(tokens) < 12

    @staticmethod
    def _is_interlinking_sentence(lowered: str, topic_keywords: list[str]) -> bool:
        if not any(marker in lowered for marker in INTERLINK_MARKERS):
            return False
        keyword_hits = sum(1 for keyword in topic_keywords if keyword and keyword in lowered)
        return keyword_hits >= 1 or sum(bucket in lowered for bucket in DIMENSION_TERMS) >= 2

    @staticmethod
    def _is_real_world_reference(lowered: str) -> bool:
        return bool(re.search(r"\b\d{4}\b", lowered)) or any(marker in lowered for marker in REAL_WORLD_MARKERS)

    @staticmethod
    def _apply_caps(*, analysis: dict, similarity: dict, relevance_score: float) -> tuple[int, list[str]]:
        max_score = 9
        applied_caps: list[str] = []
        if len(similarity["must_have_points_present"]) == 0:
            if analysis["alternative_valid"]:
                max_score = min(max_score, 6)
                applied_caps.append("alternative_valid_soft_cap_6")
            else:
                max_score = 4
                applied_caps.append("no_must_have_cap_4")
        if analysis["directive"] != "FULL":
            max_score = min(max_score, 5)
            applied_caps.append("directive_cap_5")
        if analysis["depth"] == "SURFACE":
            max_score = min(max_score, 6)
            applied_caps.append("surface_depth_cap_6")
        if relevance_score < 0.6:
            max_score = min(max_score, 4)
            applied_caps.append("low_relevance_cap_4")
        elif relevance_score < 0.7:
            max_score = min(max_score, 5)
            applied_caps.append("low_relevance_cap_5")
        return max_score, applied_caps

    @staticmethod
    def _confidence(*, analysis: dict, features: dict, component_scores: list[float]) -> float:
        spread = max(component_scores) - min(component_scores)
        confidence = 0.92 - (spread * 0.05)
        if analysis["alternative_valid"]:
            confidence -= 0.08
        if analysis["vagueness"] == "HIGH":
            confidence -= 0.1
        elif analysis["vagueness"] == "MODERATE":
            confidence -= 0.05
        if features["fact_density"] > 0.45:
            confidence += 0.04
        if features["maturity"]["level"] == "HIGH":
            confidence += 0.03
        return round(clamp(confidence, 0.45, 0.97), 2)

    @staticmethod
    def _relevance_score(*, analysis: dict, similarity: dict) -> float:
        must_have_total = max(1, len(analysis["must_have_points"]))
        must_have_ratio = len(similarity["must_have_points_present"]) / must_have_total
        base = {"OFF_TOPIC": 0.12, "PARTIAL": 0.58, "FULL": 0.86}[analysis["relevance"]]
        if analysis["alternative_valid"]:
            base += 0.04
        return clamp(base + (must_have_ratio * 0.08) + (similarity["coverage_score"] * 0.08), 0.05, 1.0)

    @staticmethod
    def _structure_score(*, analysis: dict, features: dict) -> float:
        base = {"WEAK": 0.34, "ADEQUATE": 0.62, "STRONG": 0.84}[analysis["structure"]]
        base += 0.07 if features["structure_intro_present"] else 0.0
        base += 0.07 if features["structure_conclusion_present"] else 0.0
        base += 0.06 if analysis["directive"] == "FULL" else 0.02 if analysis["directive"] == "PARTIAL" else -0.08
        base += 0.03 if features["balance_detected"] else 0.0
        return clamp(base, 0.05, 1.0)

    @staticmethod
    def _efficiency_score(*, features: dict, max_marks: int, relevance_score: float) -> float:
        total_sentences = max(1, features["total_sentences"])
        anchor_ratio = features["factual_anchor_sentences"] / total_sentences
        sentence_window_bonus = 0.08 if 4 <= total_sentences <= 11 else 0.03 if total_sentences <= 14 else 0.0
        ideal_word_count = ScoringEngine._ideal_word_count(max_marks)
        concise_bonus = (
            0.08
            if features["word_count"] <= ideal_word_count * 1.05 and relevance_score >= 0.82 and features["bluff_ratio"] < 0.18
            else 0.0
        )
        overwrite_penalty = 0.14 if features["word_count"] > ideal_word_count * 1.5 and relevance_score < 0.7 else 0.0
        score = (
            0.36
            + min(0.34, features["fact_density"] * 0.62)
            + min(0.12, anchor_ratio * 0.16)
            + sentence_window_bonus
            + concise_bonus
            - overwrite_penalty
            - min(0.28, features["bluff_ratio"] * 0.6)
        )
        return clamp(score, 0.05, 1.0)

    @staticmethod
    def _applied_penalties(
        *,
        analysis: dict,
        features: dict,
        missing_penalty: float,
        vagueness_penalty: float,
        relevance_score: float,
        structure_score: float,
        overwrite_multiplier: float,
        irrelevance_penalty: float,
    ) -> list[str]:
        penalties: list[str] = []
        if vagueness_penalty >= 2:
            penalties.append("high_vagueness_penalty")
        elif vagueness_penalty >= 1:
            penalties.append("moderate_vagueness_penalty")
        if missing_penalty > 0:
            penalties.append("missing_concepts_penalty")
        if features["bluff_ratio"] > 0.3:
            penalties.append("bluff_density_penalty")
        if analysis["directive"] == "NONE":
            penalties.append("directive_miss_penalty")
        if relevance_score < 0.7:
            penalties.append("relevance_override_penalty")
        if irrelevance_penalty >= 2:
            penalties.append("severe_irrelevance_penalty")
        if structure_score < 0.4:
            penalties.append("weak_structure_penalty")
        if overwrite_multiplier < 1.0:
            penalties.append("overwriting_irrelevance_penalty")
        return penalties

    @staticmethod
    def _ideal_word_count(max_marks: int) -> int:
        return max(75, max_marks * 15)

    @staticmethod
    def _examiner_variance(*, analysis: dict, similarity: dict, features: dict) -> float:
        seed = (
            f"{analysis['relevance']}|{analysis['depth']}|{analysis['directive']}|{analysis['structure']}|"
            f"{similarity['coverage_score']:.3f}|{similarity['similarity_score']:.3f}|"
            f"{features['fact_density']:.3f}|{features['bluff_ratio']:.3f}"
        )
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        unit = int(digest[:8], 16) / 0xFFFFFFFF
        return round((unit - 0.5) * 0.24, 3)

    @staticmethod
    def _compressed_scaled_score(*, final_score: int, max_marks: int, relevance_score: float, examiner_variance: float) -> float:
        ratio = final_score / 9
        compressed_ratio = 0.02 + (ratio**0.92) * 0.68
        compressed_ratio += (relevance_score - 0.75) * 0.02
        compressed_ratio += examiner_variance * 0.02
        compressed_ratio = clamp(compressed_ratio, 0.08, 0.7)
        return round(compressed_ratio * max_marks, 2)

    @staticmethod
    def _missing_dimension_label(missing_concepts: list[str]) -> str:
        if not missing_concepts:
            return "core coverage"
        label = str(missing_concepts[0]).strip().strip(".")
        if len(label) <= 48:
            return label
        return f"{label[:45].rstrip()}..."

    @classmethod
    def _finalize_fixed(
        cls,
        *,
        score: int,
        max_marks: int,
        weights: dict[str, float],
        applied_caps: list[str],
        applied_penalties: list[str],
    ) -> dict:
        scaled_score = cls._compressed_scaled_score(
            final_score=score,
            max_marks=max_marks,
            relevance_score=0.12 if score == 1 else 0.2,
            examiner_variance=0.0,
        )
        return {
            "content_score": float(score),
            "depth_score": 1.0,
            "similarity_component": 1.0,
            "directive_score": 1.0,
            "impression_score": 0.0,
            "relevance_score": 0.12 if score == 1 else 0.2,
            "structure_score": 0.1,
            "efficiency_score": 0.1,
            "base_formula_score": float(score),
            "ensemble_score": float(score),
            "raw_score": float(score),
            "final_score": score,
            "scaled_score": scaled_score,
            "examiner_variance": 0.0,
            "max_score_cap": score,
            "applied_caps": applied_caps,
            "applied_penalties": applied_penalties,
            "confidence": 0.95,
            "weights": weights,
        }


scoring_engine = ScoringEngine()
