# System Architecture

## Pipeline

The end-to-end UPSC answer evaluation pipeline is:

`LLM extractor -> structured signals -> deterministic scoring -> optional calibration -> rule-based feedback -> API output`

Relative evaluation is an optional sidecar step that can rank already-scored answers without changing the base score.

## Core Modules

### Extractor

- reads question, answer, and locked concept universe
- emits strict JSON signals
- does not assign marks

### Scoring Engine

- computes normalized component scores
- applies penalties, caps, extra bonus, confidence adjustment, and marks conversion
- supports GS paper tuning
- exposes explainability fields such as `weights`, `score_breakdown`, and `scoring_version`

### Calibration Layer

- simulates bounded examiner subjectivity after deterministic scoring
- uses seeded Gaussian variation for replayability
- supports `safe_mode` to bypass calibration

### Feedback Engine

- deterministic and rule-based
- converts evaluation weaknesses into actionable feedback
- does not call an LLM

### Relative Evaluation

- ranks already-scored answers
- preserves score gaps through normalized scaling
- is optional and separate from absolute scoring

## Separation of Concerns

The system deliberately separates semantic extraction from numerical scoring:

- LLMs interpret content
- code computes marks
- calibration adds bounded human-like adjustment
- feedback adds deterministic coaching

This keeps the scoring surface auditable and testable while still allowing controlled examiner realism.

## Why Deterministic Scoring

Deterministic scoring is used because it is:

- auditable
- stable across replays
- easy to regression test
- resistant to prompt drift
- easier to calibrate safely

## Why Calibration Exists

Real UPSC examiners reward presentation, punish bluffing, and show mild variability. The calibration layer exists to model those small tendencies without letting them override the core content score.

## Reproducibility and Caching

The backend uses:

- question-level concept universe locking
- answer-level evaluation result caching
- seeded calibration replay
- TTL-based in-memory caches for hot paths

These controls reduce latency and keep repeated evaluations consistent.
