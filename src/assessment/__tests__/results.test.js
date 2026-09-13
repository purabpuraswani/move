/**
 * Session and result construction, including the rules that keep a skipped test
 * from being read as a zero and an invalid test from being read as a result.
 */

import test from "node:test";
import assert from "node:assert/strict";

import {
  TEST_IDS,
  notStartedResult,
  skippedResult,
  measuredResult,
  isUsableResult,
  createSession,
  createSessionId,
  withTestResult,
  finaliseSession,
  toStoredPayload,
  ASSESSMENT_SUMMARY_STATUS,
  computeSummaryStatus,
} from "../utils/results.js";
import { PROTOCOL_VERSION, TEST_STATUS, REASON } from "../config/protocol.js";

test("a not-started test has no measurements and no reasons", () => {
  const result = notStartedResult("shoulder");

  assert.equal(result.status, TEST_STATUS.NOT_STARTED);
  assert.equal(result.measurements, null);
  assert.equal(result.quality, null);
  assert.deepEqual(result.invalidReasons, []);
  assert.equal(result.attempts, 0);
  assert.equal(isUsableResult(result), false);
});

test("a skipped test is skipped, never zero", () => {
  const result = skippedResult("balance");

  assert.equal(result.status, TEST_STATUS.SKIPPED);
  assert.equal(result.measurements, null);
  assert.equal(result.skippedByUser, true);
  assert.equal(isUsableResult(result), false);

  // The distinction that matters: nothing here can be read as a measured zero.
  assert.notEqual(result.measurements, 0);
  assert.notEqual(result.status, TEST_STATUS.COMPLETED);
});

test("an invalid test keeps its numbers but can never be read as completed", () => {
  const result = measuredResult("shoulder", {
    valid: false,
    measurements: { left: { finalElevationDeg: 151 } },
    quality: { framesSeen: 10 },
    invalidReasons: [REASON.INSUFFICIENT_REPETITIONS],
  });

  assert.equal(result.status, TEST_STATUS.INVALID);
  assert.equal(result.measurements.left.finalElevationDeg, 151);
  assert.equal(isUsableResult(result), false);
});

test("a valid test is the only thing that counts as usable", () => {
  const result = measuredResult("shoulder", {
    valid: true,
    measurements: { left: {} },
    quality: {},
  });

  assert.equal(result.status, TEST_STATUS.COMPLETED);
  assert.equal(isUsableResult(result), true);
  assert.equal(isUsableResult(null), false);
  assert.equal(isUsableResult(undefined), false);
});

test("invalidReasons is copied, so a caller cannot mutate a stored result", () => {
  const reasons = [REASON.TIMEOUT];
  const result = measuredResult("ftsst", { valid: false, measurements: {}, quality: {}, invalidReasons: reasons });

  reasons.push(REASON.POSE_LOST);

  assert.deepEqual(result.invalidReasons, [REASON.TIMEOUT]);
});

test("a new session starts with all three tests not started", () => {
  const session = createSession();

  assert.equal(session.protocolVersion, PROTOCOL_VERSION);
  assert.ok(session.sessionId);
  assert.ok(session.startedAt);
  assert.equal(session.completedAt, null);
  assert.deepEqual(Object.keys(session.tests).sort(), [...TEST_IDS].sort());

  for (const testId of TEST_IDS) {
    assert.equal(session.tests[testId].status, TEST_STATUS.NOT_STARTED);
  }
});

test("session ids are unique", () => {
  const ids = new Set([createSessionId(), createSessionId(), createSessionId()]);

  assert.equal(ids.size, 3);
});

test("withTestResult replaces one test without touching the others", () => {
  const session = createSession();
  const updated = withTestResult(session, "ftsst", skippedResult("ftsst"));

  assert.equal(updated.tests.ftsst.status, TEST_STATUS.SKIPPED);
  assert.equal(updated.tests.shoulder.status, TEST_STATUS.NOT_STARTED);

  // The original object is untouched.
  assert.equal(session.tests.ftsst.status, TEST_STATUS.NOT_STARTED);
});

test("an unknown test id is rejected rather than silently stored", () => {
  assert.throws(() => withTestResult(createSession(), "grip_strength", {}), /Unknown test id/);
});

test("the session summary counts statuses and does not combine measurements", () => {
  let session = createSession();

  session = withTestResult(
    session,
    "shoulder",
    measuredResult("shoulder", { valid: true, measurements: { value: 150 }, quality: {} })
  );
  session = withTestResult(
    session,
    "ftsst",
    measuredResult("ftsst", {
      valid: false,
      measurements: { value: 10 },
      quality: {},
      invalidReasons: [REASON.INSUFFICIENT_REPETITIONS],
    })
  );
  session = withTestResult(session, "balance", skippedResult("balance"));

  const finalised = finaliseSession(session);

  assert.deepEqual(finalised.summary, {
    testsCompleted: 1,
    testsInvalid: 1,
    testsSkipped: 1,
    testsNotStarted: 0,
    hasAnyUsableResult: true,
    status: "PARTIAL",
  });
  assert.ok(finalised.completedAt);

  // No score, rating, grade, index, or percentile is produced anywhere.
  const keys = Object.keys(finalised.summary).join(" ").toLowerCase();

  for (const forbidden of ["score", "rating", "grade", "index", "percentile", "risk", "normal"]) {
    assert.ok(!keys.includes(forbidden), `summary invented a ${forbidden}`);
  }
});

test("a session where everything was skipped has no usable result", () => {
  let session = createSession();

  for (const testId of TEST_IDS) {
    session = withTestResult(session, testId, skippedResult(testId));
  }

  const finalised = finaliseSession(session);

  assert.equal(finalised.summary.hasAnyUsableResult, false);
  assert.equal(finalised.summary.testsSkipped, 3);
  assert.equal(finalised.summary.testsCompleted, 0);
});

test("the stored payload keeps statuses and measurements but no pose data", () => {
  let session = createSession();

  session = withTestResult(
    session,
    "shoulder",
    measuredResult("shoulder", {
      valid: true,
      measurements: {
        left: { finalElevationDeg: 150, repetitionElevationsDeg: [150, 152, 148] },
        right: { finalElevationDeg: 140, repetitionElevationsDeg: [140, 141, 139] },
      },
      quality: { framesSeen: 188, usableFrameRatio: 1 },
    })
  );
  session = withTestResult(session, "balance", skippedResult("balance"));

  const payload = toStoredPayload(finaliseSession(session));

  assert.equal(payload.protocolVersion, PROTOCOL_VERSION);
  assert.deepEqual(Object.keys(payload.tests).sort(), [...TEST_IDS].sort());
  assert.equal(payload.tests.shoulder.status, TEST_STATUS.COMPLETED);
  assert.equal(payload.tests.shoulder.measurements.left.finalElevationDeg, 150);
  assert.equal(payload.tests.balance.status, TEST_STATUS.SKIPPED);
  assert.equal(payload.tests.balance.measurements, null);
  assert.equal(payload.tests.ftsst.status, TEST_STATUS.NOT_STARTED);

  const serialised = JSON.stringify(payload);

  for (const forbidden of ["keypoint", "landmark", "video", "frameData", "image", "dataUrl", "base64"]) {
    assert.ok(
      !serialised.toLowerCase().includes(forbidden.toLowerCase()),
      `stored payload leaked ${forbidden}`
    );
  }
});

test("the stored payload contains no array long enough to be a pose sequence", () => {
  let session = createSession();

  session = withTestResult(
    session,
    "shoulder",
    measuredResult("shoulder", {
      valid: true,
      measurements: { left: { repetitionElevationsDeg: [150, 152, 148] } },
      quality: {},
    })
  );

  const payload = toStoredPayload(finaliseSession(session));

  const longestArray = (value) => {
    if (Array.isArray(value)) {
      return Math.max(value.length, ...value.map(longestArray), 0);
    }

    if (value && typeof value === "object") {
      return Math.max(0, ...Object.values(value).map(longestArray));
    }

    return 0;
  };

  assert.ok(longestArray(payload) <= 20, "a stored array is long enough to be raw pose data");
});

test("the stored payload keeps setup metadata such as chair seat height", () => {
  // Without the seat height, two sit-to-stand times are not comparable, so it
  // has to survive into storage alongside the result it affects.
  const result = measuredResult("ftsst", {
    valid: true,
    measurements: { completionTimeMs: 9400, repetitionsDetected: 5 },
    quality: { framesSeen: 300 },
  });

  result.setup = {
    chairSeatHeightCm: 45,
    chairSeatHeightPlausible: true,
    measuredSide: "right",
    cameraView: "side",
    warnings: [],
  };

  const payload = toStoredPayload(finaliseSession(withTestResult(createSession(), "ftsst", result)));

  assert.equal(payload.tests.ftsst.setup.chairSeatHeightCm, 45);
  assert.equal(payload.tests.ftsst.setup.measuredSide, "right");

  // Tests that collected no setup metadata do not gain an empty object.
  assert.equal("setup" in payload.tests.shoulder, false);
});

test("summary status distinguishes NONE_COMPLETED, PARTIAL, COMPLETE, and INSUFFICIENT_DATA", () => {
  // NONE_COMPLETED
  assert.equal(
    computeSummaryStatus([TEST_STATUS.NOT_STARTED, TEST_STATUS.NOT_STARTED, TEST_STATUS.NOT_STARTED]),
    ASSESSMENT_SUMMARY_STATUS.NONE_COMPLETED
  );
  assert.equal(
    computeSummaryStatus([TEST_STATUS.SKIPPED, TEST_STATUS.SKIPPED, TEST_STATUS.SKIPPED]),
    ASSESSMENT_SUMMARY_STATUS.NONE_COMPLETED
  );

  // PARTIAL (1 or 2 completed)
  assert.equal(
    computeSummaryStatus([TEST_STATUS.COMPLETED, TEST_STATUS.NOT_STARTED, TEST_STATUS.NOT_STARTED]),
    ASSESSMENT_SUMMARY_STATUS.PARTIAL
  );
  assert.equal(
    computeSummaryStatus([TEST_STATUS.COMPLETED, TEST_STATUS.INVALID, TEST_STATUS.SKIPPED]),
    ASSESSMENT_SUMMARY_STATUS.PARTIAL
  );
  assert.equal(
    computeSummaryStatus([TEST_STATUS.COMPLETED, TEST_STATUS.COMPLETED, TEST_STATUS.SKIPPED]),
    ASSESSMENT_SUMMARY_STATUS.PARTIAL
  );

  // COMPLETE (all 3 completed)
  assert.equal(
    computeSummaryStatus([TEST_STATUS.COMPLETED, TEST_STATUS.COMPLETED, TEST_STATUS.COMPLETED]),
    ASSESSMENT_SUMMARY_STATUS.COMPLETE
  );

  // INSUFFICIENT_DATA (0 completed, >=1 invalid)
  assert.equal(
    computeSummaryStatus([TEST_STATUS.INVALID, TEST_STATUS.SKIPPED, TEST_STATUS.NOT_STARTED]),
    ASSESSMENT_SUMMARY_STATUS.INSUFFICIENT_DATA
  );
});

test("CRITICAL: Assessment 1 valid and Assessment 2 failed preserves Assessment 1 and marks status PARTIAL", () => {
  let session = createSession();

  // 1. Shoulder completes validly
  const shoulderResult = measuredResult("shoulder", {
    valid: true,
    measurements: { left: { finalElevationDeg: 140 }, right: { finalElevationDeg: 142 } },
    quality: { fps: 30, usableFrameRatio: 0.95 },
  });
  session = withTestResult(session, "shoulder", shoulderResult);

  assert.equal(session.tests.shoulder.status, TEST_STATUS.COMPLETED);
  assert.equal(session.summary.status, ASSESSMENT_SUMMARY_STATUS.PARTIAL);
  assert.equal(session.summary.testsCompleted, 1);

  // 2. FTSST fails (invalid attempt)
  const ftsstResult = measuredResult("ftsst", {
    valid: false,
    measurements: null,
    quality: { fps: 28, usableFrameRatio: 0.4 },
    invalidReasons: [REASON.INSUFFICIENT_REPETITIONS],
  });
  session = withTestResult(session, "ftsst", ftsstResult);

  // Assert Shoulder remains VALID and untouched
  assert.equal(session.tests.shoulder.status, TEST_STATUS.COMPLETED);
  assert.equal(session.tests.shoulder.measurements.left.finalElevationDeg, 140);

  // Assert FTSST is recorded as INVALID
  assert.equal(session.tests.ftsst.status, TEST_STATUS.INVALID);

  // Assert Summary is PARTIAL, NOT wiped or set to NO DATA
  assert.equal(session.summary.status, ASSESSMENT_SUMMARY_STATUS.PARTIAL);
  assert.equal(session.summary.testsCompleted, 1);
  assert.equal(session.summary.testsInvalid, 1);
  assert.equal(session.summary.hasAnyUsableResult, true);
});

