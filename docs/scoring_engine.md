# Scoring Engine

## Role

The scoring engine converts extractor JSON into deterministic, scoring-aligned outputs. It is fully rule-based and is the source of truth for normalized scores, caps, penalties, and estimated marks.

## Normalization

The engine derives bounded component scores in the `0–1` range:

- `core_score = 0.7 * core_coverage_ratio + 0.3 * core_depth_ratio`
- `directive_score = directive_coverage_ratio`
- `structure_score = 0.3 * intro + 0.4 * body + 0.3 * conclusion`
- `value_score = min(1.0, (2 * data_or_report + 1 * example + 0.5 * generic) / 5)`
- `expression_score = clarity_score / 5`

`intro`, `body`, and `conclusion` come from anchored categorical mappings:

- introduction: `present=1`, `weak=0.5`, `missing=0`
- body: `structured=1`, `semi=0.5`, `unstructured=0`
- conclusion: `present=1`, `weak=0.5`, `missing=0`

## Weighted Score

The default scorer uses a five-part weighted blend, then normalizes the weights so the effective sum remains `1.0`.

- content
- directive
- structure
- value
- expression

The returned payload exposes both the resolved `weights` and `score_breakdown` so downstream systems can explain how the score was built.

## GS Paper Tuning

The scorer supports optional `gs_paper` tuning:

- `GS1`: content emphasis increases
- `GS2`: structure and value addition get higher emphasis
- `GS3`: default balanced profile
- `GS4`: expression and clarity receive extra weight

This tuning only changes component weights. The normalization formulas, caps, and penalties remain the same.

## Penalties

Penalty handling is deterministic and deduplicated.

- `missing_conclusion`
- `poor_structure`
- `excessive_vagueness`
- `factual_error_present`
- `contradiction_present`

Total penalty is capped at `0.25`. The engine accepts both `penalty_flags[].type` and `penalty_flags[].flag` for backward compatibility.

## Caps

Caps limit overly generous scores when key UPSC conditions are not met.

- weak core coverage cap at `0.4`
- unstructured body cap at `0.6`
- weak directive coverage cap at `0.5`
- stability floor at `0.4` for strong core coverage cases without fundamental weakness

## Bonus Logic

- `extra_valid_concepts` contribute a capped bonus of up to `0.1`
- when `core_coverage_ratio < 0.3`, the bonus is halved

## Deterministic Order

The enforced order is:

`base_score -> penalties -> caps -> extra_bonus -> confidence adjustment -> calibration -> clamp -> rounding`

## Rounding Rules

For floating-point stability, `final_score` is rounded to four decimals after every major stage. Final marks are rounded to the nearest `0.5`, and `marks_range` is clamped to `[0, max_marks]`.

## Output

The scorer returns:

- component scores
- `raw_score`
- `base_final_normalized_score`
- `final_normalized_score`
- `estimated_marks`
- `marks_range`
- `applied_penalties`
- `applied_caps`
- `extra_bonus`
- `weights`
- `score_breakdown`
- `scoring_version`
- calibration metadata
