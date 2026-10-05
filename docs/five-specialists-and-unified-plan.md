# The five specialists and the unified plan

> **See also:** `docs/product-experience.md` describes the interface these
> specialists appear in after the product remodel — the four sections
> (Today / Plan / Progress / You), the design language, the MoveWell Score, and
> the journey from profile to adapted plan.

This document describes the user-facing layer of MoveWell after the adaptive
rebuild: which specialists a person actually sees, what the plan contract is,
how a recorded result reaches the next plan, and one production-blocking bug
that was found and fixed on the way.

It does not replace `docs/architecture.md`, which still describes the domain
modules (`physio_agent`, `behaviour_agent`, `nutrition_agent`,
`recovery_agent`, `activity_agent`, `progress_agent`, `safety`). Those are
unchanged, and they are not the same thing as the five specialists below.

## 1. The five specialists

`backend/orchestration/specialists.py` is the single place they are defined.

| id | presented as | fed by |
| --- | --- | --- |
| `exercise_movement` | Exercise & Movement | `physio_agent` (camera-measured movement needs, exercise selection) **and** `activity_agent` (self-reported daily volume) |
| `nutrition_lifestyle` | Nutrition & Lifestyle | `nutrition_agent` |
| `behaviour_adherence` | Behaviour & Adherence | `behaviour_agent` |
| `recovery_care` | Recovery & Care | `recovery_agent` |
| `safety_practitioner` | Safety & Practitioner Recommendation | `safety` (the gate) |

Two specialists that used to be presented separately are gone from the
user-facing surface: "Exercise & Physical Activity" and "Physiotherapy &
Movement" are now the one movement coach, and "Safety & Clinical Escalation"
is now a practitioner recommendation. `LEGACY_ID_ALIASES` maps every retired id
onto the specialist that absorbed it, so a stored id or an old link still
resolves; `src/services/unifiedPlan.js` mirrors that table, and
`src/services/__tests__/specialistsNavigation.test.js` reads the Python file and
fails if the two ever disagree.

## 2. The unified plan

`backend/workflow/response.py::build_unified_plan()` assembles ONE plan from the
persisted specialist output plus this run's Safety Result. The client renders it;
it does not compose it.

```
{
  "available": bool,
  "plan_id": "...",                  # the newest domain plan record's id
  "version": 2,                      # highest plan_version across sections
  "safety": { status, level, message, reason, requires_referral, constrains_plan },
  "specialists": [ ...five cards... ],
  "sections": [
    {
      "specialist": "exercise_movement",
      "status": "ACTIVE", "status_label": "Selected for your plan",
      "selected": true,
      "why_active": "...", "why_inactive": null,
      "current_focus": "...", "decision": "...",
      "actions": [ ...items... ],
      "tracking": {...}, "progress": {...}, "next_step": "...",
      "evidence": [...], "missing": [...]
    }
  ],
  "items": [ ...the same items, flat, in plan order... ],
  "constraints": [ ...what other specialists changed... ]
}
```

Every item carries:

```json
{
  "position": 1,
  "specialist": "exercise_movement",
  "section": "exercise_programme",
  "plan_id": "plan_ab12cd34",
  "item_id": "chair-sit-to-stand",
  "kind": "exercise",
  "title": "Chair Sit-to-Stand",
  "detail": "2 × 8",
  "why": "...",
  "target": "Everyday movements",
  "metadata": { "exercise_id": "...", "sets": 2, "repetitions": 8, "progression": "...", "safety_notes": [...] },
  "action": {
    "kind": "start_exercise",
    "label": "Start exercise",
    "route": "/exercise/chair-sit-to-stand?planId=plan_ab12cd34&itemId=chair-sit-to-stand",
    "panel": null,
    "recorded_by": "exercise_results"
  },
  "tracking": { "status": "COMPLETED", "label": "...", "summary": "8 repetitions of 8", "recorded": 2 },
  "progress": { "direction": "IMPROVING", "label": "...", "from": 6, "to": 8, "metric": "Repetitions" }
}
```

The identifiers are **domain** identifiers only. `item_id` is the exercise
library id / nutrition topic id / behaviour topic id — the identifier the
libraries and the recording APIs already use. A workflow id, an agent-run id or
a Mongo `_id` never appears (asserted in `backend/tests/test_unified_plan.py`
and `backend/tests/test_plan_generation_integration.py`).

### Four action kinds

| kind | used by | what the client does |
| --- | --- | --- |
| `start_exercise` | exercise items | navigates to the existing `ExercisePage` with `planId`/`itemId` |
| `complete_habit` | habit items | renders the inline behaviour panel, which POSTs `/api/behaviour-log` |
| `log_nutrition` | nutrition items | renders the inline food-log panel, which POSTs `/api/food-log` |
| `view_guidance` | recovery, activity volume, safety | navigates to that specialist's page |

### Selection is not hard-coded

`selected` on a section is true when the Orchestrator selected that specialist
this cycle, or when it already has actions in the plan. Everything a specialist
says comes from `orchestrator/decision.py` and from that specialist's own
reasoning module. Two users with different evidence get different specialists;
`backend/tests/test_unified_plan.py::DynamicSelectionTests` and
`verify_adaptive_loop.py` section 6 both check that.

`NOT_ASSESSED` stays its own state. It means "this project has no evidence to
judge this domain with", which is not the same sentence as "it was assessed and
nothing is needed" (`EVALUATED_NOT_REQUIRED`).

## 3. Safety reaches the plan

The Safety Gate already ran before anything was persisted, and the Orchestrator
already removed blocked recommendations from what was stored. `build_unified_plan`
carries the verdict onto the plan a user reads later:

* **ALLOW** — nothing withheld, no constraint.
* **MODIFY** — the named items carry the gate's own reason as a safety note; a
  plan-level constraint records it.
* **PAUSE / REFER** — the named items (every item, for REFER) are marked
  `withheld`, their button becomes "Paused — see safety guidance", and
  `ExercisePage` refuses to start a withheld item. A REFER withholds every
  action except the Safety specialist's own guidance, because a referral is
  exactly the case where the user has to be able to read who to talk to.

The safety specialist's own item is never withheld by its own verdict.

## 4. The feedback loop

```
PLAN  ->  user acts  ->  result persisted  ->  tracking/progress  ->  next plan
```

* **Exercise** — `ExercisePage` submits to `/api/exercise-results` with
  `plan_id` and `item_id` (`exercise_assessment/store.py` stores both). The
  unified plan reads those same records back: `tracking` counts the sessions
  recorded against *this* plan item, and `progress` compares this user's latest
  two sessions on repetitions, hold time or completion — whichever the result
  carries. One session is reported as `NOT_ENOUGH_DATA`, not as progress.
* **Behaviour** — the panel POSTs `/api/behaviour-log`; tracking reuses
  `behaviour_agent/adherence.py::compute_behaviour_adherence`, so the plan and
  the Progress Agent cannot disagree about what the records say.
* **Nutrition** — the panel POSTs `/api/food-log`; tracking counts entries
  recorded against this plan and the days they cover.
* **Recovery and activity volume** — MoveWell has no completion record for
  these, and the plan says so rather than offering a button that writes nothing.
  Their action is to open the guidance.
* **Adaptation** — `POST /api/workflow/run` with
  `{"progress_trigger": {"reason": "..."}}` runs the Progress Agent, which
  dispatches the specialist that needs to re-plan.

`routes/workflow.py::_tracking_evidence()` reads the three stores once per
request and hands them to the serialiser, so the plan screen and the specialist
screens can never disagree.

## 5. The bug that was blocking all of this

`physio_agent/input_contract.py`, `progress_agent/input_contract.py`,
`behaviour_agent/input_contract.py` and `nutrition_agent/input_contract.py` each
refused any input whose serialised text contained the word `keypoint`. The
browser sends `quality.meanKeypointScore` with **every** assessment session — a
single number summarising detector confidence, which
`assessments/schema.py` deliberately stores — so on real data:

* the Physio Agent refused its own legitimate input, and no movement plan was
  ever produced (the run reported
  `Physio Agent run failed: ... appears to contain 'keypoint'`);
* the Progress Agent refused its own input too, so no progress review ever ran.

The rule is now structural, in one shared module
(`backend/orchestration/pose_boundary.py`), mirroring the two-tier rule
`assessments/schema.py` already documents: a **scalar** under a pose-related
name is a summary and passes; a **list or object** under a pose-related name is
a sequence and is refused; a name with no legitimate scalar counterpart
(`video`, `image`, `base64`, `dataurl`, `rawFrame`, …) is refused whatever its
value; a data URI or a long encoded string is refused wherever it appears.
Prose that merely mentions keypoints is prose.

## 6. Exercise imagery

`src/movementDemos/exerciseImages.js` maps exercise ids to two kinds of asset:
the six two-panel diagrams drawn for this project, and five photographs taken
from the public-domain [free-exercise-db](https://github.com/yuhonas/free-exercise-db)
(the Unlicense) — `standing-shoulder-raise`, `standing-overhead-reach`,
`standing-trunk-rotation`, `standing-ankle-circles`, `seated-knee-extension`.
Every photograph was inspected before being kept; candidates whose depiction
showed different equipment or a different movement (a heel raise with
dumbbells, a hamstring stretch with a strap and a bent rear leg, a knee raise
for a supported single-leg stand, a squat for a chair sit-to-stand) were
rejected. An exercise with no accurate asset shows no image and falls back to
the animated demonstration; it never shows a substituted movement.

`src/movementDemos/__tests__/exerciseImages.test.js` checks that every mapped
file exists, that a diagram's file name is its exercise id, that a photograph
stays filed under its own id, that no two exercises share a picture, and that
every mapped id is a real exercise in the library.

## 7. Verifying it
```bash
# Backend unit tests (needs MONGODB_URI and JWT_SECRET in the environment)
cd backend && python -m unittest discover -s tests -t .

# End-to-end over real HTTP against a running server and a real database
cd backend && python verify_adaptive_loop.py

# Frontend unit tests, build, and a real render of the plan UI
npm test
npm run build
npm run test:render
```

`npm run test:render` builds the plan components with Vite for Node and renders
them with `react-dom/server`, so "the UI renders this payload" is answered by an
actual render rather than by compilation.

## 8. The editable profile

`routes/profile_spec.py` defines every field a user may change, the option
vocabulary for each select, and the range for each number. Both the endpoint
that serves the profile and the endpoint that validates a change read it, so the
editor can only offer what the server accepts.

| Endpoint | What it does |
| --- | --- |
| `GET /api/profile` | the four sections with this user's current values |
| `PATCH /api/profile` | a partial change: only the fields sent are touched |
| `GET /api/profile/nutrition-check-in` | the six questions and this user's answers |
| `PATCH /api/profile/nutrition-check-in` | save check-in answers |

Sections: **Basic information** (name, age, sex), **Body** (height, weight),
**Lifestyle** (work type, sitting, screen, sleep, sleep quality, steps, exercise
frequency and session length), **Goals & preferences** (the stated nutrition
goal). A value outside a field's range or vocabulary is refused with 400 and
nothing is written — a rejected save never lands half-applied.

Two deliberate exclusions:

* **The self-reported health answers are not editable** (conditions, previous
  injuries, pain). They are collected at onboarding, the Safety specialist reads
  them, and a medical-history editor is a decision about consent and review that
  a profile form should not make on its own.
* **Nothing in the profile flow regenerates the plan.** The confirmation says
  the change applies to the next plan review, and the plan keeps its own
  explicit action. A plan that changes underneath a user without them asking is
  the churn this avoids.

The write goes to the same `health_profiles` document the onboarding form
maintains, which is the document `user_state/schema.py` projects into the User
State — so an edit is input to the next run with no extra plumbing. That chain is
asserted in `tests/test_profile_editing.py`.

## 9. The Nutrition & Lifestyle check-in

`nutrition_library/check_in.py` is the single definition of the six questions,
their options, and the stored value each option means. The endpoint serves it,
the validation reads it, and the need assessment reads the same vocabularies, so
the form cannot offer an answer the server would refuse.

Two rules shaped it:

* **No second storage.** Where a question already had a field, the question
  writes that field: fruit-and-vegetable *frequency* is stored as the
  servings-per-day number onboarding already collected, and water *band* as the
  glasses-per-day number. Only three keys are new, because only three questions
  had nothing behind them: `meals_per_day`, `eating_out_frequency` and
  `nutrition_goal`.
* **A goal is not evidence.** `nutrition_goal` is stored and reaches the
  Nutrition Agent as context, and it shapes the plan's focus wording. It is
  never counted as a need factor: "I want to hydrate more" is not a finding
  about anybody's diet. A user who has answered only the goal question is
  reported as `NOT_ASSESSED`, with an explanation saying exactly that.

The chain is `check-in → persist → nutrition need → nutrition specialist →
unified plan`, and it is now reachable in practice: before this, nutrition could
only ever report NOT_ASSESSED because nothing in the product asked.

## 10. The plan as a person reads it

The reading order on `/plan` is:

1. **Your MoveWell plan** — one sentence naming the areas this plan is actually
   about, plus the areas as chips. Built from the measured need levels and any
   goal the user stated.
2. **Safety review** — one compact block, and only prominent when the verdict
   *changed* something (MODIFY / PAUSE / REFER). An ALLOW is a single quiet line.
   The same paragraph is never repeated down the page.
3. **Your MoveWell team** — exactly five compact cards: name, compact status,
   one short reason, and a way in. No exercise lists, no paragraphs.
4. **This week** — the actions, specialist by specialist, with each specialist's
   reasoning behind a `View details` disclosure.
5. **How your MoveWell team worked** — the collaboration flow.
6. **Your MoveWell summary** — the focus areas, and the one sentence describing
   what happens next.

Everything that used to lead the page is still there, inside `View details`:
current focus, what was decided, tracking, progress, what happens next, the
evidence, and what is still unknown.

Empty states are one per section rather than a "nothing recorded yet" line on
every card, and each says what is missing, why it matters, and the single thing
to do about it — all three produced server-side as `section.empty_state` with
`kind: "not_assessed"` or `kind: "no_records"`.

## 11. The collaboration flow

`unified_plan.collaboration` is a sequence: what MoveWell looked at, what each
of the five specialists contributed, and the single plan those inputs became.
A specialist that was not selected appears as `participated: false` with the
honest sentence, and — where the user can act on it — the action that would
assess it (the nutrition check-in, the movement assessment). It is a decision
summary, not a transcript: no prompts, no reasoning, no internal names.

## 12. Progress

`/progress` is five blocks in the order a person asks the questions: what you
completed, what changed in your plan, what your plan focuses on now, what moved
forward (the charts, with exercise names rather than library ids), and what
happens next. An absence of data is reported as an absence, with the action that
would give the page something to show. The Progress Agent's own machine
vocabulary is never printed.

