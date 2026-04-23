# Scoring Engine

## Role

The scoring engine converts structured extractor signals into deterministic marks-ready outputs. This layer is formula-driven and does not use model judgment.

## Normalization

The engine derives component scores in the `0–1` range:

- `core_score = 0.7 * core_coverage_ratio + 0.3 * core_depth_ratio`
- `directive_score = directive_coverage_ratio`
- `structure_score = 0.3 * intro + 0.4 * body + 0.3 * conclusion`
- `value_score = min(1.0, (2 * data_or_report + 1 * example + 0.5 * generic) / 5)`
- `expression_score = clarity_score / 5`

`intro`, `body`, and `conclusion` are mapped from anchored categorical values.

## Weights

Base weighted score:

- core: `0.40`
- directive: `0.20`
- structure: `0.15`
- value addition: `0.10`
- expression: `0.10`

## Penalties

The scorer applies standardized penalties for:

- missing conclusion
- poor structure
- excessive vagueness
- factual error
- contradiction

Severity-aware penalties are deduplicated and total penalty is capped at `0.25`.

## Caps

Strict caps prevent inflated marks when the answer misses core examiner expectations:

- weak core coverage cap
- unstructured body cap
- weak directive coverage cap

## Bonus Logic

- `extra_valid_concepts` generate a small capped bonus.
- If core coverage is especially weak, the bonus is reduced.

## Rounding Rules

For floating-point stability, the scorer rounds after key stages:

- penalties
- caps
- extra bonus
- confidence adjustment
- calibration handoff

Marks are rounded to the nearest `0.5`.

## Output

The scorer returns component scores, normalized scores, estimated marks, mark range, applied penalties, applied caps, confidence, and calibration metadata.
