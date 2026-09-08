/**
 * Pre-test positioning and framing checklist logic.
 *
 * Evaluates live camera frames during pre-test setup to ensure the user is
 * properly framed, visible, and stable before any measurement or countdown begins.
 *
 * Translates technical landmark confidence and geometry into actionable,
 * human-friendly instructions. No raw frame or keypoint data leaves the client.
 */

import { shoulderTorsoRatio } from "./geometry.js";

export const POSITIONING_STATUS = {
  SEARCHING: "searching",
  ADJUSTING: "adjusting",
  HOLDING: "holding",
  READY: "ready",
};

export const STABLE_PREFLIGHT_FRAMES = 10;
const MIN_CONFIDENCE = 0.28;

/**
 * Evaluates landmark visibility and camera framing for the given assessment.
 *
 * @param {object} frame - Current pose frame with keypoints
 * @param {"shoulder"|"ftsst"|"balance"} testType - Assessment type
 * @param {object} [options]
 * @param {number} [options.stableCount] - Consecutive stable frames so far
 * @returns {object} Positioning assessment with checklist, guidance, and status
 */
export function evaluatePositioning(frame, testType, { stableCount = 0 } = {}) {
  if (!frame || !frame.keypoints || Object.keys(frame.keypoints).length === 0) {
    return {
      status: POSITIONING_STATUS.SEARCHING,
      ready: false,
      guidance: "Step in front of the camera so we can see you.",
      actionableTip: "Position yourself in front of the camera.",
      checklist: {
        head: false,
        shoulders: false,
        hips: false,
        knees: false,
        feet: false,
      },
      stableFrames: 0,
      targetStableFrames: STABLE_PREFLIGHT_FRAMES,
      progress: 0,
      trackingQuality: "repositioning",
    };
  }

  const kp = frame.keypoints;

  // 1. Checklist landmarks check
  const hasHead = Boolean(
    (kp.nose && kp.nose.score >= MIN_CONFIDENCE) ||
    (kp.left_eye && kp.left_eye.score >= MIN_CONFIDENCE) ||
    (kp.right_eye && kp.right_eye.score >= MIN_CONFIDENCE) ||
    (kp.left_ear && kp.left_ear.score >= MIN_CONFIDENCE) ||
    (kp.right_ear && kp.right_ear.score >= MIN_CONFIDENCE)
  );

  const hasLeftShoulder = Boolean(kp.left_shoulder && kp.left_shoulder.score >= MIN_CONFIDENCE);
  const hasRightShoulder = Boolean(kp.right_shoulder && kp.right_shoulder.score >= MIN_CONFIDENCE);
  const hasShoulders = testType === "ftsst"
    ? hasLeftShoulder || hasRightShoulder
    : hasLeftShoulder && hasRightShoulder;

  const hasLeftHip = Boolean(kp.left_hip && kp.left_hip.score >= MIN_CONFIDENCE);
  const hasRightHip = Boolean(kp.right_hip && kp.right_hip.score >= MIN_CONFIDENCE);
  const hasHips = testType === "ftsst"
    ? hasLeftHip || hasRightHip
    : hasLeftHip || hasRightHip;

  const hasLeftKnee = Boolean(kp.left_knee && kp.left_knee.score >= MIN_CONFIDENCE);
  const hasRightKnee = Boolean(kp.right_knee && kp.right_knee.score >= MIN_CONFIDENCE);
  const hasKnees = testType === "ftsst"
    ? hasLeftKnee || hasRightKnee
    : hasLeftKnee || hasRightKnee;

  const hasLeftAnkle = Boolean(kp.left_ankle && kp.left_ankle.score >= MIN_CONFIDENCE);
  const hasRightAnkle = Boolean(kp.right_ankle && kp.right_ankle.score >= MIN_CONFIDENCE);
  const hasFeet = testType === "ftsst"
    ? hasLeftAnkle || hasRightAnkle
    : hasLeftAnkle || hasRightAnkle;

  // Test-specific requirements
  const hasLeftElbow = Boolean(kp.left_elbow && kp.left_elbow.score >= MIN_CONFIDENCE);
  const hasRightElbow = Boolean(kp.right_elbow && kp.right_elbow.score >= MIN_CONFIDENCE);
  const hasLeftWrist = Boolean(kp.left_wrist && kp.left_wrist.score >= MIN_CONFIDENCE);
  const hasRightWrist = Boolean(kp.right_wrist && kp.right_wrist.score >= MIN_CONFIDENCE);

  const checklist = {
    head: hasHead,
    shoulders: hasShoulders,
    hips: testType === "shoulder" ? true : hasHips, // Shoulder raise primarily requires upper body; hips are extrapolated if occluded
    knees: testType === "shoulder" ? true : hasKnees,
    feet: testType === "shoulder" ? true : hasFeet,
    ...(testType === "shoulder" ? {
      arms: (hasLeftElbow || hasLeftWrist) && (hasRightElbow || hasRightWrist),
    } : {}),
  };

  const allVisible = Object.values(checklist).every(Boolean);

  // 2. Framing boundaries & clipping analysis (adaptive to laptop webcams)
  let guidance = null;
  let actionableTip = null;

  // Check top clipping (head)
  const headY = kp.nose?.y ?? Math.min(kp.left_eye?.y ?? 1, kp.right_eye?.y ?? 1);
  if (hasHead && headY < 0.05) {
    guidance = "Move the camera slightly higher.";
    actionableTip = "Tilt your screen up or step back slightly.";
  }

  // Check bottom clipping (feet) for sit-to-stand and balance
  if (testType !== "shoulder") {
    const maxY = Math.max(
      hasLeftAnkle ? kp.left_ankle.y : 0,
      hasRightAnkle ? kp.right_ankle.y : 0
    );
    if (maxY > 0.96) {
      guidance = "Please step back so your feet are visible.";
      actionableTip = "Step back until your feet are comfortably inside the frame.";
    }
  }

  // Check distance: too close (torso spans > 80% vertical frame)
  if (hasShoulders && hasHips) {
    const shoulderY = Math.min(kp.left_shoulder?.y ?? 1, kp.right_shoulder?.y ?? 1);
    const hipY = Math.max(kp.left_hip?.y ?? 0, kp.right_hip?.y ?? 0);
    const torsoSpan = Math.abs(hipY - shoulderY);

    if (torsoSpan > 0.55 && testType !== "shoulder") {
      guidance = "Move a little farther from the camera.";
      actionableTip = "Step back so your full body fits into view.";
    } else if (torsoSpan < 0.12) {
      guidance = "Move a little closer.";
      actionableTip = "Step slightly closer to the camera.";
    }
  }

  // Check orientation for sit-to-stand: requires side orientation
  if (!guidance && testType === "ftsst" && hasLeftShoulder && hasRightShoulder && hasLeftHip && hasRightHip) {
    const ratio = shoulderTorsoRatio(
      kp.left_shoulder,
      kp.right_shoulder,
      kp.left_hip,
      kp.right_hip
    );
    if (ratio !== null && ratio > 0.48) {
      guidance = "Turn slightly sideways.";
      actionableTip = "Place your chair sideways to the camera.";
    }
  }

  // Missing body parts actionable feedback
  if (!guidance) {
    if (!hasFeet && testType !== "shoulder") {
      guidance = "Please step back so your feet are visible.";
      actionableTip = "Step back so your feet remain inside the frame.";
    } else if (!hasKnees && testType !== "shoulder") {
      guidance = "Step back so your knees are visible.";
      actionableTip = "Make sure your lower body is visible.";
    } else if (!hasHips && testType !== "shoulder") {
      guidance = "Step back so your hips are in view.";
      actionableTip = "Keep your torso centered in the camera frame.";
    } else if (!hasShoulders) {
      guidance = "Position your upper body in the frame.";
      actionableTip = "Ensure your shoulders are visible.";
    } else if (!hasHead) {
      guidance = "Move the camera slightly higher.";
      actionableTip = "Tilt camera so your head is visible.";
    } else if (testType === "shoulder" && !checklist.arms) {
      guidance = "Stand where your upper body and both arms are clearly visible.";
      actionableTip = "Make sure both arms have room to raise sideways.";
    }
  }

  // If positioning passed all checks, evaluate stability
  const isFramed = allVisible && !guidance;
  let nextStableCount = isFramed ? stableCount + 1 : 0;
  const isReady = nextStableCount >= STABLE_PREFLIGHT_FRAMES;

  if (isFramed && !isReady) {
    guidance = "Hold still for a moment...";
    actionableTip = "Hold steady while we confirm your position.";
  } else if (isReady) {
    guidance = "Great! You're in position.";
    actionableTip = "Ready to begin.";
  }

  const progress = Math.min(1, nextStableCount / STABLE_PREFLIGHT_FRAMES);

  let status = POSITIONING_STATUS.ADJUSTING;
  if (!allVisible) {
    status = POSITIONING_STATUS.SEARCHING;
  } else if (isReady) {
    status = POSITIONING_STATUS.READY;
  } else if (isFramed) {
    status = POSITIONING_STATUS.HOLDING;
  }

  const trackingQuality = isReady
    ? "ready"
    : isFramed
      ? "tracking"
      : allVisible
        ? "recovering"
        : "repositioning";

  return {
    status,
    ready: isReady,
    guidance,
    actionableTip,
    checklist,
    stableFrames: nextStableCount,
    targetStableFrames: STABLE_PREFLIGHT_FRAMES,
    progress,
    trackingQuality,
  };
}
