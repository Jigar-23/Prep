# Calibration Layer

## Role

The calibration layer is a post-processing layer applied after deterministic scoring. It simulates mild examiner subjectivity while preserving replayability.

## Examiner Profiles

Supported profiles:

- `strict`
- `balanced`
- `lenient`

Each profile defines:

- `penalty_multiplier`
- `bonus_multiplier`
- `leniency`

## Variation Model

- Variation is generated with a seeded Gaussian draw: `gauss(0, 0.01)`.
- Variation is clamped to `[-0.02, 0.02]`.
- Seed stability uses a hash of `(question_id, answer_id, calibration_seed)`.
- If `fundamental_weakness` is true, variation is forced to `0`.

## Calibration Adjustments

The layer can apply:

- presentation boost for structured, clear answers
- balanced-answer bonus for strong multidimensional answers
- bluff penalty for vague, shallow answers
- consistency correction when depth and vagueness signals conflict
- profile leniency adjustment

Presentation and balance bonuses are combined and capped.

## Bluff Penalty Interaction

If the base scorer has already applied `excessive_vagueness`, the calibration bluff penalty is reduced to avoid double punishment.

## Determinism

Calibration is optional and modular.

- If disabled, the base score is returned unchanged.
- If enabled with the same seed and IDs, replay is stable.
- The layer returns `calibration_seed_used` for auditability.
