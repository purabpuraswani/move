/**
 * Assessment result construction.
 *
 * Three rules are enforced here rather than left to the UI:
 *
 * 1. A skipped test is recorded as skipped with null measurements. It never
 *    becomes a zero, because zero is a real measurement and skipping is not.
 * 2. An invalid test keeps its measurements for debugging but carries status
 *    "invalid" and can never be read as a completed result.
 * 3. No score, rating, category, or comparison to any population is produced.
 *    This object holds measurements and quality metadata only.
 */

import { PROTOCOL_VERSION, TEST_STATUS } from "../config/protocol.js";

export const TEST_IDS = ["shoulder", "ftsst", "balance"];

/** A test that has not been attempted. */
export function notStartedResult(testId) {
  return {
    testId,
    status: TEST_STATUS.NOT_STARTED,
    measurements: null,
    quality: null,
    invalidReasons: [],
    attempts: 0,
  };
}

/**
 * A test the user chose not to do. Measurements stay null on purpose; see rule
 * 1 above.
 */
export function skippedResult(testId, { reason = null, attempts = 0 } = {}) {
  return {
    testId,
    status: TEST_STATUS.SKIPPED,
    measurements: null,
    quality: null,
    invalidReasons: reason ? [reason] : [],
    skippedByUser: true,
    attempts,
  };
}

/**
 * A completed or invalid test.
 *
 * `valid` decides the status. Callers pass the measurements they actually
 * derived either way, so an invalid attempt can be inspected, but the status
 * keeps it out of anything that consumes completed results.
 *
 * A caller that passes `valid: true` while also naming reasons the attempt was
 * not valid gets an invalid result. The two answers contradict each other, and
 * of the two ways to resolve it, only this one can be wrong in the harmless
 * direction: a real measurement withheld is a nuisance, a bad measurement
 * presented as real is the thing this whole application must not do. It
 * coerces rather than throwing because an exception here would discard an
 * assessment the user has already performed.
 */
export function measuredResult(testId, { valid, measurements, quality, invalidReasons = [], attempts = 1 }) {
  const reasons = [...invalidReasons];
  const usable = Boolean(valid) && reasons.length === 0;

  return {
    testId,
    status: usable ? TEST_STATUS.COMPLETED : TEST_STATUS.INVALID,
    measurements: measurements ?? null,
    quality: quality ?? null,
    invalidReasons: reasons,
    attempts,
  };
}

/** True only for a genuinely completed test. */
export function isUsableResult(result) {
  return Boolean(result) && result.status === TEST_STATUS.COMPLETED;
}

/** Generate a session id without needing a dependency. */
export function createSessionId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }

  return `session-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

/** A fresh session with all three tests marked not started. */
export function createSession({ sessionId = createSessionId(), startedAt = new Date().toISOString() } = {}) {
  return {
    sessionId,
    protocolVersion: PROTOCOL_VERSION,
    startedAt,
    completedAt: null,
    tests: {
      shoulder: notStartedResult("shoulder"),
      ftsst: notStartedResult("ftsst"),
      balance: notStartedResult("balance"),
    },
  };
}

/** Replace one test result, returning a new session object. */
export function withTestResult(session, testId, result) {
  if (!TEST_IDS.includes(testId)) {
    throw new Error(`Unknown test id: ${testId}`);
  }

  return {
    ...session,
    tests: { ...session.tests, [testId]: result },
  };
}

/**
 * Close the session and add a summary of what it does and does not contain.
 * The summary counts statuses; it does not aggregate measurements, because
 * combining these three measurements into one number would be inventing a
 * score.
 */
export function finaliseSession(session, { completedAt = new Date().toISOString() } = {}) {
  const statuses = TEST_IDS.map((testId) => session.tests[testId].status);

  return {
    ...session,
    completedAt,
    summary: {
      testsCompleted: statuses.filter((status) => status === TEST_STATUS.COMPLETED).length,
      testsInvalid: statuses.filter((status) => status === TEST_STATUS.INVALID).length,
      testsSkipped: statuses.filter((status) => status === TEST_STATUS.SKIPPED).length,
      testsNotStarted: statuses.filter((status) => status === TEST_STATUS.NOT_STARTED).length,
      hasAnyUsableResult: statuses.includes(TEST_STATUS.COMPLETED),
    },
  };
}

/**
 * Names that suggest pose data or imagery rather than a measurement.
 *
 * Deliberately about names and shapes, not an exhaustive list: the point is to
 * catch a mistake, and a mistake is far likelier to be called `keypoints` or
 * `debugFrames` than something deceptive. Anchored at the end for frames so
 * that `frameRate` and `framesUsed`, which are quality figures and contain no
 * imagery, are kept.
 */
const NOT_A_MEASUREMENT =
  /keypoint|landmark|frames?$|frameData|image|video|photo|snapshot|thumbnail|pixel|bitmap|blob|base64|dataUrl/i;

/** How long a run of numbers stops being a result and starts being a series. */
const SERIES_LENGTH = 30;

/**
 * Drop anything from a measurement block that is not a measurement.
 *
 * The promise this application makes is that webcam imagery never leaves the
 * browser: pose estimation runs here, and only derived numbers are sent. That
 * promise is kept by the test logic, which never puts imagery in a result. This
 * function is the second lock. It sits at the one place where assessment data
 * leaves the machine, so a future change that hangs a pose series or a debug
 * frame off a result cannot quietly turn into an upload.
 *
 * Removal is silent by design. The alternative — refusing the whole payload —
 * would lose an assessment the user has already done, over data they never
 * wanted sent in the first place.
 */
function onlyMeasurements(value) {
  if (Array.isArray(value)) {
    // A long run of plain numbers is a per-frame series, not a result.
    if (value.length > SERIES_LENGTH && value.every((item) => typeof item === "number")) {
      return null;
    }

    return value.map(onlyMeasurements).filter((item) => item !== null);
  }

  if (value && typeof value === "object") {
    return Object.entries(value).reduce((kept, [key, item]) => {
      if (NOT_A_MEASUREMENT.test(key)) return kept;

      const cleaned = onlyMeasurements(item);

      if (cleaned !== null) kept[key] = cleaned;

      return kept;
    }, {});
  }

  if (typeof value === "string" && /^data:/i.test(value)) return null;

  return value === undefined ? null : value;
}

/**
 * Strip a session down to what may be persisted.
 *
 * Nothing here contains video, frames, or keypoint sequences, and
 * `onlyMeasurements` enforces that rather than trusting it. Per-repetition
 * measurements are kept because they are a handful of numbers and they let a
 * result be re-examined; raw pose data is not kept at all.
 */
export function toStoredPayload(session) {
  return {
    sessionId: session.sessionId,
    protocolVersion: session.protocolVersion,
    startedAt: session.startedAt,
    completedAt: session.completedAt,
    summary: session.summary ?? null,
    tests: TEST_IDS.reduce((accumulator, testId) => {
      const result = session.tests[testId];

      accumulator[testId] = {
        status: result.status,
        measurements: onlyMeasurements(result.measurements),
        quality: onlyMeasurements(result.quality),
        invalidReasons: result.invalidReasons,
        attempts: result.attempts ?? 0,
      };

      // Setup metadata, where a test collected any. Chair seat height belongs
      // with the result it affects: without it, two sit-to-stand times are not
      // comparable at all.
      if (result.setup) accumulator[testId].setup = onlyMeasurements(result.setup);

      return accumulator;
    }, {}),
  };
}
