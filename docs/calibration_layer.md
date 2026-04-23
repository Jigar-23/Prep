# Calibration Layer

## Role

The calibration layer sits after deterministic scoring and simulates bounded examiner behavior. It is optional, seeded, and intentionally narrow so it adds realism without undermining reproducibility.

## Examiner Profiles

Supported modes:

- `strict`
- `balanced`
- `lenient`

Each profile defines:

- `penalty_multiplier`
- `bonus_multiplier`
- `leniency`

## Execution Rules

Calibration is only applied after the base scorer has already completed penalties, caps, bonus handling, and confidence adjustment.

If `calibration_enabled == false`, the base score is returned unchanged.

If `safe_mode == true`, the calibration layer is bypassed entirely:

- no variation
- no leniency scaling
- no profile-side boosts or penalties

## Variation Model

- the seed is derived from the tuple `(question_id, answer_id, calibration_seed)` using a stable hash
- the random draw uses `gauss(0, 0.01)`
- variation is clamped to `[-0.02, 0.02]`
- if `fundamental_weakness` is true, variation is forced to `0`

The returned payload includes `calibration_seed_used` for replay and debugging.

## Calibration Adjustments

The layer can apply:

- presentation boost for structured, clear answers
- balance bonus for good multidimensional coverage with depth
- bluff penalty for vague, shallow answers
- consistency correction when strong depth coexists with high vagueness
- profile leniency scaling

Presentation and balance bonuses are combined and capped at `0.05`.

## Bluff Penalty Interaction

If the base scorer has already triggered `excessive_vagueness`, the bluff penalty is halved to avoid double punishment.

## Fundamental Weakness Override

If `fundamental_weakness` is true, the calibrated score is capped at `0.45` even after other calibration steps.

## Output

Calibration returns:

- `calibrated_score`
- `applied_profile`
- `applied_adjustments`
- `variation`
- `calibration_seed_used`
- `enabled`
- `safe_mode`
