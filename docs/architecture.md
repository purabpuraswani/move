# MoveWell-AI — agentic architecture (living document)

This document tracks the agentic architecture as it is actually built, phase
by phase. It is updated in place as each phase lands; it does not accumulate
one file per phase. Phase 0 built the shared foundation
(`backend/user_state/`, `backend/orchestration/`,
`src/movementDemos/`). Phase 1 added the Need Assessment layer. Phase 2,
appended at the end of this document, adds the real MCP foundation, the
Exercise MCP Server and capability, the Exercise Library, thirteen movement
demonstrations, and the deterministic Exercise Movement Assessment
foundation.

```
User State  ->  Need Assessment  ->  Need Profile  ->  User State.current_needs
```

```
Exercise Library  <-- Exercise MCP Server (tools) <-- (a future Physio Agent)
        |
        v
 Movement Demonstration (src/movementDemos)   Exercise Assessment Engine (browser)
```

Still nothing past this point: the Orchestrator that reads `current_needs`
to decide which specialist agents run, the specialist agents themselves
(Physio, Nutrition, Behaviour, Progress, Safety/Referral), and any MCP
server beyond the Exercise MCP Server. Those remain later phases.

## What data is used

The Need Assessment (`backend/need_assessment/`) reads a User State
(`backend/user_state/schema.py`) — nothing else. It does not query the
database, call a model, or read a request directly; `assemble_need_profile()`
takes a User State dict and returns a Need Profile dict, which keeps it
deterministic and testable without any of that machinery.

Four User State sections currently carry real data, and each is used the way
its own section documents:

- **`physical_assessment`** — the three baseline tests' stored measurements
  (shoulder elevation angles, sit-to-stand completion time, one-leg-stand
  hold durations), plus, as of Phase 1, each test's `quality`,
  `invalidReasons` and `attempts` (added to `user_state/schema.py` this phase
  — see "Files changed" in the Phase 1 report — so the Need Assessment can
  reason about how much confidence a measurement deserves, not only what the
  number was).
- **`questionnaire`** — the onboarding answers about sitting time, screen
  time, exercise days/minutes. This is what `behaviour_need` is derived from.
  It is deliberately not the `behaviour` section (see below).
- **`medical_context`** — read only for whether it is *present*, never for
  its content. See "How confirmed medical context is handled" below.
- **`basic_profile`** — not currently used by any need dimension; present in
  the User State for a future dimension or specialist agent to use.

Everything else in the User State (`lifestyle`, `nutrition`, `behaviour`,
`exercise_history`, `adherence`, `progress`, `safety`) is still an unpopulated
placeholder from Phase 0 — nothing in Phase 1 invents data for these. Where a
Need Profile dimension has no real source (nutrition, safety), it always
reads `NOT_ASSESSED`, never a guessed level.

## The `questionnaire` / `behaviour` distinction, made explicit

The User State has both a `questionnaire` section (raw onboarding answers,
already populated) and a `behaviour` section (reserved for future adherence
tracking — whether a user *follows* a plan over time — not yet collected).
`behaviour_need` in the Need Profile is derived from `questionnaire`, because
that is the data that actually exists. Once real adherence tracking exists,
it will very likely refine `behaviour_need` further, but that is a
Behaviour-Agent-phase change, not a Phase 1 one.

## How each need is derived

Every rule lives in `backend/need_assessment/rules.py`, one function per
dimension, each a pure function of the User State. All thresholds are named
constants at the top of that file, and every one of them is commented as a
**system decision threshold — not a clinical cutoff**. None of them are
copied from `src/assessment/config/protocol.js` (whose own numbers are pose-
detection parameters, explicitly not clinical norms either) and none come
from a medical guideline. A physio/healthcare reviewer should treat every
number below as a draft to correct.

| Dimension | Source | Level rule (system thresholds) |
|---|---|---|
| `mobility_need` | Shoulder (hand/shoulder raise) test, lowest observed elevation across sides | `< 60°` → HIGH, `< 90°` → MEDIUM, `>= 90°` → LOW. A ≥20° left/right difference is added as evidence regardless of level. |
| `stability_need` | One-leg-stand test, shortest valid hold across sides | `< 5s` → HIGH, `< 15s` → MEDIUM, `>= 15s` → LOW. |
| `functional_movement_need` | Chair sit-to-stand ×5, completion time | `> 15s` → HIGH, `> 10s` → MEDIUM, `<= 10s` → LOW. |
| `behaviour_need` | Questionnaire: `daily_sitting_hours`, `daily_screen_hours`, `exercise_days`, `exercise_days × exercise_minutes` | Each of the four crosses its own threshold (8h, 8h, <2 days/week, <90 min/week) or not; the fraction that do sets the level (>2/3 → HIGH, >1/3 → MEDIUM, else LOW). The level adapts to however many of the four fields are actually answered. |
| `nutrition_need` | none | Always `NOT_ASSESSED` — the application collects no nutrition information. |
| `exercise_need` | Composite of the three physical dimensions above plus `behaviour_need` | HIGH if any contributing dimension is HIGH; MEDIUM if any is MEDIUM; LOW if all assessed contributors are LOW; `NOT_ASSESSED` only if nothing at all contributed. |
| `safety_status` | none (see below) | Always `NOT_ASSESSED` in Phase 1. |

Each entry also carries a `score` (0–1, rounded to 2 decimal places — no
invented precision beyond what a completed test's own numbers support) and a
`confidence` (`NONE`/`LOW`/`MEDIUM`/`HIGH`, based on how much of the relevant
test actually completed — e.g. both sides of the balance test vs. only one).

## Need vs. diagnosis

Every dimension is phrased as an intervention-need signal, not a clinical
finding: `stability_need = HIGH` and its evidence strings say what was
*measured* ("shortest held stance: 3.2 seconds, camera-timed, not a clinical
balance screen") and never what the user *has*. There is no code path in
`rules.py` that produces or references a named condition (a balance
disorder, a shoulder pathology, a mobility disease). This is enforced by
convention (the evidence strings are written this way) rather than by a
runtime filter — see "known limitations" below.

## Missing data handling — `NOT_ASSESSED` is not `LOW`

Every dimension function starts by checking whether it has anything to work
with, and returns `NOT_ASSESSED` with a specific reason if not — before any
threshold logic runs. `need_assessment/schema.py` enforces this at the type
level: `validate_need_entry()` refuses a `NOT_ASSESSED` entry that carries a
score or a confidence other than `NONE` (there is nothing to score or be
confident about), and refuses an assessed entry (`LOW`/`MEDIUM`/`HIGH`) with
no evidence or with confidence `NONE` (an assessed level always has to point
at what assessed it). This is not just documentation — the four
`MissingAndPartialDataTests` and the dedicated nutrition/safety tests in
`backend/tests/test_need_assessment_rules.py` and
`test_need_assessment_assembly.py` exercise exactly this, including a
brand-new, fully-empty User State producing an all-`NOT_ASSESSED` profile
without raising.

## How confirmed medical context is handled

`medical_context` is read for **presence only** — `assess_safety_status()`
notes, as evidence text, that confirmed medical information exists on file,
and explicitly states that it was not used to derive the status. No need
dimension reads any *value* out of `medical_context`, confirmed or not, so
there is no path by which an unconfirmed report extraction could influence a
result even by accident: `user_state.schema.build_user_state()` only ever
receives `confirmed_values_for_user()`'s output in the first place (a Phase 0
invariant, unchanged), and Phase 1 adds no new way to read a report.
`test_need_assessment_assembly.MedicalContextBoundaryTests` checks both that
confirmed medical context text never leaks into any dimension's evidence and
that adding it to an otherwise-identical User State does not change any
level.

## Safety status

`safety_status` is always `NOT_ASSESSED` in Phase 1, on principle, not as a
placeholder oversight: the project has no validated, curated escalation
rules yet (that is the dedicated Safety/Referral system, a later phase), and
inventing one from whatever data happens to be available would be exactly
the kind of unvalidated medical judgment the project's safety principle
rules out. `NOT_ASSESSED` here reads correctly as "no safety screening has
been performed" — never as "assessed as safe."

## How the result will be consumed later

`need_assessment/assessment.py`'s `apply_need_profile()` is the only
function that writes to `User State.current_needs`, and it does so by
returning a new state (the User State stays immutable end to end — nothing
in Phase 0 or Phase 1 mutates a state dict in place). The eventual
Orchestrator (Phase 3) is expected to read `current_needs.data` and decide
which specialist agents to run from the per-dimension `level` — e.g. only
activate the Physio Agent when `mobility_need`, `stability_need` or
`functional_movement_need` is `MEDIUM`/`HIGH`, and never activate a
Nutrition Agent while `nutrition_need` stays `NOT_ASSESSED`. Phase 1
deliberately does not build that decision logic — it only guarantees the
Orchestrator will have something explainable to decide from.

## Known limitations (carried into Phase 2 planning)

- Thresholds are first-draft system decisions, not physio-reviewed. They
  should be a specific, named review item before this is used for anything
  beyond internal development.
- The "need vs. diagnosis" separation is a writing convention in
  `rules.py`, not a runtime check. A future change to that file could
  reintroduce diagnostic language without any test catching it; a
  dedicated lint/test for banned medical-condition vocabulary in evidence
  strings would close that gap and is worth adding before Phase 2.
- `exercise_need`'s composite rule folds four other dimensions' *levels* and
  *scores* together with a simple max/average; it is the least
  independently-evidenced dimension and the most likely to need rework once
  a real Physio Agent exists to reason about exercise need directly.

---

# Phase 2 — MCP foundation, Exercise MCP, Exercise Library, Demonstrations, Movement Assessment

Phase 2 does not touch `user_state`, `orchestration/ids.py`,
`orchestration/agent_result.py`, or `need_assessment` — it builds
alongside them, reusing `orchestration/ids.py` for every MCP tool call's
trace metadata and deliberately leaving `agent_result.py`'s closed
`KNOWN_AGENT_IDS` vocabulary untouched (no agent exists yet to add to it).

## MCP foundation (`backend/mcp_servers/`)

- **SDK**: the official `mcp` package (PyPI), via
  `mcp.server.fastmcp.FastMCP` and its `@tool()` decorator.
- **Protocol version**: not hardcoded anywhere in this codebase — it is
  negotiated by the SDK's own `initialize` handshake, per the MCP spec.
  Pinning a version number here would just be a second, driftable copy of
  what the SDK already tracks correctly.
- **Transport**: Streamable HTTP, not stdio — chosen specifically because
  it has a real, protocol-level `Mcp-Session-Id`. stdio has no equivalent
  concept, which would leave Phase 0's `mcp_session_id` field permanently
  fake. Streamable HTTP is stateful: a client calls `initialize`, receives
  a session id, and reuses it across subsequent tool calls until the
  session is closed or expires — the server never mints a session id
  itself outside that handshake, and this codebase never fabricates one
  either (`orchestration.ids.new_mcp_session_id()` still always returns
  `None` unless a real transport session hands one in).
- **Process model**: the Exercise MCP Server runs standalone
  (`python -m mcp_servers.exercise_server`), not mounted into the existing
  FastAPI app. Mounting an MCP server into an existing ASGI app is possible
  with this SDK but the exact call is version-sensitive, and guessing at it
  without being able to run it in this sandbox (see Disclosure below) would
  be exactly the kind of unverified code this project's rules forbid.
  Running standalone needed no such guess.
- **Observability**: `backend/mcp_servers/observability.py`'s
  `tool_call_metadata()` derives a tool-call `TraceContext` from
  `orchestration.ids.start_tool_call()` and returns it as the `metadata`
  key every tool result carries — the same ids Phase 0 defined, not a
  parallel scheme.

### Disclosure: `mcp` could not be installed or run in this sandbox

Neither this sandbox's shell nor the connected device's shell has PyPI
network access (confirmed directly: `pip download mcp` and a raw `curl` to
`pypi.org` both failed). `exercise_server.py` is written against the `mcp`
package's documented, stable public API from training knowledge, its
import is guarded so a missing `mcp` fails with a clear, actionable
`ImportError` rather than a crash or — worse — silently fake behavior, and
`backend/tests/test_mcp_exercise_server.py` is written to **skip itself**
(via `unittest.skipUnless`), not fake-pass, when `mcp` is unavailable. This
has been verified directly in this sandbox: the import raises the intended
message, and the domain logic every tool wraps is separately, fully tested
without `mcp` at all (`test_exercise_catalog.py`,
`test_exercise_assessment_schema.py`). Before this server is used for
real, it needs `pip install mcp` inside the project's actual `.venv` and a
run of `test_mcp_exercise_server.py` there to confirm the SDK-facing
assertions (tool discovery, real session behavior) for real.

### Exercise MCP capability — implemented tools

| Tool | Wraps | Returns |
|---|---|---|
| `search_exercises_tool` | `exercise_library.catalog.search_exercises` | matching exercises + count |
| `get_exercise_details_tool` | `exercise_library.catalog.get_exercise_details` | one exercise's full document |
| `get_demo_animation_tool` | `exercise_library.catalog.get_exercise_details` | the exercise's `demonstration_id`, naming that it renders client-side |
| `check_exercise_constraints_tool` | `exercise_library.catalog.check_exercise_constraints` | safety-relevant fields only (equipment, safety constraints, common mistakes, difficulty) |
| `record_exercise_result_tool` | `exercise_assessment.schema.record_exercise_result` | the validated, cleaned result, or a refusal |

Every tool returns a plain dict with a `metadata` key
(`tool_call_metadata()`'s output); an unknown exercise id or an invalid
result is returned as `{"error": ..., "metadata": ...}`, never a crash and
never a silent best guess.

## Exercise Library (`backend/exercise_library/`)

Ten exercises, sourced from NIA Go4Life
(`go4life.nia.nih.gov/exercise`) and the CDC STEADI 4-Stage Balance Test —
both verified as real, currently-published sources before being cited, not
recalled from memory and assumed correct:

1. Chair Sit-to-Stand (`chair-sit-to-stand`)
2. Wall Sit (`wall-sit`)
3. Standing Knee Raise (`standing-knee-raise`)
4. Supported Calf Raise (`supported-calf-raise`)
5. Wall Push-Up (`wall-push-up`)
6. Standing Side Leg Raise (`standing-side-leg-raise`)
7. Standing Hip Extension (`standing-hip-extension`)
8. Heel-to-Toe / Tandem Stand (`heel-to-toe-stand`)
9. Supported Single-Leg Stand (`supported-single-leg-stand`)
10. Standing Shoulder/Arm Raise (`standing-shoulder-raise`)

Each entry's data model (`exercise_library/schema.py`) mirrors the
discipline of `assessments/schema.py`: a closed vocabulary for category,
difficulty, target capability (deliberately named to match
`need_assessment.NEED_DIMENSIONS` — `mobility`, `stability`,
`functional_movement`, plus `strength`, which the Need Profile does not
track separately) and target body area; required progression/regression
text; and a `movenet_support` block naming exactly which metrics an
exercise's MoveNet-based assessment produces. **Nine of the ten are marked
`implemented: true`; `heel-to-toe-stand` is honestly marked
`implemented: false, metrics: []`** — a tandem/narrow stance is not yet
distinguished from a normal stance by the existing pose logic, and Phase 2
does not invent that detection to avoid leaving this gap unmarked.
`measurable_metrics` is enforced to exactly match `movenet_support.metrics`
— the two can never silently disagree.

`backend/exercise_library/catalog.py` provides the read-only query layer
(`search_exercises`, `get_exercise_details`, `check_exercise_constraints`)
the MCP tools call directly; none of it makes a recommendation or a safety
judgment about a specific user — reading a Need Profile to decide what a
given user should do is future Physio Agent work.

## Exercise Result schema (`backend/exercise_assessment/`)

Mirrors `assessments/schema.py`'s two-tier privacy filter exactly: a
forbidden-substring check (`video`, `image`, `base64`, `dataurl`, …) that
refuses a field outright, and a broader pose-related check (`keypoint`,
`landmark`, `pose`, `frame`, `skeleton`) that refuses a list/object value
even if the name only loosely suggests pose data. A result's
`measurements` are restricted to the fixed `KNOWN_METRICS` vocabulary
*and* to whatever that specific exercise declares in its own
`measurable_metrics` — a result can never report a metric its exercise
doesn't claim to produce. `record_exercise_result()` is a thin, explicit
seam for future persistence; nothing is written to a database in Phase 2.

## Movement Demonstrations (`src/movementDemos/`)

Phase 0's framework (`schema.js`'s data shape, `MovementDemo.jsx`'s
renderer, `registry.js`'s lookup) is extended, not replaced. `schema.js`'s
pose vocabulary grows from a single field (`armAngleDeg`) to nine optional,
additive fields (`stance`, `legLift`, `sideLegLift`, `hipExtension`,
`heelRaiseDeg`, `armBendDeg`, `leanDeg`, `tandemStance`, plus the original
`armAngleDeg`) — the validator's contract is unchanged (a pose is still
"any object"); only `MovementDemo.jsx`'s `StickFigure` gained the drawing
logic to interpret the new fields, additively, so an unfamiliar field is
ignored rather than breaking rendering.

Thirteen demonstrations are authored in `src/movementDemos/content.js`,
each written directly from the exercise's or panel's own existing
instructions (never invented freehand): the three baseline assessments
(`assessment-shoulder-raise`, `assessment-chair-sit-to-stand`,
`assessment-one-leg-stand`) and one per Exercise Library entry, matched by
`demonstration_id`. `content.js` is imported once, for its registration
side effect, from `src/App.jsx` — not from `registry.js` itself, to avoid
a circular import (`content.js` imports `registerMovementDemo` from
`registry.js`).

The three baseline demonstrations are wired into `ShoulderPanel.jsx`,
`FtsstPanel.jsx`, and `BalancePanel.jsx`'s **idle state only** — shown
before the "Start recording" button, above the existing instructions text.
No measurement/test-logic file (`shoulderLogic.js`, `ftsstLogic.js`,
`balanceLogic.js`, `poseEngine.js`, `protocol.js`) was touched.

As with the exercise content itself, every pose angle used in a
demonstration is an illustrative choice made to render a distinct,
readable phase — not a claim about a clinically correct range of motion,
and not derived from measured data.

## Exercise Movement Assessment foundation (`src/exerciseAssessment/`)

Two generic, exercise-agnostic, deterministic engines — no LLM, no model
call, nothing but arithmetic on a browser-supplied signal:

- **`RepCountingEngine`** — a thin configuration layer over the existing
  `RepetitionDetector` (`src/assessment/utils/peaks.js`) and `MedianFilter`
  (`src/assessment/utils/smoothing.js`); these are reused directly, not
  duplicated. Produces `{ repetitions, completion, durationSeconds }`.
- **`HoldDurationEngine`** — the same hysteresis idea the baseline balance
  test already relies on (a position must be continuously re-validated,
  not sampled once), generalized into a reusable class over `MedianFilter`.
  Produces `{ durationSeconds, completion }`.

`src/exerciseAssessment/config.js` maps each of the **nine
MoveNet-`implemented` exercises** to one of these two engines and a set of
named threshold constants — explicitly labelled, the same as
`need_assessment/rules.py` and `protocol.js`, as **system decisions, not
clinical or validated values**, placeholders that make the engines
runnable and testable ahead of a physio/healthcare review pass.
`heel-to-toe-stand` has no configuration at all, matching its
`movenet_support.implemented: false`. `src/exerciseAssessment/index.js`'s
`createExerciseAssessmentEngine(exerciseId)` is the one factory function a
later camera-integration phase would call.

**What this foundation deliberately does not include**: the per-exercise
"camera keypoints → one number" extraction step — the equivalent of what
`shoulderLogic.js` already does for the shoulder-raise test — for any of
the nine exercises. Building that for all nine, live, wired to a camera
loop, is more than a "foundation" and was not in Phase 2's declared scope;
it is the natural next content-and-integration phase. Both engines are
already fully unit-tested against synthetic signals, independent of
however that signal ends up being produced.

## Privacy

Unchanged principle, re-verified for the new surface area: a webcam frame
never leaves the browser, MoveNet runs in the browser, and only small
derived numbers (`RepCountingEngine`/`HoldDurationEngine`'s output,
`exercise_assessment.schema`'s validated `measurements`) ever reach the
backend or an MCP tool. `exercise_assessment/schema.py`'s privacy filter is
tested directly against inputs naming `rawFrameData` and
`keypointSequence`-style fields, and both are refused.

## Known limitations (carried into Phase 3 planning)

- The `mcp` package has not been executed in any environment available to
  this session — see the Disclosure section above. This is the single
  highest-priority verification item before Phase 2's MCP layer is
  considered production-ready.
- Every threshold in `exerciseAssessment/config.js` is a first-draft system
  decision, exactly like Phase 1's Need Assessment thresholds — both are
  candidates for the same physio/healthcare review pass.
- Nine exercises' actual pose→angle extraction is not built; only the
  generic assessment math they would feed into is.
- `heel-to-toe-stand` has no MoveNet-based assessment and no assessment
  engine configuration — it is demonstrable but not yet measurable.

---

# Phase 3 — Real Orchestrator + Physio Agent

The first genuinely functional agentic workflow. Everything below actually
executes — this section documents what runs, not an intended design.

```
User State
    |
Need Assessment (Phase 1, reused — recomputed only if current_needs is
    not already populated; never duplicated)
    |
current_needs
    |
Orchestrator (backend/orchestrator/orchestrator.py)
    |
decide_physio_required() (backend/orchestrator/decision.py)
    |                                    |
  not required                       required
    |                                    |
  return, no agent run        Physio Agent (backend/physio_agent/agent.py)
                                          |
                              ExerciseToolClient (interface)
                                          |
                     McpExerciseToolClient (production, real MCP)
                                          |
                              Exercise MCP Server (Phase 2, unchanged)
                                          |
                              search_exercises_tool /
                              check_exercise_constraints_tool
                                          |
                              structured tool results
                                          |
                              Physio Agent builds an Exercise Plan
                              (backend/physio_agent/plan_schema.py)
                                          |
                              Agent Result (orchestration.agent_result,
                              agent="physio" — already in Phase 0's
                              KNOWN_AGENT_IDS, unchanged)
                                          |
                              Orchestrator validates the result
                                          |
                              apply_physio_plan() writes exercise_history
                              (backend/orchestrator/state_update.py)
                                          |
                              Updated User State
```

## Orchestrator

`backend/orchestrator/orchestrator.py`'s `run_workflow(user_state,
tool_client=..., workflow_id=..., request_id=...)` is the entry point.

- **Determines whether Physio is required** via `decision.py`'s
  `decide_physio_required(need_profile)`: an explicit, structural rule —
  Physio runs if and only if at least one of `mobility_need`,
  `stability_need`, `functional_movement_need` is currently `MEDIUM` or
  `HIGH`. `NOT_ASSESSED` and `LOW` never trigger it. The decision always
  names which dimension(s) at which level(s) did or did not trigger it —
  never a bare boolean.
- **Inputs**: the User State (validated first; a missing/malformed one is
  handled as a distinct "could not determine" outcome, not a crash) and,
  only when Physio will actually run, an `ExerciseToolClient`.
- **Returns**: a structured Orchestrator Result —
  `workflow_id, request_id, orchestrator_decision, selected_agents,
  agent_results, state_updates, updated_user_state, errors` — generated
  fresh per run, never the brief's own illustrative example values.
- Distinguishes three outcomes explicitly, per the Phase 3 brief's failure
  rules: **not required** (empty `selected_agents`, no error), **required
  but failed** (`selected_agents=["physio"]`, an `agent_results` entry with
  `status="failed"`, no state update), and **could not determine**
  (malformed/missing User State — `errors` names why, `updated_user_state`
  is `None`).
- Never runs every available agent — only Physio exists to run in Phase 3,
  and even it only runs when the decision says so.

## Physio Agent

`backend/physio_agent/agent.py`'s `run_physio_agent(user_state,
tool_client, parent_trace=...)`.

- **Inputs**: never the raw User State directly — `input_contract.py`'s
  `build_physio_agent_input()` first reduces it to
  `workflow_id, request_id, agent_run_id, physical_assessment,
  current_needs, relevant_user_profile, relevant_lifestyle_constraints,
  confirmed_medical_context, exercise_preferences`. `confirmed_medical_context`
  is read only from `medical_context.data.confirmed_reports` — the
  self-reported onboarding checklist and any unconfirmed report data never
  cross this boundary (verified directly:
  `test_unconfirmed_medical_context_never_reaches_the_physio_input`).
  `exercise_preferences` is always `None` — no preference-collection UI
  exists yet, and this field is not invented content.
- **Reasoning/decision process**: maps each physical need dimension
  currently at `MEDIUM`/`HIGH` to the `exercise_library` target
  capability/capabilities it corresponds to (`mobility_need` -> `mobility`,
  `stability_need` -> `stability`, `functional_movement_need` ->
  `functional_movement` and `strength`), searches only for those
  capabilities (never all ten exercises unconditionally), applies the
  safety gate (below) to every candidate, and builds a plan capped at five
  exercises.
- **Tools used**: `search_exercises_tool` (via the client's
  `search_exercises`, filtered by `target_capability` and
  `movenet_implemented_only=True`) and `check_exercise_constraints_tool`
  (via `check_exercise_constraints`, one call per surviving candidate).
  `get_exercise_details_tool` is deliberately NOT called: `search_exercises`
  already returns each candidate's full document, so a second per-exercise
  detail call would be a redundant round trip the Phase 3 brief's own rule
  ("only call tools that are actually needed") rules out.
  `record_exercise_result_tool` is not called either — recording a
  performed exercise is a later-phase concern, once a user has actually
  done one.
- **Outputs**: a Phase 0 Agent Result
  (`orchestration.agent_result.build_agent_result`, `agent="physio"`,
  already present in `KNOWN_AGENT_IDS` since Phase 0 — no schema change
  needed), with `findings = {need_levels, plan, rejected_candidates}` and
  `recommendations` mirroring the plan's exercises. Every plan entry
  carries a `rationale` string, checked at build time
  (`plan_schema.py`'s `_check_no_diagnostic_language`) against a denylist
  of diagnostic/clinical-sounding phrases — "supports balance training",
  never "treats your balance disorder", enforced as a runtime check, not
  only a writing convention (closing the exact gap Phase 1's "known
  limitations" flagged for `need_assessment/rules.py`).

### The safety gate (section 12)

Deliberately limited to what is actually knowable: (1) a difficulty
ceiling — exercises above `intermediate` are excluded by default, since
nothing in the User State provides fitness-history or medical-clearance
evidence to justify recommending `advanced`; (2) the real
`check_exercise_constraints_tool` result — safety constraints, common
mistakes, equipment — surfaced verbatim into each plan entry's
`safety_notes`. This is explicitly **not** a comprehensive medical safety
system: it cannot evaluate a specific person's risk, because no such data
exists anywhere in this system yet. That limitation is documented here,
not hidden — the Physio Agent never bypasses this gate, and a candidate
that fails it is recorded in `findings.rejected_candidates` with a reason,
never silently dropped.

## MCP

- **Client**: `backend/physio_agent/mcp_client.py`'s
  `McpExerciseToolClient` — the only `ExerciseToolClient` implementation
  permitted in production. Uses the real SDK
  (`mcp.ClientSession` + `mcp.client.streamable_http.streamablehttp_client`),
  performs a real `initialize` handshake, and calls exactly the Exercise
  MCP Server's five existing tools — no sixth tool was invented, and
  `create_exercise_plan` (mentioned as an example in the Phase 3 brief) was
  deliberately NOT added as an MCP tool: plan construction is the Physio
  Agent's own reasoning over real tool results, not something delegated to
  the server.
- **Server**: `backend/mcp_servers/exercise_server.py` (Phase 2, unchanged
  except a `--port` CLI argument added so the Phase 3 integration test can
  start it on an ephemeral port).
- **Transport / protocol / session**: unchanged from Phase 2 — Streamable
  HTTP, protocol version negotiated by the SDK, a real per-connection
  session id. `McpExerciseToolClient` opens one connection, handshake, and
  tool call per method call rather than holding a long-lived session
  across a whole agent run — a documented Phase 3 simplification (see the
  module's docstring), not a fake session: every step is still a genuine
  protocol exchange when it runs.
- **Tools actually called**: `search_exercises_tool`,
  `check_exercise_constraints_tool`.
- **Was the real integration tested?** No — `mcp` cannot be installed in
  this sandbox (confirmed unchanged from Phase 2: no PyPI network access).
  `backend/tests/test_physio_agent_mcp_integration.py` is written to run
  the real client -> real server -> real tool -> real result path
  end-to-end (starting `exercise_server.py` as a subprocess, connecting
  over real Streamable HTTP) and to skip itself honestly
  (`unittest.skipUnless`) when `mcp` is unavailable — it currently skips,
  2 of 2 tests, in this environment. What IS verified directly in this
  sandbox: the Physio Agent's own decision-making (capability selection,
  safety gate, plan construction, rationale, Agent Result validity)
  against `physio_agent/tool_client.py`'s `InProcessExerciseToolClient` —
  an explicitly-labelled, test-only double that calls the exact same
  underlying `exercise_library`/`exercise_assessment` functions the real
  MCP tools wrap, in-process, never a fake protocol response. This proves
  the agent's logic; it does not and cannot substitute for actually
  running the MCP transport.

## Exercise Plan

```
{
  "plan_id": "plan_<uuid hex>",
  "created_at": "<ISO8601>",
  "goal": "Support the movement capabilities flagged by the current needs assessment.",
  "exercises": [
    {
      "exercise_id": "standing-knee-raise",
      "sets": 2, "repetitions": 10, "duration_seconds": null,
      "difficulty": "beginner",
      "progression": "...", "regression": "...",
      "rationale": "Selected because mobility need is HIGH, and Standing Knee Raise supports mobility training at the beginner level.",
      "safety_notes": ["Keep a hand on support if balance feels uncertain."]
    }
  ]
}
```

Validated by `physio_agent/plan_schema.py`; capped at 5 exercises per plan;
never contains a sets/repetitions/duration combination the exercise itself
does not declare (each entry's fields come directly from
`exercise_library`'s own document, not invented per-user dosing).

## State Update

`backend/orchestrator/state_update.py`'s `apply_physio_plan()` is the only
function that writes a Physio Agent Result's effect into the User State —
into `exercise_history`, previously always an unavailable
`NOT_YET_COLLECTED` placeholder (Phase 0/1). Only what is actually known at
plan-creation time is recorded: `plan_id, plan_version, created_at, goal,
exercise_ids, source, agent_run_id, recorded_at`. It never claims a user
performed or completed an exercise (that remains
`exercise_assessment.record_exercise_result`'s job, once real performance
data exists). Pure, non-mutating, exactly Phase 1's
`apply_need_profile()` discipline; raises rather than silently recording a
`failed` or empty-plan result.

## Old Agents

**Kept, not removed** — `agents/wellness.py` (`wellness_guidance`) and
`agents/navigation.py` (`care_navigation`), together with their existing
`agents/orchestrator.py`, `agents/registry.py`, and the `/guidance` route
(`routes/guidance.py`, linked from `Dashboard.jsx` and rendered by
`GuidancePage.jsx`) all remain, unchanged.

**Why they remain**: inspected directly this phase (per rule 17) — they
are a genuinely different capability from the Physio Agent, not an earlier,
non-functioning attempt at the same one. `wellness_guidance` writes
free-text reflective wellness observations and `care_navigation` suggests
which kind of professional to talk to, both via an LLM (OpenRouter)
constrained by `agents/guardrails.py`'s rule-checking. The Physio Agent
produces a structured, deterministic exercise plan via MCP tool calls —
it does not write free text, does not suggest a type of professional, and
does not read a medical report the way `agents/context.py` does. Nothing
in Phase 3 does what `wellness_guidance`/`care_navigation` do, so removing
them would delete a still-active, still-used user-facing feature (`/guidance`
is a live route) with nothing replacing it — exactly what the project's
"do not delete until genuinely replaced" rule (carried from Phase 0)
forbids. They were not renamed into Physio, and the Physio Agent shares no
code, prompt, or contract with them.

**What was NOT kept**: nothing was removed, because nothing was found to
be dead. If a future phase's Physio/Nutrition/Behaviour/Safety agents ever
cover everything `wellness_guidance`/`care_navigation` do, that would be
the point to revisit removal — not before.

## Medical Report Reader

Not rebuilt, not touched, and not incorrectly treated as verified: the
Physio Agent's `confirmed_medical_context` input is built exclusively from
`user_state["medical_context"]["data"]["confirmed_reports"]`, which itself
(per Phase 0's `user_state/schema.py`, unchanged) only ever receives
`confirmed_values_for_user()`'s output — a value the user has explicitly
confirmed. No path exists from an unconfirmed report extraction into the
Physio Agent; `test_unconfirmed_medical_context_never_reaches_the_physio_input`
checks this directly.

## Known limitations (carried into Phase 4 planning)

- The real MCP transport has still not been executed in any environment
  available to this project's development sessions — see **MCP** above.
  This remains the single highest-priority verification item.
- `McpExerciseToolClient` reconnects per tool call rather than reusing one
  session across a whole agent run; a longer-lived session would be more
  efficient for a production deployment serving concurrent requests.
- The safety gate is a difficulty ceiling plus the library's own stated
  constraints — not a personalized medical safety evaluation. A real
  Safety Agent, reading confirmed medical context and a validated
  escalation ruleset (neither of which exists yet), is later work.
- The Physio Agent's `relevant_user_profile` and
  `relevant_lifestyle_constraints` fields are populated but do not
  currently influence exercise selection — no exercise in the library is
  tagged by age or lifestyle factor yet. They exist so a later phase can
  wire them in without changing the input contract's shape.
- No UI surfaces the generated plan yet (rule 20: no dashboard was built
  this phase). The plan exists in `User State.exercise_history` and in the
  Orchestrator Result; presenting it to a user is separate, later work.

---

# Phase 4 — Multi-Agent Expansion

Extends Phase 3's single-specialist (Physio) Orchestrator into a genuine
multi-agent architecture: Behaviour and Nutrition specialist agents, and a
Safety Gate that sits across all three. Nothing in Phase 0-3 was replaced;
the Physio Agent and its tests are unchanged and still pass.

## Architecture

```
User State
    |
Need Assessment (Phase 1, unchanged — now nutrition_need is real)
    |
Orchestrator (orchestrator/orchestrator.py)
    |-- decide_physio_required(need_profile)      -> bool, explained
    |-- decide_behaviour_required(need_profile)   -> bool, explained
    |-- decide_nutrition_required(need_profile)   -> bool, explained
    |
    (each selected agent runs independently — no agent reads another
     agent's output; there is no agent-to-agent conversation)
    |
    |-- Physio Agent      -> Exercise MCP Server    -> Exercise Library
    |-- Behaviour Agent    -> Behaviour MCP Server   -> Behaviour Library
    |-- Nutrition Agent    -> Nutrition MCP Server   -> Nutrition Library
    |
Candidate recommendations from every *completed* agent, normalised
    |
Safety Gate (safety/gate.py) -> ALLOW / MODIFY / PAUSE / REFER / NOT_ASSESSED
    |
Safety decision applied (a PAUSE/REFER'd candidate is removed from both
    `final_recommendations` and whatever gets persisted)
    |
User State updates (exercise_history / behaviour / nutrition_plan)
    |
Orchestrator Result (workflow_id, request_id, orchestrator_decision,
    selected_agents, agent_results, safety_result, final_recommendations,
    coordination_notes, state_updates, updated_user_state, errors)
```

## Dynamic Selection

Each of the three agents is selected independently and explicitly —
`orchestrator/decision.py`'s `decide_physio_required`/`decide_behaviour_required`/
`decide_nutrition_required` each read exactly one Need Profile dimension
(`mobility_need`/`stability_need`/`functional_movement_need` combined for
Physio; `behaviour_need` alone for Behaviour; `nutrition_need` alone for
Nutrition) and trigger only at MEDIUM or HIGH. There is no "always run all
three" and no hidden threshold — `tests/test_orchestrator_multiagent.py`'s
`DynamicSelectionTests` verifies all six selection outcomes named in the
Phase 4 brief (Physio-only, Behaviour+Nutrition, Nutrition-only,
Behaviour-only, all three, none).

## Nutrition Agent (`nutrition_agent/`)

**Responsibility**: general wellness nutrition guidance — meal regularity,
fruit/vegetable intake, hydration, and processed-food frequency. Never a
deficiency diagnosis, a supplement/medication recommendation, a
restrictive diet, or a claim of dietitian/doctor review.

**Inputs** (`nutrition_agent/input_contract.py`): `current_needs`
(specifically `nutrition_need`), `relevant_nutrition_signals` (the four
Phase 4 self-reported fields — see below), a narrow
`relevant_lifestyle_constraints` (work_type only), `confirmed_medical_context`
(confirmed reports only, never self-reported or unconfirmed extraction),
and `food_preferences` (always `None` — no preference-collection UI
exists yet, structured for a later phase).

**New input data**: this application collected no nutrition information
before Phase 4. Four optional fields were added to the onboarding profile
document (`routes/profile.py`'s `/api/profile/complete`, all
`Form(None)` — the existing onboarding form is unchanged and still works):
`meal_pattern`, `fruit_vegetable_servings`, `water_glasses_per_day`,
`processed_food_frequency`. `user_state/schema.py`'s `nutrition` section
(schema version bumped to `0.4.0`) surfaces them raw, exactly like
`questionnaire` does for the existing lifestyle fields — no interpretation
happens there. `need_assessment/rules.py`'s `assess_nutrition_need()` was
extended (previously always `NOT_ASSESSED`) with the same
fraction-of-factors-triggered pattern `assess_behaviour_need()` already
used, against new named system-decision thresholds
(`FRUIT_VEGETABLE_SERVINGS_LOW_THRESHOLD`, `WATER_GLASSES_LOW_THRESHOLD`,
and two closed string vocabularies). A profile with none of these fields
answered still produces `nutrition_need = NOT_ASSESSED` — no existing
Phase 1 test needed to change.

**MCP tools** (`mcp_servers/nutrition_server.py`): `search_nutrition_guidance_tool`,
`get_nutrition_topic_details_tool` — both wrap real
`nutrition_library.catalog` functions over four source-cited guidance
topics (`nutrition_library/data.py`, adapted from USDA MyPlate general
dietary guidance). `create_nutrition_plan`/`record_nutrition_adherence`/
`update_nutrition_plan` are deliberately NOT MCP tools — plan
construction is agent/orchestrator work over user-specific state, the same
precedent Phase 2/3 set for `create_exercise_plan`.

**Output**: a `NutritionPlan` (`nutrition_agent/plan_schema.py`) — up to 4
goals, each with a `practical_goal`, a `rationale`, and `safety_notes`,
checked against a diagnostic/prescriptive-language denylist (adds
`deficien`/`supplement`/`medication` to the Physio Agent's denylist).

**Limitations**: no food-preference-collection UI exists; the four
signals are self-reported one-time estimates, not food-tracking data;
thresholds are system decisions, not clinical/dietitian-reviewed cutoffs.

## Behaviour Agent (`behaviour_agent/`)

**Responsibility**: sedentary behaviour, movement breaks, exercise
frequency, and habit formation. Never a mental-health diagnosis or
treatment claim.

**Inputs** (`behaviour_agent/input_contract.py`): `current_needs`
(`behaviour_need`), `relevant_behaviour_signals` (`daily_sitting_hours`,
`daily_screen_hours`, `exercise_days`, `exercise_minutes`, `work_type` —
all already collected by the existing onboarding questionnaire; **no new
fields were added**, confirmed sufficient by direct inspection),
`confirmed_medical_context`, and `adherence_feedback` (always `None` — no
adherence-tracking UI exists yet).

**MCP tools** (`mcp_servers/behaviour_server.py`): `search_behaviour_guidance_tool`,
`get_behaviour_topic_details_tool`, wrapping `behaviour_library.catalog`
over four source-cited topics (`behaviour_library/data.py`, adapted from
the WHO 2020 guidelines on physical activity and sedentary behaviour).
`get_behaviour_history`/`get_adherence`/`get_user_feedback`/`identify_barriers`/
`create_habit_plan`/`record_adherence`/`update_habit_plan` are deliberately
NOT implemented: this application stores no behaviour history, feedback,
or adherence data anywhere, so those tools would have no real data source
— exactly the placeholder-tool this project's rules forbid.

**Output**: a `HabitPlan` (`behaviour_agent/plan_schema.py`) — up to 4
goals, same structure and diagnostic-language discipline as the Nutrition
Plan (denylist additionally covers `mental illness`/`therapy`/`treatment for`).

**Limitations**: no adherence or feedback history exists to read, so
"barriers" and "adherence support" are addressed only via the library's
own general `common_barriers` text, not a personalised read of this
user's actual barriers (which this application does not collect).

## Safety

**Not another recommendation agent.** `safety/` sits across the pipeline,
evaluating the aggregated candidate recommendations from Physio/Behaviour/
Nutrition before the Orchestrator returns a result — never after, never
skippable once at least one agent has produced an Agent Result.

**Rules implemented** (`safety/rules.py`, evaluated in fixed order, first
match wins — REFER before PAUSE before MODIFY before ALLOW, NOT_ASSESSED
checked first):

1. `rule_no_candidates_not_assessed` — no candidate recommendations at all
   → `NOT_ASSESSED` (never a false `ALLOW`).
2. `rule_safety_status_high_refers` — the Need Profile's own `safety_status`
   is `HIGH` → `REFER`, blocks every candidate. `assess_safety_status()`
   (Phase 1) is always `NOT_ASSESSED` in this application today (no
   validated escalation ruleset exists), so this path is not reachable by
   a live run — it is a real, tested, supported code path, not an invented
   clinical case (`tests/test_safety_gate.py`'s `ReferTests` constructs
   the Need Profile field directly, per the Phase 4 brief's explicit
   instruction not to invent a clinical scenario).
3. `rule_advanced_exercise_with_confirmed_medical_context_paused` — a
   confirmed medical report exists on file AND a candidate exercise is
   above a reduced "beginner-only" ceiling → `PAUSE` that exercise (not a
   blanket block — this system cannot confirm the report is actually
   relevant to that exercise, so it withholds pending review rather than
   silently allowing or overreaching into a diagnosis).
4. `rule_confirmed_medical_context_modifies_with_disclaimer` — a confirmed
   report exists but nothing above matched → `MODIFY`: every candidate is
   allowed through with an added disclaimer action.
5. `rule_default_allow` — nothing matched → `ALLOW`.

**MCP tools** (`mcp_servers/safety_server.py`): `check_safety_tool` wraps
`safety.gate.evaluate_safety()`; `check_contraindications_tool` wraps the
same real `exercise_library.catalog.check_exercise_constraints` Phase 2's
Exercise MCP Server already exposes. `evaluate_risk`/`trigger_alert`/
`pause_intervention`/`create_referral` are deliberately not separate
tools: `check_safety_tool`'s one real result (status + flags + actions +
requires_referral) already **is** the risk evaluation, pause signal, and
referral signal — there is no separate alerting or referral-record system
in this application to give those four tool names real behaviour of
their own.

**Decision statuses**: `ALLOW` / `MODIFY` / `PAUSE` / `REFER` /
`NOT_ASSESSED` (`safety/schema.py`), each a full `SafetyResult`:
`status`, `flags`, `actions`, `reason`, `requires_referral`,
`modified_recommendation_ids`, `blocked_recommendation_ids`.

**Escalation behaviour**: `REFER` sets `requires_referral: True` and
blocks every candidate recommendation (named or not) from that workflow
run — nothing from a REFER'd run is written to the User State or appears
in `final_recommendations`. `PAUSE` blocks only the named candidate(s);
the rest of that agent's plan (and other agents' plans) proceed normally.

## Orchestrator

`orchestrator/orchestrator.py`'s `run_workflow()` was extended, not
replaced. A Physio-only run behaves identically to Phase 3
(`selected_agents == ["physio"]`, `state_updates == ["exercise_history"]`,
the same distinct "required but no client" error) — all 10 of Phase 3's
`test_orchestrator_workflow.py` tests pass unchanged.

- **Execution order**: Physio, Behaviour, and Nutrition each run
  independently in the order they are selected — none reads another's
  output. A missing tool client or a runtime failure for one selected
  agent is recorded as a named error and does not stop the others.
- **Aggregation**: `agent_results` is a list of the real,
  `orchestration.agent_result`-validated results from every agent that
  actually ran, in `selected_agents` order — never a re-derived or
  re-shaped format per agent.
- **Candidate normalisation**: `_candidate_recommendations()` flattens
  every *completed* agent's plan entries into `{"id", "agent", "type",
  "difficulty"}` for the Safety Gate — an agent that did not run, or
  produced no plan, contributes nothing.
- **Safety gate integration**: runs once per workflow whenever at least
  one agent produced a result — even an empty plan — recording a real
  `NOT_ASSESSED`/`ALLOW`/etc. decision every time, never silently skipped.
- **Cross-agent coordination**: `_coordination_notes()` implements the one
  concrete conflict the Phase 4 brief names — Physio recommending more
  exercise while `behaviour_need` is `HIGH` (poor baseline adherence) —
  producing one combined-guidance note. This is a deterministic check on
  already-computed levels/plans, not a generated or invented synthesis.
- **State updates**: `exercise_history` (Physio, unchanged from Phase 3),
  `behaviour` (Behaviour's habit-plan history — the same section
  `user_state/schema.py` reserved for this in Phase 0), `nutrition_plan`
  (Nutrition's plan history — a new section, since `nutrition` itself
  now holds this user's raw self-reported survey answers, mirroring how
  `questionnaire` and `exercise_history` are kept separate for Physio).
  A plan reduced to nothing by the Safety Gate is treated exactly like "no
  plan was produced" — nothing is written for it.
- **Failure handling**: a selected-but-unrunnable agent (no client) and a
  selected-and-run-but-failed agent (MCP/tool error) are both named,
  distinct entries in `errors`/`agent_results` — never silently converted
  into a success. `tests/test_orchestrator_multiagent.py`'s
  `PartialFailureTests` proves Nutrition failing does not hide or corrupt
  Physio/Behaviour's real, preserved results, and that Safety still
  evaluates whatever candidates did exist.
- **Safety override proof**: `SafetyOverrideTests` proves a `PAUSE`d
  exercise recommendation is present in the raw Agent Result (audit trail
  of what the agent proposed) but absent from both `final_recommendations`
  and the persisted `exercise_history` — a rejected candidate never
  reaches the "approved" set unchanged.

## MCP

Two new servers (`mcp_servers/nutrition_server.py`,
`mcp_servers/behaviour_server.py`) and one new server for the Safety Gate
(`mcp_servers/safety_server.py`), all built on the exact Phase 2/3 pattern:
`FastMCP`, Streamable HTTP transport, an `ImportError` guard with an
install message, tools wrapping already-tested pure functions, and
`mcp_servers.observability.tool_call_metadata()` reused for every tool's
metadata (no second observability scheme). **Real MCP transport could
still not be tested in this development sandbox** — no PyPI network
access exists here to install the `mcp` package, confirmed unchanged from
Phase 2/3. Every new `mcp_client.py` (`nutrition_agent/mcp_client.py`,
`behaviour_agent/mcp_client.py`) carries the same disclosure Phase 3's
did: written against the SDK's documented public client API, not
executed. `InProcessNutritionToolClient`/`InProcessBehaviourToolClient`
(test-only, never usable in production) call the exact same
`nutrition_library.catalog`/`behaviour_library.catalog` functions the real
MCP tools wrap, so the tests that use them exercise the real tool
*implementation*, just not the real MCP *transport* — this remains the
single highest-priority verification item, unchanged from Phase 2/3.

## Old Agents (re-evaluated, not re-decided)

Re-checked directly this phase, per the explicit instruction to verify
rather than assume the Phase 3 decision still holds:

- **Active frontend usage**: confirmed — `src/App.jsx` still routes
  `/guidance`, and `src/pages/Dashboard.jsx` still navigates to it.
- **Still a user-facing feature**: confirmed — `backend/main.py` still
  registers `routes/guidance.py`'s router; nothing disables the route.
- **Functionality duplicated by the new agents?** No. `wellness_guidance`
  and `care_navigation` are free-text, LLM-driven (OpenRouter) reflective
  wellness writing and professional-type suggestions. Physio/Behaviour/
  Nutrition are deterministic, MCP-tool-driven, structured-plan-producing
  agents that never call an LLM and never write free text. Nothing added
  in Phase 4 does what `/guidance` does.
- **Can it be migrated safely?** Not without building an entirely
  different (LLM-based, free-text) capability — out of scope for Phase 4,
  which was explicitly agentic/structured/deterministic per the brief.

**Decision: KEPT, unchanged, for the same reason as Phase 3.** Not
renamed into Nutrition or Behaviour (they share no code, prompt, or
contract). Nothing was found to be dead, so nothing was removed.

## Medical Report Reader

Unchanged and not touched this phase. Nutrition and Behaviour follow the
exact same rule Physio already did: `confirmed_medical_context` is built
exclusively from `user_state["medical_context"]["data"]["confirmed_reports"]`
(itself only ever populated by `confirmed_values_for_user()`'s already-
confirmed output) — never from `self_reported` values and never from any
unconfirmed report extraction. There is still no code path from an
unconfirmed extraction into any agent.

## Known limitations (Phase 4 additions)

- Real MCP transport is still untested end-to-end in any environment
  available here — unchanged, highest-priority item from Phase 2/3.
- The Safety Gate's rules are deliberately narrow and structural (a
  declared exercise difficulty, whether a confirmed report exists, one
  Need Profile field) — not a personalised clinical safety evaluation. A
  richer, reviewed rule set (and the escalation rules that would let
  `safety_status` ever actually be `HIGH`) is later work.
- Nutrition's and Behaviour's new/reused self-reported signals are
  one-time onboarding estimates, not tracked history — there is no
  adherence or food-tracking data anywhere in this application yet.
- No UI surfaces a Nutrition Plan, Habit Plan, or Safety decision to a
  user yet — they exist in `User State` and the Orchestrator Result.
- `food_preferences` and `adherence_feedback` are structured but always
  `None` — no collection UI exists for either.
- The Progress Agent and closed-loop reassessment shipped in Phase 5 —
  see below. This line is kept, struck through in spirit, as a record
  that Phase 4 made no such claim at the time.

---

# Phase 5 — Progress Agent + Closed-Loop Adaptation

Scope: a Progress Agent, a deterministic comparison/adherence engine, a
Progress MCP Server, an Orchestrator extension that closes the loop from
"user performed a plan" back to "plan adapted", plan versioning with
structured adaptation reasons, and a reassessment mechanism. Phase 6 was
explicitly NOT started.

## Closed-loop architecture

```
INITIAL ASSESSMENT -> NEED ASSESSMENT -> ORCHESTRATOR (Phase A: need-based
    selection, unchanged from Phase 4)
        |-- Physio Agent -> Exercise MCP
        |-- Behaviour Agent -> Behaviour MCP
        |-- Nutrition Agent -> Nutrition MCP
        |
    SAFETY GATE -> PLAN (versioned, exercise_history / behaviour /
        nutrition_plan)
        |
    USER ACTIVITY (exercises actually performed)
        |
    PERFORMANCE / ADHERENCE (exercise_results collection, real submitted
        results; exercise_history plan records, already real)
        |
    PROGRESS AGENT (only when a progress_trigger is supplied — no invented
        schedule): compares baseline vs current and previous vs current
        physical assessments, computes adherence against the active plan,
        checks whether a reassessment is due, and recommends one of
        CONTINUE / PROGRESS / MAINTAIN / REGRESS / MODIFY / REASSESS
        |
    ORCHESTRATOR (Phase B): maps the recommendation to a specialist agent
        (PROGRESS/REGRESS -> Physio, MODIFY -> Behaviour; MAINTAIN/
        CONTINUE/REASSESS -> no dispatch), skips a specialist that already
        ran in Phase A this cycle, attributes the adaptation reason either
        way
        |
    RELEVANT SPECIALIST AGENT -> its own need-gated logic decides whether
        a plan actually changes (Progress can request a review; it can
        never force a plan into existence — see "Progress never bypasses
        the specialist" below)
        |
    ONE UNIFIED SAFETY GATE PASS over Phase A + Phase B candidates
        combined (never two separate gate evaluations)
        |
    NEW PLAN (a new plan_version, `adaptation_reason` + `triggered_by`
        recorded; the previous version is never overwritten)
        |
    UPDATED USER STATE -> REPEAT
```

## Baseline / current / history

`assessments_collection` (`backend/assessments/store.py`, unchanged this
phase) was already a real, append-only, multi-session store before Phase
5 — every completed physical assessment is its own document, and nothing
in this codebase ever updates one in place. Phase 5 does not add a 14th
`user_state` section for "assessment history": `baseline_assessment`,
`previous_assessment`, and `current_assessment` are passed to the
Progress Agent directly by the caller (the Orchestrator, or a route
handler above it), each a raw assessment document in exactly the shape
`assessments/store.py` already returns. This keeps
`user_state/schema.py`'s `physical_assessment` section exactly as Phase 0
defined it (still "the current/latest one"), and it means baseline
preservation is structurally free: nothing in Phase 5 writes to
`assessments_collection`, so a baseline can never be silently replaced by
a reassessment. `user_state/schema.py` gained one new **public** function,
`extract_assessment_tests(assessment_doc)`, extracted from what was
previously private inline logic — the Progress Agent's comparison engine
reuses this exact function so it can never quietly disagree with the Need
Assessment about what a test's measurements mean. Tested in
`tests/test_orchestrator_progress.py::test_full_closed_loop_...` and
`test_plan_versioning_preserves_every_historical_version`, both of which
assert byte-for-byte equality of the baseline/first plan version after a
reassessment cycle.

## Progress Agent

- **Responsibility** (`backend/progress_agent/agent.py`): compares
  baseline vs. current and previous vs. current physical assessments,
  computes adherence against the currently active plan, determines
  whether a reassessment is due, and recommends one adaptation category.
  It never diagnoses, never invents a clinical threshold, and never
  claims improvement/decline without sufficient data — a genuine,
  calculated result every time, never a canned "you are improving."
- **Inputs** (`progress_agent/input_contract.py`): exactly
  `workflow_id, request_id, agent_run_id, baseline_assessment,
  previous_assessment, current_assessment, exercise_history,
  exercise_results, adherence, previous_plan, current_plan,
  current_needs` — no raw webcam frames, MoveNet keypoints, or other
  unnecessary personal data can cross this boundary (checked by the same
  forbidden-substring guard every other agent's input contract uses).
- **Outputs**: a Phase 0 Agent Result (`orchestration.agent_result`,
  `agent="progress"`, already in `KNOWN_AGENT_IDS` since Phase 0 — no
  contract change needed) whose `findings` carries
  `physical_comparison`, `overall_direction`, `adherence`,
  `adherence_level`, `adaptation_recommendation`, `reassessment`.
- **Calculations**: see "Progress Engine" and "Adherence" below — both
  deterministic, both computed by `progress_agent/comparison.py` and
  `progress_agent/adherence.py` respectively (called through the injected
  `ProgressToolClient`, never directly).
- **MCP tools used**: `compare_assessments_tool`, `calculate_adherence_tool`,
  `check_reassessment_required_tool` (see "MCP" below).
- **Limitations**: non-diagnostic by design — a DECLINED result is a
  computed observation, never a claim of injury or disease; adherence
  reflects only exercise-plan completion (see "Adherence" — nutrition
  adherence has no data source yet); thresholds
  (`STABLE_TOLERANCE`, `ADHERENCE_HIGH_THRESHOLD`/`ADHERENCE_LOW_THRESHOLD`,
  `REASSESSMENT_STALE_AFTER_DAYS`) are system decisions, not clinically
  validated cut-offs.

## Progress Engine (`progress_agent/comparison.py`)

- **Baseline vs. current, previous vs. current**: `compare_physical_assessments()`
  runs both comparisons for all three metrics in one call, each entry
  independently `{"baseline_vs_current", "previous_vs_current"}` so a
  caller can distinguish "improved since the very first assessment" from
  "improved/declined since the last one."
- **Direction-aware metrics**: three named, documented metrics, reusing
  the exact extraction logic `need_assessment/rules.py` already applies
  to the same raw tests:
  - `mobility_shoulder_elevation_deg` — **higher is better** (more
    elevation), tolerance 5°.
  - `stability_balance_hold_seconds` — **higher is better** (longer
    hold), tolerance 2s.
  - `functional_movement_ftsst_seconds` — **lower is better** (faster
    sit-to-stand completion), tolerance 1s. `compare_metric()` explicitly
    flips its "improved" test for this one metric — verified in
    `tests/test_progress_comparison.py::test_lower_is_better_*`.
- **Improvement calculation**: `compare_metric(baseline, current, metric)`
  is a pure function — `signed_change = raw_change` (or `-raw_change` for
  a lower-is-better metric), then IMPROVED/DECLINED/STABLE against the
  metric's own tolerance, or NOT_ENOUGH_DATA if either value is `None`
  (never coerced to 0). Identical input always produces identical output
  — asserted directly by `test_deterministic` in both the comparison and
  agent test suites.
- **Overall direction**: `overall_direction()` rolls per-metric
  comparisons up with a fixed, documented priority — any DECLINED wins
  first (a regression is never hidden by an unrelated improvement), then
  any IMPROVED, then STABLE if anything had data, else NOT_ENOUGH_DATA.
- **STABLE vs. NOT_ENOUGH_DATA**: kept explicitly distinct throughout —
  STABLE means a real current measurement existed and the change was
  inside tolerance; NOT_ENOUGH_DATA means no comparable value existed at
  all. Never conflated (`compare_metric`'s own branching guarantees this;
  tested directly).

## Adherence (`progress_agent/adherence.py`)

- **Data source**: real, persisted data only. Phase 5 added
  `exercise_results_collection` (`backend/database.py`) +
  `backend/exercise_assessment/store.py` (`save_exercise_result`,
  `list_exercise_results`, ...) + `POST/GET /api/exercise-results`
  (`backend/routes/exercise_results.py`) — the first place this
  application persists "the user actually did this exercise," mirroring
  `assessments/store.py`'s append-only, ownership-scoped discipline
  exactly. No exercise result was ever written to a database before this
  phase (confirmed by inspection: `exercise_assessment/schema.py`'s
  `record_exercise_result()` only ever validated and returned in Phase 2).
  There is still no scheduling system anywhere in this application (no
  "planned for Tuesday"), so "adherence" here means exactly one thing: of
  the exercises a specific plan named, how many has the user submitted at
  least one completed result for — never a claim about a recurring
  schedule this application does not track.
- **Calculation**: `calculate_completion_rate(planned, completed)` is the
  atomic, deterministic function; `compute_plan_adherence(plan_record,
  exercise_results)` derives `planned_sessions` (distinct exercise ids a
  plan named) and `completed_sessions` (distinct exercise ids from that
  plan with a `status="completed"` result recorded against that exact
  `plan_id` — never a result for a different plan or different exercise).
- **Missing-data behaviour**: `planned_sessions is None`,
  `completed_sessions is None`, or `planned_sessions == 0` are each
  `NOT_ENOUGH_DATA`, never a fabricated 0% — a genuine 0% (planned
  sessions exist, none completed yet) is represented as a real
  `completion_rate: 0.0`, kept explicitly distinct from missing data.
  Negative or non-numeric values raise `AdherenceCalculationError`, never
  silently coerced.

## Reassessment (`progress_agent/reassessment.py`)

- **When triggered**: `requires_reassessment = true` when (a) the user
  has never completed a physical assessment, (b) the most recent
  assessment's completion timestamp cannot be parsed, or (c) it is older
  than `REASSESSMENT_STALE_AFTER_DAYS` (30, a **configurable,
  project-level system decision**, explicitly not a clinical timing
  recommendation, per the brief's instruction). This overrides the
  comparison-based recommendation — `_recommend_adaptation()` checks
  `reassessment_required` before `overall_direction`, so a stale-data
  case is never reported as a confident IMPROVED/DECLINED.
- **How represented**: `findings.reassessment = {"required": bool,
  "reason": "..."}`, always a specific, non-generic reason string (never
  just "reassessment needed").

## Plan Versioning (`orchestrator/state_update.py`)

- **How versioned**: unchanged mechanism from Phase 0/4 —
  `plan_version = len(previous_plans) + 1`, appended to the existing
  `plans` list, never overwritten. All prior versions remain in
  `exercise_history` / `behaviour` / `nutrition_plan`'s `data.plans[]`.
- **What's new this phase**: `apply_physio_plan` / `apply_nutrition_plan`
  / `apply_behaviour_plan` each accept two new optional keyword
  arguments, `adaptation_reason: str = None` and `triggered_by: str =
  None`, both defaulting to `None` so every pre-Phase-5 call site is
  unaffected. A plan version created by ordinary need-based selection
  (Phase A alone, no progress trigger) has both fields `None` — it is an
  initial/routine selection, not an adaptation. A plan version created (or
  confirmed) off a Progress Agent recommendation carries a real,
  structured `adaptation_reason` (e.g. `"Progress Agent recommended
  PROGRESS (overall_direction=IMPROVED, reassessment_required=False)"`
  — never the vague "Plan updated.") and `triggered_by="progress_agent"`.
- **Answering "what/when/why changed"**: for any plan, `plans[-1]` is the
  active version; `plans[i]["created_at"]`/`recorded_at` says when;
  `plans[i]["adaptation_reason"]` says why (or `None` for an initial
  plan); the full list is the decision trail, and it is never truncated
  or rewritten in place.

## Orchestrator (`orchestrator/orchestrator.py`, `orchestrator/decision.py`)

- **When Progress runs**: only when the caller supplies a
  `progress_trigger` (a `{"reason": "..."}` dict) — `decide_progress_required()`
  never invents one and never runs on a fixed schedule (the brief
  explicitly defers scheduling: this application has no scheduling
  mechanism to hook into yet). Two concrete triggers this phase actually
  supports end-to-end (a caller passing the trigger after either event):
  (a) after a completed exercise activity is recorded, (b) after a new
  physical assessment (reassessment) completes. A periodic/scheduled
  review remains explicitly out of scope, as instructed.
- **`run_workflow()` is now two phases**: Phase A is the unchanged Phase 4
  need-based selection (physio/behaviour/nutrition, each decided
  independently). Phase B, only when `progress_decision["progress_required"]`,
  runs the Progress Agent, reads its `adaptation_recommendation`, and maps
  it through `_ADAPTATION_DISPATCH` (`PROGRESS`/`REGRESS -> physio`,
  `MODIFY -> behaviour`; `MAINTAIN`/`CONTINUE`/`REASSESS -> no dispatch`).
- **How adaptation is selected/attributed**: if the dispatch-target agent
  already ran in Phase A this cycle (its own need level independently
  warranted it), Phase B does **not** re-run it — that would create a
  redundant duplicate plan version. Either way — freshly (re)run in
  Phase B, or already run in Phase A — if that agent ends up with a
  completed, plan-bearing result this cycle, the resulting plan version is
  attributed to the Progress recommendation (`adaptation_reason`/
  `triggered_by`), since a supplied `progress_trigger` whose own
  comparison independently agrees with that specialist genuinely was the
  motivating reason for this cycle's plan, not a bare coincidence.
- **Progress never bypasses the specialist**: Physio/Behaviour's own
  plan-generation logic remains exactly what Phase 3/4 built — gated on
  that agent's own need level, unmodified. This means a Progress-only
  dispatch to a specialist whose current need level is LOW produces no
  plan (the specialist's own criteria say no) — Progress can request a
  review, but it can never force a plan into existence, and it never
  selects an exercise or habit goal itself (`_candidate_recommendations()`
  explicitly skips the `progress` agent id — it contributes no candidate
  of its own, only ever a request that a specialist run). This is an
  intentional consequence of rule "Physio/Behaviour remain responsible for
  exercise/habit selection," not a bug — documented as a known interaction
  in Limitations below.
- **Which specialists can be triggered**: Physio (PROGRESS/REGRESS) and
  Behaviour (MODIFY) are wired end-to-end this phase. **Nutrition
  adaptation dispatch is deliberately out of scope** — no nutrition
  adherence data source exists yet (no food-tracking or nutrition-plan
  completion data anywhere in this application), so there is nothing real
  to compute a nutrition-adherence signal from; adding a Nutrition
  dispatch target now would mean inventing that signal, which the brief's
  "do not fabricate adherence" rule forbids. This mirrors the Phase 4
  precedent of a real-but-currently-unreachable `safety_status=HIGH`
  path — the dispatch mapping (`_ADAPTATION_DISPATCH`) is structurally
  ready for a `"nutrition"` entry the moment real nutrition adherence data
  exists.
- **How Safety is applied**: Phase A's and Phase B's agent results are
  merged into `agent_results` **before** the existing single Safety Gate
  block runs — there is exactly one `evaluate_safety()` call per
  `run_workflow()` invocation, over the combined candidate set, whether or
  not a progress trigger was supplied. Verified directly by
  `test_safety_gate_still_applies_to_a_progress_triggered_adaptation`.

## MCP

- **Progress MCP Server** (`backend/mcp_servers/progress_server.py`):
  same `FastMCP` + Streamable HTTP + `ImportError`-guard pattern as every
  prior server. Three tools, each wrapping a real, already-tested pure
  function — **no placeholder tools**: `compare_assessments_tool`,
  `calculate_adherence_tool`, `check_reassessment_required_tool`.
  `get_progress`/`generate_progress_report`/`trigger_reassessment` from
  the brief's suggested list were deliberately not built as separate
  tools: the first two would only re-package the same three calls with no
  new underlying functionality, and no notification/scheduling system
  exists anywhere in this application for a `trigger_reassessment` tool
  to actually trigger — `check_reassessment_required_tool` is the honest,
  real version of that capability.
- **Client** (`backend/progress_agent/mcp_client.py`,
  `backend/progress_agent/tool_client.py`): `McpProgressToolClient` (real
  transport) and `InProcessProgressToolClient` (TEST-ONLY, calls
  `progress_agent.comparison`/`.adherence`/`.reassessment` directly, in
  process) both implement the same `ProgressToolClient` interface the
  agent depends on — the agent never bypasses this abstraction to call
  the pure functions directly.
- **Transport**: identical Streamable HTTP pattern to every prior server.
- **Session behaviour / observability**: `workflow_id`, `request_id`,
  `agent_run_id`, `tool_call_id`, `mcp_session_id` are threaded through
  every Progress tool call via the existing `orchestration.ids`/
  `mcp_servers.observability.tool_call_metadata()` framework, unchanged.
- **Real integration status**: not executed over the real transport in
  this sandbox — same, unchanged, highest-priority disclosure as every
  MCP server since Phase 2 (`mcp` package unavailable, no PyPI network
  access here). `tests/test_progress_mcp_integration.py` exists,
  self-skips honestly here (3 skipped), and will run for real in an
  environment with `mcp` installed. Every real tool's underlying
  *implementation* (not the transport) is exercised via
  `InProcessProgressToolClient` throughout the rest of the Phase 5 test
  suite.

## Closed Loop

**Tested and confirmed, at least once, end-to-end, exactly as specified**:
`tests/test_orchestrator_progress.py::DispatchAndClosedLoopTests::test_full_closed_loop_improved_high_adherence_dispatches_physio_and_versions_plan`
runs the real chain — Baseline physical assessment -> initial Physio Plan
(`plan_version=1`) -> simulated user activity (real `exercise_results`
completed against that plan) -> Progress Agent (real
`compare_physical_assessments`/`compute_plan_adherence`/
`check_reassessment_required` calls via `InProcessProgressToolClient`) ->
Orchestrator Phase B decision -> Physio Agent re-run -> one unified Safety
Gate pass -> new Plan (`plan_version=2`, `adaptation_reason` set,
`triggered_by="progress_agent"`) -> Updated User State, with the original
`plan_version=1` record asserted byte-for-byte unchanged. Companion tests
cover the STABLE/MAINTAIN, MODIFY/Behaviour, DECLINED/REASSESS, and
NOT_ENOUGH_DATA/REASSESS paths, the no-double-run guarantee, and
three-cycle plan-version accumulation.

## Tests

```
Phase 0:         34   (unchanged)
Phase 1:         66   (unchanged)
Phase 2:         64   (unchanged)
Phase 3:         62   (unchanged)
Phase 4:         46   (unchanged)
Phase 5:         89   (24 comparison, 22 adherence, 23 Progress Agent
                       [input contract, findings schema, execution
                       lifecycle incl. the 5 brief scenarios], 6
                       reassessment, 11 Orchestrator/closed-loop, 3 MCP
                       integration [skipped])
Pre-existing:   200   (original app tests, unchanged)
Full backend:   561
Full frontend:  175
Lint:            12  pre-existing errors (unchanged — no frontend file
                     touched this phase)
Passed:         736  (561 backend + 175 frontend)
Failed:           0
Skipped:         16  (13 unchanged from Phase 2-4 [`mcp` package
                     unavailable] + 3 new Phase 5 MCP integration tests,
                     same honest self-skip discipline)
Regressions:      0
```

## MoveNet

**Not modified.** No file under `src/assessment/` was read or touched
this phase — Phase 5 is entirely backend, reading only already-computed
User State / assessment-history / exercise-result data, exactly like
Phases 1-4. `progress_agent/comparison.py` explicitly reuses
`need_assessment/rules.py`'s and `user_state/schema.py`'s existing
raw-value extraction logic rather than reimplementing or altering it.

## Known limitations (Phase 5 additions)

- **Nutrition adaptation dispatch is not wired** — see "Orchestrator"
  above. Structurally ready, not reachable, because no real nutrition
  adherence data exists yet.
- **A Progress-triggered dispatch to a specialist whose own need level is
  currently LOW produces no new plan.** This is intentional (the
  specialist agent, not Progress, remains the authority on whether/what
  to prescribe — see "Progress never bypasses the specialist" above), but
  it does mean a genuinely-improved user whose need level has already
  dropped below the specialist's own threshold will not receive an
  automatic "harder" plan purely from a Progress trigger; a human-in-the-
  loop or a future phase's explicit "progression mode" would be needed
  for that specific case. Not a defect — a direct, deliberate consequence
  of the brief's own "Physio remains responsible for exercise selection"
  rule.
- **Periodic/scheduled Progress review does not exist** — explicitly
  deferred per the brief; `progress_trigger` must be supplied by a
  caller reacting to a real event (an exercise result was recorded, a
  reassessment completed), never invented on a timer.
- `REASSESSMENT_STALE_AFTER_DAYS = 30`, `ADHERENCE_HIGH_THRESHOLD = 0.7`,
  `ADHERENCE_LOW_THRESHOLD = 0.4`, and each metric's `STABLE_TOLERANCE`
  are system decisions, not clinically validated thresholds — same
  discipline as every threshold in Phases 1-4.
- Real MCP transport for the Progress MCP Server is untested end-to-end
  in this sandbox — unchanged, carried-forward, highest-priority item
  from Phase 2.
- No UI surfaces Progress results, adaptation history, or plan versions
  to a user yet — they exist in `User State` and the Orchestrator Result
  only.
- The system does not predict clinical outcomes, diagnose injury or
  disease, or guarantee improvement — it computes and reports structured
  comparisons and adherence over data the user has actually generated,
  nothing more.

---

# Phase 5.1 — Cleanup, Medical Report Reader Repair, Baseline Assessment Reliability

Scope: a focused reliability/cleanup pass, not a redesign. No new phase of
the agent architecture was added. Phase 6 was explicitly NOT started.

## Architecture cleanup

Audited every agent-like component in the repo against the approved
7-component architecture (Need Assessment, Orchestrator, Physio, Nutrition,
Behaviour, Progress, Safety Gate). Result: **nothing was removed.** The
pre-existing `wellness_guidance`/`care_navigation` LLM agents
(`backend/agents/`, `backend/routes/guidance.py`) remain live,
frontend-reachable (`src/pages/GuidancePage.jsx`, linked from
`Dashboard.jsx`), and functionally distinct (free-text LLM reflection vs.
the new agents' deterministic, MCP-tool-driven, structured output) — the
same conclusion Phase 3/4 reached, now re-verified rather than assumed.
No duplicate, placeholder, or dead agent code was found anywhere.

## Medical Report Reader

The pipeline itself (`backend/reports/{schema,extraction,storage,store}.py`,
`routes/reports.py`) was already implemented correctly end-to-end —
upload, extraction (candidate/unconfirmed), review, confirmation, and
`User State -> medical_context.data.confirmed_reports` all wired
correctly, with an honest `EXTRACTION_UNAVAILABLE`-style failure path
already in place. The actual gap was **test coverage**: nothing exercised
the full chain, so a wiring regression between individually-correct
modules could have gone unnoticed. Added
`backend/tests/test_report_pipeline_integration.py` (8 tests, real
modules, a fake Mongo collection and a fake HTTP transport standing in for
the two genuine external dependencies) proving the full chain and proving
upload-without-confirmation creates no confirmed context. The 5 tests that
need `pymongo`/`bson` (unavailable in this sandbox, same constraint as the
`mcp` package since Phase 2) self-skip honestly, mirroring the existing
MCP-integration-test discipline — they do not silently fail the suite.

## Baseline assessment reliability

Root-caused and fixed all three tests without touching MoveNet or the
shared camera/inference loop:

- **One-Leg Stand** ("too many frames"): the pre-hold setup phase had no
  time bound, and quality was scored over the whole attempt (setup +
  hold), so ordinary balancing wobble while getting into position could
  fail an otherwise-clean timed hold. Fixed with a bounded setup timeout
  and by scoping the usable-frame-ratio check to the timed hold itself.
- **Chair Sit-to-Stand x5**: same unbounded-setup flaw, plus a
  zero-millisecond minimum stand duration that let a single noisy frame
  register as a full repetition. Fixed with a setup timeout and a real,
  small minimum-hold floor before a "stand" is accepted.
  Note: this fix works by retracting a provisional rep count via the
  `RepetitionDetector`'s `REJECTED` event, because the completion clock
  must still start the instant standing is reached (an existing,
  deliberately unchanged behavior) — see `docs/architecture.md`'s inline
  code comments for the exact mechanism.
- **Hand/Shoulder Raise**: orientation checks (trunk lean, hip shift,
  front-facing) used the same strict calibration-time thresholds during
  active measurement, so ordinary sway mid-repetition could drop frames
  and truncate a rep's peak. Fixed with modestly relaxed, phase-gated
  thresholds for the measurement phase only; calibration is unchanged.
  A dead, never-used constant (`SHOULDER_MIN_FRAMES`) was removed.

Shared camera/attempt-state reset discipline was audited and confirmed
already correct — no leakage between tests or attempts existed, and none
of the fixes above touch that mechanism.

## Tests / regression

Backend: 569 tests, 21 skipped (the pre-existing 16 mcp-package skips +
5 new pymongo/bson skips), 0 failures — unchanged from before this pass
except for the 8 new Medical Report Reader tests (3 run, 5 skip).
Frontend: 185 tests, 0 failures (175 baseline + 10 new assessment-fix
tests). Lint: 12 pre-existing errors, unchanged. All Phase 0-5 tests,
including the full Progress Agent / closed-loop suite, remain green.

## Known limitations (Phase 5.1 additions)

- The Medical Report Reader's live OpenRouter HTTP round-trip is still
  unverified from this sandbox (no egress to openrouter.ai here) — only
  the real parsing/storage/confirmation logic was exercised, against a
  fake transport, per the project's existing `transport=` injection
  pattern. The real API key is present in the project's own `.env`.
- The baseline-assessment fixes were verified against synthetic pose
  fixtures (unit tests) and by inspection, not against a live camera/real
  user session — this sandbox has no camera. A short real-world check is
  recommended before considering the "too many frames" issue fully closed
  in practice.

---

# Phase 6 — Nutrition Closed Loop: Progress Extension (in progress)

This section documents the Progress Agent / Orchestrator extension built
so far for Phase 6 (the final implementation phase). Phase 6 is not yet
complete; this section will be superseded by the full Phase 6 report.

## Nutrition Progress (separate from physical progress)

- **New module** `progress_agent/nutrition_progress.py`: two pure
  functions, `compare_nutrition_adherence()` and
  `recommend_nutrition_adaptation()`, mirroring
  `progress_agent/comparison.py`'s discipline exactly (same input, same
  output, always; no clock, no randomness).
- **Never conflated with physical progress or a health claim.**
  `findings.nutrition_progress` is a distinct, optional key alongside the
  existing physical-comparison fields — "adherence improved" is reported
  as exactly that, never as "health improved" (see the module's own
  docstring). It is `None` whenever the caller supplies no nutrition
  context to `run_progress_agent()`/`run_workflow()` — never fabricated.
- **Status vocabulary**: `IMPROVED` / `STABLE` / `DECLINED` /
  `NOT_ENOUGH_DATA`, computed by comparing two
  `nutrition_agent.adherence.compute_food_log_adherence()` results (a
  previous period and a current period) with a `0.10` tolerance band (a
  system decision, same discipline as every other tolerance in this
  project). A missing/rate-less current or previous period is always
  `NOT_ENOUGH_DATA` — never treated as "improved from nothing."
- **Nutrition-specific adaptation table** (deliberately excludes
  PROGRESS/REGRESS — physical-difficulty concepts with no nutrition
  equivalent):

  ```
  NOT_ENOUGH_DATA                          -> REASSESS
  IMPROVED                                 -> CONTINUE
  STABLE, current period ADHERED           -> MAINTAIN
  STABLE, current period not ADHERED       -> MODIFY
  DECLINED                                 -> MODIFY
  ```

## Progress Agent extension

`run_progress_agent()` gained five new optional parameters
(`nutrition_plan`, `nutrition_food_log_previous_period`,
`nutrition_food_log_current_period`, `nutrition_period_previous`,
`nutrition_period_current`), all `None` by default so every pre-Phase-6
call site is unaffected. When `nutrition_plan` is given, the agent calls
the new `ProgressToolClient.calculate_nutrition_adherence()` method twice
(once per period, wrapping `nutrition_agent.adherence.compute_food_log_adherence`
exactly), compares the two results, and adds the recommendation +
reason onto `findings.nutrition_progress`. `progress_agent/schema.py`'s
`validate_progress_findings()` optionally validates this key's shape when
present and not `None` — a pre-Phase-6 findings dict with no such key
remains valid.

`calculate_nutrition_adherence()` is a concrete (not abstract) method on
`ProgressToolClient`, raising `NotImplementedError` by default — this
keeps every pre-Phase-6 test double that only implements the three
original methods working unchanged. `InProcessProgressToolClient`,
`McpProgressToolClient`, and a new `calculate_nutrition_adherence_tool`
on the Progress MCP Server (`mcp_servers/progress_server.py`) all
implement it for real.

## Orchestrator: nutrition adaptation dispatch

`run_workflow()` gained four new optional parameters
(`nutrition_food_log_previous_period`, `nutrition_food_log_current_period`,
`nutrition_period_previous`, `nutrition_period_current`) — the caller
supplies the food-log data for two comparison periods; `run_workflow`
builds the `nutrition_plan` record itself from the User State's own
`nutrition_plan` section, exactly the way it already builds the exercise
`current_plan` record for the existing physical Progress path.

Phase B's dispatch is now two independent checks per cycle, since a
physical adaptation recommendation and a nutrition adaptation
recommendation can both fire from the same Progress run (they are
separate axes): the existing `_ADAPTATION_DISPATCH`
(`PROGRESS`/`REGRESS -> physio`, `MODIFY -> behaviour`) and the new
`_NUTRITION_ADAPTATION_DISPATCH = {"MODIFY": "nutrition"}`. Both follow
the identical no-double-run rule (never re-run a specialist that Phase A
already ran this cycle) and the identical attribution rule (attribute a
structured `adaptation_reason`/`triggered_by="progress_agent"` whenever
the dispatch target ends up with a completed, plan-bearing result this
cycle, whether freshly re-run or already run in Phase A and independently
agreeing) — see `tests/test_orchestrator_nutrition_progress.py`'s full
closed-loop test for the end-to-end proof:

    Need (HIGH) -> Orchestrator -> Nutrition Agent -> Nutrition MCP ->
    Personalized Plan -> User Food Log -> Nutrition Adherence ->
    Progress Agent -> Orchestrator -> Nutrition Agent -> Updated Plan ->
    Safety Gate

## Section 15 resolved: Low Need vs. Progress Trigger (explicit, tested)

Previously documented as a "known limitation" (Phase 5's "A
Progress-triggered dispatch to a specialist whose own need level is
currently LOW produces no new plan"). Phase 6 reframes this as an
**intentional, explicitly tested design decision**, not a gap:

- A current LOW physical need does **not** prevent a legitimate
  Progress-triggered specialist review. When Progress recommends
  PROGRESS/REGRESS (physical) or MODIFY (nutrition), the Orchestrator
  unconditionally dispatches the mapped specialist for a cycle in which
  it was not already run in Phase A — the specialist's own need level is
  never consulted to decide *whether to review at all*.
- The specialist retains sole authority over whether a new/modified plan
  actually results. Physio/Nutrition/Behaviour's own need-gated plan
  logic (unchanged since Phase 3/4) still runs exactly as it always has:
  if no physical need dimension is MEDIUM/HIGH (or no nutrition signal
  crossed its threshold), the specialist returns a `completed` result
  with no `plan` key, and nothing is written to the User State.
- Proven directly by
  `tests/test_orchestrator_nutrition_progress.py::LowNeedDoesNotBlockProgressTriggeredReviewTests`:
  a LOW stability need with a genuinely IMPROVED comparison still gets
  Physio *reviewed* (`"physio" in selected_agents`, a `completed` Agent
  Result), while its own need-gate still correctly produces no plan and
  no `exercise_history` state update.


## Real workflow wiring (Phase 6): run_workflow() reaches the running app

Before this phase, `run_workflow()` (the whole Physio/Nutrition/Behaviour
-> Progress -> Safety Gate pipeline) was invoked only from
`backend/tests/`. There was no HTTP route that assembled a real User State
from the database and ran it. Phase 6 adds that wiring, and nothing else:

- `backend/workflow/assembly.py` -- `assemble_user_state_from_documents()`,
  a pure function (no pymongo/bson import) that builds a full,
  Need-Assessed User State from already-fetched documents. Directly
  unit-tested without a database connection.
- `backend/workflow/response.py` -- `serialise_workflow_state()`, the one
  clean, user-facing JSON shape this API returns: plan summaries by name
  (never raw ids or Mongo `_id`s) and a plain-language safety status
  (`safety_status_message()` translates ALLOW/MODIFY/PAUSE/REFER/
  NOT_ASSESSED into a sentence a non-technical user can act on). Never a
  `workflow_id`/`request_id`/`agent_run_id`/`tool_call_id`/
  `mcp_session_id`, and never a raw Agent Result.
- `backend/user_state/store.py` -- one persisted User State document per
  user (`user_state_collection`, upserted in place, not a history
  collection -- each plan section already keeps its own version history
  internally). The real Safety Result from the run that produced the
  current state is stored alongside it as `last_safety_result`, since
  `user_state/schema.py`'s own `safety` section is reserved for a
  different, not-yet-built purpose.
- `backend/routes/workflow.py` -- `build_user_state_for_user(user_id)`
  (fetches the profile, most recent physical assessment, and confirmed
  medical report values, then calls the pure assembly function above),
  `POST /api/workflow/run` (builds the User State, decides which
  specialists are required, constructs the REAL `Mcp*ToolClient`s for
  only those specialists, runs the Orchestrator, persists the result, and
  returns the redacted summary), and `GET /api/workflow/latest` (returns
  the same redacted summary for whatever was last persisted, or an honest
  "no recommendations yet" 200 -- never a 404/500 for "nothing yet"). If
  the `mcp` package cannot be imported when a client is needed, the route
  returns a clean 503 ("The recommendation engine is temporarily
  unavailable") -- the real exception is logged server-side only, never
  shown to the end user.
- **Known, disclosed limitation**: this route only ever passes the
  caller's single latest assessment as the Progress Agent's
  `current_assessment`. A real `baseline_assessment`/`previous_assessment`
  history (which past session counts as "baseline" across reassessments)
  is not assembled yet -- until it is, a progress-triggered run correctly
  reports `NOT_ENOUGH_DATA` rather than fabricate a comparison.
- **Staff accounts**: `routes/auth.py`'s signup now sets `is_staff: False`
  on every new user document (additive; existing accounts unaffected).
  `auth/deps.py`'s new `require_staff_user` dependency 403s any caller
  whose account is not `is_staff: True`. There is intentionally no admin
  UI to promote a user to staff yet -- it is set by a direct database
  update only, a disclosed limitation, not an oversight.

## Internal healthcare/developer dashboard (Phase 6)

`backend/dashboard/serialisers.py` (pure, no pymongo/bson/fastapi import)
and `backend/routes/dashboard.py` (prefix `/api/dashboard`, every route
gated by `require_staff_user` -- a normal account gets a 403 from every
endpoint in this file, never patient-facing data):

- `GET /api/dashboard/users/{user_id}/state` -- the full, UNREDACTED
  persisted User State for one user, plus a safe account-info subset
  (`safe_account_info()` explicitly excludes `password_hash` -- asserted
  by a key-scan test, not just by convention).
- `GET /api/dashboard/users/{user_id}/plan-history` -- every historical
  plan version (not just the latest) across physio/nutrition/behaviour,
  each with its real `plan_version`/`created_at`/`adaptation_reason`/
  `triggered_by` (`flatten_plan_history()`).
- `GET /api/dashboard/users/{user_id}/safety` -- the real, persisted
  Safety Result from that user's last workflow run, read straight from
  `user_state.store`'s `last_safety_result` -- never re-derived or
  guessed.
- `GET /api/dashboard/mcp-status` -- for each specialist, whether the
  `mcp` package is importable right now
  (`importlib.util.find_spec("mcp") is not None`) and the REAL
  `@server.tool()` function names read from that specialist's actual
  `mcp_servers/*.py` file (physio's server module is `exercise_server.py`).
  Says "NOT INSTALLED IN THIS ENVIRONMENT" honestly where true (it is, in
  this sandbox) -- never claims a server is connected when nothing was
  actually connected.

Frontend: `src/pages/DashboardInternalPage.jsx` (route
`/internal/dashboard`) + `src/services/dashboard.js`. A plain "enter a
user ID, load their data" internal tool with a visible "Internal / Staff
Only" banner -- deliberately not a polished patient-facing screen. Real
access control is the backend's `require_staff_user` dependency; the
frontend adds no gating of its own beyond requiring sign-in.

**Disclosed limitation**: this project's frontend test suite
(`node --test "src/**/__tests__/**/*.test.js"`) exercises pure JS logic
modules only -- there is no React component-rendering test infrastructure
(no `@testing-library/react`/jsdom) anywhere in this repo, and none could
be installed in this sandbox (no npm registry access, same network
restriction documented elsewhere in this file). The new page was verified
with `eslint` (0 new errors, clean AST parse of the JSX) and by direct
code review against the project's existing page/service conventions, but
has no automated rendering test, matching every other `.jsx` page in this
repo, none of which have one either.


## Medical Report Reader: live extraction status (Phase 6, re-verified)

Re-verified this phase, directly, rather than repeating Phase 5.1's
finding unchecked:

- `python3 -c "urllib.request.urlopen('https://openrouter.ai/api/v1/models')"`
  from this sandbox -> `URLError: Tunnel connection failed: 403 Forbidden`.
  `pip install mcp --dry-run` -> the same proxy 403, `No matching
  distribution found`. `npm ping --registry=https://registry.npmjs.org`
  (from the frontend side) -> the same 403. All three confirm, freshly
  this phase: **this sandbox has zero outbound network egress**, not just
  a missing package -- installing `mcp`/`pymongo`/`bson`, or making a real
  HTTP call to OpenRouter, are both structurally impossible here, not a
  configuration gap that more effort would close.
- **Supported formats** (`config.py`): `REPORT_ALLOWED_EXTENSIONS = (".pdf",
  ".png", ".jpg", ".jpeg")` -- a PDF or a photo of a printed report;
  anything else is rejected before it would sit unread.
- **AI provider**: `SUPPORTED_AI_PROVIDERS = ("openrouter",)` only.
  `ai_extraction_available()` (config.py) returns `True` only when a real
  `OPENROUTER_API_KEY` is configured and the provider is `"auto"` or
  `"openrouter"` -- `AI_PROVIDER="none"` deliberately disables extraction
  even with a key present, for testing the unavailable path honestly.
- **What was and was not verified this phase**: the real parsing,
  candidate/unconfirmed-vs-confirmed distinction, storage, and
  confirmation logic (`reports/extraction.py`, `reports/storage.py`,
  `reports/store.py`) were exercised via `tests/test_report_pipeline_integration.py`
  against a fake transport, per this project's established
  `transport=`-injection pattern (Phase 5.1) -- this is REAL logic under
  test, not a placeholder. The actual HTTP round-trip to OpenRouter's API
  was NOT executed this phase, or any prior phase, because no environment
  available to this project's automated work has outbound network access
  to verify it. This is classified honestly in this document as an
  **UNAVAILABLE EXTERNAL DEPENDENCY** in this sandbox, not a
  UNVERIFIED-but-fixable gap and not a REAL-and-tested integration.
  A real API key is present in the project's own `.env` for a deployment
  environment that does have network access to actually exercise this.

## Real MCP runtime verification (Phase 6, re-verified)

- The `mcp` package (the official Python SDK every `Mcp*ToolClient` and
  every `mcp_servers/*.py` server module is written against) could not be
  installed in this sandbox this phase either -- same 403 proxy error,
  confirmed directly above. A real `connect -> initialize -> session ->
  tool calls -> close` lifecycle over Streamable HTTP was therefore **not
  executed** this phase, exactly as every prior phase (2-5) already
  disclosed. This is not a new gap Phase 6 introduced or failed to close;
  it is the same, unchanged, structural sandbox limitation.
- What IS real: every MCP server file (`mcp_servers/exercise_server.py`,
  `behaviour_server.py`, `nutrition_server.py`, `progress_server.py`,
  `safety_server.py`) is real, reviewed production code wrapping
  already-tested pure functions -- not a placeholder. Every
  `Mcp*ToolClient` (`physio_agent/mcp_client.py` and its four siblings) is
  real, reviewed production code written against the SDK's documented,
  stable client API -- not a test double. `backend/routes/workflow.py`
  (new this phase) is the first place any of these real clients are
  actually constructed and used outside a test file, though the
  connection itself still cannot be exercised here.
- What is explicitly a TEST DOUBLE, and labeled as such everywhere it
  appears: `InProcess*ToolClient` classes (one per agent) implement the
  same tool-client interface by calling the underlying pure function
  directly, in-process, with no MCP transport at all -- used throughout
  `backend/tests/` to exercise every agent's decision logic deterministically.
  This is never described as, or confused with, a production MCP
  execution anywhere in this codebase.
- `tests/test_*_mcp_integration.py` (one per agent, 4 files, ~13 tests
  total across the project) exist specifically to run for real the moment
  `mcp` is installed in an environment that has it; here, they self-skip
  honestly via the established `importlib.util.find_spec` guard, counted
  in the "skipped" total of every regression report in this document,
  never silently omitted or claimed as passing.


## Security follow-up closed (Phase 6)

Phase 5.1's security review flagged, but did not fix, one Low-severity
gap: `routes/profile.py`'s document-upload path had no size cap, unlike
`reports/storage.py`'s own upload path (`REPORT_MAX_UPLOAD_BYTES`). Fixed
this phase: `routes/profile.py` now writes uploads in bounded 1 MB chunks
and rejects/deletes a file that exceeds the same `REPORT_MAX_UPLOAD_BYTES`
limit (reused, not duplicated, from `config.py`) mid-write, mirroring
`reports/storage.py`'s own discipline exactly. The other flagged item --
the internal dashboard must be staff-gated when built -- is addressed by
this same phase's `require_staff_user` dependency (see above); it was not
left open.


## Second AI provider: Gemini, direct (post-Phase-6, user-requested)

Phase 6's final report named this build's live-AI-extraction limitation
honestly: it calls OpenRouter only, and OpenRouter needs credit. After
that report, the user's OpenRouter account ran out of credit and asked
for a way to use a Google Gemini key instead. This is a small, scoped
addition on top of the finished Phase 6 build, not a new phase: no agent,
route, or data model changed, only which HTTP call reads a report or
writes guidance when a Gemini key is configured instead of (or alongside)
an OpenRouter one.

**config.py**: `SUPPORTED_AI_PROVIDERS = ("openrouter", "gemini")`.
`GEMINI_API_KEY` (also accepts `GOOGLE_API_KEY`), `GEMINI_BASE_URL`
(default `https://generativelanguage.googleapis.com/v1beta`),
`GEMINI_MODEL` (default `gemini-2.0-flash`, chosen because it has a free
tier and supports both function calling and image/PDF input -- the same
two requirements `OPENROUTER_MODEL`'s own comment states), and
`GEMINI_AGENT_MODEL` (defaults to `GEMINI_MODEL`, mirroring
`AI_AGENT_MODEL`'s relationship to `OPENROUTER_MODEL`). `AI_PROVIDER=auto`
(the existing default) tries OpenRouter first, then Gemini -- this order
was chosen deliberately so an existing single-provider deployment's
behaviour is byte-for-byte unchanged when only `OPENROUTER_API_KEY` is
set. `AI_PROVIDER=gemini` (or `=openrouter`) forces one explicitly.
`ai_provider_available()` was extended the same way.

**agents/llm.py**: `GeminiAgentModel(BaseModel)`, reached directly against
`{GEMINI_BASE_URL}/models/{model}:generateContent`. Authenticates with an
`x-goog-api-key` header, not a bearer token -- a real difference from
OpenRouter's OpenAI-compatible shape, not a stylistic one. Structured
output is still mandatory: `toolConfig.functionCallingConfig` is forced to
`mode: "ANY"` with `allowedFunctionNames` set to the one tool offered,
mirroring `AgentModel`'s `tool_choice` discipline exactly. A response that
answers in prose instead of the forced function call is `AgentFailed`, not
scraped -- the same rule `_tool_input()` enforces for OpenRouter, applied
by `_gemini_function_call_args()` to Gemini's different response shape
(`candidates[0].content.parts[].functionCall.args`, already an object,
unlike the chat-completions shape's JSON-string arguments). A blocked
prompt (`promptFeedback.blockReason`) is reported as its real reason, not
folded into the generic "answered in prose" message, since that message
would be false in that case. `select_model()` now checks OpenRouter, then
Gemini, in that order, before falling back to `UnavailableModel` with a
reason naming both `OPENROUTER_API_KEY` and `GEMINI_API_KEY`.

**reports/extraction.py**: `GeminiProvider(ExtractionProvider)`, same
transport-injection and forced-function-call discipline as
`OpenRouterProvider`. The document travels as Gemini's own
`inlineData: {mimeType, data}` shape rather than OpenRouter's `data:` URL
-- covered directly by a test that inspects the outgoing payload, since
this is exactly the kind of wire-format detail that silently regresses.
`select_provider()` was extended with the same OpenRouter-then-Gemini
order as `select_model()`.

**Credential redaction**: `_KEY_SHAPED` in both files was widened from
`sk-[A-Za-z0-9_-]{4,}` (OpenRouter's shape) to also match
`AIza[A-Za-z0-9_-]{10,}` (Gemini's shape), since an upstream error message
proxied back could in principle quote either credential shape.

**Tests**: `backend/tests/test_gemini_provider.py` (13 tests, all real --
no pymongo/fastapi dependency in either `GeminiAgentModel` or
`GeminiProvider`, so no self-skip guard is needed). Covers: a successful
function-call round trip for both the guidance-agent path and the
document-extraction path (asserting the real `inlineData` wire shape);
prose-instead-of-function-call is a failure, not a guess; a blocked
prompt names its real block reason; a 401 names `GEMINI_API_KEY`
specifically, not `OPENROUTER_API_KEY`; a Gemini-shaped key is never
echoed back in an error message; and `select_model()`/`select_provider()`
correctly prefer OpenRouter when both keys are present, fall back to
Gemini when only that key is present, and are honestly unavailable when
neither is. Full regression re-run after this change: 708 backend tests
(695 + 13 new), 0 failures, 34 skips (unchanged) -- no regression to the
Phase 6 baseline.

**Not done, and out of scope for this change**: no live network call to
Gemini was made or could be made from any environment available to this
project's automated work (same zero-egress sandbox constraint Phase 6
documented for OpenRouter) -- `GeminiAgentModel`/`GeminiProvider` are
REAL production code, tested against a fake transport exactly as
`AgentModel`/`OpenRouterProvider` always have been, never claimed as
live-network-tested. The user was told to revoke and regenerate the key
they pasted into chat, since pasting a credential into a conversation is
itself a compromise of that credential regardless of what this build does
with it -- the new `GEMINI_API_KEY` line in `backend/.env` was left blank
for the user to fill in themselves, directly on their machine, never
through chat.
