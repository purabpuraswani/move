# MoveWell-AI — Final integration pass

Appendix to `docs/architecture.md`. Records what was connected in the final
pass, and what remains genuinely unverified. Written to be checkable: every
claim names the file that supports it, and anything not actually run is
labelled NOT VERIFIED rather than described as working.

---

## What was disconnected, and what closed it

The architecture was largely built. Three things were wired but unreachable,
and one was wired wrongly.

### 1. The orchestrator was unreachable from the UI

`POST /api/workflow/run` and `GET /api/workflow/latest` existed with **no
frontend caller anywhere in `src/`**. The only AI-output screen was
`/guidance` — the legacy Wellness Guide / Care Navigator pair — which the
dashboard actively promoted.

Closed by: `src/services/workflow.js`, `src/pages/PlanPage.jsx` (route
`/plan`), and `src/journey/stages.js`. `Dashboard.jsx`'s call-to-action now
routes to `/plan`; nothing in the application navigates to `/guidance`, and
`App.jsx` marks that route deprecated, kept only so an existing bookmark
resolves.

### 2. Every progress-triggered run returned HTTP 500

`_progress_inputs()` in `routes/workflow.py` returned `current_plan`,
`current_needs` and `nutrition_plan`. None is a `run_workflow()` parameter,
and they were splatted in with `**progress_kwargs`, so the call raised
`TypeError` before reaching the orchestrator. `tests/test_workflow_route.py`
never sent a `progress_trigger`, so nothing caught it.

Closed by: removing those three keys — `run_workflow()` already derives all
three from the User State it is handed (`orchestrator.py:449-463`).

Guarded by: `tests/test_workflow_route_progress.py`, which reads both
signatures by AST and fails if `_progress_inputs()` ever returns a key
`run_workflow()` does not accept. A second test fails if `run_workflow()`
gains `**kwargs`, since that would silently make the first test toothless.
**The guard was verified against the original bug** — re-introducing the three
keys makes it fail, restoring the fix makes it pass.

### 3. The nutrition loop never ran outside tests

`routes/workflow.py` never loaded food-log documents and never defined
comparison periods, so `findings["nutrition_progress"]` was always `None` in
the running application. The logic and its unit tests were real; the
production wiring was not.

Closed by: `_nutrition_periods()`, which derives two consecutive observation
windows from the active nutrition plan's own `created_at`, and the food-log
queries that fill them. Entries are deliberately **not** filtered by
`plan_id` at the query: `compute_food_log_adherence()` does that accounting
itself and reports another plan's entries separately, and filtering early
would make another plan's logging look like an absence of logging.

### 4. No assessment history reached the Progress Agent

The route passed only the latest assessment, so physical comparison always
returned NOT_ENOUGH_DATA.

Closed by: `assessments/store.py`'s `baseline_assessment()` (oldest session)
and `previous_assessment()` (the one before the latest). Baseline is defined
positionally and only ever read — nothing in that module can promote a later
session to baseline, so a reassessment adds a document and leaves the
comparison anchor where it was.

### 5. The exercise engines were dead code

`src/exerciseAssessment/` — the rep counter, the hold timer and their
per-exercise thresholds — was **imported by no page**. `/api/exercise-results`
had no caller. So no exercise result was ever produced, and the Progress
Agent's exercise-performance path could never fire in the real application.

The reason it was unreachable is recorded in `config.js` itself: each entry
declares a `signal`, but nothing turned a MoveNet frame into that signal.
That extraction was the missing link.

Closed by:

- `src/exerciseAssessment/signals.js` — deterministic geometry mapping
  MoveNet keypoints to each configured signal. No model runs per frame.
- `src/pages/ExercisePage.jsx` (route `/exercise/:exerciseId`) — demonstration,
  camera setup guidance, live metrics, completion.
- `src/services/exerciseResults.js` — submits the engine summary.
- `workflow/response.py` now returns `exercise_items` (`{id, name}`) alongside
  the existing `exercises` name list, so the plan screen can address an
  exercise. The existing field is unchanged and its tests still pass.

---

## Honest limits, stated rather than engineered around

**The calf raise is not camera-scored, deliberately.** Its configured signal is
a heel-raise angle. MoveNet's 17-keypoint model has no heel and no toe
keypoint — the ankle is the lowest point it estimates — so a heel lift of a
few centimetres is not observable. Producing a number for it would be an
invention dressed as a measurement. It is listed in `UNSUPPORTED_SIGNALS` with
a user-facing reason, and the page shows that reason instead of a score.

**These are 2D projections, not anatomical angles.** Each signal assumes the
camera view its exercise declares (`VIEW_GUIDANCE` in `ExercisePage.jsx`).
Filmed from the wrong angle the number is wrong, not merely noisy, which is
why the view is stated to the user as setup guidance.

**Thresholds remain unreviewed.** Every value in `config.js` is a system
decision, as that file already says. Nothing in this pass changed that status,
and no clinical review has happened.

**An unmeasurable recording is reported as unmeasurable.** `ExercisePage`
counts frames the extractor could not read; below half, the result is
submitted with status `invalid` and no measurements. A reading nobody could
make is not a score of zero, and the progress screen excludes `invalid`
results from its evidence count for the same reason.

**Absence of logging is not failure.** The server already distinguishes
NOT_LOGGED from NOT_ADHERED; the food-log and progress screens keep that
distinction in their wording.

---

## Privacy

Frames and keypoints stay in the browser. `ExercisePage` holds no frame
history — each frame is reduced to one number, pushed to the engine, and
discarded. What leaves the browser is the engine summary: counts, durations,
a completion fraction. `exercise_assessment/schema.py` independently refuses
anything resembling pose data, so this is enforced on both sides.

---

## Verification status

Run in this environment, for real:

| Check | Result |
|---|---|
| `tests/test_workflow_route.py` | 13 tests, 12 passed, 1 skipped (needs pymongo) |
| `tests/test_workflow_route_progress.py` AST guards | 2 passed; **verified to fail on the original bug** |
| `src/journey/__tests__/stages.test.js` | 10 passed |
| `src/exerciseAssessment/__tests__/signals.test.js` | 11 passed |
| Endpoint-to-caller audit | every endpoint has a caller except the deprecated `/api/guidance/*` |

NOT VERIFIED — requires the local machine:

- **`npm run build`.** npm's registry is blocked in this sandbox, so the new
  JSX was checked structurally, not compiled. This is the most important
  outstanding check.
- **Full backend suite** (`python -m unittest discover -s tests -v`). pymongo,
  fastapi and mcp are not installable here; database-backed tests self-skip.
- **Real-camera exercise run.** No camera in this environment. The chain is
  implemented end to end but has not been executed against a live webcam.
- **MCP runtime.** The `mcp` package is not installable here; the honest
  ImportError → 503 path is unchanged.
- **Live Gemini extraction** through the running app.

Nothing above should be described as working until those are run.
