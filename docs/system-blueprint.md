# Perp UPSC AI Platform Blueprint

## Objective

Build a UPSC-focused learning system that behaves like:

- an examiner during evaluation
- a topper mentor during content rebuild
- a revision engine during recall

Not:

- a generic chatbot
- a free-form conversational tool

## High-Level Architecture

### Clients

- Web client: Next.js App Router
- Mobile client: Expo React Native shared app for iOS and Android

### Backend

- FastAPI
- JWT authentication
- modular route and service layers

### Data

- Turso/libSQL in production
- SQLite fallback locally

### AI layer

- Gemini `gemini-1.5-pro` for evaluation extraction and model answers
- Gemini `gemini-1.5-flash` for cleaning and learning bundle generation

### Cache layer

- TTL in-memory cache
- DB remains source of truth

## Core Rule

- LLM extracts
- backend scores
- DB stores
- cache accelerates

## Evaluation Architecture

### 1. Input

- `question`
- `student_answer`
- `ocr_text`
- `handwritten_image_base64`

### 2. Normalization

Output:

```json
{
  "cleaned_answer": "string",
  "sentence_list": ["string"]
}
```

### 3. LLM Analysis

Strict JSON only:

```json
{
  "relevance": "FULL | PARTIAL | OFF_TOPIC",
  "domain": "CORRECT | WRONG",
  "must_have_points": [],
  "good_to_have_points": [],
  "extra_edge_points": [],
  "missing_points": [],
  "incorrect_points": [],
  "depth": "SURFACE | MODERATE | DEEP",
  "thinking": "DESCRIPTIVE | ANALYTICAL | CRITICAL",
  "directive": "FULL | PARTIAL | NONE",
  "vagueness": "LOW | MODERATE | HIGH"
}
```

### 4. Model Answer Generation

Cached by question hash and topic id.

### 5. Similarity Engine

- deterministic hashed embeddings
- cosine similarity
- coverage of must/good/edge points

### 6. Feature Extraction

- fact density
- reasoning signals
- multidimensional terms
- balance markers
- example detection
- bluff phrase detection
- intro/conclusion structure

### 7. Rule-Based Scoring

Hard rules:

- off-topic => score `1`
- wrong domain => score `2`

Normal scoring:

- must-have coverage
- good-to-have coverage
- extra-edge coverage
- depth bonus
- directive bonus
- similarity bonus
- coverage bonus
- fact-density bonus
- vagueness penalty

### 8. Ensemble Normalization

Components:

- content score
- depth score
- similarity component
- directive score

Output:

- final band score `1..9`
- scaled marks
- percentile
- performance band

## Learning Architecture

## Notes Engine

One note payload contains:

- 30-second revision
- core facts
- classification
- case laws
- current affairs link if relevant
- prelim traps
- mains answer structure
- value addition
- PYQ anchors

## Flashcard Engine

Each topic generates:

- 5 factual cards
- 3 conceptual cards
- 2 trap cards
- 2 mains cards

## Revision Engine

Stored per card:

```json
{
  "ease_factor": 2.5,
  "interval_days": 1,
  "next_review": "ISO_DATE",
  "correct_count": 0,
  "incorrect_count": 0
}
```

Review ladder:

- 1
- 2
- 4
- 7
- 15
- 30

## Optimization Blueprint

### Cache keys

- `notes::{topic_id}`
- `flashcards::{topic_id}`
- `learning_bundle::{topic_id}`
- `model_answer::{topic_id}::{question_hash}`
- `review::{user_id}`

### Cost controls

- never regenerate if DB already has payload
- combine learning assets into one generation bundle
- separate evaluation from generation
- keep prompts compact
- retry invalid JSON at most twice

### Reliability

- strict JSON schemas
- retries with fallback
- safe error envelopes
- deterministic local demo fallback when Gemini is unavailable

## Active Data Model

### Core

- `users`
- `exams`
- `subjects`
- `topics`

### Learning

- `notes`
- `flashcards`
- `model_answers`

### Evaluation

- `answers`
- `evaluation_history`

### Revision

- `revision_progress`

## API Contracts

### `POST /auth/signup`

Creates user and returns JWT session.

### `POST /auth/login`

Authenticates user and returns JWT session.

### `GET /catalog/tree`

Returns UPSC catalog tree.

### `POST /generate-notes`

Input:

```json
{
  "topic_id": "topic_upsc_polity_fundamental_rights"
}
```

### `POST /generate-flashcards`

Input:

```json
{
  "topic_id": "topic_upsc_polity_fundamental_rights"
}
```

### `POST /evaluate`

Input:

```json
{
  "topic_id": "topic_upsc_polity_fundamental_rights",
  "question": "Discuss the significance of Fundamental Rights.",
  "student_answer": "string",
  "ocr_text": "optional",
  "handwritten_image_base64": "optional",
  "handwritten_image_mime_type": "optional",
  "max_marks": 10,
  "include_learning_assets": true
}
```

Output:

```json
{
  "evaluation": {},
  "analysis": {},
  "notes": {},
  "flashcards": [],
  "revision": {},
  "normalized_answer": {},
  "similarity": {},
  "features": {},
  "scoring": {}
}
```

### `GET /review-cards`

Returns due cards for the authenticated user.

### `POST /update-progress`

Updates revision progress after self-check.

## User Flow

1. Open dashboard.
2. Pick a topic.
3. Submit answer.
4. Receive deterministic score, mistakes, ideal answer.
5. Load notes for the same topic.
6. Load flashcards for the same topic.
7. Seed revision queue.
8. Return daily for review cards.

## Platform Implementation

### Web

- App Router pages
- auth context
- API hooks
- topic workspace
- daily review queue

### Mobile

- Expo shared app
- one codebase for iOS and Android
- local session persistence
- answer evaluation flow
- flashcard and review flow

### Backend

- service-per-capability architecture
- route-level auth protection
- deterministic scoring core
- cache invalidation per topic/user

## Production Notes

### Required to go live

- real Turso URL and auth token
- real Gemini API key
- strong JWT secret
- deployed frontend and backend URLs
- EAS build + store publishing for mobile

### Store links

Store links do not exist yet because publishing is not performed locally. The mobile codebase is included and ready for EAS-based release.
