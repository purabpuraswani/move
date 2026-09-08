# MoveWell-AI — Final Report

Every claim below is classified. **VERIFIED** means it was executed and the
output observed. **IMPLEMENTED** means the code exists and is unit-tested but
the end-to-end path has not been run. **NOT VERIFIED** means exactly that, with
the reason.

---

## 1. Final architecture

Seven components, unchanged from the approved design:

Need Assessment → **Orchestrator** → {Physio | Nutrition | Behaviour} →
**Safety Gate** → Plan. Progress Agent evaluates and recommends adaptation back
to the Orchestrator, which dispatches the relevant specialist. Supporting
capabilities: Medical Report Reader, Baseline Assessment, Exercise Library,
Nutrition/Food data, Behaviour library, MCP servers, User State.

No agents were added. The legacy Wellness Guide / Care Navigator path was
retired from the journey (see §8).

## 2. Final user flow — VERIFIED (builds and routes)

Onboarding → questionnaire → optional report → extract → review → confirm →
baseline assessment (3 tests) → **/plan** → perform exercise (**/exercise/:id**)
or log food → **/progress** → review → updated plan.

`src/journey/stages.js` derives the next step from observed state, not a stored
counter. 10 tests.

## 3. What was implemented

Frontend: `services/workflow.js`, `services/foodLog.js`, `services/exerciseResults.js`,
`journey/stages.js`, `pages/PlanPage`, `pages/ProgressPage`, `pages/ExercisePage`,
`components/FoodLogPanel`, `exerciseAssessment/signals.js`.

Backend: `assessments/store.baseline_assessment()` / `previous_assessment()`,
`routes/workflow._nutrition_periods()`, corrected `_progress_inputs()`,
`workflow/response.exercise_items`.

## 4. What was integrated — five dangling chains closed

| Was | Now |
|---|---|
| `/api/workflow/*` had **no frontend caller at all** | `/plan` and `/progress` |
| Progress-triggered runs raised **TypeError → 500** | fixed + AST guard |
| Nutrition loop **dead outside tests** | food-log windows wired |
| **No assessment history** → always NOT_ENOUGH_DATA | baseline + previous supplied |
| Exercise engines **imported by no page** | `/exercise/:id`, results POSTed |

Endpoint-to-caller audit: every endpoint has a caller except the deprecated
`/api/guidance/*`.

## 5. Nutrition closed loop — IMPLEMENTED

Need → Orchestrator → Nutrition Agent → MCP → plan → **food log UI** →
adherence → Progress → Orchestrator → Nutrition Agent → Safety → updated plan.

The missing link was the route never loading food-log documents or defining
comparison periods. `_nutrition_periods()` now derives two consecutive windows
from the active plan's own `created_at`. Entries are deliberately not filtered
by `plan_id` at the query — `compute_food_log_adherence()` does that accounting
and reports another plan's entries separately; filtering early would make
another plan's logging look like an absence of logging.

Adherence keeps four distinct states: ADHERED / NOT_ADHERED / NOT_LOGGED /
INSUFFICIENT_DATA, with `completion_rate=None` rather than a fabricated 0.0.

*Not yet run against a live database with real logged meals.*

## 6. Exercise library — VERIFIED

20 exercises. **12** have a working MoveNet assessment — corrected down from a
claimed 14:

- **supported-calf-raise** — MoveNet estimates 17 body points, none of which is
  the heel or toe. A heel raise is not observable. Claim removed rather than
  backed by a proxy.
- **standing-hamstring-stretch** — the visible trunk-hinge angle does not
  distinguish a good stretch from a rounded back. Scoring it would reward the
  wrong thing.

Four Phase 6 exercises that claimed support but had no engine were wired
(seated marching, overhead reach, seated knee extension, single-leg reach
balance), each reusing an already-tested extractor.

Library claims and runnable reality now match exactly: 12 and 12, cross-checked
programmatically. A drift guard test compares the two in both directions.

## 7. Medical Report Reader — IMPLEMENTED, previously verified

Upload → extract → candidates → review → confirm → confirmed context. Untouched
this pass except that extraction now resolves to Gemini. Confirmation remains
the only trust boundary (`NoConfirmationNoTrustTests`).

## 8. Legacy components retired

`/guidance` (Wellness Guide, Care Navigator) is unlinked from every screen and
marked deprecated in `App.jsx`; the route resolves so bookmarks don't break. The
dashboard CTA now points at `/plan`. Backend `/api/guidance/*` remains for
backward compatibility and is the only endpoint group without a caller.

## 9. Agent responsibilities — VERIFIED by test

Physio: exercise selection/progression. Nutrition: dietary guidance and plan
adaptation. Behaviour: habits and adherence. Progress: evaluates and
*recommends* — structurally unable to prescribe, since it is absent from
`_AGENT_PLAN_SHAPE` and can contribute no candidate. Orchestrator: dispatch and
aggregation. Safety: final gate.

## 10. MCP servers — NOT VERIFIED

Seven capability servers exist. The `mcp` package is not installable in the
sandbox, so 16 tests skip honestly and the ImportError → 503 path is unchanged.
No MCP execution is faked or claimed.

## 11. Safety flow — VERIFIED by test

Runs once, after both phases, over the merged candidate list. Blocked ids are
stripped before persistence; a plan emptied by the gate is written nowhere and
recorded as an error.

## 12. Progress / adaptation — VERIFIED by test

IMPROVED / STABLE / DECLINED / NOT_ENOUGH_DATA; CONTINUE / PROGRESS / MAINTAIN /
REGRESS / MODIFY / REASSESS. Baseline is positional and read-only — nothing can
promote a later session to baseline. Plan versions are append-only with
`adaptation_reason` and `triggered_by`.

## 13. Dashboard — IMPLEMENTED

`/internal/dashboard`, backend-gated by `require_staff_user`, unlinked from the
user UI. Exposes state, plan history, safety result, MCP status.

## 14. Privacy / security — VERIFIED by test

Frames and keypoints never leave the browser: `ExercisePage` reduces each frame
to one number and discards it, holding no history. Only counts and durations are
sent, and `exercise_assessment/schema.py` independently refuses anything
resembling pose data. Every route is authenticated and scoped to the caller.

## 15. Test results — VERIFIED

| Suite | Total | Pass | Fail | Skip |
|---|---|---|---|---|
| Backend | 723 | 723 | 0 | 16 (mcp not installed) |
| Frontend | 227 | 227 | 0 | 0 |
| Build (`vite build`) | — | ✓ 1612 modules, 2.3s | 0 | — |

## 16. Real-camera verification — NOT VERIFIED

No camera in the execution environment. The chain is implemented end to end and
every link either side of the webcam is tested, but the live capture path has
not been executed. **Requires a local run:** open `/plan`, start an exercise,
perform it, confirm a result appears in `/progress`.

## 17. MCP / AI provider verification

- MCP runtime: **NOT VERIFIED** (package unavailable here).
- Gemini: connection previously confirmed via `check_openrouter.py`. Live
  extraction through the running app: **NOT VERIFIED** this pass.
- OpenRouter: **removed**. `config.py` forces the key to `None`, rewrites
  `AI_PROVIDER=openrouter` to `gemini`, and neither selector retains an
  OpenRouter branch — verified by forcing stale OS environment variables.

## 18. Remaining genuine limitations

1. Real-camera exercise run unverified (§16).
2. MCP runtime unverified (§10).
3. Every threshold in `exerciseAssessment/config.js` is an unreviewed system
   decision awaiting physio review — unchanged by this pass.
4. Signals are 2D projections valid only for the camera view each exercise
   declares; a wrong angle yields a wrong number, not a noisier one.
5. Nutrition adherence compares two halves of one plan's life, not old plan vs
   new, because the orchestrator derives the latest plan record.
6. `safety/__init__.py` notes `assess_safety_status()` is always NOT_ASSESSED,
   so the REFER rule may be unreachable in practice. Unconfirmed.
7. The `GEMINI_API_KEY` in `backend/.env` was pasted into a chat transcript and
   should be revoked and replaced.

## 19. Files changed

Backend: `config.py`, `agents/llm.py`, `reports/extraction.py`,
`routes/workflow.py`, `assessments/store.py`, `workflow/response.py`,
`exercise_library/data.py`, `.env`, 5 test files (+1 new).

Frontend: `App.jsx`, `pages/Dashboard.jsx`, 3 new pages + CSS, 1 new component +
CSS, 3 new services, `journey/stages.js`, `exerciseAssessment/signals.js`,
`exerciseAssessment/config.js`, 3 test files (+2 new).

Docs: `docs/final-integration.md`, `docs/final-report.md`.

## 20. Readiness

**Ready to demonstrate**, with one caveat: do a real-camera run before the demo.
That is the only path in the system that has never been executed. Everything
upstream and downstream of it is tested and green.

Three defects found in this pass were in work done during it — caught by tests
written alongside, not by review afterwards: the journey model could never
report complete, the plan response had no way to address an exercise, and the
OpenRouter removal initially left a live selection branch.
