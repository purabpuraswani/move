import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  createSession,
  buildSessionSummary,
  finaliseSession,
  measuredResult,
  toStoredPayload,
  withTestResult,
} from "../utils/results.js";
import { saveAssessmentForWorkflow } from "../utils/submission.js";

const savedPayloadFixture = JSON.parse(readFileSync(
  fileURLToPath(new URL("../fixtures/active-assessment-submission.json", import.meta.url)),
  "utf8",
));

function completeSession() {
  let session = createSession({ sessionId: "session-round-trip" });
  session = withTestResult(session, "shoulder", measuredResult("shoulder", {
    valid: true,
    measurements: { left: { finalElevationDeg: 151.5 }, right: { finalElevationDeg: 149.2 } },
    quality: { framesSeen: 200 },
  }));
  session = withTestResult(session, "balance", measuredResult("balance", {
    valid: true,
    measurements: {
      left: { holdDurationSeconds: 30 },
      right: { holdDurationSeconds: 29.7 },
      differenceSeconds: 0.3,
    },
    quality: { framesSeen: 900 },
  }));
  return finaliseSession(session);
}

test("a failed assessment save never starts plan generation", async () => {
  let planCalls = 0;
  await assert.rejects(
    saveAssessmentForWorkflow(completeSession(), {
      save: async () => { throw new Error("save failed"); },
      runWorkflow: async () => { planCalls += 1; },
    }),
    /save failed/,
  );
  assert.equal(planCalls, 0);
});

test("an incomplete saved assessment is retained but does not start the workflow", async () => {
  const session = completeSession();
  const incomplete = {
    ...session,
    tests: { ...session.tests, balance: { ...session.tests.balance, status: "invalid" } },
  };
  incomplete.summary = buildSessionSummary(incomplete.tests);
  let planCalls = 0;
  const result = await saveAssessmentForWorkflow(incomplete, {
    save: async (payload) => ({ ...payload }),
    runWorkflow: async () => { planCalls += 1; },
  });
  assert.equal(result.workflow, null);
  assert.equal(result.saved.summary.status, "PARTIAL");
  assert.equal(planCalls, 0);
});

test("both confirmed measurements are saved before one idempotent workflow starts", async () => {
  const session = completeSession();
  const events = [];
  const result = await saveAssessmentForWorkflow(session, {
    save: async (payload) => {
      events.push("saved");
      return payload;
    },
    runWorkflow: async ({ idempotencyKey }) => {
      events.push("workflow");
      assert.equal(idempotencyKey, "assessment-session-round-trip");
      return { plan_status: "PLAN_AVAILABLE" };
    },
  });
  assert.deepEqual(events, ["saved", "workflow"]);
  assert.equal(result.workflow.plan_status, "PLAN_AVAILABLE");
  assert.equal(Object.keys(result.saved.tests).sort().join(","), "balance,shoulder");
});

test("the actual assessment payload shape contains shoulder and balance only", () => {
  const payload = toStoredPayload(completeSession());
  assert.deepEqual(Object.keys(payload.tests).sort(), ["balance", "shoulder"]);
  assert.equal("ftsst" in payload.tests, false);
  assert.deepEqual(payload.tests, savedPayloadFixture.tests);
});

test("mismatched server read-back is rejected before plan generation", async () => {
  const session = completeSession();
  let planCalls = 0;
  await assert.rejects(
    saveAssessmentForWorkflow(session, {
      save: async (payload) => ({ ...payload, tests: { ...payload.tests, balance: { status: "not_started", measurements: null } } }),
      runWorkflow: async () => { planCalls += 1; },
    }),
    /did not confirm both assessment results/,
  );
  assert.equal(planCalls, 0);
});
