/**
 * Reading the server's plan, and the one thing this client is not allowed to
 * do: build one.
 *
 * The plan arrives whole. These tests use a realistic response body and check
 * that the client's readers return what the server sent — the five
 * specialists, the sections, the items, each item's own action and dosage —
 * and that nothing here invents a specialist, a dosage or a fallback
 * programme when the payload is missing or malformed.
 */

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  actionOf,
  actionSections,
  allSections,
  canonicalSpecialistId,
  collaboration,
  dosageOf,
  emptyStateOf,
  exerciseIdOf,
  habitGoals,
  pendingSections,
  planItems,
  planSummary,
  safetyNeedsAttention,
  safetyNoteOf,
  sectionFor,
  sectionPlanId,
  selectedSections,
  trackingOf,
  teamCards,
  unifiedPlan,
} from "../unifiedPlan.js";
import { getExerciseImage } from "../../movementDemos/exerciseImages.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const src = path.resolve(here, "../..");

function exerciseItem(overrides = {}) {
  return {
    specialist: "exercise_movement",
    section: "exercise_programme",
    plan_id: "plan_abc123",
    item_id: "chair-sit-to-stand",
    kind: "exercise",
    title: "Chair Sit-to-Stand",
    detail: "2 × 8",
    why: "Everyday movement practice.",
    target: "Everyday movements",
    metadata: {
      exercise_id: "chair-sit-to-stand",
      sets: 2,
      repetitions: 8,
      difficulty: "beginner",
      progression: "Reduce how much you push off the armrests.",
      regression: "Use a higher seat.",
      safety_notes: ["Use a chair without wheels."],
    },
    action: {
      kind: "start_exercise",
      label: "Start exercise",
      route: "/exercise/chair-sit-to-stand?planId=plan_abc123&itemId=chair-sit-to-stand",
      panel: null,
      recorded_by: "exercise_results",
    },
    tracking: {
      status: "NOT_RECORDED",
      label: "Nothing recorded for this yet.",
      summary: null,
      recorded: 0,
      rows: [],
    },
    progress: {
      direction: "NOT_RECORDED",
      label: "Nothing recorded for this yet",
      metric: null,
      previous: null,
      current: null,
    },
    position: 1,
    ...overrides,
  };
}

const WORKFLOW = {
  available: true,
  safety_status: "Reviewed and approved.",
  unified_plan: {
    available: true,
    plan_id: "plan_abc123",
    version: 2,
    generated_at: "2026-10-01T09:00:00+00:00",
    safety: {
      status: "ALLOW",
      level: "SAFE",
      message: "Reviewed and approved.",
      reason: "No safety rule was triggered.",
      requires_referral: false,
      constrains_plan: false,
    },
    specialists: [
      {
        id: "exercise_movement",
        title: "Exercise & Movement",
        subtitle: "Your personalised movement coach",
        icon: "🏃",
        route: "/specialist/exercise-movement",
        active: true,
        plan_included: true,
        status: "ACTIVE",
        status_label: "Selected for your plan",
        reason: "mobility_need is at HIGH",
      },
      {
        id: "nutrition_lifestyle",
        title: "Nutrition & Lifestyle",
        subtitle: "Everyday nutrition and lifestyle support",
        icon: "🍎",
        route: "/specialist/nutrition-lifestyle",
        active: false,
        plan_included: false,
        status: "NOT_ASSESSED",
        status_label: "Not yet assessed",
        reason: "nutrition_need could not be evaluated",
      },
      {
        id: "behaviour_adherence",
        title: "Behaviour & Adherence",
        subtitle: "Habits that are actually maintainable",
        icon: "🧠",
        route: "/specialist/behaviour-adherence",
        active: true,
        plan_included: true,
        status: "ACTIVE",
        status_label: "Selected for your plan",
        reason: "behaviour_need is at HIGH",
      },
      {
        id: "recovery_care",
        title: "Recovery & Care",
        subtitle: "Rest, recovery and sustainable pacing",
        icon: "🌙",
        route: "/specialist/recovery-care",
        active: false,
        plan_included: false,
        status: "EVALUATED_NOT_REQUIRED",
        status_label: "Reviewed — nothing needed right now",
        reason: "Reported sleep did not cross this project's markers",
      },
      {
        id: "safety_practitioner",
        title: "Safety & Practitioner Recommendation",
        subtitle: "Reviews every recommendation before you see it",
        icon: "🛡️",
        route: "/specialist/safety-practitioner",
        active: true,
        plan_included: false,
        status: "ALLOW",
        status_label: "Reviewed — approved",
        reason: "No safety rule was triggered.",
      },
    ],
    sections: [
      {
        specialist: "exercise_movement",
        title: "Exercise & Movement",
        subtitle: "Your personalised movement coach",
        icon: "🏃",
        route: "/specialist/exercise-movement",
        status: "ACTIVE",
        status_label: "Selected for your plan",
        selected: true,
        why_active: "mobility_need is at HIGH",
        why_inactive: null,
        current_focus: "Upper-body mobility: Needs work",
        decision: "Move more freely.",
        actions: [exerciseItem()],
        tracking: {
          status: "NOT_RECORDED",
          label: "Nothing recorded for this part of the plan yet.",
          rows: [],
        },
        progress: { direction: "NOT_RECORDED", label: "Nothing recorded yet.", rows: [] },
        next_step: "Your recorded exercises are reviewed against your assessment.",
        evidence: ["Hand / shoulder raise: measured"],
        missing: [],
        is_safety_supervisor: false,
      },
      {
        specialist: "behaviour_adherence",
        title: "Behaviour & Adherence",
        subtitle: "Habits that are actually maintainable",
        icon: "🧠",
        route: "/specialist/behaviour-adherence",
        status: "ACTIVE",
        status_label: "Selected for your plan",
        selected: true,
        why_active: "behaviour_need is at HIGH",
        why_inactive: null,
        current_focus: "Daily activity habits: Needs work",
        decision: "Break up long sitting blocks.",
        actions: [
          {
            specialist: "behaviour_adherence",
            section: "habit_goals",
            plan_id: "habit_p1",
            item_id: "take_regular_movement_breaks",
            kind: "habit_goal",
            title: "Take regular movement breaks",
            detail: "Stand up for two minutes every hour.",
            why: "You reported nine hours of sitting.",
            metadata: { topic_id: "take_regular_movement_breaks" },
            action: {
              kind: "complete_habit",
              label: "Complete habit",
              route: null,
              panel: "behaviour_actions",
              recorded_by: "behaviour_log",
            },
            tracking: {
              status: "NOT_RECORDED",
              label: "Nothing recorded for this habit yet.",
              rows: [],
            },
            progress: { direction: "NOT_LOGGED", label: "Nothing recorded yet.", rows: [] },
            position: 2,
          },
        ],
        tracking: {
          status: "NOT_RECORDED",
          label: "Nothing recorded for this part of the plan yet.",
          rows: [],
        },
        progress: { direction: "NOT_RECORDED", label: "Nothing recorded yet.", rows: [] },
        next_step: "How consistently you keep these up decides whether they stay.",
        evidence: [],
        missing: [],
        is_safety_supervisor: false,
      },
      {
        specialist: "nutrition_lifestyle",
        title: "Nutrition & Lifestyle",
        subtitle: "Everyday nutrition and lifestyle support",
        icon: "🍎",
        route: "/specialist/nutrition-lifestyle",
        status: "NOT_ASSESSED",
        status_label: "Not yet assessed",
        selected: false,
        why_active: null,
        why_inactive: "nutrition_need could not be evaluated",
        current_focus: null,
        decision: null,
        actions: [],
        tracking: { status: "NOT_RECORDED", label: "No actions yet.", rows: [] },
        progress: { direction: "NOT_RECORDED", label: "Nothing recorded yet.", rows: [] },
        next_step: "Answer the lifestyle questions so this can be evaluated.",
        evidence: [],
        missing: ["Meal pattern", "Water intake"],
        is_safety_supervisor: false,
      },
    ],
    items: [
      exerciseItem(),
      {
        specialist: "behaviour_adherence",
        section: "habit_goals",
        plan_id: "habit_p1",
        item_id: "take_regular_movement_breaks",
        kind: "habit_goal",
        title: "Take regular movement breaks",
        detail: "Stand up for two minutes every hour.",
        why: "You reported nine hours of sitting.",
        metadata: { topic_id: "take_regular_movement_breaks" },
        action: {
          kind: "complete_habit",
          label: "Complete habit",
          route: null,
          panel: "behaviour_actions",
          recorded_by: "behaviour_log",
        },
        tracking: {
          status: "NOT_RECORDED",
          label: "Nothing recorded for this habit yet.",
          rows: [],
        },
        progress: { direction: "NOT_LOGGED", label: "Nothing recorded yet.", rows: [] },
        position: 2,
      },
    ],
    constraints: [
      {
        source: "recovery_care",
        type: "limit_progression",
        reason: "Recovery evidence this cycle: sleep is 5.5 hours a night.",
        applies_to: ["exercise_movement"],
      },
    ],
    active_specialists: ["exercise_movement", "behaviour_adherence", "safety_practitioner"],
    counts: { selected_specialists: 2, actions: 2, exercises: 1 },
  },
};

test("the plan is read from unified_plan and never rebuilt", () => {
  const plan = unifiedPlan(WORKFLOW);

  assert.ok(plan);
  assert.equal(plan.version, 2);
  assert.equal(plan.plan_id, "plan_abc123");
});

test("there is no unified plan when the server did not send one", () => {
  assert.equal(unifiedPlan({}), null);
  assert.equal(unifiedPlan(null), null);
  assert.deepEqual(planItems({}), []);
  assert.deepEqual(allSections({}), []);
});

test("exactly the five specialists the server sent are returned", () => {
  const team = teamCards(WORKFLOW);

  assert.equal(team.length, 5);
  assert.deepEqual(
    team.map((card) => card.id),
    [
      "exercise_movement",
      "nutrition_lifestyle",
      "behaviour_adherence",
      "recovery_care",
      "safety_practitioner",
    ],
  );
});

test("team cards fall back to the server's specialists_team, not to a local list", () => {
  const team = teamCards({ specialists_team: [{ id: "recovery_care", title: "Recovery & Care" }] });

  assert.equal(team.length, 1);
  assert.equal(team[0].id, "recovery_care");
});

test("only sections the server marked as selected are shown as the plan", () => {
  const selected = selectedSections(WORKFLOW);

  assert.deepEqual(
    selected.map((section) => section.specialist),
    ["exercise_movement", "behaviour_adherence"],
  );

  // The unselected specialist is still available for its own detail page —
  // with its own honest reason for not being needed.
  const nutrition = sectionFor(WORKFLOW, "nutrition_lifestyle");

  assert.equal(nutrition.selected, false);
  assert.match(nutrition.why_inactive, /could not be evaluated/);
  assert.equal(nutrition.why_active, null);
});

test("a retired specialist link resolves to the one that absorbed it", () => {
  assert.equal(canonicalSpecialistId("physio"), "exercise_movement");
  assert.equal(canonicalSpecialistId("exercise"), "exercise_movement");
  assert.equal(canonicalSpecialistId("exercise_activity"), "exercise_movement");
  assert.equal(canonicalSpecialistId("habits"), "behaviour_adherence");
  assert.equal(canonicalSpecialistId("safety"), "safety_practitioner");
  assert.equal(canonicalSpecialistId("not-a-specialist"), null);

  // And that resolution finds the right section.
  assert.equal(sectionFor(WORKFLOW, "physio").specialist, "exercise_movement");
});

test("plan items keep the server's order and positions", () => {
  const items = planItems(WORKFLOW);

  assert.deepEqual(
    items.map((item) => item.position),
    [1, 2],
  );
});

test("the action on an item is the server's, verbatim", () => {
  const [exercise, habit] = planItems(WORKFLOW);

  assert.equal(actionOf(exercise).kind, "start_exercise");
  assert.match(actionOf(exercise).route, /^\/exercise\/chair-sit-to-stand\?planId=/);
  assert.equal(actionOf(habit).kind, "complete_habit");
  // The habit is recorded by an inline panel, so it has no route — and the
  // client must not invent one.
  assert.equal(actionOf(habit).route, null);
});

test("an item with no action yields no action", () => {
  assert.equal(actionOf({}), null);
  assert.equal(actionOf({ action: { kind: "start_exercise" } }), null);
  assert.equal(actionOf({ action: { label: "Start exercise" } }), null);
});

test("an exercise item's image is looked up by its own library id", () => {
  const [exercise] = planItems(WORKFLOW);

  assert.equal(exerciseIdOf(exercise), "chair-sit-to-stand");

  const image = getExerciseImage(exerciseIdOf(exercise));

  // Whether or not an image exists for this specific id, the lookup must be
  // for THIS id — never a substituted movement.
  if (image) {
    assert.match(image.src, /chair-sit-to-stand/);
  }

  // A non-exercise item has no exercise id at all.
  assert.equal(exerciseIdOf({ kind: "habit_goal", item_id: "x" }), null);
});

test("every image the client maps belongs to a real library exercise id", () => {
  // Guards the "do not substitute an unrelated exercise" rule from the other
  // side: the map may only hold ids the backend library actually defines.
  const data = readFileSync(
    path.join(src, "../backend/exercise_library/data.py"),
    "utf8",
  );
  const libraryIds = new Set(
    [...data.matchAll(/"exercise_id": "([a-z0-9-]+)"/g)].map(([, id]) => id),
  );

  const images = readFileSync(
    path.join(src, "movementDemos/exerciseImages.js"),
    "utf8",
  );
  const mapped = [...images.matchAll(/^\s{2}"([a-z0-9-]+)": \{/gm)].map(([, id]) => id);

  assert.ok(mapped.length > 0);

  for (const id of mapped) {
    assert.ok(libraryIds.has(id), `exerciseImages maps unknown exercise id ${id}`);
  }
});

test("dosage comes from the item's own numbers", () => {
  assert.equal(dosageOf(planItems(WORKFLOW)[0]), "2 × 8");
  assert.equal(dosageOf({ metadata: { sets: 2, duration_seconds: 20 } }), "2 sets · 20s hold");
  assert.equal(dosageOf({ detail: "10 repetitions" }), "10 repetitions");
  assert.equal(dosageOf({}), null);
});

test("a safety note is surfaced, and a withheld item says so", () => {
  assert.equal(safetyNoteOf({ metadata: {} }), null);

  const annotated = safetyNoteOf({
    metadata: { safety: { withheld: false, note: "Discuss with a professional." } },
  });

  assert.equal(annotated.withheld, false);
  assert.equal(annotated.text, "Discuss with a professional.");

  const withheld = safetyNoteOf({
    metadata: { safety: { withheld: true, status: "PAUSE", reason: "Paused." } },
  });

  assert.equal(withheld.withheld, true);
  assert.equal(withheld.text, "Paused.");
});

test("habit goals are built from the habit items' own topic ids", () => {
  const behaviour = sectionFor(WORKFLOW, "behaviour_adherence");
  const goals = habitGoals(behaviour);

  assert.equal(goals.length, 1);
  assert.equal(goals[0].topicId, "take_regular_movement_breaks");
  assert.equal(goals[0].name, "Take regular movement breaks");

  // A section whose items are not habits yields no habit goals rather than a
  // guessed one.
  assert.deepEqual(habitGoals(sectionFor(WORKFLOW, "exercise_movement")), []);
});

test("a section's plan id is the plan id its own items carry", () => {
  assert.equal(sectionPlanId(sectionFor(WORKFLOW, "exercise_movement")), "plan_abc123");
  assert.equal(sectionPlanId(sectionFor(WORKFLOW, "behaviour_adherence")), "habit_p1");
  // Advice with no persisted plan has no plan id to record against.
  assert.equal(sectionPlanId({ actions: [{ plan_id: null }] }), null);
});

test("tracking is passed through, including that nothing is recorded", () => {
  const tracking = trackingOf(planItems(WORKFLOW)[0]);

  assert.equal(tracking.status, "NOT_RECORDED");
  assert.equal(tracking.recorded, 0);
});

test("the plan modules contain no locally written plan content", () => {
  // The structural half of "React does not reconstruct unified_plan": the plan
  // screen reads the server's plan and holds no programme, dosage or rationale
  // of its own.
  const planPage = readFileSync(path.join(src, "pages/PlanPage.jsx"), "utf8");
  const readers = readFileSync(path.join(src, "services/unifiedPlan.js"), "utf8");

  for (const source of [planPage, readers]) {
    assert.ok(
      !/targetRepetitions|defaultRecommendations|defaultEvidence|defaultReason/.test(
        source,
      ),
      "a locally written recommendation table is back in the plan path",
    );
  }

  assert.match(planPage, /unifiedPlan\(/, "PlanPage no longer reads the server's plan");
  assert.match(
    planPage,
    /actionSections\(/,
    "PlanPage no longer uses the server's action list",
  );
  assert.match(
    planPage,
    /pendingSections\(/,
    "PlanPage no longer uses the server's empty-state actions",
  );
});

// ---------------------------------------------------------------------------
// The parts that exist so a person can read the plan
// ---------------------------------------------------------------------------

const PRESENTABLE = {
  available: true,
  summary: {
    headline: "Your plan is currently focused on balance and consistency.",
    focus_areas: ["Balance", "Consistency"],
    next: "Complete your activities. MoveWell uses what you record to adapt it.",
  },
  safety: {
    status: "MODIFY",
    level: "CAUTION",
    message: "Some recommendations need review before you follow them.",
    reason: "A confirmed medical report is on file.",
    requires_referral: false,
    constrains_plan: true,
  },
  collaboration: {
    title: "How your MoveWell team worked",
    intro: "MoveWell picked the specialists your own evidence called for.",
    steps: [
      { kind: "assessment", title: "Your assessment", icon: "📋", participated: true, summary: "MoveWell looked at your movement assessment." },
      { kind: "specialist", specialist: "exercise_movement", title: "Exercise & Movement", icon: "🏃", participated: true, summary: "Your assessment highlighted balance." },
      { kind: "specialist", specialist: "nutrition_lifestyle", title: "Nutrition & Lifestyle", icon: "🍎", participated: false, summary: "Not assessed yet.", action: { kind: "nutrition_check_in", label: "Complete check-in", route: "/nutrition-check-in" } },
      { kind: "synthesis", title: "MoveWell", icon: "✨", participated: true, summary: "These were combined into your one MoveWell plan." },
    ],
  },
  sections: [
    {
      specialist: "exercise_movement",
      selected: true,
      team_status: "ACTIVE",
      team_status_label: "Active",
      short_reason: "Your assessment highlighted balance.",
      actions: [{ item_id: "wall-sit", kind: "exercise", position: 1 }],
      empty_state: null,
    },
    {
      specialist: "nutrition_lifestyle",
      selected: false,
      team_status: "NOT_ASSESSED",
      team_status_label: "Not assessed",
      short_reason: "Not assessed yet — the nutrition check-in has not been completed.",
      actions: [],
      empty_state: {
        kind: "not_assessed",
        message: "Complete your nutrition check-in so MoveWell can personalize this part of your plan.",
        action: { kind: "nutrition_check_in", label: "Complete check-in", route: "/nutrition-check-in" },
      },
    },
    {
      specialist: "recovery_care",
      selected: true,
      team_status: "ACTIVE",
      team_status_label: "Active",
      short_reason: "Your reported rest is pacing how quickly activity increases.",
      actions: [{ item_id: "protect_sleep_window", kind: "recovery_action", position: 2 }],
      empty_state: null,
    },
  ],
  specialists: [],
  items: [],
  constraints: [],
};

test("the summary is passed through untouched", () => {
  const workflow = { unified_plan: PRESENTABLE };
  const summary = planSummary(workflow);

  assert.equal(summary.headline, PRESENTABLE.summary.headline);
  assert.deepEqual(summary.focus_areas, ["Balance", "Consistency"]);
  assert.match(summary.next, /adapt/);
});

test("there is no summary or collaboration to read when none was sent", () => {
  assert.equal(planSummary({}), null);
  assert.equal(collaboration({}), null);
  assert.equal(collaboration({ unified_plan: { collaboration: { steps: "no" } } }), null);
});

test("the collaboration flow keeps its order and its honest participation", () => {
  const block = collaboration({ unified_plan: PRESENTABLE });

  assert.equal(block.steps[0].kind, "assessment");
  assert.equal(block.steps.at(-1).kind, "synthesis");

  const nutrition = block.steps.find((step) => step.specialist === "nutrition_lifestyle");

  assert.equal(nutrition.participated, false);
  assert.equal(nutrition.action.route, "/nutrition-check-in");
});

test("the action list is the sections that actually have something to do", () => {
  const workflow = { unified_plan: PRESENTABLE };
  const actions = actionSections(workflow);

  assert.deepEqual(
    actions.map((section) => section.specialist),
    ["exercise_movement", "recovery_care"],
  );
});

test("the pending list is the sections whose empty state offers a next step", () => {
  const workflow = { unified_plan: PRESENTABLE };
  const pending = pendingSections(workflow);

  assert.deepEqual(
    pending.map((section) => section.specialist),
    ["nutrition_lifestyle"],
  );
  assert.match(emptyStateOf(pending[0]).message, /check-in/);
});

test("safety is only prominent when it changed something", () => {
  assert.equal(
    safetyNeedsAttention({ safety: { status: "ALLOW", constrains_plan: false } }),
    false,
  );
  assert.equal(
    safetyNeedsAttention({ safety: { status: "MODIFY", constrains_plan: true } }),
    true,
  );
  assert.equal(
    safetyNeedsAttention({ safety: { status: "REFER", requires_referral: true } }),
    true,
  );
  assert.equal(safetyNeedsAttention(null), false);
});
