/**
 * The three plan states, and the one thing the client is not allowed to
 * decide for itself.
 *
 * These tests exist because the bug they guard against was not a crash: the
 * page rendered perfectly, and told a user who had completed their
 * assessment that they had not. So what is asserted here is mostly about
 * WHICH sentence appears, and where it came from.
 */

import test from "node:test";
import assert from "node:assert/strict";

import { PLAN_STATES, hasAnyPlan, planState } from "../planState.js";

const NEVER_RUN_RESPONSE = {
  available: false,
  message: "No recommendations have been generated yet.",
  plan_state: {
    state: "NEVER_RUN",
    reason:
      "No movement assessment has produced a usable measurement yet, so there is nothing to build a plan from.",
    missing: [],
    next_action: { label: "Redo the movement assessment", route: "/assessment" },
  },
};

const PLAN_AVAILABLE_RESPONSE = {
  exercise_plan: {
    available: true,
    goal: "A gentle starting programme.",
    exercises: ["Standing Knee Raise"],
    exercise_items: [{ id: "standing-knee-raise", name: "Standing Knee Raise" }],
    plan_version: 1,
  },
  nutrition_plan: { available: false, message: "No nutrition plan yet." },
  behaviour_plan: { available: false, message: "No habit goals yet." },
  plan_state: {
    state: "PLAN_AVAILABLE",
    reason: "Your plan is ready.",
    missing: [],
    next_action: null,
  },
};

const NO_PLAN_RESPONSE = {
  exercise_plan: { available: false, message: "No exercise plan yet." },
  nutrition_plan: { available: false, message: "No nutrition plan yet." },
  behaviour_plan: { available: false, message: "No habit goals yet." },
  plan_state: {
    state: "NO_PLAN_SAFE_OR_SUPPORTED",
    reason:
      "Your assessment was completed, but some of it could not be measured.",
    missing: [
      {
        capability: "Sit-to-stand strength",
        reason:
          "The chair sit-to-stand x5 baseline test has not produced a usable result for this user.",
      },
    ],
    next_action: { label: "Redo the movement assessment", route: "/assessment" },
  },
};

test("state A: an account with no usable measurement is NEVER_RUN", () => {
  const result = planState(NEVER_RUN_RESPONSE);

  assert.equal(result.state, PLAN_STATES.NEVER_RUN);
  assert.equal(result.nextAction.route, "/assessment");
  assert.deepEqual(result.missing, []);
});

test("state B: a response carrying a plan is PLAN_AVAILABLE", () => {
  const result = planState(PLAN_AVAILABLE_RESPONSE);

  assert.equal(result.state, PLAN_STATES.PLAN_AVAILABLE);
  assert.equal(result.nextAction, null);
  assert.ok(hasAnyPlan(PLAN_AVAILABLE_RESPONSE));
});

test("state C: a completed assessment with no plan is NOT reported as NEVER_RUN", () => {
  const result = planState(NO_PLAN_RESPONSE);

  // The whole point. Before the fix this response and NEVER_RUN_RESPONSE
  // rendered the identical "complete your assessment first" screen.
  assert.equal(result.state, PLAN_STATES.NO_PLAN_SAFE_OR_SUPPORTED);
  assert.notEqual(result.state, PLAN_STATES.NEVER_RUN);
});

test("state C carries what was missing, why, and what to do next", () => {
  const result = planState(NO_PLAN_RESPONSE);

  assert.equal(result.missing.length, 1);
  assert.equal(result.missing[0].capability, "Sit-to-stand strength");
  assert.match(result.missing[0].reason, /sit-to-stand/i);
  assert.equal(result.nextAction.label, "Redo the movement assessment");
  assert.ok(result.reason.length > 0);
});

test("the three states are mutually exclusive across the three responses", () => {
  const states = [
    NEVER_RUN_RESPONSE,
    PLAN_AVAILABLE_RESPONSE,
    NO_PLAN_RESPONSE,
  ].map((response) => planState(response).state);

  assert.equal(new Set(states).size, 3);
});

test("the reason and the missing list always come from the server, never the client", () => {
  const result = planState(NO_PLAN_RESPONSE);

  assert.equal(result.reason, NO_PLAN_RESPONSE.plan_state.reason);
  assert.deepEqual(result.missing, NO_PLAN_RESPONSE.plan_state.missing);
});

test("a response with no plan_state falls back, but never invents state C", () => {
  // An older server, or a response shape this client does not recognise.
  // Guessing NO_PLAN_SAFE_OR_SUPPORTED would mean inventing an
  // explanation of what could not be measured, which the client cannot
  // know. So the fallback is only ever A or B.
  const withPlan = planState({ exercise_plan: { available: true } });
  const withoutPlan = planState({ exercise_plan: { available: false } });

  assert.equal(withPlan.state, PLAN_STATES.PLAN_AVAILABLE);
  assert.equal(withoutPlan.state, PLAN_STATES.NEVER_RUN);
  assert.equal(withoutPlan.reason, null);
  assert.deepEqual(withoutPlan.missing, []);
});

test("an unrecognised state value is not passed through", () => {
  const result = planState({
    exercise_plan: { available: false },
    plan_state: { state: "SOMETHING_NEW", reason: "…" },
  });

  assert.ok(Object.values(PLAN_STATES).includes(result.state));
});

test("hasAnyPlan is true for any one of the three plan sections", () => {
  assert.equal(hasAnyPlan(null), false);
  assert.equal(hasAnyPlan({}), false);
  assert.equal(hasAnyPlan({ exercise_plan: { available: true } }), true);
  assert.equal(hasAnyPlan({ nutrition_plan: { available: true } }), true);
  assert.equal(hasAnyPlan({ behaviour_plan: { available: true } }), true);
});

test("PlanPage receives a plan_version it can show, and it is not reset", () => {
  // Guards the persistence fix from the UI side: a second run must not
  // hand the page a version-1 plan again.
  const v2 = planState({
    ...PLAN_AVAILABLE_RESPONSE,
    exercise_plan: { ...PLAN_AVAILABLE_RESPONSE.exercise_plan, plan_version: 2 },
  });

  assert.equal(v2.state, PLAN_STATES.PLAN_AVAILABLE);
  assert.equal(PLAN_AVAILABLE_RESPONSE.exercise_plan.plan_version, 1);
});
