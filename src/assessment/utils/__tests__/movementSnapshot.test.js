import { test } from "node:test";
import assert from "node:assert/strict";

import {
  buildMovementSnapshot,
  countCompleted,
  describeMeasurements,
  previousCompletedSessions,
} from "../movementSnapshot.js";

// Shapes copied from real stored sessions (backend assessments collection).
const shoulder = {
  status: "completed",
  measurements: {
    left: { repetitionCount: 3, finalElevationDeg: 142, repetitionElevationsDeg: [140, 141, 142], rejectedRepetitions: 0 },
    right: { repetitionCount: 3, finalElevationDeg: 137.6, repetitionElevationsDeg: [135, 137, 138], rejectedRepetitions: 1 },
    observableDifferenceDeg: 4,
    requiredRepetitions: 3,
  },
};
const ftsst = {
  status: "completed",
  measurements: { repetitionsDetected: 5, requiredRepetitions: 5, completionTimeMs: 12420, completionTimeSeconds: 12.42 },
};
const balance = {
  status: "completed",
  measurements: {
    left: { attempted: true, valid: true, holdDurationMs: 18000, holdDurationSeconds: 18, reachedMaxDuration: false },
    right: { attempted: true, valid: true, holdDurationMs: 30000, holdDurationSeconds: 30, reachedMaxDuration: true },
    maxDurationMs: 30000,
  },
};
const session = (tests, extra = {}) => ({
  id: "latest", startedAt: "2026-09-13T10:00:00+00:00", completedAt: "2026-09-13T10:08:00+00:00", tests, ...extra,
});
const SKIPPED = { status: "skipped", measurements: null };

test("no session: no-checks state, no invented values", () => {
  const s = buildMovementSnapshot(null);
  assert.equal(s.state, "none");
  assert.equal(s.completed, 0);
  assert.equal(s.badge, "NO CHECKS YET");
  assert.deepEqual(s.tests, []);
});

test("all three completed: complete state and real values", () => {
  const s = buildMovementSnapshot(session({ shoulder, ftsst, balance }));
  assert.equal(s.state, "complete");
  assert.equal(s.badge, "3 CHECKS COMPLETED");
  assert.equal(s.remaining, 0);
  assert.equal(s.lastUpdated, "2026-09-13T10:08:00+00:00");
  const [sh, ft, ba] = s.tests;
  assert.equal(sh.value, "6 raises recorded");
  assert.ok(sh.details.includes("3 with each arm"));
  assert.ok(sh.details.includes("Final raise angle: 142° left · 138° right"));
  assert.equal(ft.value, "12.4 seconds");
  assert.equal(ba.value, "18.0 s left · 30.0 s right");
  assert.ok(ba.details.includes("Held to the 30-second limit on the right leg"));
});

test("partial: counts, badge singular, incomplete statuses stated plainly", () => {
  const s = buildMovementSnapshot(session({ shoulder, ftsst: SKIPPED, balance: { status: "invalid", measurements: {} } }));
  assert.equal(s.state, "partial");
  assert.equal(s.completed, 1);
  assert.equal(s.remaining, 2);
  assert.equal(s.badge, "1 CHECK COMPLETED");
  assert.equal(s.tests[1].statusLabel, "Skipped");
  assert.equal(s.tests[1].value, null);
  assert.equal(s.tests[2].statusLabel, "Couldn't be measured");
  assert.equal(s.tests[2].value, null);
});

test("a missing test is 'Not completed', never zero", () => {
  const s = buildMovementSnapshot(session({ shoulder }));
  assert.equal(s.tests[2].status, "not_started");
  assert.equal(s.tests[2].statusLabel, "Not completed");
  assert.equal(s.tests[2].value, null);
  assert.equal(s.completed, 1);
});

test("completed check with unrecognised measurements shows no number", () => {
  const r = describeMeasurements("ftsst", { somethingElse: 1 });
  assert.equal(r.value, null);
  const s = buildMovementSnapshot(session({ shoulder: { status: "completed", measurements: {} }, ftsst, balance }));
  assert.equal(s.tests[0].value, null);
  assert.equal(s.tests[0].completed, true);
});

test("balance only shows attempted sides", () => {
  const r = describeMeasurements("balance", {
    left: { attempted: true, holdDurationMs: 12500 },
    right: { attempted: false, holdDurationMs: 0 },
  });
  assert.equal(r.value, "12.5 s left");
  assert.deepEqual(r.details, ["Time held on the left leg"]);
});

test("previous result is neutral: the earlier value and date, no judgement", () => {
  const previous = {
    ftsst: {
      startedAt: "2026-09-01T09:00:00+00:00",
      test: { status: "completed", measurements: { completionTimeSeconds: 13.1 } },
    },
  };
  const s = buildMovementSnapshot(session({ shoulder, ftsst, balance }), previous);
  assert.deepEqual(s.tests[1].previous, { value: "13.1 seconds", date: "2026-09-01T09:00:00+00:00" });
  assert.equal(s.tests[0].previous, null);
  const text = JSON.stringify(s).toLowerCase();
  for (const word of ["improv", "worse", "better", "declin", "healthy", "normal", "risk", "score"]) {
    assert.ok(!text.includes(word), `snapshot must not contain "${word}"`);
  }
});

test("no previous value is shown for a check that is not completed now", () => {
  const previous = { balance: { startedAt: "2026-09-01", test: balance } };
  const s = buildMovementSnapshot(session({ shoulder, ftsst, balance: SKIPPED }), previous);
  assert.equal(s.tests[2].previous, null);
});

test("previousCompletedSessions picks the newest earlier completed session per check", () => {
  const listings = [
    { id: "latest", statuses: { shoulder: "completed", ftsst: "completed", balance: "completed" } },
    { id: "s2", statuses: { shoulder: "completed", ftsst: "skipped", balance: "invalid" } },
    { id: "s3", statuses: { shoulder: "completed", ftsst: "completed", balance: "skipped" } },
  ];
  const picked = previousCompletedSessions(listings, "latest");
  assert.equal(picked.shoulder.id, "s2");
  assert.equal(picked.ftsst.id, "s3");
  assert.equal(picked.balance, null);
});

test("countCompleted", () => {
  assert.equal(countCompleted(null), 0);
  assert.equal(countCompleted(session({ shoulder, ftsst: SKIPPED, balance })), 2);
});
