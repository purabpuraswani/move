/**
 * TEMPORARY verification harness (deleted after use).
 *
 * Renders src/pages/TodayPage.jsx under Node with a recorded workflow response
 * and checks what actually comes out — the whole point of the page is what a
 * person reads, and this is the only way to see it without a browser.
 */

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";

const team = [
  {
    id: "exercise_movement",
    title: "Exercise & Movement",
    subtitle: "Personalised movement guidance",
    icon: "🏃",
    route: "/specialist/exercise_movement",
    status: "ACTIVE",
    status_label: "Selected for your plan",
  },
  {
    id: "nutrition_lifestyle",
    title: "Nutrition & Lifestyle",
    subtitle: "Everyday nutrition and hydration",
    icon: "🥗",
    route: "/specialist/nutrition_lifestyle",
    status: "ACTIVE",
    status_label: "Selected for your plan",
  },
  {
    id: "behaviour_adherence",
    title: "Behaviour & Adherence",
    subtitle: "Habits that hold up in a normal week",
    icon: "🧠",
    route: "/specialist/behaviour_adherence",
    status: "NOT_ASSESSED",
    status_label: "Not yet assessed",
  },
  {
    id: "recovery_care",
    title: "Recovery & Care",
    subtitle: "Rest, sleep and pacing",
    icon: "🌙",
    route: "/specialist/recovery_care",
    status: "EVALUATED_NOT_REQUIRED",
    status_label: "Reviewed — nothing needed right now",
  },
  {
    id: "safety_practitioner",
    title: "Safety & Practitioner Recommendation",
    subtitle: "Checks your plan before you see it",
    icon: "🛡️",
    route: "/specialist/safety_practitioner",
    status: "MODIFY",
    status_label: "Reviewed — modified",
  },
];

const exerciseItem = {
  specialist: "exercise_movement",
  section: "exercise_programme",
  plan_id: "plan_abc123",
  item_id: "chair-sit-to-stand",
  kind: "exercise",
  title: "Chair Sit-to-Stand",
  detail: "2 × 8",
  why: "Your sit-to-stand measured slow.",
  target: "Everyday movements",
  metadata: { exercise_id: "chair-sit-to-stand", sets: 2, repetitions: 8 },
  action: {
    kind: "start_exercise",
    label: "Start exercise",
    route: "/exercise/chair-sit-to-stand?planId=plan_abc123&itemId=chair-sit-to-stand",
  },
  tracking: {
    status: "COMPLETED",
    label: "2 sessions recorded, 1 meeting the target",
    recorded: 2,
    completed: 1,
    counts_toward_section: true,
    rows: [],
  },
  progress: { direction: "IMPROVING", label: "Up on your last session", rows: [] },
  position: 1,
};

const nutritionItem = {
  specialist: "nutrition_lifestyle",
  section: "nutrition_goals",
  plan_id: "plan_nut1",
  item_id: "hydration",
  kind: "nutrition_goal",
  title: "Hydration",
  detail: "Drink a glass of water with each meal.",
  why: "You reported drinking little during the day.",
  target: null,
  metadata: { topic_id: "hydration" },
  action: {
    kind: "log_nutrition",
    label: "Log a meal",
    route: null,
    panel: "food_log",
  },
  tracking: { status: "NOT_RECORDED", label: "Nothing logged against this plan yet.", recorded: 0, rows: [] },
  progress: { direction: "NOT_RECORDED", label: "Nothing logged against this plan yet.", rows: [] },
  position: 3,
};

const sectionBase = (specialist, title, extra) => ({
  specialist,
  title,
  subtitle: null,
  icon: null,
  route: `/specialist/${specialist}`,
  status: "ACTIVE",
  status_label: "Selected for your plan",
  team_status: "ACTIVE",
  team_status_label: "Active",
  short_reason: "Your assessment highlighted standing balance.",
  selected: true,
  current_focus: null,
  decision: null,
  actions: [],
  tracking: { status: "NOT_RECORDED", label: "No actions are in this part of your plan yet.", rows: [] },
  progress: { direction: "NOT_RECORDED", label: "Nothing recorded for this part of the plan yet.", rows: [] },
  next_step: null,
  evidence: [],
  missing: [],
  empty_state: null,
  is_safety_supervisor: false,
  ...extra,
});

const fullPlan = {
  available: true,
  plan_id: "plan_abc123",
  version: 2,
  generated_at: "2026-02-01T09:00:00Z",
  state: { state: "PLAN_AVAILABLE", reason: "Your plan is ready.", missing: [], next_action: null },
  summary: {
    headline: "Your plan is currently focused on balance and consistency.",
    focus_areas: ["Standing balance", "Consistency"],
    next: "Complete your activities and MoveWell will adapt the plan after the next assessment.",
  },
  safety: {
    status: "MODIFY",
    message: "Some recommendations need review before you follow them.",
    reason: "You reported knee pain at onboarding.",
    flags: [],
    requires_referral: false,
    constrains_plan: true,
  },
  specialists: team,
  sections: [
    sectionBase("exercise_movement", "Exercise & Movement", {
      actions: [exerciseItem],
      tracking: { status: "COMPLETED", label: "1 of 2 recorded sessions met the target", rows: [] },
      team_status_label: "Active",
      short_reason: "Your assessment highlighted standing balance.",
      empty_state: null,
    }),
    sectionBase("nutrition_lifestyle", "Nutrition & Lifestyle", {
      actions: [nutritionItem],
      tracking: { status: "NOT_RECORDED", label: "No actions are in this part of your plan yet.", rows: [] },
      short_reason: "Your nutrition check-in answers brought this in.",
      empty_state: null,
    }),
    sectionBase("behaviour_adherence", "Behaviour & Adherence", {
      status: "NOT_ASSESSED",
      status_label: "Not yet assessed",
      team_status: "NOT_ASSESSED",
      team_status_label: "Not assessed",
      selected: false,
      short_reason: "Not assessed yet — the lifestyle questions are unanswered.",
      empty_state: {
        kind: "not_assessed",
        message: "Answer the lifestyle questions so MoveWell can build a habit plan that fits your week.",
        action: { kind: "answer_lifestyle_questions", label: "Answer the questions", route: "/onboarding" },
      },
    }),
    sectionBase("recovery_care", "Recovery & Care", {
      status: "EVALUATED_NOT_REQUIRED",
      status_label: "Reviewed — nothing needed right now",
      team_status: "NOT_NEEDED",
      team_status_label: "Not needed right now",
      selected: false,
      short_reason: "Your reported rest did not need a change.",
    }),
    sectionBase("safety_practitioner", "Safety & Practitioner Recommendation", {
      status: "MODIFY",
      status_label: "Reviewed — modified",
      team_status: "MODIFIED",
      team_status_label: "Reviewed — precautions",
      short_reason: "Reviewed your plan and added precautions.",
      selected: true,
      is_safety_supervisor: true,
    }),
  ],
  items: [exerciseItem, nutritionItem],
  constraints: [],
  collaboration: { title: "How your MoveWell team worked", intro: "", steps: [] },
  active_specialists: ["exercise_movement", "nutrition_lifestyle"],
  counts: { selected_specialists: 3, actions: 2, exercises: 1 },
};

const fullWorkflow = {
  available: true,
  generated_at: "2026-02-01T09:00:00Z",
  movewell_score: {
    available: true,
    value: 72,
    message: "You're doing well overall.",
    focus: { key: "stability_need", label: "Balance and steadiness" },
    focus_statement: "Balance is the thing to work on next.",
    method: "Built from the movement results you recorded and the answers you gave.",
    previous: { value: 64, recorded_at: "2026-01-01T09:00:00Z" },
    change: 8,
    domains: [
      { key: "stability_need", label: "Stability", value: 68, previous_value: 57, change: 11, assessed: true },
      { key: "mobility_need", label: "Mobility", value: 74, previous_value: 78, change: -4, assessed: true },
      { key: "nutrition_need", label: "Nutrition", value: 60, previous_value: 60, change: 0, assessed: true },
      { key: "behaviour_need", label: "Daily habits", value: null, previous_value: null, change: null, assessed: false },
    ],
  },
  plan_state: { state: "PLAN_AVAILABLE", reason: "Your plan is ready.", missing: [], next_action: null },
  plan_status: "PLAN_AVAILABLE",
  unified_plan: fullPlan,
  specialists: [],
  specialists_team: team,
  assessment_summary: {
    status: "COMPLETE",
    tests_completed: 3,
    tests_total: 3,
    completed_tests: ["shoulder", "ftsst", "balance"],
    remaining_tests: [],
    tests: { shoulder: "completed", ftsst: "completed", balance: "completed" },
  },
};

/** A brand-new account: nothing measured, no plan, no records. */
const neverRunWorkflow = {
  available: false,
  message: "No recommendations have been generated yet.",
  plan_state: {
    state: "NEVER_RUN",
    reason: "No movement assessment has produced a usable measurement yet, so there is nothing to build a plan from.",
    missing: [],
    next_action: { label: "Redo the movement assessment", route: "/assessment" },
  },
  movewell_score: {
    available: false,
    value: null,
    message: null,
    focus: null,
    focus_statement: null,
    method: "Built from the results you record and the answers you give.",
    domains: [],
    previous: null,
    change: null,
  },
  specialists_team: team,
  unified_plan: {
    available: false,
    state: {
      state: "NEVER_RUN",
      reason: "No movement assessment has produced a usable measurement yet.",
      missing: [],
      next_action: { label: "Redo the movement assessment", route: "/assessment" },
    },
    summary: {
      headline:
        "Nothing in your plan needs a change right now. Your assessment and answers did not show a need MoveWell would build a plan around.",
      focus_areas: [],
      next: "Complete your activities.",
    },
    safety: { status: "NOT_ASSESSED", message: "Not yet assessed.", reason: null, flags: [], requires_referral: false, constrains_plan: false },
    specialists: team.map((card) => ({ ...card, status: "NOT_ASSESSED", status_label: "Not yet assessed" })),
    sections: team.map((card) =>
      sectionBase(card.id, card.title, {
        status: "NOT_ASSESSED",
        status_label: "Not yet assessed",
        team_status: "NOT_ASSESSED",
        team_status_label: "Not assessed",
        selected: false,
        short_reason: "Not assessed yet — this needs a movement assessment.",
        empty_state:
          card.id === "exercise_movement"
            ? {
                kind: "not_assessed",
                message: "Complete your movement assessment and MoveWell can build this part of your plan.",
                action: { kind: "start_assessment", label: "Start assessment", route: "/assessment" },
              }
            : null,
      }),
    ),
    items: [],
    constraints: [],
    collaboration: { title: "", intro: "", steps: [] },
    active_specialists: [],
    counts: { selected_specialists: 0, actions: 0, exercises: 0 },
  },
  assessment_summary: {
    status: "NONE_COMPLETED",
    tests_completed: 0,
    tests_total: 3,
    completed_tests: [],
    remaining_tests: ["shoulder", "ftsst", "balance"],
    tests: { shoulder: "not_started", ftsst: "not_started", balance: "not_started" },
  },
};

/** An assessment that is saved, with no plan built from it yet. */
const assessmentReadyWorkflow = {
  ...neverRunWorkflow,
  plan_state: {
    state: "NEVER_RUN",
    reason: "Your movement assessment is saved and ready.",
    missing: [],
    next_action: null,
  },
  assessment_summary: {
    status: "PARTIAL",
    tests_completed: 2,
    tests_total: 3,
    completed_tests: ["shoulder", "ftsst"],
    remaining_tests: ["balance"],
    tests: { shoulder: "completed", ftsst: "completed", balance: "not_started" },
  },
  movewell_score: {
    available: true,
    value: 41,
    message: "There is a clear starting point here.",
    focus: { key: "stability_need", label: "Balance and steadiness" },
    focus_statement: "Balance is the place to start.",
    method: "Built from the two checks that were recorded.",
    previous: null,
    change: null,
    domains: [{ key: "stability_need", label: "Stability", value: 41, previous_value: null, change: null, assessed: true }],
  },
  unified_plan: {
    ...neverRunWorkflow.unified_plan,
    available: false,
    state: { state: "NEVER_RUN", reason: "Your movement assessment is saved and ready.", missing: [], next_action: null },
    sections: team.map((card) =>
      sectionBase(card.id, card.title, {
        status: card.id === "exercise_movement" ? "EVALUATED_NOT_REQUIRED" : "NOT_ASSESSED",
        status_label: card.id === "exercise_movement" ? "Reviewed — nothing needed right now" : "Not yet assessed",
        team_status: card.id === "exercise_movement" ? "NOT_NEEDED" : "NOT_ASSESSED",
        team_status_label: card.id === "exercise_movement" ? "Not needed right now" : "Not assessed",
        selected: false,
        short_reason: "Your movement assessment did not show a need right now.",
      }),
    ),
  },
};

const checks = [];
const check = (label, condition) => checks.push({ label, ok: Boolean(condition) });

function render(payload) {
  globalThis.window.__mockWorkflow = payload;

  return renderToStaticMarkup(
    createElement(MemoryRouter, null, createElement(TodayPage)),
  );
}

// The module is imported after the globals exist: services/auth reads
// localStorage at call time, and the page reads the mock at mount.
globalThis.localStorage = {
  getItem: () => "test-token",
  setItem: () => {},
  removeItem: () => {},
};
globalThis.window = globalThis;

const { default: TodayPage } = await import("../pages/TodayPage.jsx");

const full = render(fullWorkflow);
const fresh = render(neverRunWorkflow);
const ready = render(assessmentReadyWorkflow);

console.log("===== FULL PLAN =====");
console.log(full.replace(/></g, ">\n<"));

console.log("\n\n===== FRESH =====");
console.log(fresh.replace(/></g, ">\n<"));

console.log("\n\n===== ASSESSMENT READY =====");
console.log(ready.replace(/></g, ">\n<"));

const { writeFileSync } = await import("node:fs");

writeFileSync("node_modules/.tmp-today/full.html", full.replace(/></g, ">\n<"), "utf8");
writeFileSync("node_modules/.tmp-today/fresh.html", fresh.replace(/></g, ">\n<"), "utf8");
writeFileSync("node_modules/.tmp-today/ready.html", ready.replace(/></g, ">\n<"), "utf8");

// --- the score ----------------------------------------------------------------
check("the score value renders", full.includes(">72<"));
check("the score's own message renders", full.includes("You&#x27;re doing well overall."));
check("the current focus renders", full.includes("Current focus") && full.includes("Balance and steadiness"));
check("the change renders as a comparison", full.includes("64 → 72") && full.includes("+8 since your previous assessment"));
check(
  "the method is behind a disclosure",
  full.includes("How this is worked out") && full.includes("Built from the movement results you recorded"),
);
check("a mover renders with its sign", full.includes("Stability") && full.includes("+11"));
check("a fall renders with a plain minus", full.includes("Mobility") && full.includes("-4"));
check("a zero-change mover is not listed", !full.includes(">+0<") && !full.includes(">-0<"));

// --- today's focus ------------------------------------------------------------
check("the day shows at most three actions", (full.match(/class="plan-item /g) || []).length <= 3);
check("the coach who asked for the action is named", full.includes("Your Movement Coach"));
check("the item's own dosage renders", full.includes("2 × 8"));
check("the server's button label renders", full.includes("Start exercise"));
// The item's button carries the server's label and is wired to the action the
// server sent (the route itself lives in the click handler, not in the markup).
check("the item's button is the server's action", full.includes(">Start exercise</button>"));
check("the day links to the full plan", full.includes(">View plan<") && full.includes('href="/plan"'));

// --- progress, team, plan progress, safety ------------------------------------
check("the team renders five cards", (full.match(/class="mw-card mw-card--flat today-team-card"/g) || []).length === 5);
check("a team card carries the server's status wording", full.includes("Reviewed — precautions"));
check("a team card carries the server's short reason", full.includes("Your nutrition check-in answers brought this in."));
check("plan progress counts the plan's own items", full.includes("Today&#x27;s plan — 1 of 2 actions completed"));
check("a recorded section's own wording renders", full.includes("1 of 2 recorded sessions met the target"));
check("no percentage is invented", !/%/.test(full));
check("safety renders when it changed something", full.includes("Safety review") && full.includes("Some recommendations need review"));
check("safety links to the guidance", full.includes('href="/specialist/safety-practitioner"'));

// --- hygiene ------------------------------------------------------------------
check(
  "no internal or machine vocabulary leaks",
  !/\b(workflow_id|agent_run_id|request_id|NOT_RECORDED|RECORDED|COMPLETED|IMPROVING|DECLINING|NOT_ENOUGH_DATA)\b/.test(full) &&
    !/_need\b/.test(full) &&
    !/orchestrat/i.test(full),
);
check("no raw JSON renders", !full.includes('{"') && !full.includes("&quot;"));

// --- fresh account ------------------------------------------------------------
check("a new account is greeted", fresh.includes("Good ") && fresh.includes("Today"));
check("a new account is invited to assess", fresh.includes("Start with your movement assessment"));
check("the empty score dial says so", fresh.includes("Not measured yet"));
check(
  "the no-score card asks for the assessment",
  fresh.includes("Complete your assessment to understand your current state.") && fresh.includes("Start assessment"),
);
check(
  "the focus empty state carries the server's own message and action",
  fresh.includes("Complete your movement assessment and MoveWell can build this part of your plan."),
);
check("a new account sees no fabricated progress", !fresh.includes("Your progress"));
check("a new account sees no plan count", !fresh.includes("actions completed"));
check("an unapproved plan shows no safety block", !fresh.includes("Safety review"));

// --- assessment ready, no plan ------------------------------------------------
check("the greeting repeats the server's own reason", ready.includes("Your movement assessment is saved and ready."));
check(
  "the headline is not repeated when there is no plan to describe",
  !ready.includes("Nothing in your plan needs a change right now"),
);
check("a real score still renders before a plan exists", ready.includes(">41<"));
check("no comparison is claimed without a previous assessment", !ready.includes("since your previous assessment"));
check("the plan section says there are no actions", ready.includes("There are no actions in your plan yet."));

const failed = checks.filter((entry) => !entry.ok);

for (const entry of checks) {
  console.log(`  [${entry.ok ? "PASS" : "FAIL"}] ${entry.label}`);
}

console.log(`\nPASSED ${checks.length - failed.length}  FAILED ${failed.length}`);

if (failed.length) process.exitCode = 1;
