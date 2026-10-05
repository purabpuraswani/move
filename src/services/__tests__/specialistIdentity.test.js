/**
 * The five specialists as people, and the status words a card may use.
 *
 * Two rules are pinned here. There are exactly five identities and no fallback
 * that invents a sixth; and a status this build does not recognise reads as
 * "Not assessed", because the alternative — guessing at something reassuring —
 * is how a card ends up claiming a review that never happened.
 */

import test from "node:test";
import assert from "node:assert/strict";

import {
  SPECIALIST_IDENTITY,
  SPECIALIST_PRESENTATION_ORDER,
  identityFor,
  statusWording,
} from "../specialistIdentity.js";

const CANONICAL_IDS = [
  "exercise_movement",
  "nutrition_lifestyle",
  "behaviour_adherence",
  "recovery_care",
  "safety_practitioner",
];

test("there are exactly five specialists, in presentation order", () => {
  assert.equal(Object.keys(SPECIALIST_IDENTITY).length, 5);
  assert.deepEqual(SPECIALIST_PRESENTATION_ORDER, CANONICAL_IDS);
  assert.deepEqual(Object.keys(SPECIALIST_IDENTITY).sort(), [...CANONICAL_IDS].sort());
});

test("no retired or duplicate specialist identity exists", () => {
  const ids = Object.keys(SPECIALIST_IDENTITY);

  for (const retired of [
    "physio",
    "physiotherapy",
    "exercise",
    "activity",
    "exercise_activity",
    "safety",
    "clinical",
  ]) {
    assert.ok(!ids.includes(retired), `${retired} is back as its own specialist`);
  }
});

test("exercise and movement is ONE specialist, as both coach and canonical name", () => {
  const movement = identityFor("exercise_movement");

  assert.equal(movement.canonical, "Exercise & Movement");
  assert.equal(movement.coach, "Your Movement Coach");
});

test("each specialist has a coach name, a role and its own canonical name", () => {
  const coaches = new Set();
  const canonicals = new Set();

  for (const id of SPECIALIST_PRESENTATION_ORDER) {
    const identity = identityFor(id);

    assert.ok(identity.coach, `${id} has no coach name`);
    assert.ok(identity.role, `${id} has no role line`);
    assert.ok(identity.canonical, `${id} has no canonical name`);
    assert.ok(identity.icon, `${id} has no icon`);

    coaches.add(identity.coach);
    canonicals.add(identity.canonical);
  }

  assert.equal(coaches.size, 5, "two specialists share a coach name");
  assert.equal(canonicals.size, 5);
});

test("the coach names never read like software components", () => {
  for (const id of SPECIALIST_PRESENTATION_ORDER) {
    const identity = identityFor(id);

    for (const word of ["agent", "module", "service", "engine", "orchestrator", "llm", "ai"]) {
      assert.ok(
        !identity.coach.toLowerCase().includes(word),
        `${id}'s coach name says "${word}"`,
      );
      assert.ok(!identity.role.toLowerCase().includes(word), `${id}'s role says "${word}"`);
    }
  }
});

test("an unknown specialist id renders as itself rather than as one of the five", () => {
  const unknown = identityFor("cardiologist", "Cardiology");

  assert.equal(unknown.coach, "Cardiology");
  assert.equal(unknown.canonical, "Cardiology");
  assert.equal(unknown.role, null);
  assert.ok(!SPECIALIST_PRESENTATION_ORDER.includes(unknown.id));
});

test("a status this build does not know reads as not assessed", () => {
  assert.deepEqual(statusWording("SOMETHING_NEW"), { label: "Not assessed", tone: "muted" });
  assert.deepEqual(statusWording(undefined, "Reviewed"), { label: "Reviewed", tone: "muted" });
});

test("each status the server can send has a word and a tone", () => {
  assert.deepEqual(statusWording("ACTIVE"), { label: "Active", tone: "active" });
  assert.deepEqual(statusWording("NOT_NEEDED"), { label: "Not needed right now", tone: "muted" });
  assert.deepEqual(statusWording("NOT_ASSESSED"), { label: "Not assessed", tone: "muted" });
  assert.equal(statusWording("MODIFIED").tone, "warn");
  assert.equal(statusWording("PAUSED").tone, "warn");
  assert.equal(statusWording("REFERRAL").tone, "danger");
  assert.equal(statusWording("REVIEWED").tone, "active");
});

test("no status word claims clinical authority", () => {
  const statuses = ["ACTIVE", "REVIEWED", "MODIFIED", "PAUSED", "REFERRAL", "NOT_NEEDED", "NOT_ASSESSED"];

  for (const status of statuses) {
    const { label } = statusWording(status);

    for (const word of ["diagnos", "cleared", "safe to", "healthy", "disease", "condition"]) {
      assert.ok(!label.toLowerCase().includes(word), `${status} reads as "${label}"`);
    }
  }
});
