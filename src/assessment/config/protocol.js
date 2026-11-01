/**
 * Assessment protocol configuration.
 *
 * Every number in this file is an IMPLEMENTATION PARAMETER chosen so the
 * detection logic behaves sensibly with a consumer webcam. None of these are
 * clinical norms, diagnostic cut-offs, or published reference values, and they
 * must never be presented to a user as such.
 *
 * PROTOCOL_VERSION must be incremented whenever a change here could alter the
 * measurement produced from the same movement, so stored results always record
 * which parameter set produced them.
 */

export const PROTOCOL_VERSION = "1.0.0";

/** Shared pose-quality parameters, applied to every test. */
export const POSE = {
  /** Minimum per-keypoint confidence for a keypoint to be used at all. */
  minKeypointScore: 0.3,

  /** Minimum confidence for keypoints a test cannot function without. */
  minRequiredKeypointScore: 0.4,

  /** Frames per second below which the recording is flagged as low quality. */
  lowFpsThreshold: 12,

  /**
   * Share of processed frames that must pass validation for a test result to
   * be treated as usable.
   */
  minUsableFrameRatio: 0.6,

  /** Consecutive milliseconds of unusable pose that aborts a running test. */
  maxPoseLossMs: 1500,

  /** Show repositioning guidance before a loss becomes a final failure. */
  trackingWarningMs: 500,

  /** Sustained loss timeout for an active assessment attempt. */
  maxRecoveryMs: 5000,
};

/** Test 1 - bilateral active shoulder abduction, front-facing camera. */
export const SHOULDER = {
  requiredRepetitions: 3,

  /**
   * Arm-elevation angle, in degrees, of the shoulder-to-elbow segment measured
   * from the downward vertical in the image plane. 0 is arm at the side.
   */
  repEnterAngleDeg: 55,
  repExitAngleDeg: 30,

  /** Rejects jitter being counted as a repetition. */
  minRepDurationMs: 400,
  maxRepDurationMs: 12000,

  /** Median filter window (frames) applied to the raw angle signal. */
  smoothingWindow: 5,

  /** Trunk lean from vertical, in degrees, above which a frame is discarded. */
  maxTrunkLeanDeg: 18,

  /**
   * Horizontal movement of the mid-hip point away from its resting position,
   * as a fraction of shoulder width, above which a frame is discarded.
   */
  maxHipShiftRatio: 0.35,

  /**
   * Shoulder width divided by torso length. A front-facing torso is wide; the
   * ratio collapses as the person rotates away from the camera.
   */
  minFrontFacingRatio: 0.42,

  /** Frames of quiet standing used to establish the resting hip position. */
  calibrationFrames: 15,

  /**
   * During active movement (MEASURING), natural sway - a weight shift, a
   * brief trunk lean, momentary hip drift - is expected and should not blank
   * out an otherwise-good frame mid-repetition. These loosen the CALIBRATING
   * thresholds above by a modest, explicit software margin for the MEASURING
   * phase only; CALIBRATING keeps the stricter thresholds so the resting
   * reference position is still established cleanly. Not clinical values.
   */
  maxTrunkLeanDegMeasuring: 22,
  maxHipShiftRatioMeasuring: 0.5,
  minFrontFacingRatioMeasuring: 0.32,
};

/** Test 3 - eyes-open single-leg stance, front-facing camera. */
export const BALANCE = {
  /** Upper bound on a single hold. Reaching it is a valid, complete result. */
  maxDurationMs: 30000,

  /**
   * Vertical separation between the lifted and support ankle, as a fraction of
   * hip-to-ankle length, that counts as a lifted foot.
   */
  minLiftRatio: 0.10,

  /** The lift ratio at which the foot is considered to have come back down. */
  lossLiftRatio: 0.05,

  /** Consecutive visible frames required to confirm a deliberate foot return. */
  footDownConfirmationFrames: 3,

  /** Valid position must be held this long before the clock starts. */
  stabilizationMs: 400,

  /** Trunk lean from vertical, in degrees, treated as loss of position. */
  maxTrunkLeanDeg: 22,

  /**
   * Horizontal travel of the support ankle from where it was when timing
   * started, as a fraction of hip-to-ankle length. Catches hopping and
   * stepping without needing to classify either.
   */
  maxSupportAnkleShiftRatio: 0.18,

  smoothingWindow: 3,

  /**
   * Ceiling on WAITING + STABILISING combined: how long the person can take
   * to find and hold a valid lifted position before the attempt is ended,
   * rather than accumulating an unbounded stream of setup frames into the
   * quality accounting forever. A software ceiling, not a clinical cut-off.
   */
  maxSetupDurationMs: 20000,

  /** Front-facing ratio threshold for balance: allows slight natural sway without flagging orientation failure. */
  minFrontFacingRatio: 0.30,

  sides: ["left", "right"],
};

/**
 * Reason codes. Stored instead of prose so results stay comparable and can be
 * re-interpreted later without parsing sentences.
 */
export const REASON = {
  KEYPOINTS_MISSING: "keypoints_missing",
  LOW_CONFIDENCE: "low_confidence",
  BOTH_SIDES_NOT_VISIBLE: "both_sides_not_visible",
  NOT_FRONT_FACING: "not_front_facing",
  EXCESSIVE_TRUNK_LEAN: "excessive_trunk_lean",
  HIP_SHIFT: "hip_shift",
  TOO_FEW_USABLE_FRAMES: "too_few_usable_frames",
  POSE_LOST: "pose_lost",
  LOW_FPS: "low_fps",
  TIMEOUT: "timeout",
  FOOT_LOWERED: "foot_lowered",
  SUPPORT_FOOT_MOVED: "support_foot_moved",
  NO_VALID_POSITION: "no_valid_position",
  MAX_DURATION_REACHED: "max_duration_reached",
  ABORTED_BY_USER: "aborted_by_user",
};

/** Lifecycle status of a single test within a session. */
export const TEST_STATUS = {
  NOT_STARTED: "not_started",
  COMPLETED: "completed",
  INVALID: "invalid",
  SKIPPED: "skipped",
};

export const PROTOCOL = {
  version: PROTOCOL_VERSION,
  pose: POSE,
  shoulder: SHOULDER,
  balance: BALANCE,
};

export const TEST_TITLES = {
  shoulder: "Shoulder movement",
  balance: "Standing on one leg",
};

export const TEST_ORDER = ["shoulder", "balance"];
