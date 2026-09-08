/**
 * Synthetic pose sequences for developing and testing the measurement logic.
 *
 * These are generated from simple geometry, not recorded from anyone. They exist
 * so the geometry, smoothing, repetition detection, timing, and validity rules
 * can be exercised without a camera. They are NOT training data, they are never
 * used at runtime, and no model is fitted to them.
 */

import { KEYPOINT_NAMES } from "../utils/keypoints.js";

const DEG = Math.PI / 180;

/** Default frame interval, 30 frames per second. */
export const DEFAULT_FRAME_MS = 1000 / 30;

/** Build a frame from a partial map of keypoint positions. */
export function makeFrame(timestamp, positions, { score = 0.9, missing = [] } = {}) {
  const keypoints = {};

  for (const name of KEYPOINT_NAMES) {
    if (missing.includes(name)) continue;

    const position = positions[name];

    if (!position) continue;

    keypoints[name] = {
      x: position.x,
      y: position.y,
      score: position.score ?? score,
    };
  }

  return { timestamp, keypoints };
}

/**
 * Front-facing standing skeleton.
 * Shoulder width 160 over torso length 190 gives a front-facing ratio of ~0.84.
 */
export function frontFacingBase() {
  return {
    nose: { x: 320, y: 110 },
    left_eye: { x: 310, y: 105 },
    right_eye: { x: 330, y: 105 },
    left_ear: { x: 300, y: 110 },
    right_ear: { x: 340, y: 110 },
    left_shoulder: { x: 240, y: 150 },
    right_shoulder: { x: 400, y: 150 },
    left_elbow: { x: 240, y: 270 },
    right_elbow: { x: 400, y: 270 },
    left_wrist: { x: 240, y: 380 },
    right_wrist: { x: 400, y: 380 },
    left_hip: { x: 270, y: 340 },
    right_hip: { x: 370, y: 340 },
    left_knee: { x: 295, y: 480 },
    right_knee: { x: 345, y: 480 },
    left_ankle: { x: 300, y: 620 },
    right_ankle: { x: 340, y: 620 },
  };
}

/** Place an elbow at a given elevation from the downward vertical. */
function elbowAt(shoulder, elevationDeg, outwardSign, upperArmLength = 120) {
  const radians = elevationDeg * DEG;

  return {
    x: shoulder.x + outwardSign * Math.sin(radians) * upperArmLength,
    // y grows downward, so cos(0) = 1 keeps the arm hanging down.
    y: shoulder.y + Math.cos(radians) * upperArmLength,
  };
}

/**
 * Shoulder abduction sequence: quiet standing, then a number of repetitions
 * that ramp up, hold at the peak, and return.
 *
 * @param {object} options
 * @param {number[]} options.leftPeaks peak elevation in degrees per repetition
 * @param {number[]} options.rightPeaks
 * @param {number} [options.calibrationFrames]
 * @param {number} [options.rampFrames]
 * @param {number} [options.holdFrames] frames held at the peak
 */
export function shoulderSequence({
  leftPeaks,
  rightPeaks,
  calibrationFrames = 20,
  rampFrames = 20,
  holdFrames = 8,
  restFrames = 8,
  frameMs = DEFAULT_FRAME_MS,
  score = 0.9,
  trunkLeanFrames = [],
  trunkLeanShift = 90,
} = {}) {
  const frames = [];
  let timestamp = 0;

  const emit = (leftAngle, rightAngle, index) => {
    const base = frontFacingBase();

    base.left_elbow = elbowAt(base.left_shoulder, leftAngle, -1);
    base.right_elbow = elbowAt(base.right_shoulder, rightAngle, +1);

    // Optional trunk lean: shift the shoulder line sideways so the mid-shoulder
    // to mid-hip line tilts away from vertical.
    if (trunkLeanFrames.includes(index)) {
      const shift = trunkLeanShift;

      base.left_shoulder = { x: base.left_shoulder.x + shift, y: base.left_shoulder.y };
      base.right_shoulder = { x: base.right_shoulder.x + shift, y: base.right_shoulder.y };
      base.left_elbow = elbowAt(base.left_shoulder, leftAngle, -1);
      base.right_elbow = elbowAt(base.right_shoulder, rightAngle, +1);
    }

    frames.push(makeFrame(timestamp, base, { score }));
    timestamp += frameMs;
  };

  let index = 0;

  for (let i = 0; i < calibrationFrames; i += 1, index += 1) emit(0, 0, index);

  const repetitions = Math.max(leftPeaks.length, rightPeaks.length);

  for (let rep = 0; rep < repetitions; rep += 1) {
    const leftPeak = leftPeaks[rep] ?? 0;
    const rightPeak = rightPeaks[rep] ?? 0;

    for (let step = 1; step <= rampFrames; step += 1, index += 1) {
      const fraction = step / rampFrames;

      emit(leftPeak * fraction, rightPeak * fraction, index);
    }

    for (let step = 0; step < holdFrames; step += 1, index += 1) {
      emit(leftPeak, rightPeak, index);
    }

    for (let step = rampFrames - 1; step >= 0; step -= 1, index += 1) {
      const fraction = step / rampFrames;

      emit(leftPeak * fraction, rightPeak * fraction, index);
    }

    for (let step = 0; step < restFrames; step += 1, index += 1) emit(0, 0, index);
  }

  return frames;
}

/**
 * Side-facing skeleton with the knee at a chosen angle.
 * A narrow shoulder line (width 20 over torso 190, ratio ~0.11) reads as a side
 * view.
 */
export function sideFacingBase(kneeAngleDeg) {
  const ankle = { x: 300, y: 500 };
  const knee = { x: 300, y: 400 };

  const radians = kneeAngleDeg * DEG;
  const thighLength = 150;

  // Angle is measured at the knee between the thigh and the shank. The shank
  // points straight down from the knee, so the thigh is placed at kneeAngle
  // from that downward direction.
  const hip = {
    x: knee.x + Math.sin(radians) * thighLength,
    y: knee.y + Math.cos(radians) * thighLength,
  };

  const shoulderY = hip.y - 190;

  return {
    nose: { x: hip.x, y: shoulderY - 40 },
    left_shoulder: { x: hip.x - 10, y: shoulderY },
    right_shoulder: { x: hip.x + 10, y: shoulderY },
    left_elbow: { x: hip.x, y: shoulderY + 90 },
    right_elbow: { x: hip.x, y: shoulderY + 90 },
    left_hip: { x: hip.x - 5, y: hip.y },
    right_hip: { x: hip.x + 5, y: hip.y },
    left_knee: { x: knee.x - 5, y: knee.y },
    right_knee: { x: knee.x + 5, y: knee.y },
    left_ankle: { x: ankle.x - 5, y: ankle.y },
    right_ankle: { x: ankle.x + 5, y: ankle.y },
  };
}

/**
 * Five times sit-to-stand sequence.
 *
 * @param {object} options
 * @param {number} [options.repetitions] number of stands performed
 * @param {number} [options.seatedAngle]
 * @param {number} [options.standAngle]
 */
export function ftsstSequence({
  repetitions = 5,
  seatedAngle = 90,
  standAngle = 170,
  sideSelectionFrames = 12,
  seatedFrames = 10,
  transitionFrames = 15,
  standHoldFrames = 8,
  seatHoldFrames = 8,
  frameMs = DEFAULT_FRAME_MS,
  score = 0.9,
} = {}) {
  const frames = [];
  let timestamp = 0;

  const emit = (kneeAngle) => {
    frames.push(makeFrame(timestamp, sideFacingBase(kneeAngle), { score }));
    timestamp += frameMs;
  };

  for (let i = 0; i < sideSelectionFrames + seatedFrames; i += 1) emit(seatedAngle);

  for (let rep = 0; rep < repetitions; rep += 1) {
    for (let step = 1; step <= transitionFrames; step += 1) {
      emit(seatedAngle + ((standAngle - seatedAngle) * step) / transitionFrames);
    }

    for (let step = 0; step < standHoldFrames; step += 1) emit(standAngle);

    for (let step = transitionFrames - 1; step >= 0; step -= 1) {
      emit(seatedAngle + ((standAngle - seatedAngle) * step) / transitionFrames);
    }

    for (let step = 0; step < seatHoldFrames; step += 1) emit(seatedAngle);
  }

  return { frames, frameMs };
}

/**
 * Single-leg stance sequence.
 *
 * @param {object} options
 * @param {"left"|"right"} options.supportSide
 * @param {number} options.holdFrames frames the foot stays lifted
 * @param {number} [options.liftRatio] target lift as a fraction of body scale
 * @param {boolean} [options.leanAtEnd] finish with excessive trunk lean instead
 * @param {number} [options.ankleShiftAtEnd] move the support ankle sideways
 */
export function balanceSequence({
  supportSide = "left",
  holdFrames = 90,
  liftRatio = 0.18,
  standingFrames = 6,
  frameMs = DEFAULT_FRAME_MS,
  score = 0.9,
  leanAtEnd = false,
  ankleShiftAtEnd = 0,
  trailingFrames = 6,
} = {}) {
  const frames = [];
  let timestamp = 0;

  const liftedSide = supportSide === "left" ? "right" : "left";

  const emit = ({ lift = 0, lean = false, ankleShift = 0 } = {}) => {
    const base = frontFacingBase();

    const supportAnkle = base[`${supportSide}_ankle`];
    const midHipY = (base.left_hip.y + base.right_hip.y) / 2;
    const midHipX = (base.left_hip.x + base.right_hip.x) / 2;

    const scale = Math.hypot(midHipX - supportAnkle.x, midHipY - supportAnkle.y);

    base[`${liftedSide}_ankle`] = {
      x: base[`${liftedSide}_ankle`].x,
      y: supportAnkle.y - lift * scale,
    };

    if (ankleShift) {
      base[`${supportSide}_ankle`] = {
        x: supportAnkle.x + ankleShift * scale,
        y: supportAnkle.y,
      };
    }

    if (lean) {
      const shift = 110;

      base.left_shoulder = { x: base.left_shoulder.x + shift, y: base.left_shoulder.y };
      base.right_shoulder = { x: base.right_shoulder.x + shift, y: base.right_shoulder.y };
    }

    frames.push(makeFrame(timestamp, base, { score }));
    timestamp += frameMs;
  };

  for (let i = 0; i < standingFrames; i += 1) emit({ lift: 0 });

  for (let i = 0; i < holdFrames; i += 1) emit({ lift: liftRatio });

  if (leanAtEnd) {
    for (let i = 0; i < trailingFrames; i += 1) emit({ lift: liftRatio, lean: true });
  } else if (ankleShiftAtEnd) {
    for (let i = 0; i < trailingFrames; i += 1) {
      emit({ lift: liftRatio, ankleShift: ankleShiftAtEnd });
    }
  } else {
    for (let i = 0; i < trailingFrames; i += 1) emit({ lift: 0 });
  }

  return { frames, frameMs };
}

/** Drop the score of the named keypoints so they fall below the floor. */
export function withLowConfidence(frames, names, fromIndex, toIndex, score = 0.05) {
  return frames.map((frame, index) => {
    if (index < fromIndex || index > toIndex) return frame;

    const keypoints = { ...frame.keypoints };

    for (const name of names) {
      if (keypoints[name]) keypoints[name] = { ...keypoints[name], score };
    }

    return { ...frame, keypoints };
  });
}

/** Remove the named keypoints entirely for a span of frames. */
export function withMissingKeypoints(frames, names, fromIndex, toIndex) {
  return frames.map((frame, index) => {
    if (index < fromIndex || index > toIndex) return frame;

    const keypoints = { ...frame.keypoints };

    for (const name of names) delete keypoints[name];

    return { ...frame, keypoints };
  });
}
