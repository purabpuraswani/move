/**
 * Test 3 - single-leg stance logic, driven by synthetic pose sequences.
 */

import test from "node:test";
import assert from "node:assert/strict";

import {
  SingleLegStanceTest,
  BALANCE_PHASE,
  END_REASON,
  skippedSide,
  combineBalanceResults,
} from "../tests/balance/balanceLogic.js";
import { BALANCE, POSE, REASON, TEST_STATUS } from "../config/protocol.js";
import {
  balanceSequence,
  withMissingKeypoints,
  makeFrame,
  frontFacingBase,
  DEFAULT_FRAME_MS,
} from "../fixtures/syntheticPoses.js";

/**
 * Drop a keypoint on every frame except every `keepEvery`-th one, within
 * [fromIndex, toIndex]. Produces short, scattered gaps (a couple of frames
 * each) rather than one long dropout, so no single gap trips POSE_LOST -
 * used to simulate a persistently noisy signal rather than a single outage.
 */
function stippleMissingKeypoints(frames, names, fromIndex, toIndex, keepEvery = 3) {
  return frames.map((frame, index) => {
    if (index < fromIndex || index > toIndex || index % keepEvery === 0) return frame;

    const keypoints = { ...frame.keypoints };

    for (const name of names) delete keypoints[name];

    return { ...frame, keypoints };
  });
}

/**
 * A long, unstable search for the position - built from repeated short
 * dropouts rather than a clean standing period - followed by a normal clean
 * hold. Simulates someone who takes a while, with plenty of wobble, to find
 * their balance before actually holding it.
 */
function wobblySetupThenCleanHold({ supportSide = "left", wobbleFrames = 250, holdFrames = 90 } = {}) {
  const frames = [];
  let timestamp = 0;

  for (let i = 0; i < wobbleFrames; i += 1) {
    frames.push(makeFrame(timestamp, frontFacingBase(), { score: 0.9 }));
    timestamp += DEFAULT_FRAME_MS;
  }

  const wobbled = stippleMissingKeypoints(frames, ["left_ankle", "right_ankle"], 0, wobbleFrames - 1, 3);

  const { frames: holdFramesSeq } = balanceSequence({ supportSide, holdFrames });

  for (const frame of holdFramesSeq) {
    wobbled.push({ ...frame, timestamp: frame.timestamp + timestamp });
  }

  return wobbled;
}

/** One frame of tolerance on any duration assertion. */
const FRAME_TOLERANCE_MS = 40;

function run(frames, options = {}) {
  const test3 = new SingleLegStanceTest({ supportSide: "left", ...options });

  frames.forEach((frame) => test3.push(frame));

  return test3;
}

test("supportSide is required and validated", () => {
  assert.throws(() => new SingleLegStanceTest({ supportSide: "either" }), /supportSide must be/);
  assert.throws(() => new SingleLegStanceTest({}), /supportSide must be/);

  const test3 = new SingleLegStanceTest({ supportSide: "right" });

  assert.equal(test3.supportSide, "right");
  assert.equal(test3.liftedSide, "left");
});

test("a hold that ends when the foot comes down is a valid measurement", () => {
  const { frames } = balanceSequence({ supportSide: "left", holdFrames: 90 });
  const test3 = run(frames);

  assert.equal(test3.phase, BALANCE_PHASE.DONE);

  const side = test3.finish();

  assert.equal(side.supportSide, "left");
  assert.equal(side.valid, true);
  assert.equal(side.endReason, END_REASON.FOOT_LOWERED);
  assert.deepEqual(side.invalidReasons, []);
  assert.equal(side.reachedMaxDuration, false);

  // Timing starts only after the position has been held for the stabilisation
  // window, so the duration is shorter than the time the foot was up.
  const liftedMs = 90 * (1000 / 30);

  assert.ok(side.holdDurationMs > 0);
  assert.ok(
    side.holdDurationMs < liftedMs,
    `expected less than ${liftedMs}ms, got ${side.holdDurationMs}`
  );
  assert.ok(
    Math.abs(side.holdDurationMs - (liftedMs - BALANCE.stabilizationMs)) <
      BALANCE.stabilizationMs,
    `unexpected duration ${side.holdDurationMs}`
  );
  assert.ok(
    Math.abs(side.holdDurationSeconds * 1000 - side.holdDurationMs) <= 10,
    `seconds and milliseconds disagree: ${side.holdDurationSeconds}s vs ${side.holdDurationMs}ms`
  );
});

test("a foot that is never lifted reports null, never zero", () => {
  const { frames } = balanceSequence({ supportSide: "left", holdFrames: 0 });
  const test3 = run(frames);

  const side = test3.finish();

  assert.equal(side.valid, false);
  assert.equal(side.holdDurationMs, null);
  assert.equal(side.holdDurationSeconds, null);
  assert.notEqual(side.holdDurationMs, 0);
  assert.ok(side.invalidReasons.includes(REASON.NO_VALID_POSITION));
  assert.equal(side.endReason, END_REASON.NEVER_STARTED);
});

test("a lift too small to count does not start the clock", () => {
  const { frames } = balanceSequence({
    supportSide: "left",
    holdFrames: 90,
    liftRatio: BALANCE.minLiftRatio / 2,
  });

  const side = run(frames).finish();

  assert.equal(side.valid, false);
  assert.equal(side.holdDurationMs, null);
  assert.ok(side.invalidReasons.includes(REASON.NO_VALID_POSITION));
});

test("a brief lift that does not survive the stabilisation window is not timed", () => {
  // Six frames is 200ms, below the 400ms stabilisation window.
  const { frames } = balanceSequence({ supportSide: "left", holdFrames: 6 });

  const side = run(frames).finish();

  assert.equal(side.valid, false);
  assert.equal(side.holdDurationMs, null);
  assert.ok(side.invalidReasons.includes(REASON.NO_VALID_POSITION));
});

test("reaching the maximum duration is a complete result, not a failure", () => {
  const framesNeeded = Math.ceil(BALANCE.maxDurationMs / (1000 / 30)) + 60;
  const { frames } = balanceSequence({ supportSide: "left", holdFrames: framesNeeded });

  const side = run(frames).finish();

  assert.equal(side.valid, true);
  assert.equal(side.reachedMaxDuration, true);
  assert.equal(side.endReason, END_REASON.MAX_DURATION);
  assert.ok(
    Math.abs(side.holdDurationMs - BALANCE.maxDurationMs) < FRAME_TOLERANCE_MS,
    `expected about ${BALANCE.maxDurationMs}ms, got ${side.holdDurationMs}`
  );
});

test("excessive trunk lean ends the hold and is still a valid duration", () => {
  const { frames } = balanceSequence({ supportSide: "left", holdFrames: 90, leanAtEnd: true });

  const side = run(frames).finish();

  assert.equal(side.endReason, END_REASON.TRUNK_LEAN);
  assert.equal(side.valid, true);
  assert.ok(side.holdDurationMs > 0);
});

test("the support foot moving ends the hold and is still a valid duration", () => {
  const { frames } = balanceSequence({
    supportSide: "left",
    holdFrames: 90,
    ankleShiftAtEnd: 0.3,
  });

  const side = run(frames).finish();

  assert.equal(side.endReason, END_REASON.SUPPORT_FOOT_MOVED);
  assert.equal(side.valid, true);
  assert.ok(side.holdDurationMs > 0);
});

test("losing the pose during a hold invalidates it, because the end is unknown", () => {
  const { frames } = balanceSequence({ supportSide: "left", holdFrames: 200 });
  const damaged = withMissingKeypoints(frames, ["left_ankle"], 40, 110);

  const side = run(damaged).finish();

  assert.equal(side.endReason, END_REASON.POSE_LOST);
  assert.equal(side.valid, false);
  assert.equal(side.holdDurationMs, null);
  assert.ok(side.invalidReasons.includes(REASON.POSE_LOST));
});

test("a short dropout during a hold does not end it", () => {
  const { frames } = balanceSequence({ supportSide: "left", holdFrames: 200 });
  const damaged = withMissingKeypoints(frames, ["left_ankle"], 40, 50);

  const side = run(damaged).finish();

  assert.equal(side.endReason, END_REASON.FOOT_LOWERED);
  assert.equal(side.valid, true);
  assert.equal(side.quality.reasonCounts[REASON.KEYPOINTS_MISSING], 11);
});

test("stopping deliberately is recorded as aborted, not as a measurement", () => {
  const { frames } = balanceSequence({ supportSide: "left", holdFrames: 200 });
  const test3 = new SingleLegStanceTest({ supportSide: "left" });

  frames.slice(0, 60).forEach((frame) => test3.push(frame));

  assert.equal(test3.phase, BALANCE_PHASE.TIMING);

  test3.stop(frames[60].timestamp);

  const side = test3.finish();

  assert.equal(side.endReason, END_REASON.ABORTED);
  assert.equal(side.valid, false);
  assert.equal(side.holdDurationMs, null);
  assert.ok(side.invalidReasons.includes(REASON.ABORTED_BY_USER));
});

test("both support legs are measured separately and compared", () => {
  const left = run(balanceSequence({ supportSide: "left", holdFrames: 120 }).frames).finish();

  const right = run(balanceSequence({ supportSide: "right", holdFrames: 60 }).frames, {
    supportSide: "right",
  }).finish();

  assert.equal(left.supportSide, "left");
  assert.equal(right.supportSide, "right");
  assert.ok(left.holdDurationMs > right.holdDurationMs);

  const result = combineBalanceResults(left, right);

  assert.equal(result.testId, "balance");
  assert.equal(result.status, TEST_STATUS.COMPLETED);
  assert.equal(result.measurements.left.attempted, true);
  assert.equal(result.measurements.right.attempted, true);
  assert.equal(
    result.measurements.observableDifferenceMs,
    Math.abs(left.holdDurationMs - right.holdDurationMs)
  );
  assert.equal(result.measurements.maxDurationMs, BALANCE.maxDurationMs);
});

test("skipping both sides is recorded as skipped, with no measurements", () => {
  const result = combineBalanceResults(skippedSide("left"), skippedSide("right"));

  assert.equal(result.status, TEST_STATUS.SKIPPED);
  assert.equal(result.measurements, null);
  assert.equal(result.skippedByUser, true);
});

test("skipping one side keeps the other, and does not turn the skip into a zero", () => {
  const left = run(balanceSequence({ supportSide: "left", holdFrames: 120 }).frames).finish();
  const result = combineBalanceResults(left, skippedSide("right"));

  assert.equal(result.status, TEST_STATUS.COMPLETED);
  assert.equal(result.measurements.left.valid, true);
  assert.equal(result.measurements.right.attempted, false);
  assert.equal(result.measurements.right.holdDurationMs, null);
  assert.equal(result.measurements.observableDifferenceMs, null);
});

test("an invalid side is namespaced in the combined reasons and blocks completion", () => {
  const left = run(balanceSequence({ supportSide: "left", holdFrames: 120 }).frames).finish();

  const right = run(balanceSequence({ supportSide: "right", holdFrames: 0 }).frames, {
    supportSide: "right",
  }).finish();

  const result = combineBalanceResults(left, right);

  assert.equal(result.status, TEST_STATUS.INVALID);
  assert.deepEqual(result.invalidReasons, [`right:${REASON.NO_VALID_POSITION}`]);
  assert.equal(result.measurements.left.valid, true);
  assert.equal(result.measurements.right.valid, false);
  assert.equal(result.measurements.observableDifferenceMs, null);
});

test("the combined result records how the duration was defined", () => {
  const left = run(balanceSequence({ supportSide: "left", holdFrames: 120 }).frames).finish();
  const result = combineBalanceResults(left, skippedSide("right"));

  assert.equal(result.measurements.definition.condition, "eyes_open");
  assert.equal(
    result.measurements.definition.endsOn,
    "observable_position_loss_or_maximum_duration"
  );
});

test("reset clears timing so a retry is independent", () => {
  const test3 = run(balanceSequence({ supportSide: "left", holdFrames: 120 }).frames);

  assert.equal(test3.isDone(), true);

  test3.reset();

  assert.equal(test3.phase, BALANCE_PHASE.WAITING);
  assert.equal(test3.startTimestamp, null);
  assert.equal(test3.durationMs, null);
  assert.equal(test3.elapsedMs(), 0);
});

test("elapsedMs advances while the hold is running, not only once it has ended", () => {
  // The live timer on screen reads this value. If it only became non-zero at
  // the end, the user would watch a frozen zero for the whole hold.
  const { frames } = balanceSequence({ supportSide: "left", holdFrames: 120 });
  const test3 = new SingleLegStanceTest({ supportSide: "left" });

  let index = 0;

  while (index < frames.length && test3.phase !== BALANCE_PHASE.TIMING) {
    test3.push(frames[index]);
    index += 1;
  }

  assert.equal(test3.phase, BALANCE_PHASE.TIMING, "the fixture never reached the timing phase");

  const atStart = test3.elapsedMs();

  for (let step = 0; step < 30 && index < frames.length; step += 1) {
    test3.push(frames[index]);
    index += 1;
  }

  const later = test3.elapsedMs();

  assert.ok(later > atStart, `expected the live timer to advance, got ${atStart} then ${later}`);

  // It is derived from frame timestamps, so it tracks the frames it was given.
  const expected = frames[index - 1].timestamp - test3.startTimestamp;

  assert.ok(Math.abs(later - expected) <= FRAME_TOLERANCE_MS);
});

test("elapsedMs is zero before a hold begins and after a reset", () => {
  const test3 = new SingleLegStanceTest({ supportSide: "left" });

  assert.equal(test3.elapsedMs(), 0);

  const { frames } = balanceSequence({ supportSide: "left", holdFrames: 90 });

  frames.forEach((frame) => test3.push(frame));
  assert.ok(test3.elapsedMs() > 0);

  test3.reset();
  assert.equal(test3.elapsedMs(), 0);
});

test("a long, wobbly setup no longer fails an otherwise-clean hold", () => {
  const frames = wobblySetupThenCleanHold({ supportSide: "left", wobbleFrames: 250, holdFrames: 90 });
  const test3 = run(frames);

  assert.equal(test3.phase, BALANCE_PHASE.DONE);

  const side = test3.finish();

  assert.equal(side.valid, true);
  assert.equal(side.endReason, END_REASON.FOOT_LOWERED);
  assert.ok(!side.invalidReasons.includes(REASON.TOO_FEW_USABLE_FRAMES));
  assert.ok(side.holdDurationMs > 0);

  // The quality check is scoped to the TIMING segment: framesSeen must
  // reflect only the hold, not the 250-frame wobbly search that preceded it.
  assert.ok(
    side.quality.framesSeen < 150,
    `expected the quality tracker to be scoped to the hold, saw ${side.quality.framesSeen} frames`
  );
});

test("an attempt that is genuinely too wobbly throughout the hold still fails", () => {
  const { frames: clean } = balanceSequence({ supportSide: "left", holdFrames: 180, trailingFrames: 6 });

  // Standing (0-5) and stabilisation (roughly 6-20) are left clean so TIMING
  // is actually reached; the wobble is injected only once timing is running,
  // scattered as short gaps so no single one exceeds POSE_LOST's 1500ms.
  const frames = stippleMissingKeypoints(clean, ["left_ankle"], 26, 176, 3);

  const side = run(frames).finish();

  assert.equal(side.valid, false);
  assert.ok(side.invalidReasons.includes(REASON.TOO_FEW_USABLE_FRAMES));
  assert.ok(
    side.quality.usableFrameRatio < POSE.minUsableFrameRatio,
    `expected a low usable ratio, got ${side.quality.usableFrameRatio}`
  );
});

test("a setup that never stabilises hits the bounded timeout with a clear, distinct reason", () => {
  const { frames } = balanceSequence({
    supportSide: "left",
    holdFrames: 0,
    standingFrames: 700,
    trailingFrames: 0,
  });

  const test3 = run(frames);

  assert.equal(test3.phase, BALANCE_PHASE.DONE);

  const side = test3.finish();

  assert.equal(side.endReason, END_REASON.NEVER_STARTED);
  assert.equal(side.valid, false);
  assert.equal(side.holdDurationMs, null);
  assert.ok(side.invalidReasons.includes(REASON.NO_VALID_POSITION));

  // Distinct from the frame-usability reason: this is a setup timeout, not a
  // quality problem with the frames that were seen.
  assert.ok(!side.invalidReasons.includes(REASON.TOO_FEW_USABLE_FRAMES));

  // The timeout must have fired automatically, mid-push, well before the
  // fixture's 700 frames ran out - proving push() itself now bounds the
  // setup phase rather than relying on finish()'s fallback.
  assert.ok(
    test3.quality.framesSeen < frames.length,
    "push() should stop processing frames once the setup timeout ends the attempt"
  );
});

test("a stance genuinely lost mid-hold and a brief recoverable dropout are unaffected by the setup-timing fix", () => {
  // Regression coverage for the two existing behaviours the balance fix must
  // not disturb: a real loss of pose during the hold still invalidates the
  // result, and a brief dropout that recovers does not end it.
  const { frames: lost } = balanceSequence({ supportSide: "left", holdFrames: 200 });
  const lostSide = run(withMissingKeypoints(lost, ["left_ankle"], 40, 110)).finish();

  assert.equal(lostSide.valid, false);
  assert.equal(lostSide.endReason, END_REASON.POSE_LOST);

  const { frames: brief } = balanceSequence({ supportSide: "left", holdFrames: 200 });
  const briefSide = run(withMissingKeypoints(brief, ["left_ankle"], 40, 50)).finish();

  assert.equal(briefSide.valid, true);
  assert.equal(briefSide.endReason, END_REASON.FOOT_LOWERED);
});
