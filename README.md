# Prep UPSC AI Platform

## Core Loop

Understand → Write → Evaluate → Improve → Revise → Repeat

## 1. Project Overview

Prep is a syllabus-driven exam preparation platform with a deterministic evaluation core.

The current product layer is organized around exam context:

1. Select exam on the dashboard
2. Open a subject
3. Navigate the full syllabus tree
4. Study one topic at a time
5. Practice through answer writing or MCQs
6. Evaluate, revise, and return through the revision loop

This is not a generic AI chat interface. It is a structured preparation system with:

- FastAPI backend for deterministic scoring, progress, revision, and study APIs
- Next.js frontend for the exam-aware dashboard, subject, topic, practice, and revision flows
- SQLite-compatible local database with Turso/libSQL-compatible schema
- Gemini used only for extraction and generation, never for direct mark assignment

## 2. Product Architecture

### Web Route Structure

The main web product now uses a reduced route set:

- `/dashboard`
- `/subject/[subjectId]`
- `/topic/[topicId]`
- `/topic/[topicId]/subtopic/[subtopicId]`
- `/practice`
- `/revision`

Legacy compatibility routes still exist:

- `/review` redirects to `/revision`
- `/topics/[topicId]` redirects to `/topic/[topicId]`

### Global Exam Context

The frontend persists the selected exam in local storage through a global `ExamContext`.

This context drives:

- dashboard subject filtering
- subject page syllabus tree
- practice aggregator
- revision queue filtering
- exam label in the app shell

### Subject → Topic Backbone

The learning hierarchy is:

Dashboard → Subject → Chapter (`topic`) → Subtopic → Apply Now (write → evaluate → fix)

This keeps UPSC learning granular (subtopic-level) and makes the improvement loop actionable.

## 3. Syllabus Backbone

The platform seeds a static-plus-database-backed syllabus catalog.

### Core Catalog Tables

- `exams`
- `subjects`
- `topics`
- `subtopics`
- `topic_notes`
- `questions`

### UPSC Coverage

The UPSC seed now includes a full GS backbone across:

- Polity
- Economy
- Geography
- History
- Environment
- Science & Tech
- Ethics

Each subject contains a full topic list rather than a short showcase set. Topics also include ordered subtopics, learning objectives, deterministic knowledge scaffolding, seeded practice prompts, and MCQs.

### Multi-Exam Coverage

The seeded catalog also includes exam-aware subject trees for:

- SSC
- Banking

Practice mode differs by exam:

- UPSC shows answer writing and MCQs
- SSC and Banking show MCQs only

## 4. How This Mimics A UPSC Examiner

The evaluator is designed to feel closer to a real examiner than a generic LLM grader.

- score compression keeps strong answers in realistic UPSC ranges
- relevance dominance prevents irrelevant content from scoring well
- structure priority makes organization matter more than decorative coverage
- impression factor simulates first-read examiner feel through deterministic signals
- soft penalties explain where value density, demand handling, or clarity broke down
- seeded examiner variance adds tiny human-like drift without losing reproducibility

## 5. Why The Full Answer Is Not Shown

The product does not expose the full backend reference concept space in the main UI.

- passive reading weakens active recall
- copying a ready-made answer reduces writing discipline
- the system uses a backend reference concept space for evaluation
- the UI shows directional hints, strengths, and gaps instead of a full ready-made answer

The `ideal_answer` field remains in the API for backward compatibility, but the product UI is intentionally built around directional feedback rather than a visible full sample answer.

## 6. Current UX Flow

### Dashboard

The dashboard is intentionally minimal. It shows:

- exam selector
- streak
- average score
- last score
- continue where you left
- subjects for the selected exam only

It does not show:

- random topics
- answer editor
- mixed feature panels

### Subject Page

Each subject page has:

- left: full expandable syllabus tree
- right: tabs for `Notes`, `Questions`, `MCQs`, and `Progress`

Tabs do not navigate to new routes. The subject page keeps the syllabus tree stable while changing the right-side content panel.

### Topic Page

The topic page acts as a **chapter overview**:

- progress bar + weak-subtopic highlight
- sectioned subtopic list (✅ done / 🔴 weak / ⚪ not started)
- “Continue where you left” CTA into the next subtopic

Detailed notes + answer-writing happen on the subtopic page.

### Practice Page

`/practice` is a light aggregator, not a duplicate workspace.

It shows:

- today’s question
- weak topics
- mixed MCQ drill entry points

### Revision Page

`/revision` contains:

- due flashcards
- reveal / self-check / reschedule flow
- weak topics to revisit next

## 7. Clean Answer Writing And OCR UX

### Answer Writing Screen

The answer-writing view is intentionally narrow in scope.

It shows only:

- question
- answer textarea
- word count
- ideal word target
- submit button

### OCR Upload Flow

OCR is separated from writing so the writing surface stays clean.

When uploading a sheet:

- image preview is shown
- file readiness is visible with a green ready state
- `Read answer sheet` runs deterministic normalization / OCR extraction
- extracted text can be moved into the answer box
- if reading fails, the UI keeps the preview and shows:
  - a friendly failure message
  - retry upload
  - paste text manually

### Input Error Handling

The backend returns structured input errors:

```json
{
  "error_type": "INPUT_INVALID",
  "reason": "empty_or_unreadable",
  "suggestions": [
    "Write complete sentences",
    "Avoid empty input",
    "Retry submission"
  ]
}
```

The frontend does not advance to evaluation on these errors. It keeps the user on the writing screen and highlights the answer box.

## 8. Evaluation Engine

The evaluation engine remains deterministic and backend-controlled.

### Non-Negotiable Rules

- LLM never assigns marks
- all marks are computed in backend logic
- temperature is `0` for structured evaluator and guidance calls
- evaluator outputs are strict JSON only

### Pipeline

1. normalize answer text or OCR text
2. generate or load the backend reference concept space
3. run structured evaluator passes for content, reasoning, and directive handling
4. compute similarity and concept coverage
5. extract deterministic writing signals
6. score through rule-based backend logic
7. compress and calibrate the final score

### Relevance Dominance

If `relevance_score < 0.7`:

- coverage reward is heavily suppressed
- a strong penalty is applied
- irrelevant polished writing is prevented from scoring well

### Structure Dominance

Structure is explicitly weighted above raw coverage:

- strong structure receives a boost
- weak structure receives a meaningful penalty

### Impression Score

The current grounded formula is:

```text
0.30 * readability_score
+ 0.25 * structure_score
+ 0.20 * relevance_score
+ 0.15 * conciseness
+ 0.10 * coherence
```

This value is bounded between `0` and `1` and includes alignment logic so high structure does not create an implausibly low first-read impression.

### Overwriting Penalty

If the answer exceeds `1.5x` ideal length while relevance is still weak, a strong multiplier penalty is applied.

## 9. Scoring Philosophy

The scoring philosophy is intentionally conservative.

- strong answers are compressed into realistic UPSC ranges
- relevance outranks surface polish
- structure outranks raw point dumping
- impression matters, but only through deterministic signals
- penalties are visible rather than hidden
- consistency matters more than stylistic flourish

The system is trying to feel like a serious examiner plus mentor, not a generosity-biased AI grader.

## 10. Mentor Feedback Layer

The evaluation response includes short, production-facing feedback blocks:

- `score_band`
- `answer_gap_summary`
- `strengths`
- `top_improvements`
- `penalty_reasons`
- `ideal_answer_directions`
- `next_action`

This is deliberately concise. The UI favors fast comprehension over long explanations.

## 11. Progress, Streak, And Daily Question

### Progress Tracking

The backend stores and refreshes:

- average score
- exam-wise performance
- subject-wise performance
- topic-wise performance

Progress deltas are smoothed through a moving average of the last five scores to avoid noisy swings.

### Daily Question Mix

The daily question selector uses deterministic mixing:

- 70% weak topics
- 20% moderate topics
- 10% rotation

When history is still thin, it falls back to a weak visible topic or a rotating seeded prompt.

### Streak

The system tracks a minimal `daily_answer_streak`.

- answering today increments or maintains the streak
- missing a day resets it

## 12. Notes, MCQs, Flashcards, And Revision

### Subtopic Notes

The product layer uses `subtopic_notes` for exam-ready notes and an “Apply now” loop per subtopic.

### Detailed Revision Notes

The existing notes engine still exists and can generate deeper revision bundles from the topic page on demand.

### MCQs

Each topic is seeded with at least five deterministic MCQs.

MCQ attempts are evaluated through backend submission logic, stored in attempts/performance tables, and fed back into progress and revision.

### Flashcards + SRS

Flashcards remain topic-scoped and feed the revision queue.

SRS data tracks:

- ease factor
- interval days
- next review
- correct count
- incorrect count

## 13. Backend API Contract

### Core Study Endpoints

- `GET /catalog/tree?exam_id=...`
- `GET /study/dashboard?exam_id=...`
- `GET /study/subject/{subject_id}?exam_id=...`
- `GET /study/topic/{topic_id}`
- `GET /study/subtopic/{subtopic_id}/notes`
- `GET /study/practice?exam_id=...`
- `GET /study/revision?exam_id=...`
- `POST /study/ocr-preview`
- `POST /study/mcq-attempt`

### Existing Evaluation Endpoints

- `POST /evaluate`
- `GET /daily-question`
- `POST /generate-notes`
- `POST /generate-flashcards`
- `GET /review-cards`
- `POST /update-progress`

### Evaluation Response Additions

The evaluation payload includes:

- `impression_score`
- `score_band`
- `penalty_reasons`
- `answer_gap_summary`
- `top_improvements`
- `strengths`
- `ideal_answer_directions`
- `progress_delta`
- `next_action`
- `streak`

### Dashboard Response Shape

`GET /study/dashboard` returns:

- selected exam
- available exams
- summary metrics
- continue target
- subject cards for the selected exam

### Topic Response Shape

`GET /study/topic/{topic_id}` returns:

- exam
- subject
- topic
- seeded topic notes status
- practice mode
- practice questions
- PYQs
- MCQs
- flashcard preview
- topic progress
- chapter progress + sectioned subtopic list (for chapter UX)

## 14. Frontend Architecture

### App Providers

The web app uses:

- `AuthProvider`
- `ExamProvider`

### Key Web Files

- `frontend/app/dashboard/page.tsx`
- `frontend/app/subject/[subjectId]/page.tsx`
- `frontend/app/topic/[topicId]/page.tsx`
- `frontend/app/practice/page.tsx`
- `frontend/app/revision/page.tsx`
- `frontend/components/app-shell.tsx`
- `frontend/lib/exam-context.tsx`
- `frontend/lib/hooks.ts`

### Design Principles

- one page = one purpose
- one primary action per screen
- whitespace over border clutter
- evaluation shown only after submission
- study anchored in syllabus order, not floating widgets

## 15. Mobile

The mobile app remains in the repository and continues to use the existing evaluation-focused UPSC flow and backend contracts.

The exam-context-driven product shell described above is currently implemented on the web app.

## 16. Setup

### Backend

```bash
make backend-install
make backend-dev
```

Optional Turso extras:

```bash
make backend-install-turso
```

### Frontend

```bash
make frontend-install
make frontend-dev
```

Production build:

```bash
make frontend-build
make frontend-start
```

### Environment

Set at minimum:

```env
JWT_SECRET=replace_with_a_long_random_secret
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
FRONTEND_ORIGIN=http://localhost:3000
```

Optional Gemini/Turso settings remain supported through `.env`.

## 17. Verification

The current implementation was verified with:

```bash
./.venv/bin/python -m compileall backend/app
./.venv/bin/python -m unittest discover -s backend/tests -v
cd frontend && npm run typecheck
cd frontend && npm run build
```

These checks cover:

- upgraded deterministic scoring
- progress smoothing
- daily-question continuity
- syllabus-backed catalog counts
- structured error handling
- new App Router pages and redirects
