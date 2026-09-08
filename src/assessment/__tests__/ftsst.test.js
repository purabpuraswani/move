/**
 * Test 2 - five times sit-to-stand logic, driven by synthetic pose sequences.
 */

import test from "node:test";
import assert from "node:assert/strict";

import { FiveTimesSitToStandTest, FTSST_PHASE } from "../tests/ftsst/ftsstLogic.js";
import { FTSST, REASON, TEST_STATUS } from "../config/protocol.js";
import {
  ftsstSequence,
  withLowConfidence,
  withMissingKeypoints,
  makeFrame,
  sideFacingBase,
  DEFAULT_FRAME_MS,
} from "../fixtures/syntheticPoses.js";

/** Rebuild frames in [fromIndex, toIndex] at a different knee angle, same timestamps. */
function withKneeAngleSpike(frames, fromIndex, toIndex, angle, score = 0.9) {
  return frames.map((frame, index) => {
    if (index < fromIndex || index > toIndex) return frame;

    return makeFrame(frame.timestamp, sideFacingBase(angle), { score });
  });
}

/**
 * Drop a keypoint on every frame except every `keepEvery`-th one, within
 * [fromIndex, toIndex]. Short, scattered gaps rather than one long dropout.
 */
function stippleMissingKeypoints(frames, names, fromIndex, toIndex, keepEvery = 3) {
  return frames.map((frame, index) => {
    if (index < fromIndex || index > toIndex || index % keepEvery === 0) return frame;

    const keypoints = { ...frame.keypoints };

    for (const name of names) delete keypoints[name];

    return { ...frame, keypoints };
  });
}

const RIGHT_CHAIN = ["right_shoulder", "right_hip", "right_knee", "right_ankle"];

function run(frames, options = {}) {
  const test2 = new FiveTimesSitToStandTest({ chairSeatHeightCm: 45, ...options });

  frames.forEach((frame) => test2.push(frame));

  return test2;
}

test("five clean stands produce a completed, timed result", () => {
  const { frames } = ftsstSequence({ repetitions: 5 });
  const test2 = run(frames);

  assert.equal(test2.isComplete(), true);
  assert.equal(test2.isTimedOut(), false);
  assert.equal(test2.phase, FTSST_PHASE.DONE);

  const result = test2.finish();

  assert.equal(result.testId, "ftsst");
  assert.equal(result.status, TEST_STATUS.COMPLETED);
  assert.deepEqual(result.invalidReasons, []);
  assert.equal(result.measurements.repetitionsDetected, 5);
  assert.equal(result.measurements.requiredRepetitions, 5);
  assert.ok(result.measurements.completionTimeMs > 0);
  assert.equal(
    result.measurements.completionTimeSeconds,
    Math.round((result.measurements.completionTimeMs / 1000) * 100) / 100
  );
});

test("timing runs from leaving the seat to the fifth stand, not from frame zero", () => {
  const { frames } = ftsstSequence({ repetitions: 5 });
  const result = run(frames).finish();

  const stands = result.measurements.standTimestampsMs;

  assert.equal(stands.length, 5);
  assert.ok(stands[0] > 0, "the first stand happens after the clock starts");

  for (let index = 1; index < stands.length; index += 1) {
    assert.ok(stands[index] > stands[index - 1], "stand times must increase");
  }

  // The clock stops on the fifth stand, so the two must agree exactly.
  assert.equal(stands[4], Math.round(result.measurements.completionTimeMs));

  // The clock must not include the seated set-up frames.
  const wholeSequenceMs = frames[frames.length - 1].timestamp - frames[0].timestamp;

  assert.ok(result.measurements.completionTimeMs < wholeSequenceMs);
});

test("the definition records how the number was produced", () => {
  const { frames } = ftsstSequence({ repetitions: 5 });
  const { definition } = run(frames).finish().measurements;

  assert.equal(definition.signal, "knee_angle_hip_knee_ankle");
  assert.equal(definition.timingEndsOn, FTSST.timingEndsOn);
  assert.equal(definition.administration, "automatic_threshold_detection_not_clinician_timed");
});

test("three stands is invalid and reports no completion time", () => {
  const { frames } = ftsstSequence({ repetitions: 3 });
  const test2 = run(frames);

  assert.equal(test2.isComplete(), false);

  const result = test2.finish();

  assert.equal(result.status, TEST_STATUS.INVALID);
  assert.ok(result.invalidReasons.includes(REASON.INSUFFICIENT_REPETITIONS));
  assert.equal(result.measurements.repetitionsDetected, 3);

  // Null, not zero: the fifth stand never happened, so there is no time.
  assert.equal(result.measurements.completionTimeMs, null);
  assert.equal(result.measurements.completionTimeSeconds, null);
});

test("partial stands that never clear the stand threshold are not counted", () => {
  const { frames } = ftsstSequence({ repetitions: 5, standAngle: 140 });
  const result = run(frames).finish();

  assert.equal(result.measurements.repetitionsDetected, 0);
  assert.equal(result.status, TEST_STATUS.INVALID);
  assert.equal(result.measurements.completionTimeMs, null);
});

test("a seated starting position must be observed before the clock can start", () => {
  // Standing the whole time: nothing to time from.
  const { frames } = ftsstSequence({ repetitions: 0, seatedAngle: 170, standAngle: 170 });
  const result = run(frames).finish();

  assert.equal(result.status, TEST_STATUS.INVALID);
  assert.ok(result.invalidReasons.includes(REASON.NO_VALID_POSITION));
  assert.equal(result.measurements.completionTimeMs, null);
  assert.deepEqual(result.measurements.standTimestampsMs, []);
});

test("the side the camera sees best is the side measured", () => {
  const { frames } = ftsstSequence({ repetitions: 5 });

  const leftResult = run(frames).finish();

  assert.equal(leftResult.setup.measuredSide, "left");

  const rightBiased = withLowConfidence(frames, RIGHT_CHAIN, 0, frames.length - 1, 0.99);
  const rightResult = run(rightBiased).finish();

  assert.equal(rightResult.setup.measuredSide, "right");
  assert.equal(rightResult.measurements.repetitionsDetected, 5);
  assert.equal(rightResult.status, TEST_STATUS.COMPLETED);
});

test("an implausible chair height is a setup warning, not an invalid movement", () => {
  const { frames } = ftsstSequence({ repetitions: 5 });
  const result = run(frames, { chairSeatHeightCm: 200 }).finish();

  assert.equal(result.setup.chairSeatHeightCm, 200);
  assert.equal(result.setup.chairSeatHeightPlausible, false);
  assert.deepEqual(result.setup.warnings, [REASON.CHAIR_HEIGHT_IMPLAUSIBLE]);

  // The repetitions were still performed and timed.
  assert.equal(result.status, TEST_STATUS.COMPLETED);
  assert.equal(result.measurements.repetitionsDetected, 5);
});

test("a missing chair height is recorded honestly rather than guessed", () => {
  const { frames } = ftsstSequence({ repetitions: 5 });
  const result = run(frames, { chairSeatHeightCm: null }).finish();

  assert.equal(result.setup.chairSeatHeightCm, null);
  assert.equal(result.setup.chairSeatHeightPlausible, false);
  assert.deepEqual(result.setup.warnings, [REASON.CHAIR_HEIGHT_IMPLAUSIBLE]);
});

test("a plausible chair height produces no warnings", () => {
  const { frames } = ftsstSequence({ repetitions: 5 });
  const result = run(frames, { chairSeatHeightCm: 45 }).finish();

  assert.equal(result.setup.chairSeatHeightPlausible, true);
  assert.deepEqual(result.setup.warnings, []);
  assert.equal(result.setup.cameraView, "side");
});

test("exceeding the whole-test ceiling marks the attempt as timed out", () => {
  const { frames } = ftsstSequence({ repetitions: 5 });

  const test2 = new FiveTimesSitToStandTest({
    chairSeatHeightCm: 45,
    config: { ...FTSST, maxTestDurationMs: 2000 },
  });

  frames.forEach((frame) => test2.push(frame));

  assert.equal(test2.isTimedOut(), true);

  const result = test2.finish();

  assert.equal(result.status, TEST_STATUS.INVALID);
  assert.ok(result.invalidReasons.includes(REASON.TIMEOUT));
});

test("a long pose dropout invalidates the attempt", () => {
  const { frames } = ftsstSequence({ repetitions: 5 });
  const damaged = withMissingKeypoints(frames, ["left_knee"], 40, 100);

  const result = run(damaged).finish();

  assert.equal(result.status, TEST_STATUS.INVALID);
  assert.ok(result.invalidReasons.includes(REASON.POSE_LOST));
  assert.ok(result.quality.longestPoseLossMs > 1500);
});

test("aborting marks the attempt invalid", () => {
  const { frames } = ftsstSequence({ repetitions: 5 });
  const result = run(frames).finish({ attempts: 3, aborted: true });

  assert.equal(result.status, TEST_STATUS.INVALID);
  assert.ok(result.invalidReasons.includes(REASON.ABORTED_BY_USER));
  assert.equal(result.attempts, 3);
});

test("guidance asks the user to sit down before the test can begin", () => {
  const { frames } = ftsstSequence({ repetitions: 1, seatedAngle: 170, standAngle: 170 });
  const test2 = new FiveTimesSitToStandTest({ chairSeatHeightCm: 45 });

  frames.slice(0, 20).forEach((frame) => test2.push(frame));

  assert.equal(test2.currentGuidance(), "sit_down_to_begin");
});

test("reset clears repetitions and timing so a retry starts fresh", () => {
  const { frames } = ftsstSequence({ repetitions: 5 });
  const test2 = run(frames);

  assert.equal(test2.isComplete(), true);

  test2.reset();

  assert.equal(test2.phase, FTSST_PHASE.SELECTING_SIDE);
  assert.equal(test2.isComplete(), false);
  assert.equal(test2.side, null);
  assert.deepEqual(test2.standTimestamps, []);
});

test("elapsedMs advances while the attempt is running, not only once it is complete", () => {
  // Used for the timeout guard and for progress feedback. A frozen zero here
  // would also mean the timeout could never fire.
  const { frames } = ftsstSequence({ repetitions: 5 });
  const test2 = new FiveTimesSitToStandTest({ chairSeatHeightCm: 45 });

  let index = 0;

  while (index < frames.length && test2.startTimestamp === null) {
    test2.push(frames[index]);
    index += 1;
  }

  assert.notEqual(test2.startTimestamp, null, "the fixture never left the seated position");

  const atStart = test2.elapsedMs();

  for (let step = 0; step < 30 && index < frames.length; step += 1) {
    test2.push(frames[index]);
    index += 1;
  }

  assert.equal(test2.isComplete(), false, "the fixture completed before the check could run");

  const later = test2.elapsedMs();

  assert.ok(later > atStart, `expected the elapsed time to advance, got ${atStart} then ${later}`);
  assert.equal(later, frames[index - 1].timestamp - test2.startTimestamp);
});

test("a single-frame knee-angle spike between reps does not inflate the count", () => {
  const { frames } = ftsstSequence({ repetitions: 5 });

  // The first rep's seat-hold gap (frames 60-67 by construction: 22 setup +
  // 15 up + 8 hold + 15 down = 60) gets 3 frames of noise spiking past the
  // stand threshold and immediately falling back - short enough to survive
  // the 5-frame median filter as a brief excursion, but well under the
  // 200ms minimum dwell time for a real stand.
  const spiked = withKneeAngleSpike(frames, 62, 64, 170);

  const result = run(spiked).finish();

  assert.equal(result.status, TEST_STATUS.COMPLETED);
  assert.equal(
    result.measurements.repetitionsDetected,
    5,
    "the noise spike must not be counted as a 6th stand"
  );
});

test("a knee-angle spike standing in for the final rep does not complete the test", () => {
  const { frames } = ftsstSequence({ repetitions: 4 });
  const lastTimestamp = frames[frames.length - 1].timestamp;

  // Ten seated frames tacked on, with a brief 3-frame noise spike in the
  // middle - the kind of thing that used to register as an instant 5th
  // stand even though the person never actually stood up again.
  const tail = [];

  for (let i = 1; i <= 10; i += 1) {
    const angle = i >= 4 && i <= 6 ? 170 : 90;

    tail.push(makeFrame(lastTimestamp + i * DEFAULT_FRAME_MS, sideFacingBase(angle), { score: 0.9 }));
  }

  const test2 = run(frames.concat(tail));

  assert.equal(test2.isComplete(), false);

  const result = test2.finish();

  assert.equal(result.status, TEST_STATUS.INVALID);
  assert.ok(result.invalidReasons.includes(REASON.INSUFFICIENT_REPETITIONS));
  assert.equal(result.measurements.repetitionsDetected, 4);
  assert.equal(result.measurements.completionTimeMs, null);
});

test("a long, wobbly wait to sit down no longer fails an otherwise-clean run", () => {
  const wobbleFrames = 200;
  const frames = [];
  let timestamp = 0;

  // Hovering above the seated band the whole time, so seatedConfirmed cannot
  // be reached during this span regardless of frame usability.
  for (let i = 0; i < wobbleFrames; i += 1) {
    frames.push(makeFrame(timestamp, sideFacingBase(170), { score: 0.9 }));
    timestamp += DEFAULT_FRAME_MS;
  }

  const wobbled = stippleMissingKeypoints(frames, ["left_knee", "right_knee"], 0, wobbleFrames - 1, 3);

  const { frames: cleanReps } = ftsstSequence({ repetitions: 5 });

  for (const frame of cleanReps) {
    wobbled.push({ ...frame, timestamp: frame.timestamp + timestamp });
  }

  const result = run(wobbled).finish();

  assert.equal(result.status, TEST_STATUS.COMPLETED);
  assert.equal(result.measurements.repetitionsDetected, 5);
  assert.ok(!result.invalidReasons.includes(REASON.TOO_FEW_USABLE_FRAMES));

  // The quality check is scoped from the confirmed-seated point onward. If
  // the 200-frame wobbly wait were still included, framesSeen would be well
  // over cleanReps.length (200 wobble frames + the whole clean run); scoped
  // correctly it can be no more than the clean run itself.
  assert.ok(
    result.quality.framesSeen < cleanReps.length,
    `expected the quality tracker to be scoped past the wobbly wait, saw ${result.quality.framesSeen} of ${cleanReps.length} frames`
  );
});

test("a person who never sits down hits the bounded setup timeout", () => {
  const test2 = new FiveTimesSitToStandTest({ chairSeatHeightCm: 45 });

  let timestamp = 0;
  let index = 0;

  while (test2.phase !== FTSST_PHASE.DONE && index < 900) {
    test2.push(makeFrame(timestamp, sideFacingBase(170), { score: 0.9 }));
    timestamp += DEFAULT_FRAME_MS;
    index += 1;
  }

  assert.equal(test2.phase, FTSST_PHASE.DONE);
  assert.ok(index < 900, "the setup timeout should have ended the attempt before the safety cap");

  const result = test2.finish();

  assert.equal(result.status, TEST_STATUS.INVALID);
  assert.ok(result.invalidReasons.includes(REASON.NO_VALID_POSITION));
  assert.equal(result.measurements.completionTimeMs, null);
});
