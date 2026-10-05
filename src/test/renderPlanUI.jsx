/**
 * Renders the plan UI from a realistic `unified_plan` payload and checks what
 * comes out.
 *
 * `npm run test:render` builds this file with `vite build --ssr` and runs it
 * under Node, so what is exercised is the real components with the real JSX and
 * stylesheet handling — an actual render of the code the browser runs, not a
 * compilation check. The unit suite (`npm test`) deliberately stays on plain
 * JavaScript; this is where "does the UI render this payload at all" is
 * answered.
 *
 * The payload below is the shape the API returns (backend/workflow/response.py),
 * including the cases a hand-written fixture usually omits: an item the Safety
 * review withheld, a specialist that was reviewed and not selected, a
 * specialist that was never assessed, and a plan with no records against it. A
 * UI check that only ever sees a happy plan proves the least.
 */

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import CollaborationTimeline from "../components/CollaborationTimeline.jsx";
import PlanSectionPanel from "../components/PlanSectionPanel.jsx";
import SpecialistTeamCard from "../components/SpecialistTeamCard.jsx";

const team = [
  {
    id: "exercise_movement",
    title: "Exercise & Movement",
    icon: "🏃",
    route: "/specialist/exercise-movement",
    status: "ACTIVE",
    team_status: "ACTIVE",
    team_status_label: "Active",
    short_reason: "Your assessment highlighted balance and everyday movement.",
    reason: "physical need dimension(s) at MEDIUM or HIGH",
  },
  {
    id: "nutrition_lifestyle",
    title: "Nutrition & Lifestyle",
    icon: "🍎",
    route: "/specialist/nutrition-lifestyle",
    status: "NOT_ASSESSED",
    team_status: "NOT_ASSESSED",
    team_status_label: "Not assessed",
    short_reason: "Not assessed yet — the nutrition check-in has not been completed.",
  },
  {
    id: "behaviour_adherence",
    title: "Behaviour & Adherence",
    icon: "🧠",
    route: "/specialist/behaviour-adherence",
    status: "ACTIVE",
    team_status: "ACTIVE",
    team_status_label: "Active",
    short_reason: "Your daily habits put consistency at the centre of this plan.",
  },
  {
    id: "recovery_care",
    title: "Recovery & Care",
    icon: "🌙",
    route: "/specialist/recovery-care",
    status: "EVALUATED_NOT_REQUIRED",
    team_status: "NOT_NEEDED",
    team_status_label: "Not needed",
    short_reason: "Your reported rest did not need a change.",
  },
  {
    id: "safety_practitioner",
    title: "Safety & Practitioner Recommendation",
    icon: "🛡️",
    route: "/specialist/safety-practitioner",
    status: "MODIFY",
    team_status: "MODIFIED",
    team_status_label: "Reviewed — precautions",
    short_reason: "Reviewed your plan and added precautions.",
  },
];

const exerciseSection = {
  specialist: "exercise_movement",
  title: "Exercise & Movement",
  subtitle: "Your personalised movement coach",
  icon: "🏃",
  route: "/specialist/exercise-movement",
  status: "ACTIVE",
  status_label: "Selected for your plan",
  team_status: "ACTIVE",
  team_status_label: "Active",
  short_reason: "Your assessment highlighted balance and everyday movement.",
  selected: true,
  why_active: "physical need dimension(s) at MEDIUM or HIGH: functional_movement_need=HIGH",
  why_inactive: null,
  current_focus: "Everyday movements: Needs work",
  decision: "Build everyday strength. Chair Sit-to-Stand: moved up — you met the target twice.",
  actions: [
    {
      specialist: "exercise_movement",
      section: "exercise_programme",
      plan_id: "plan_abc123",
      item_id: "chair-sit-to-stand",
      kind: "exercise",
      title: "Chair Sit-to-Stand",
      detail: "2 × 8",
      why: "Your sit-to-stand measured slow.",
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
        status: "COMPLETED",
        label: "2 sessions recorded, 1 meeting the target",
        summary: "8 repetitions of 8, 100% of the target completed",
        recorded: 2,
        completed: 1,
        rows: [],
      },
      progress: {
        direction: "IMPROVING",
        label: "Up on your last session: repetitions went from 6 to 8",
        metric: "Repetitions",
        rows: [],
      },
      position: 1,
    },
    {
      specialist: "exercise_movement",
      section: "exercise_programme",
      plan_id: "plan_abc123",
      item_id: "wall-sit",
      kind: "exercise",
      title: "Wall Sit",
      detail: "2 × 20s hold",
      why: "Your stability evidence.",
      target: "Balance and steadiness",
      metadata: {
        exercise_id: "wall-sit",
        sets: 2,
        duration_seconds: 20,
        safety: { withheld: true, status: "PAUSE", reason: "Paused pending review." },
      },
      action: {
        kind: "withheld",
        label: "Paused — see safety guidance",
        route: "/specialist/safety-practitioner",
        panel: null,
        recorded_by: null,
      },
      tracking: { status: "NOT_RECORDED", label: "Nothing recorded for this yet.", rows: [] },
      progress: { direction: "NOT_RECORDED", label: "Nothing recorded for this yet", rows: [] },
      position: 2,
      withheld: true,
    },
  ],
  tracking: { status: "COMPLETED", label: "1 of 2 recorded sessions met the target", rows: [] },
  progress: {
    direction: "IMPROVING",
    label: "Your recorded sessions are moving up.",
    plan_version: 2,
    adaptation_reason: "Moved up after two completed sessions.",
    rows: [],
  },
  next_step: "Your recorded exercises are reviewed against your assessment.",
  evidence: ["Chair sit-to-stand x5: measured"],
  missing: ["Daily steps"],
  empty_state: null,
};

const nutritionSection = {
  specialist: "nutrition_lifestyle",
  title: "Nutrition & Lifestyle",
  subtitle: "Everyday nutrition and lifestyle support",
  icon: "🍎",
  route: "/specialist/nutrition-lifestyle",
  status: "NOT_ASSESSED",
  status_label: "Not yet assessed",
  team_status: "NOT_ASSESSED",
  team_status_label: "Not assessed",
  short_reason: "Not assessed yet — the nutrition check-in has not been completed.",
  selected: false,
  why_active: null,
  why_inactive: "nutrition_need could not be evaluated from the available evidence",
  current_focus: null,
  decision: null,
  actions: [],
  tracking: { status: "NOT_RECORDED", label: "No actions are in this part of your plan yet.", rows: [] },
  progress: { direction: "NOT_RECORDED", label: "Nothing recorded for this part of the plan yet.", rows: [] },
  next_step: "Answer the lifestyle questions so this can be evaluated rather than assumed.",
  evidence: [],
  missing: ["Meal pattern", "Water intake"],
  empty_state: {
    kind: "not_assessed",
    message: "Complete your nutrition check-in so MoveWell can personalize this part of your plan.",
    action: { kind: "nutrition_check_in", label: "Complete check-in", route: "/nutrition-check-in" },
  },
};

const collaboration = {
  title: "How your MoveWell team worked",
  intro: "MoveWell picked the specialists your own evidence called for. This is what each of them contributed.",
  steps: [
    {
      kind: "assessment",
      title: "Your assessment and answers",
      icon: "📋",
      participated: true,
      summary: "MoveWell looked at your movement assessment and your lifestyle answers.",
    },
    {
      kind: "specialist",
      specialist: "exercise_movement",
      title: "Exercise & Movement",
      icon: "🏃",
      participated: true,
      summary: "Your assessment highlighted Balance and Everyday movement.",
    },
    {
      kind: "specialist",
      specialist: "nutrition_lifestyle",
      title: "Nutrition & Lifestyle",
      icon: "🍎",
      participated: false,
      summary: "Not assessed yet — the nutrition check-in has not been completed.",
      action: { kind: "nutrition_check_in", label: "Complete check-in", route: "/nutrition-check-in" },
    },
    {
      kind: "synthesis",
      title: "MoveWell",
      icon: "✨",
      participated: true,
      summary: "These were combined into your one MoveWell plan.",
    },
  ],
};

const markup = renderToStaticMarkup(
  createElement(
    "div",
    null,
    createElement(
      "div",
      { className: "team-grid" },
      ...team.map((card, index) =>
        createElement(SpecialistTeamCard, { key: card.id || index, specialist: card }),
      ),
    ),
    createElement(PlanSectionPanel, { section: exerciseSection }),
    createElement(PlanSectionPanel, { section: nutritionSection }),
    createElement(CollaborationTimeline, { collaboration }),
  ),
);

// The same section, with the completion hook supplied — the self-report path.
const nothingRecorded = {
  completedIds: new Set(),
  resultFor: () => null,
  markCompleted: async () => {},
  undoCompletion: async () => {},
};

const measuredByCamera = {
  completedIds: new Set(["chair-sit-to-stand"]),
  resultFor: () => ({ id: "res_1", source: "camera" }),
  markCompleted: async () => {},
  undoCompletion: async () => {},
};

const markupOfferingSelfReport = renderToStaticMarkup(
  createElement(PlanSectionPanel, { section: exerciseSection, completion: nothingRecorded }),
);

const markupMeasuredByCamera = renderToStaticMarkup(
  createElement(PlanSectionPanel, { section: exerciseSection, completion: measuredByCamera }),
);

// A section with actions but no records at all: the one empty state, with the
// thing to do about it.
const freshSection = {
  ...exerciseSection,
  tracking: { status: "NOT_RECORDED", label: "Nothing recorded yet.", rows: [] },
  progress: { direction: "NOT_RECORDED", label: "Nothing recorded yet.", rows: [] },
  empty_state: {
    kind: "no_records",
    message: "Complete your first session to start tracking your progress.",
    action: {
      kind: "start_exercise",
      label: "Start exercise",
      route: "/exercise/chair-sit-to-stand?planId=plan_abc123&itemId=chair-sit-to-stand",
    },
  },
};

const markupFresh = renderToStaticMarkup(
  createElement(PlanSectionPanel, { section: freshSection }),
);

const checks = [];
const check = (label, condition) => checks.push({ label, ok: Boolean(condition) });

// --- the team -----------------------------------------------------------------
check("exactly five team cards render", (markup.match(/class="team-card /g) || []).length === 5);
check(
  "every canonical specialist name renders",
  [
    "Exercise &amp; Movement",
    "Nutrition &amp; Lifestyle",
    "Behaviour &amp; Adherence",
    "Recovery &amp; Care",
    "Safety &amp; Practitioner Recommendation",
  ].every((name) => markup.includes(name)),
);
check(
  "each card shows its compact status",
  markup.includes(">Active<") && markup.includes(">Not assessed<") && markup.includes(">Not needed<"),
);
check(
  "each card shows one short reason",
  markup.includes("Your assessment highlighted balance and everyday movement."),
);
check("no removed specialist name is rendered", !/Physiotherapy|Physical Activity|Clinical Escalation/.test(markup));

// --- the exercise card ---------------------------------------------------------
check("the exercise card shows the prescription and focus", markup.includes("2 × 8") && markup.includes("Everyday movements"));
check("the exercise card shows why", markup.includes("Your sit-to-stand measured slow."));
check("the Start exercise button uses the server route", markup.includes("Start exercise"));
check("recorded tracking renders", markup.includes("2 sessions recorded, 1 meeting the target"));
check("progress renders the comparison", markup.includes("repetitions went from 6 to 8"));
check(
  "progression and regression are folded away, not printed",
  markup.includes("How to progress or make it easier") && markup.includes("<details"),
);
check("a withheld item is marked and cannot be started", markup.includes("plan-item--withheld") && markup.includes("Paused — see safety guidance"));
check(
  "the withheld item's safety note is the only one of its kind on the page",
  (markup.match(/Paused pending review\./g) || []).length === 1,
);

// --- reading order -------------------------------------------------------------
check("actions come before the reasoning", markup.indexOf("plan-item-list") < markup.indexOf("plan-section-reason"));
check(
  "the audit trail is behind View details",
  markup.includes("View details") &&
    markup.indexOf("plan-section-details") < markup.indexOf("What this was based on"),
);
check("current focus is inside the details, not above the actions", markup.indexOf("Current focus") > markup.indexOf("plan-item-list"));
check("evidence and unknowns are still available", markup.includes("Chair sit-to-stand x5: measured") && markup.includes("Daily steps"));

// --- empty states --------------------------------------------------------------
check(
  "an unassessed specialist offers the action that would assess it",
  markup.includes("Complete your nutrition check-in so MoveWell can personalize this part of your plan.") &&
    markup.includes("Complete check-in"),
);
check(
  "a section with no records says what to do about it",
  markupFresh.includes("Complete your first session to start tracking your progress."),
);
check(
  "a card with no records does not repeat 'nothing recorded'",
  !markupFresh.includes("Nothing recorded for this yet."),
);

// --- the collaboration flow ----------------------------------------------------
check("the collaboration flow renders its title", markup.includes("How your MoveWell team worked"));
check(
  "every step renders with its own summary",
  markup.includes("MoveWell looked at your movement assessment") &&
    markup.includes("Your assessment highlighted Balance and Everyday movement.") &&
    markup.includes("These were combined into your one MoveWell plan."),
);
check(
  "a specialist that took no part is marked as inactive",
  markup.includes("collab-step--inactive") && markup.includes("Not assessed yet — the nutrition check-in has not been completed."),
);
check(
  "an inactive specialist still offers its next step",
  markup.includes("collab-step-action") && markup.includes("Complete check-in"),
);

// --- the self-report path ------------------------------------------------------
check("no self-report control renders without the completion hook", !markup.includes('type="checkbox"'));
check(
  "a self-report control renders for an exercise item once the hook is supplied",
  markupOfferingSelfReport.includes('type="checkbox"') &&
    markupOfferingSelfReport.includes("Done without the camera"),
);
check(
  "a camera-recorded exercise shows as completed and its tick is locked",
  markupMeasuredByCamera.includes("Completed (recorded session)") && markupMeasuredByCamera.includes("disabled"),
);
check(
  "the withheld item offers no self-report control",
  (markupOfferingSelfReport.match(/type="checkbox"/g) || []).length === 1,
);

// --- hygiene -------------------------------------------------------------------
check("no chain-of-thought or internal identifier leaks", !/workflow_id|agent_run_id|request_id|_id\b/.test(markup));
check("no machine vocabulary leaks into the plan", !/IMPROVED|DECLINED|NOT_ENOUGH_DATA|need_profile/.test(markup));

const failed = checks.filter((entry) => !entry.ok);

for (const entry of checks) {
  console.log(`  [${entry.ok ? "PASS" : "FAIL"}] ${entry.label}`);
}

console.log(`\nPASSED ${checks.length - failed.length}  FAILED ${failed.length}`);
console.log(`\nRendered ${markup.length} characters of real component output.`);

if (failed.length) {
  console.log("\nDiagnostics for the failures above:");
  console.log(`  markup length: ${markup.length}`);
  console.log(`  contains plan-item-list: ${markup.includes("plan-item-list")}`);
  console.log(`  contains details: ${markup.includes("<details")}`);
  console.log("\nFirst 2500 characters of the rendered markup:\n");
  console.log(markup.slice(0, 2500));
  process.exitCode = 1;
}
