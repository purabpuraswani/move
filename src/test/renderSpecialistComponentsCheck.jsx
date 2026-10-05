/**
 * Temporary: render the team cards and the collaboration timeline against the
 * real stylesheet, so their appearance can be checked in a browser.
 */

import "./renderSpecialistDetailPrelude.js";

import { writeFileSync } from "node:fs";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import CollaborationTimeline from "../components/CollaborationTimeline.jsx";
import SpecialistTeamCard from "../components/SpecialistTeamCard.jsx";

const cards = [
  { id: "exercise_movement", title: "Exercise & Movement", team_status: "ACTIVE", team_status_label: "Active", selected: true, route: "/specialist/exercise-movement", short_reason: "Your assessment highlighted balance and everyday movement." },
  { id: "nutrition_lifestyle", title: "Nutrition & Lifestyle", team_status: "ACTIVE", team_status_label: "Active", route: "/specialist/nutrition-lifestyle", short_reason: "Your nutrition check-in answers brought this in, focused on hydration." },
  { id: "behaviour_adherence", title: "Behaviour & Adherence", team_status: "ACTIVE", team_status_label: "Active", route: "/specialist/behaviour-adherence", short_reason: "Your daily habits put consistency at the centre of this plan." },
  { id: "recovery_care", title: "Recovery & Care", team_status: "NOT_NEEDED", team_status_label: "Not needed", route: "/specialist/recovery-care", short_reason: "Your reported rest did not need a change." },
  { id: "safety_practitioner", title: "Safety & Practitioner Recommendation", team_status: "MODIFIED", team_status_label: "Reviewed — precautions", route: "/specialist/safety-practitioner", short_reason: "Reviewed your plan and added precautions." },
  { id: "nutrition_lifestyle", title: "Nutrition & Lifestyle", team_status: "NOT_ASSESSED", team_status_label: "Not assessed", route: "/specialist/nutrition-lifestyle", short_reason: "Not assessed yet — the nutrition check-in has not been completed." },
];

const collaboration = {
  title: "How your MoveWell team worked",
  intro: "MoveWell picked the specialists your own evidence called for. This is what each of them contributed.",
  steps: [
    { kind: "assessment", title: "Your assessment and answers", icon: "📋", participated: true, summary: "MoveWell looked at your movement assessment and your lifestyle answers." },
    { kind: "specialist", specialist: "exercise_movement", participated: true, summary: "Your assessment highlighted balance and everyday movement." },
    { kind: "specialist", specialist: "nutrition_lifestyle", participated: false, summary: "Not assessed yet — the nutrition check-in has not been completed.", action: { label: "Complete check-in", route: "/nutrition-check-in" } },
    { kind: "specialist", specialist: "recovery_care", participated: false, summary: "Your reported rest did not need a change." },
    { kind: "synthesis", title: "MoveWell", icon: "✨", participated: true, summary: "These were combined into your one MoveWell plan, with the safety review applied before anything reached you." },
  ],
};

const markup = renderToStaticMarkup(
  createElement(
    "div",
    null,
    createElement("div", { className: "mw-grid mw-grid--team" }, ...cards.map((card, index) => createElement(SpecialistTeamCard, { key: index, specialist: card }))),
    createElement("div", { style: { marginTop: 40 } }, createElement(CollaborationTimeline, { collaboration })),
  ),
);

console.log(markup.length);

if (process.env.COMPONENTS_SHOT) {
  writeFileSync(
    process.env.COMPONENTS_SHOT,
    `<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="./styles.css">
<style>body{background:#f6f4f0;padding:24px;max-width:1100px;margin:0 auto}</style></head><body>${markup}</body></html>`,
  );
}
