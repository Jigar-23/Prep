## 2026-04-17 Continuous Improvement Loop

### What was done
- Added `user_topic_weakness` persistence to track per-user per-topic weak dimension counts and repeated mistake streaks.
- Implemented `backend/app/services/improvement_service.py` to:
  - detect weakest dimension after each evaluation (structure/relevance/content)
  - track repeated mistakes and consecutive repetition
  - provide a user-level summary for dashboard
  - provide a focus signal for daily question selection
- Updated UPSC evaluation response to include loop signals (post-processing only):
  - `weakest_dimension`, `consistent_weakness`, `repeated_mistake`, `repeated_mistake_count`, `pressure_message`
  - replaced `next_action` content with a weakness-prioritized action (retry same question / similar question)
- Updated daily question behavior to prioritize the focus dimension when available (`Today's focus: <dimension>`).
- Upgraded dashboard UI to show two sharp signals immediately:
  - `Your Weakest Area`
  - `Most Repeated Mistake`
- Surfaced reinforcement + pressure-loop messaging in evaluation UI on both web and mobile.

### Why it was done
- The system needed to move from one-off evaluation to a loop that forces repair of repeat weaknesses before progressing.
- Persisted tracking enables minimal but consistent signals across evaluation, daily focus, and dashboard without changing scoring.

### Impact
- Users now see “what they keep getting wrong” immediately after evaluation and on dashboard.
- Next action is no longer a generic progression hint; it prioritizes fixing the detected weak dimension.
- Daily question selection can align with the user’s weakest dimension to create a continuous repair loop.

### Files affected
- `backend/app/database.py`
- `backend/app/services/improvement_service.py`
- `backend/app/services/evaluation_engine.py`
- `backend/app/services/continuity_service.py`
- `backend/app/services/study_service.py`
- `backend/app/schemas.py`
- `frontend/lib/types.ts`
- `frontend/app/dashboard/page.tsx`
- `frontend/components/EvaluationPanel.tsx`
- `mobile/src/types.ts`
- `mobile/App.tsx`
- `README.md`
- `DEVLOG.md`

## 2026-04-17 Chapter → Subtopic learning hierarchy + Apply Now loop

### What was done
- Added persistence for subtopic-level learning:
  - `subtopic_notes` for exam-ready subtopic notes blocks
  - `user_subtopic_progress` for per-user subtopic status (not started / in progress / done) + weakness flag
  - `user_subtopic_weakness` for per-user subtopic weakness + mistake repetition signals
- Extended evaluation requests **without changing scoring logic**:
  - `/evaluate` now accepts optional `subtopic_id`
  - when `subtopic_id` is present, the existing evaluation output is used to update subtopic progress + weakness tracking
- Upgraded study APIs to expose chapter-style hierarchy (backward compatible):
  - `/study/topic/{id}` now includes `chapter_progress`, `sections`, `weak_subtopics`, `completed_subtopics`
  - added `/study/subtopic/{subtopic_id}/notes` to fetch (and auto-generate) structured subtopic notes
- Rebuilt the chapter learning UX in Next.js:
  - chapter page no longer shows full notes; it shows progress + sectioned subtopics with status indicators (✅/🔴/⚪)
  - added a subtopic notes page with an “Apply now” 150-word answer box wired to existing `/evaluate`
- Dashboard and practice alignment:
  - dashboard now prefers a single “Continue improvement loop” CTA that deep-links into a weakest subtopic when available
  - daily question payload can include an optional subtopic focus and links directly to that subtopic

### Why it was done
- UPSC prep needs chapter → subtopic granularity; chapter-level notes are too flat and not actionable.
- Moving notes to subtopics enables direct answer-writing practice and makes weakness repair precise (at the subtopic level).
- The “Apply now” loop forces the reading → writing → evaluation → retry cycle without breaking the existing evaluation engine.

### Impact
- Learning is now hierarchical and action-driven: users open a subtopic, read a ready framework, write 150 words, and get evaluated.
- Weakness signals can be tracked and surfaced at the subtopic level, enabling tighter practice targeting and retries.
- UI text density is reduced; hierarchy is clearer (Chapter > Section > Subtopic) with immediate status cues.

### Files affected
- `backend/app/database.py`
- `backend/app/schemas.py`
- `backend/app/routes/study.py`
- `backend/app/services/evaluation_engine.py`
- `backend/app/services/improvement_service.py`
- `backend/app/services/study_service.py`
- `backend/app/services/continuity_service.py`
- `backend/app/services/subtopic_notes_service.py`
- `frontend/lib/types.ts`
- `frontend/lib/hooks.ts`
- `frontend/app/topic/[topicId]/page.tsx`
- `frontend/app/topic/[topicId]/subtopic/[subtopicId]/page.tsx`
- `frontend/app/dashboard/page.tsx`
- `frontend/app/practice/page.tsx`
- `mobile/src/types.ts`
- `mobile/src/api.ts`

