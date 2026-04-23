# Extractor

## Role

The extractor is the LLM-facing layer of the UPSC evaluation pipeline. Its only job is to convert a question, an answer, and a locked concept universe into structured evaluation signals. It does not assign marks.

## Concept Universe

- `concept_universe` is the scoring lock.
- Only concepts inside that universe are used for `concept_scores`.
- Strong concepts outside the universe are surfaced under `extra_valid_concepts`.
- Once a question-level universe is locked, the backend reuses it instead of regenerating it.

## Key Signals

- `core_coverage_ratio`: fraction of core concepts covered at least weakly.
- `core_depth_ratio`: fraction of core concepts clearly explained.
- `directive_coverage_ratio`: checklist coverage against question demand.
- `dimension_balance`: breadth across causes, impacts, challenges, way forward, and examples.
- `clarity_score`: anchored 0–5 expression score.
- `vague_ratio`: normalized estimate of vague, low-information writing.
- `penalty_flags`: standardized structural/content warning flags for deterministic scoring.
- `fundamental_weakness`: hard weakness signal, usually tied to weak core coverage.

## JSON Schema Shape

The extractor returns a strict JSON object containing:

- `directive`
- `required_components`
- `concept_scores`
- `extra_valid_concepts`
- `core_summary`
- `dimension_counts`
- `dimension_balance`
- `structure`
- `core_coverage_ratio`
- `core_depth_ratio`
- `clarity_score`
- `value_additions`
- `vague_ratio`
- `directive_coverage_ratio`
- `factual_error_present`
- `contradiction_present`
- `penalty_flags`
- `partial_concepts_count`
- `answer_length_category`
- `fundamental_weakness`
- `confidence`

## Design Goal

The extractor is intentionally strict and schema-bound so the backend scorer can remain deterministic, reproducible, and easy to audit.
