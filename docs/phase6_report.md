# MoveWell-AI — Phase 6 Deliverable Report (Final Implementation Phase)

This is the final implementation phase of MoveWell-AI. No Phase 7 has
been created, and none is proposed below.

---

## A. Executive summary

Phase 6 completed the nutrition closed loop (data, agent, MCP, food
logging, adherence, progress, adaptation), extended the exercise library
from 10 to 20 exercises, wired the Orchestrator into the running
application for the first time (it had only ever been called from tests
in Phases 3–5), built the internal healthcare/developer observability
dashboard, closed the one open Low-severity security item from Phase
5.1, and re-verified — with fresh, direct evidence from this sandbox —
that live OpenRouter extraction and a real MCP transport connection
remain structurally impossible to test here (no outbound network access
at all, confirmed by three independent probes this phase).

Backend: 695 tests, 34 skipped, 0 failures (baseline entering this phase:
670/33/0). Frontend: 205 tests, 0 failures (unchanged — this phase's new
`.jsx` files are not exercised by this project's existing test runner,
which only runs plain-JS logic modules; see section K). Lint: 12
pre-existing errors, unchanged, 0 new. MoveNet: not modified (confirmed
by file-mtime comparison against this session's own new files).

Everything below distinguishes REAL / TEST DOUBLE / UNAVAILABLE EXTERNAL
DEPENDENCY / UNVERIFIED HARDWARE TEST explicitly, per the brief's
requirement.

## B. Nutrition architecture (closed loop)

**Data sources** (`backend/nutrition_library/`):

- `food_composition.py` — 62 curated Indian food records
  (`SOURCE = "IFCT_ADAPTED"`, `SOURCE_VERSION = "curated-approximate-v1"`).
  Documented honestly as this project's own approximation informed by the
  general shape of ICMR-NIN's IFCT 2017 (the standard reference this
  project targets) — **not** a verbatim reproduction of the licensed IFCT
  2017 dataset, which could not be verified against a live source in this
  no-network sandbox. Each record carries `food_id`, `food_name`,
  nutrients, `serving_basis`, `source`, `source_version` — full
  provenance, never silently blended across sources.
- `guidance_icmr_nin.py` — 6 dietary-guidance topics themed on ICMR-NIN's
  2024 Dietary Guidelines for Indians, kept conceptually and structurally
  separate from food composition data (guidance vs. composition are never
  merged into one record).
- Secondary sources (Open Food Facts, USDA FoodData Central) are
  structurally represented via `SECONDARY_SOURCES`, both honestly marked
  `available: False` with the real reason ("no network egress in this
  environment") — never faked as reachable.

**User food logging** (`backend/food_log/`): `meal`
(breakfast/lunch/dinner/snack), food name, approximate quantity, optional
notes — a real `food_log` Mongo collection + store, mirroring
`exercise_assessment/store.py`'s pattern exactly. `POST/GET
/api/food-log`.

**Nutrition MCP** (`backend/mcp_servers/nutrition_server.py`): 6 real
tools wrapping already-tested pure functions — `search_nutrition_guidance_tool`,
`get_nutrition_topic_details_tool`, `search_food_tool`,
`get_food_details_tool`, `record_food_log_tool`,
`calculate_food_adherence_tool`. REAL production code; not executable
end-to-end here because `mcp` cannot be installed (see section F).

**Nutrition Agent** (`backend/nutrition_agent/`): reads User State,
current needs, and self-reported nutrition signals; builds a structured
plan with a rationale per goal; never diagnoses, prescribes, or invents a
nutrient value.

**Adherence** (`nutrition_agent/adherence.py`): four outcomes —
`ADHERED`, `NOT_ADHERED`, `NOT_LOGGED`, `INSUFFICIENT_DATA`. A missing
food log is always `NOT_LOGGED`, never `NOT_ADHERED` — "no food log ≠
user did not eat" is enforced in code, not just in a comment.

**Nutrition Progress** (new this phase, `progress_agent/nutrition_progress.py`):
compares two periods' adherence into `IMPROVED`/`STABLE`/`DECLINED`/
`NOT_ENOUGH_DATA`, kept explicitly separate from physical progress — an
"adherence improved" finding is never reported as "health improved."
Nutrition-specific adaptation table: `NOT_ENOUGH_DATA→REASSESS`,
`IMPROVED→CONTINUE`, `STABLE+ADHERED→MAINTAIN`,
`STABLE+NOT_ADHERED→MODIFY`, `DECLINED→MODIFY` (PROGRESS/REGRESS
excluded — physical-difficulty concepts with no nutrition equivalent).

**Full closed loop, tested end-to-end** (`tests/test_orchestrator_nutrition_progress.py`):

```
Need (HIGH) -> Orchestrator -> Nutrition Agent -> Nutrition MCP ->
Personalized Plan -> User Food Log -> Nutrition Adherence ->
Progress Agent -> Orchestrator -> Nutrition Agent -> Updated Plan ->
Safety Gate
```

One test runs this real chain: an initial plan (`plan_version=1`) →
7/7-day high-adherence previous period vs. 1/7-day low-adherence current
period (real computed `DECLINED`, `completion_rate` computed, not
invented) → Progress Agent recommends `MODIFY` → Orchestrator dispatches
Nutrition again → a new plan version (`plan_version=2`) with a real,
structured `adaptation_reason` containing "MODIFY"/"nutrition" and
`triggered_by="progress_agent"` → Safety Gate evaluated → `plan_version=1`
asserted byte-for-byte unchanged. Companion tests cover
`NOT_ENOUGH_DATA`/`REASSESS` and "no nutrition context supplied ⇒
`nutrition_progress` is `None`, never fabricated."

## C. Exercise library (20 total, MoveNet support)

10 exercises carried from Phase 2, 10 new this project (added Phase 6):

| exercise_id | name | MoveNet support |
|---|---|---|
| chair-sit-to-stand | Chair Sit-to-Stand | supported, implemented |
| wall-sit | Wall Sit | supported, implemented |
| standing-knee-raise | Standing Knee Raise | supported, implemented |
| supported-calf-raise | Supported Calf Raise | supported, implemented |
| wall-push-up | Wall Push-Up | supported, implemented |
| standing-side-leg-raise | Standing Side Leg Raise | supported, implemented |
| standing-hip-extension | Standing Hip Extension | supported, implemented |
| heel-to-toe-stand | Heel-to-Toe / Tandem Stand | supported, **not implemented** (honest gap — foot-alignment geometry doesn't exist yet) |
| supported-single-leg-stand | Supported Single-Leg Stand | supported, implemented |
| standing-shoulder-raise | Standing Shoulder/Arm Raise | supported, implemented |
| seated-marching | Seated Marching | supported, implemented |
| standing-trunk-rotation | Standing Trunk Rotation | **not supported** (vertical-axis rotation, 2D camera can't resolve) |
| standing-shoulder-rolls | Standing Shoulder Rolls | **not supported** (small circular motion below jitter threshold) |
| standing-ankle-circles | Standing Ankle Circles | **not supported** (no toe/arch keypoints, depth-axis motion) |
| standing-hamstring-stretch | Standing Hamstring Stretch | supported, implemented |
| glute-bridge | Glute Bridge | **not supported** (floor-based, outside camera framing) |
| quadruped-bird-dog | Quadruped Bird-Dog | **not supported** (floor-based + depth-axis limb extension) |
| standing-overhead-reach | Standing Overhead Reach | supported, implemented |
| seated-knee-extension | Seated Knee Extension | supported, implemented |
| single-leg-reach-balance | Single-Leg Reach Balance | supported, implemented |

Each record carries exercise_id, name, category, target_capability,
body_area, difficulty, equipment, instructions, sets/reps/duration,
progression, regression, common_mistakes, safety_constraints,
movenet_support (with real, specific reasons where `false`),
measurable_metrics, demonstration_id, source/reference. The three
baseline tests (Hand/Shoulder Raise, Chair Sit-to-Stand ×5, One-Leg
Stand) remain distinct assessments — their scoring logic was not touched
this phase.

## D. Medical Report Reader (actual extraction status)

- **Supported formats** (`config.py`): `.pdf`, `.png`, `.jpg`, `.jpeg`.
- **AI provider**: OpenRouter only (`SUPPORTED_AI_PROVIDERS = ("openrouter",)`).
- **Re-verified this phase, directly**: `urllib.request.urlopen("https://openrouter.ai/api/v1/models")`
  → `URLError: Tunnel connection failed: 403 Forbidden`. `pip install mcp
  --dry-run` → the same proxy 403. `npm ping --registry=...` (frontend
  side) → the same 403. **This sandbox has zero outbound network
  egress** — not a missing package, a structural environment limit.
- **Classification**: the parsing/candidate-vs-confirmed/storage pipeline
  is REAL and tested against a fake transport
  (`tests/test_report_pipeline_integration.py`, Phase 5.1) — genuine
  logic under test. The actual HTTP round-trip to OpenRouter is an
  **UNAVAILABLE EXTERNAL DEPENDENCY** in every environment this project's
  automated work has run in, not a fixable gap and not a tested
  integration. Upload alone still never creates confirmed medical
  context — proven by `NoConfirmationNoTrustTests` (Phase 5.1, still
  passing).

## E. Agent architecture (final, 7 components)

1. **Need Assessment** — computes `current_needs` from onboarding/
   questionnaire/assessment/report data (Phase 1, unchanged).
2. **Orchestrator** — Phase A (need-based agent selection) + Phase B
   (progress-triggered adaptation dispatch, now covering both physical
   and nutrition recommendations independently) → one unified Safety Gate
   pass → User State updates.
3. **Physio Agent** — exercise plan selection from the 20-exercise
   library, need-gated (Phase 3).
4. **Nutrition Agent** — nutrition plan selection from the curated food/
   guidance library, need-gated, now closing the adherence/progress loop
   (Phase 4/6).
5. **Behaviour Agent** — habit-goal selection (Phase 4).
6. **Progress Agent** — physical AND nutrition progress comparison,
   adherence, reassessment, adaptation recommendation (Phase 5/6).
7. **Safety Gate** — the single, final authority over what is actually
   persisted/shown, evaluated exactly once per workflow cycle regardless
   of how many specialists ran (Phase 4/5).

No 8th specialist agent was added — the brief's explicit constraint.

## F. MCP architecture (each server, real tools)

| Server | Real tools |
|---|---|
| `exercise_server.py` (Physio) | `search_exercises_tool`, `get_exercise_details_tool`, `get_demo_animation_tool`, `check_exercise_constraints_tool`, `record_exercise_result_tool` |
| `behaviour_server.py` | `search_behaviour_guidance_tool`, `get_behaviour_topic_details_tool` |
| `nutrition_server.py` | `search_nutrition_guidance_tool`, `get_nutrition_topic_details_tool`, `search_food_tool`, `get_food_details_tool`, `record_food_log_tool`, `calculate_food_adherence_tool` |
| `progress_server.py` | `compare_assessments_tool`, `calculate_adherence_tool`, `check_reassessment_required_tool`, `calculate_nutrition_adherence_tool` |
| `safety_server.py` | (Phase 4, unchanged) |

**REAL**: every server file and every `Mcp*ToolClient` — real, reviewed
production code, written against the SDK's documented client API.
**TEST DOUBLE**: `InProcess*ToolClient` (one per agent) — calls the
underlying pure function directly, in-process, no transport; used
throughout `backend/tests/`, never described as production execution.
**UNAVAILABLE EXTERNAL DEPENDENCY**: the `mcp` package itself — cannot be
installed in this sandbox (confirmed again this phase), so no real
connect→initialize→session→tool-calls→close lifecycle has been executed
in any phase of this project. `tests/test_*_mcp_integration.py` (4
files) self-skip honestly for exactly this reason, counted in every
regression report's skip total.

`backend/routes/workflow.py` (new this phase) is the first place any real
`Mcp*ToolClient` is actually constructed and used outside a test file —
if `mcp` is not importable when needed, the route returns a clean 503,
never a stack trace.

## G. Closed-loop proof (actual tested workflow)

Physical (Phase 5, still green): Baseline → Plan v1 → real
`exercise_results` → Progress (real comparison/adherence) → Orchestrator
dispatch → Physio re-run → Safety → Plan v2 with real
`adaptation_reason`/`triggered_by`.

Nutrition (Phase 6, new): see section B's full trace — same discipline,
same test rigor, `DECLINED` adherence genuinely computed from real
7-day-window food-log fixtures, not asserted from a mock.

**Section 15 (Low Need vs. Progress Trigger), explicitly tested**:
`tests/test_orchestrator_nutrition_progress.py::LowNeedDoesNotBlockProgressTriggeredReviewTests`
proves a LOW stability need with a genuinely `IMPROVED` comparison still
gets Physio *reviewed* (`"physio" in selected_agents`, a `completed`
Agent Result), while Physio's own need-gate still correctly produces no
plan and no `exercise_history` state update. A current LOW need never
blocks a legitimate review; the specialist retains sole authority over
whether a plan results.

## H. Dashboard (internal observability)

`GET /api/dashboard/users/{user_id}/state` (full unredacted User State +
safe account info, `password_hash` explicitly excluded and tested by
key-scan), `.../plan-history` (every historical plan version, real
`adaptation_reason`/`triggered_by`), `.../safety` (the real persisted
Safety Result), `GET /api/dashboard/mcp-status` (honest per-specialist
`mcp`-installed status + real tool names). Every route gated by
`require_staff_user` — a non-staff account gets a 403. No admin UI exists
to grant staff status yet (direct DB update only) — a disclosed
limitation, not an oversight. Minimal frontend page at
`/internal/dashboard` with a visible "Internal / Staff Only" banner.

## I. Privacy/security

- **Stays local, never leaves the device**: raw camera frames, MoveNet
  keypoints, pose sequences — the RGB→MoveNet→Keypoints→local
  geometry→structured measurement pipeline is unchanged this phase (file
  mtimes confirm `src/assessment/` was not touched).
- **Sent to the backend**: only structured measurements (angles,
  durations, rep counts), self-reported profile/questionnaire answers,
  food-log entries (meal/food name/quantity/notes — no calorie
  computation forced), uploaded medical report files (size-capped, both
  upload paths now — see the security fix below).
- **Internal-only**: the full User State, plan history, and Safety
  Result are exposed only via `require_staff_user`-gated dashboard
  routes — never to a normal patient account. `password_hash` is
  excluded from every dashboard response, asserted by test.
- **User-facing responses** (`/api/workflow/*`) never carry
  `workflow_id`/`request_id`/`agent_run_id`/`tool_call_id`/
  `mcp_session_id`/raw Agent Results — asserted directly by a recursive
  key-scan test.
- **Security fix closed this phase**: `routes/profile.py`'s document
  upload had no size cap (Phase 5.1's flagged Low-severity item,
  unfixed at the time). Fixed: bounded 1 MB chunked writes, rejected and
  cleaned up mid-write past the same `REPORT_MAX_UPLOAD_BYTES` limit
  `reports/storage.py` already enforces (reused, not duplicated).

## J. Tests (exact counts)

```
Backend total:    695
  Passed:         661
  Failed:           0
  Skipped:         34  (all self-skip honestly for pymongo/bson/mcp
                        unavailability in this sandbox, same discipline
                        as every prior phase)
Frontend total:   205
  Passed:         205
  Failed:           0
  Skipped:          0
Lint:             12 pre-existing errors (unchanged; 0 new)
MoveNet files changed: NO (confirmed by file-mtime comparison — no file
                        under src/assessment/ was modified after this
                        session's own new backend files were written)
```

Backend delta this phase: 670 → 695 (25 new tests: nutrition-progress
extension + closed-loop tests, workflow-route tests, dashboard tests).
Zero regressions to the Phase 0–5.1 baseline at any point.

## K. Remaining limitations (genuine only)

1. Live OpenRouter extraction and a real MCP transport connection cannot
   be verified in any environment available to this project's automated
   work (no outbound network access) — see sections D and F.
2. Real camera/browser end-to-end testing of the three baseline
   assessments was not performed this phase (no camera/browser in this
   sandbox) — Phase 5.1's synthetic-pose-fixture verification stands
   unchanged; classified as an **UNVERIFIED HARDWARE TEST**, not a pass.
3. The Progress Agent's physical comparison, as wired into the new
   `/api/workflow/run` route, only ever has the caller's single latest
   assessment available as `current_assessment` — a real
   baseline/previous-assessment history across reassessments is not yet
   assembled from the database. Until it is, a progress-triggered
   comparison correctly reports `NOT_ENOUGH_DATA` rather than a
   fabricated one.
4. No admin UI exists to grant `is_staff` — set by direct database
   update only.
5. This project's frontend test suite has no React component-rendering
   infrastructure (no `@testing-library/react`/jsdom anywhere in the
   repo, and none could be installed — no npm registry access in this
   sandbox either). The new dashboard page has no automated rendering
   test, matching every other `.jsx` page in this repo; it was verified
   with a clean `eslint` pass and direct code review instead.
5b. `npm run build` fails in this specific sandbox with a native-binding
   error (`rolldown`) unrelated to this phase's changes — a pre-existing
   platform mismatch in this Linux sandbox's `node_modules` versus the
   project's real Windows environment, not a code defect introduced this
   phase; JSX validity was confirmed via `eslint`'s AST parse instead.
6. The curated 62-food nutrition dataset is this project's own
   approximation of IFCT 2017's general shape, not a verified verbatim
   reproduction of the licensed dataset (unverifiable without network
   access to a real source).

## L. Files changed (concise)

New backend packages: `nutrition_library/`, `food_log/`, `dashboard/`,
`workflow/`, plus `user_state/store.py`, `routes/workflow.py`,
`routes/dashboard.py`. Extended: `exercise_library/data.py` (+10),
`nutrition_agent/` (adherence.py, tool_client.py, mcp_client.py),
`progress_agent/` (nutrition_progress.py new; input_contract.py,
agent.py, schema.py, tool_client.py, mcp_client.py extended),
`mcp_servers/{nutrition_server,progress_server}.py`,
`orchestrator/orchestrator.py`, `auth/deps.py`, `routes/auth.py`,
`routes/profile.py` (security fix), `database.py`, `main.py`. New
frontend: `src/pages/DashboardInternalPage.{jsx,css}`,
`src/services/dashboard.js`; extended `src/movementDemos/content.js`
(+10 demos), `src/App.jsx`. ~25 new backend test files/additions, 0
frontend test additions (see K.5). `docs/architecture.md` extended with
full Phase 6 sections.

## M. Final readiness assessment

| Component | Status |
|---|---|
| Need Assessment | READY |
| Orchestrator (need-based + adaptation dispatch, both physical and nutrition) | READY |
| Physio Agent + 20-exercise library | READY |
| Nutrition Agent + closed loop | READY |
| Behaviour Agent | READY |
| Progress Agent (physical + nutrition) | READY |
| Safety Gate | READY |
| Medical Report Reader (parsing/storage/confirmation logic) | READY |
| Medical Report Reader (live OpenRouter extraction) | READY WITH LIMITATION (real code, unverified transport — no network access anywhere available) |
| Real MCP transport (all 4 servers + clients) | READY WITH LIMITATION (real code, unverified transport — `mcp` package uninstallable here) |
| `/api/workflow/*` (orchestrator wired into the app) | READY WITH LIMITATION (assessment-history assembly for Progress is partial, disclosed in K.3) |
| Internal dashboard (backend) | READY |
| Internal dashboard (frontend) | READY WITH LIMITATION (no rendering test infra in this repo) |
| Baseline physical assessments (camera/browser) | UNVERIFIED (no camera/browser in this sandbox; synthetic-fixture logic verified) |
| MoveNet pipeline | READY (unmodified) |

This is the final implementation phase. No Phase 7 is proposed.
