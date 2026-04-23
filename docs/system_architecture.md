# System Architecture

## Pipeline

The UPSC evaluation pipeline is:

`LLM extractor -> structured signals -> deterministic scoring -> optional calibration -> API output`

## Separation of Concerns

### Extractor

- understands answer content
- maps content into fixed JSON signals
- does not assign marks

### Scoring Engine

- deterministic
- formula-based
- applies penalties, caps, bonuses, and mark normalization

### Calibration Layer

- sits after base scoring
- adds mild examiner-like behavior
- remains seeded and replayable

## Why Deterministic Scoring

Deterministic scoring is used because:

- it is auditable
- it is stable across replays
- it prevents model drift from changing marks
- it makes calibration and testing practical

## Why Calibration Exists

Real UPSC examiners are not perfectly mechanical. Calibration exists to simulate:

- preference for well-structured presentation
- mild reward for balanced argumentation
- extra skepticism toward bluff or vague writing
- slight examiner-to-examiner variation

The calibration layer is intentionally bounded so it feels human-like without becoming unstable or opaque.

## Reproducibility and Caching

The system locks concept universes per question identity and reuses cached evaluations for exact repeats when possible. This improves consistency, latency, and auditability.
