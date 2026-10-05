/**
 * Reading the server's plan. Not building one.
 *
 * `unified_plan` is produced by the backend (workflow/response.py) from the
 * persisted specialist output, with the cross-specialist constraints and the
 * Safety Gate already applied. Everything a plan screen needs is in it: the
 * five specialists with their selection status, one section per specialist
 * with its status / why / focus / decision / tracking / progress / next step,
 * and a flat, ordered list of plan items each carrying its own domain ids and
 * the action button that follows from it.
 *
 * That is deliberate. A client that recomputes a plan has a second opinion
 * about what the user should do, and the two will disagree the first time
 * either changes. So this module only reads: it selects, it does not derive.
 * There is no default programme here, no fallback exercise, no locally
 * computed dosage, and no local decision about which specialist matters.
 *
 * The one thing that does live here is the mapping from a specialist's route
 * alias to the canonical specialist, because that is URL parsing, not plan
 * composition — and the server's own alias table
 * (backend/orchestration/specialists.py) is mirrored in
 * services/__tests__/specialistsNavigation.test.js so the two cannot drift.
 */

/** The five canonical specialist ids, in presentation order. Used only to
 * order what the server sent — never to add a specialist the server did not
 * send. */
export const SPECIALIST_ORDER = [
  "exercise_movement",
  "nutrition_lifestyle",
  "behaviour_adherence",
  "recovery_care",
  "safety_practitioner",
];

/** Route alias -> canonical specialist id. Mirrors the backend's
 * LEGACY_ID_ALIASES so an older link (/specialist/physio) still lands on the
 * one specialist that absorbed it. */
export const SPECIALIST_ALIASES = {
  exercise_movement: "exercise_movement",
  "exercise-movement": "exercise_movement",
  exercise_activity: "exercise_movement",
  exercise: "exercise_movement",
  physio: "exercise_movement",
  movement: "exercise_movement",
  activity: "exercise_movement",

  nutrition_lifestyle: "nutrition_lifestyle",
  "nutrition-lifestyle": "nutrition_lifestyle",
  nutrition: "nutrition_lifestyle",
  diet: "nutrition_lifestyle",

  behaviour_adherence: "behaviour_adherence",
  "behaviour-adherence": "behaviour_adherence",
  behaviour: "behaviour_adherence",
  behavior: "behaviour_adherence",
  habits: "behaviour_adherence",
  daily_habits: "behaviour_adherence",

  recovery_care: "recovery_care",
  "recovery-care": "recovery_care",
  recovery: "recovery_care",
  sleep: "recovery_care",

  safety_practitioner: "safety_practitioner",
  "safety-practitioner": "safety_practitioner",
  safety: "safety_practitioner",
  clinical: "safety_practitioner",
  safety_clinical_escalation: "safety_practitioner",
};

export function canonicalSpecialistId(value) {
  if (typeof value !== "string" || !value) return null;

  return SPECIALIST_ALIASES[value.trim().toLowerCase()] || null;
}

/** The unified plan from a workflow response, or null when the server did not
 * send one. */
export function unifiedPlan(workflow) {
  const plan = workflow?.unified_plan;

  return plan && typeof plan === "object" ? plan : null;
}

/** The five specialist cards, in the server's order. Falls back to the
 * server's `specialists_team` (the same five, from the same backend module)
 * when an older response has no unified plan. */
export function teamCards(workflow) {
  const plan = unifiedPlan(workflow);

  if (plan && Array.isArray(plan.specialists)) return plan.specialists;

  return Array.isArray(workflow?.specialists_team)
    ? workflow.specialists_team
    : [];
}

/** Every section the server sent, in its order. */
export function allSections(workflow) {
  const plan = unifiedPlan(workflow);

  return plan && Array.isArray(plan.sections) ? plan.sections : [];
}

/** The sections that are part of this user's plan: the Orchestrator selected
 * the specialist this cycle, or it already has actions in the plan. Both are
 * the server's decision (`section.selected`). */
export function selectedSections(workflow) {
  return allSections(workflow).filter((section) => section?.selected);
}

export function sectionFor(workflow, specialistId) {
  const canonical = canonicalSpecialistId(specialistId);
  const wanted = canonical || specialistId;

  return (
    allSections(workflow).find((section) => section.specialist === wanted) ||
    null
  );
}

/** Every plan item, in plan order, exactly as the server ordered them. */
export function planItems(workflow) {
  const plan = unifiedPlan(workflow);

  return plan && Array.isArray(plan.items) ? plan.items : [];
}

export function itemActions(section) {
  return Array.isArray(section?.actions) ? section.actions : [];
}

/** The action button for one plan item, or null when the item has none. The
 * label, the route and the kind all come from the server. */
export function actionOf(item) {
  const action = item?.action;

  if (!action || typeof action !== "object") return null;
  if (!action.kind || !action.label) return null;

  return action;
}

/**
 * The image for an exercise item, or null. Keyed strictly on the item's own
 * server-provided `item_id`, which for an exercise item is the exercise
 * library id — so a card can never show a different movement from the one
 * the plan names.
 */
export function exerciseIdOf(item) {
  if (!item || item.kind !== "exercise") return null;

  return item.metadata?.exercise_id || item.item_id || null;
}

export function dosageOf(item) {
  const metadata = item?.metadata || {};

  const parts = [];

  if (metadata.sets && metadata.repetitions) {
    parts.push(`${metadata.sets} × ${metadata.repetitions}`);
  } else {
    if (metadata.sets) parts.push(`${metadata.sets} sets`);
    if (metadata.repetitions) parts.push(`${metadata.repetitions} reps`);
  }

  if (metadata.duration_seconds) parts.push(`${metadata.duration_seconds}s hold`);

  return parts.length ? parts.join(" · ") : item?.detail || null;
}

/** The safety note the server attached to this item, if any. */
export function safetyNoteOf(item) {
  const safety = item?.metadata?.safety;

  if (!safety || typeof safety !== "object") return null;

  if (safety.withheld) {
    return { withheld: true, text: safety.reason || "Withheld for safety." };
  }

  if (safety.note) {
    return { withheld: false, text: safety.note };
  }

  return null;
}

export function trackingOf(item) {
  return item?.tracking && typeof item.tracking === "object" ? item.tracking : null;
}

export function progressOf(item) {
  return item?.progress && typeof item.progress === "object" ? item.progress : null;
}

/** Goal entries for the behaviour panel, built only from the server's habit
 * items: the panel records an action against `topicId`, which for a habit
 * item is the item's own `item_id`. */
export function habitGoals(section) {
  return itemActions(section)
    .filter((item) => item.kind === "habit_goal" && item.item_id)
    .map((item) => ({
      topicId: item.item_id,
      name: item.title,
      action: item.detail || "",
    }));
}

/** The plan id an action from this section should be recorded against: the
 * plan_id the server put on the section's own items. Null when the section's
 * items are advice rather than a persisted plan (a volume target, recovery
 * guidance), in which case there is nothing to link a record to — and the
 * client must not invent one. */
export function sectionPlanId(section) {
  const item = itemActions(section).find((entry) => entry.plan_id);

  return item?.plan_id || null;
}

// ---------------------------------------------------------------------------
// The parts of the plan that exist so a person can read it
//
// The summary sentence, the compact status on each team card, the "what to do
// about it" empty state and the collaboration timeline are all produced
// server-side (workflow/response.py). These readers pass them through; none of
// them writes a sentence of its own.
// ---------------------------------------------------------------------------

/** The short summary at the top of the plan, or null. */
export function planSummary(workflow) {
  const summary = unifiedPlan(workflow)?.summary;

  return summary && typeof summary === "object" ? summary : null;
}

/** The collaboration timeline, or null when the server did not send one. */
export function collaboration(workflow) {
  const block = unifiedPlan(workflow)?.collaboration;

  return block && Array.isArray(block.steps) ? block : null;
}

/** What to tell the user when this part of the plan has nothing yet. */
export function emptyStateOf(section) {
  const state = section?.empty_state;

  return state && typeof state === "object" ? state : null;
}

/**
 * The sections that have something for the user to do, in server order. This is
 * the "this week" list: a specialist that was reviewed and needed nothing is
 * not an action, so it does not appear here.
 */
export function actionSections(workflow) {
  return selectedSections(workflow).filter(
    (section) => itemActions(section).length > 0,
  );
}

/**
 * The sections the user can do something about even though they are empty — a
 * nutrition check-in nobody has completed, a movement assessment nobody has
 * taken. Each carries the server's own message and action.
 */
export function pendingSections(workflow) {
  return allSections(workflow).filter(
    (section) =>
      itemActions(section).length === 0 && emptyStateOf(section)?.action,
  );
}

/** Whether the safety verdict is one a user needs to see prominently. */
export function safetyNeedsAttention(plan) {
  const safety = plan?.safety;

  return Boolean(safety?.constrains_plan) || Boolean(safety?.requires_referral);
}
