# Relative Evaluation

## Role

Relative evaluation ranks a batch of already-scored answers without modifying the underlying absolute score.

## API

`rank_answers(answer_scores: list[float])`

Returns:

- `rankings`
- `normalized_scores`

## Method

The current implementation uses deterministic min-max scaling:

- scores are clamped to `[0, 1]`
- if all scores are equal, normalized scores default to `0.5`
- otherwise, each score is mapped to `(score - min) / (max - min)`

Ranking is ordinal and stable:

- higher scores rank better
- ties are resolved by original order

## Why Separate It

Relative ranking is useful for comparison inside a cohort, but it should not distort the absolute UPSC-style score. Keeping it separate preserves auditability and lets downstream systems choose whether to display absolute marks, relative standing, or both.
