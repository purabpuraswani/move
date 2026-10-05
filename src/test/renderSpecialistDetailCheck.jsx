import "./renderSpecialistDetailPrelude.js";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { writeFileSync } from "node:fs";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { SpecialistDetailPageInner } from "../pages/SpecialistDetailPage.jsx";

const workflow = {
  unified_plan: {
    available: true,
    version: 4,
    specialists: [
      {
        id: "exercise_movement",
        title: "Exercise & Movement",
        team_status: "ACTIVE",
        team_status_label: "Active",
        short_reason: "Your assessment highlighted balance and everyday movement.",
        route: "/specialist/exercise-movement",
        selected: true,
      },
      {
        id: "nutrition_lifestyle",
        title: "Nutrition & Lifestyle",
        team_status: "NOT_ASSESSED",
        team_status_label: "Not assessed",
        short_reason: "Not assessed yet — the nutrition check-in has not been completed.",
        route: "/specialist/nutrition-lifestyle",
        selected: false,
      },
      {
        id: "recovery_care",
        title: "Recovery & Care",
        team_status: "NOT_NEEDED",
        team_status_label: "Not needed",
        short_reason: "Your reported rest did not need a change.",
        route: "/specialist/recovery-care",
        selected: false,
      },
    ],
    sections: [
      {
        specialist: "exercise_movement",
        title: "Exercise & Movement",
        team_status: "ACTIVE",
        team_status_label: "Active",
        short_reason: "Your assessment highlighted balance and everyday movement.",
        selected: true,
        current_focus: "Balance: Could improve; Everyday movements",
        decision: "Added two exercises from your movement evidence.",
        actions: [
          {
            specialist: "exercise_movement",
            section: "exercise_programme",
            plan_id: "plan_1",
            item_id: "wall-sit",
            kind: "exercise",
            title: "Wall Sit",
            detail: "2 × 20s hold",
            why: "Your stability evidence.",
            target: "Balance and steadiness",
            metadata: { exercise_id: "wall-sit", sets: 2, duration_seconds: 20 },
            action: { kind: "start_exercise", label: "Start exercise", route: "/exercise/wall-sit?planId=plan_1&itemId=wall-sit" },
            tracking: { status: "RECORDED", label: "2 sessions recorded, 1 meeting the target", summary: "2s held", recorded: 2, completed: 1, rows: [] },
            progress: { direction: "IMPROVING", label: "Up on your last session: hold time went from 15 to 20", rows: [] },
            position: 1,
          },
        ],
        tracking: { status: "RECORDED", label: "2 sessions recorded so far", summary: "measured by camera", rows: [{ label: "Wall Sit", value: "2 sessions recorded" }] },
        progress: { direction: "IMPROVING", label: "Your recorded sessions are moving up.", plan_version: 4, adaptation_reason: "Two sessions met the target.", rows: [] },
        next_step: "Keep recording your sessions so the programme can be adjusted.",
        evidence: ["Balance: measured", "Daily steps: not measured (not_started)"],
        missing: ["Standing balance could not be measured"],
      },
      {
        specialist: "nutrition_lifestyle",
        title: "Nutrition & Lifestyle",
        team_status: "NOT_ASSESSED",
        team_status_label: "Not assessed",
        short_reason: "Not assessed yet — the nutrition check-in has not been completed.",
        selected: false,
        current_focus: null,
        decision: null,
        actions: [],
        tracking: { status: "NOT_RECORDED", label: "No actions are in this part of your plan yet.", rows: [] },
        progress: { direction: "NOT_RECORDED", label: "Nothing recorded for this part of the plan yet.", rows: [{ label: "Iron", value: "Nothing recorded against this plan yet." }] },
        next_step: "Answer the lifestyle questions so this can be evaluated rather than assumed.",
        evidence: [],
        missing: ["Meal pattern"],
        empty_state: {
          kind: "not_assessed",
          message: "Complete your nutrition check-in so MoveWell can personalize this part of your plan.",
          action: { kind: "nutrition_check_in", label: "Complete check-in", route: "/nutrition-check-in" },
        },
      },
      {
        specialist: "recovery_care",
        title: "Recovery & Care",
        team_status: "NOT_NEEDED",
        team_status_label: "Not needed",
        short_reason: "Your reported rest did not need a change.",
        selected: false,
        current_focus: null,
        decision: null,
        actions: [],
        tracking: { status: "NOT_RECORDED", label: "No actions are in this part of your plan yet.", rows: [] },
        progress: { direction: "NOT_RECORDED", label: "Nothing recorded for this part of the plan yet.", rows: [] },
        next_step: "Your reported rest did not cross this project's markers for treating recovery as a constraint.",
        evidence: ["Reported sleep: 7 hours"],
        missing: [],
        empty_state: null,
      },
    ],
    constraints: [
      {
        source: "recovery_care",
        type: "limit_progression",
        reason: "Your reported rest is pacing how quickly activity increases.",
        actions: ["Hold the current prescription for one more cycle."],
        applies_to: ["exercise_movement"],
      },
      {
        source: "safety_practitioner",
        type: "modify",
        reason: "One exercise needed a precaution.",
        actions: [],
        applies_to: ["wall-sit", "chair-sit-to-stand"],
      },
    ],
    collaboration: {
      title: "How your MoveWell team worked",
      intro: "MoveWell picked the specialists your own evidence called for.",
      steps: [
        { kind: "assessment", title: "Your assessment and answers", icon: "📋", participated: true, summary: "MoveWell looked at your movement assessment." },
        { kind: "specialist", specialist: "exercise_movement", title: "Exercise & Movement", participated: true, summary: "Your assessment highlighted balance and everyday movement." },
        { kind: "specialist", specialist: "nutrition_lifestyle", title: "Nutrition & Lifestyle", participated: false, summary: "Not assessed yet — the nutrition check-in has not been completed.", action: { kind: "nutrition_check_in", label: "Complete check-in", route: "/nutrition-check-in" } },
        { kind: "synthesis", title: "MoveWell", icon: "✨", participated: true, summary: "These were combined into your one MoveWell plan." },
      ],
    },
  },
};


const checks = [];
const check = (label, condition, detail = "") => checks.push({ label, ok: Boolean(condition), detail });

function render(path) {
  return renderToStaticMarkup(
    createElement(
      MemoryRouter,
      { initialEntries: [path] },
      createElement(
        Routes,
        null,
        createElement(Route, {
          path: "/specialist/:specialistType",
          element: createElement(SpecialistDetailPageInner, { workflow }),
        }),
      ),
    ),
  );
}

const movement = render("/specialist/exercise-movement");
const nutrition = render("/specialist/nutrition-lifestyle");
const recovery = render("/specialist/recovery-care");
const unknown = render("/specialist/not-a-specialist");
const alias = render("/specialist/physio");

check("movement: coach is named", movement.includes("Your Movement Coach"));
check("movement: canonical name is shown as meta", movement.includes("Exercise &amp; Movement"));
check("movement: role is shown", movement.includes("Personalised movement guidance"));
check("movement: status badge comes from statusWording", movement.includes(">Active<"));
check("movement: why block", movement.includes("Why this specialist is involved"));
check("movement: focus label is the coach's", movement.includes("Movement focus"));
check("movement: decision block", movement.includes("What MoveWell decided"));
check("movement: actions render through PlanActionItem", movement.includes("plan-item") && movement.includes("Start exercise"));
check("movement: result block", movement.includes("Result and progress") && movement.includes("2 sessions recorded so far"));
check("movement: next block", movement.includes("Next") && movement.includes("Keep recording your sessions"));
check("movement: details drawer", movement.includes("View details") && movement.includes("What this was based on"));
check("movement: unknowns are in the drawer", movement.includes("What is not known yet"));
check("movement: plan version is in the drawer", movement.includes("Plan version 4"));
check("movement: NOT_RECORDED is not printed", !/Nothing recorded against this plan yet/.test(movement));
check("movement: collaboration from recovery shows", movement.includes("Working with") && movement.includes("Your Recovery Coach") && movement.includes("pacing how quickly activity increases"));
check("movement: safety constraint (exercise-id applies_to) shows no false collaboration", !movement.includes("Safety Review"));

check("nutrition: coach is named", nutrition.includes("Your Nutrition Coach"));
check("nutrition: not-assessed wording", nutrition.includes("Why this specialist is not involved"));
check("nutrition: server empty state message", nutrition.includes("Complete your nutrition check-in so MoveWell can personalize this part of your plan."));
check("nutrition: server empty state action", nutrition.includes("Complete check-in"));
check("nutrition: no action list", !nutrition.includes("specialist-action-list"));
check("nutrition: not-recorded progress row is dropped", !nutrition.includes("Nothing recorded against this plan yet."));

check("recovery: not-needed status", recovery.includes("Not needed"));
check("recovery: not involved heading", recovery.includes("Why this specialist is not involved"));
check("recovery: still offers its next step", recovery.includes("markers for treating recovery as a constraint"));
check("recovery: evidence is available behind details", recovery.includes("Reported sleep: 7 hours"));

check("unknown specialist: no specialist by that name", unknown.includes("No specialist by that name"));

check("no chain-of-thought or internal identifier leaks", !/workflow_id|agent_run|mcp|orchestrator|_id"/i.test(movement + nutrition + recovery));
check("no JSON blobs", !movement.includes("{&#x22;") && !movement.includes('{"'));

for (const entry of checks) {
  console.log(`  [${entry.ok ? "PASS" : "FAIL"}] ${entry.label}${entry.detail ? ` — ${entry.detail}` : ""}`);
}

// A visual check: one HTML file, the same markup, the real stylesheet.
if (process.env.SPECIALIST_SHOT) {
  writeFileSync(
    process.env.SPECIALIST_SHOT,
    `<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap">
<link rel="stylesheet" href="./styles.css">
<style>body{background:#f6f4f0}.shot{display:grid;gap:32px;padding:24px;max-width:1080px;margin:0 auto}.shot h2{font:700 13px/1.3 Manrope,sans-serif;color:#8a958f;text-transform:uppercase;letter-spacing:.08em}</style>
</head><body><div class="shot">
<section><h2>Exercise &amp; Movement (active)</h2>${movement.replace(/<details>/g, "<details open>")}</section>
<section><h2>Nutrition (not assessed)</h2>${nutrition.replace(/<details>/g, "<details open>")}</section>
<section><h2>Recovery (not needed)</h2>${recovery.replace(/<details>/g, "<details open>")}</section>
</div></body></html>`,
  );
}

const failed = checks.filter((entry) => !entry.ok).length;

console.log(`\nmarkup: movement=${movement.length} nutrition=${nutrition.length} recovery=${recovery.length} unknown=${unknown.length}`);
console.log(`alias /specialist/physio resolves to the movement coach: ${alias.includes("Your Movement Coach")}`);
console.log(`\nPASSED ${checks.length - failed}  FAILED ${failed}`);

if (failed) {
  console.log("\n--- movement markup ---\n" + movement);
  process.exitCode = 1;
}

if (process.env.SPECIALIST_STRUCTURE) {
  const main = (html) => (html.match(/<main class="shell-main" id="main">([\s\S]*)<\/main>/) || [, ""])[1];
  const labels = (html) =>
    [...main(html).matchAll(/<(h1|h2|h3|p|button|a)[^>]*>([^<]{1,90})</g)]
      .map((m) => `${m[1]}: ${m[2].replace(/\s+/g, " ").trim()}`)
      .filter((line) => line.length > 4);

  console.log("\n--- nutrition (not assessed) ---");
  console.log(labels(nutrition).join("\n"));
  console.log("\n--- recovery (not needed) ---");
  console.log(labels(recovery).join("\n"));
}