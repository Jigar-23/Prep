# Feedback Engine

## Role

The feedback engine generates deterministic, rule-based coaching from evaluation JSON. It never calls an LLM and does not change marks.

## Input

The engine reads scoring-relevant signals such as:

- `core_coverage_ratio`
- `directive_coverage_ratio` or `directive_score`
- `structure.body`
- `vague_ratio`
- `value_additions` or `value_score`
- `clarity_score`

## Output

It returns:

- `strengths`
- `weaknesses`
- `improvements`

Each list is capped to keep the payload concise and stable.

## Rules

Examples of deterministic mappings:

- low core coverage -> `Add more core concepts from the concept universe.`
- low directive coverage -> `Answer the directive more directly.`
- weak structure -> `Improve intro, body grouping, and conclusion flow.`
- high vagueness -> `Reduce vague statements and add concrete linkage.`
- low value addition -> `Include examples, data, or reports to support the argument.`

## Design Goal

The feedback engine is meant to be predictable, explainable, and cheap to run. It complements the scorer by turning numeric weaknesses into clear next actions.
