/**
 * Tests for the journey derivation.
 *
 * This logic decides what every signed-in user is shown next, so the cases
 * that matter are the ones where getting it wrong sends someone backwards:
 * treating still-loading data as complete, letting the optional health step
 * block the journey, and forgetting that a user can finish.
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { STAGE, deriveJourney } from "../stages.js";

const COMPLETE_PROFILE = { profile_complete: true };

test("a brand new user starts at the first step", () => {
  const journey = deriveJourney();

  assert.equal(journey.next.id, STAGE.ABOUT_YOU);
  assert.equal(journey.complete, false);
});

test("missing data is treated as not-yet-done, never as done", () => {
  // Everything null, as it is on first render while requests are in flight.
  // The failure this guards against is optimistically marking steps complete
  // and skipping the user past work they have not done.
  const journey = deriveJourney({
    profile: null,
    assessment: null,
    workflow: null,
  });

  assert.equal(journey.next.id, STAGE.ABOUT_YOU);
  assert.ok(journey.steps.every((step) => step.complete === false));
});

test("an incomplete profile does not advance past the questionnaire", () => {
  const journey = deriveJourney({ profile: { profile_complete: false } });

  assert.equal(journey.next.id, STAGE.ABOUT_YOU);
});

test("the optional health step never blocks the journey", () => {
  // Profile done, no report confirmed, no assessment. The next demanded step
  // must be the assessment -- not the optional health step, which would trap
  // a user who has no report to give.
  const journey = deriveJourney({ profile: COMPLETE_PROFILE });

  assert.equal(journey.next.id, STAGE.ASSESSMENT);

  const healthStep = journey.steps.find((step) => step.id === STAGE.HEALTH_INFO);

  assert.equal(healthStep.optional, true);
  assert.equal(healthStep.complete, false);
});

test("a confirmed report marks the optional health step addressed", () => {
  const journey = deriveJourney({
    profile: COMPLETE_PROFILE,
    workflow: { medical_context_confirmed: true },
  });

  const healthStep = journey.steps.find((step) => step.id === STAGE.HEALTH_INFO);

  assert.equal(healthStep.complete, true);
});

test("after the assessment the next step is the plan", () => {
  const journey = deriveJourney({
    profile: COMPLETE_PROFILE,
    assessment: { session_id: "s1" },
  });

  assert.equal(journey.next.id, STAGE.PLAN);
});

test("with a plan the user is asked to follow it, not to rebuild it", () => {
  const journey = deriveJourney({
    profile: COMPLETE_PROFILE,
    assessment: { session_id: "s1" },
    hasPlan: true,
  });

  assert.equal(journey.next.id, STAGE.FOLLOW);
});

test("recorded activity moves the user on to progress", () => {
  const journey = deriveJourney({
    profile: COMPLETE_PROFILE,
    assessment: { session_id: "s1" },
    hasPlan: true,
    hasActivity: true,
  });

  // Progress is the ongoing loop, not a task to be completed, so there is
  // nothing left to demand -- the user has arrived rather than been given
  // another instruction.
  assert.equal(journey.next, null);
  assert.equal(journey.currentStageId, STAGE.PROGRESS);
});

test("a fully finished journey reports complete rather than looping", () => {
  // Every step done including the optional one. `next` must be null, not a
  // step already completed -- otherwise the UI would keep prompting a user
  // who has done everything.
  const journey = deriveJourney({
    profile: COMPLETE_PROFILE,
    assessment: { session_id: "s1" },
    workflow: { medical_context_confirmed: true },
    hasPlan: true,
    hasActivity: true,
  });

  assert.equal(journey.next, null);
  assert.equal(journey.complete, true);
  assert.equal(journey.currentStageId, STAGE.PROGRESS);
});

test("no step exposes internal architecture to the user", () => {
  // The brief is explicit that the user must never be shown agents, MCP,
  // orchestration or workflow ids. This asserts it of the step text itself
  // so it cannot drift back in through a well-meaning label.
  const forbidden = [
    "agent",
    "orchestrat",
    "mcp",
    "workflow id",
    "physio",
    "safety gate",
    "llm",
    "tool call",
  ];

  const journey = deriveJourney();

  for (const step of journey.steps) {
    const text = `${step.title} ${step.description}`.toLowerCase();

    for (const term of forbidden) {
      assert.ok(
        !text.includes(term),
        `step "${step.id}" exposes internal term "${term}" in user-facing text`,
      );
    }
  }
});
