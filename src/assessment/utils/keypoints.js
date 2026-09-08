/**
 * MoveNet keypoint access.
 *
 * MoveNet returns the 17 COCO keypoints. Test logic should never index into
 * that array by number; it asks for keypoints by name through these helpers so
 * a change of model layout stays contained in this file.
 */

export const KEYPOINT_NAMES = [
  "nose",
  "left_eye",
  "right_eye",
  "left_ear",
  "right_ear",
  "left_shoulder",
  "right_shoulder",
  "left_elbow",
  "right_elbow",
  "left_wrist",
  "right_wrist",
  "left_hip",
  "right_hip",
  "left_knee",
  "right_knee",
  "left_ankle",
  "right_ankle",
];

/**
 * Build a name-keyed frame from a raw detector pose.
 *
 * @param {{keypoints: Array<{x: number, y: number, score?: number, name?: string}>}} pose
 * @param {number} timestamp milliseconds, monotonic within a session
 * @returns {{timestamp: number, keypoints: Record<string, {x: number, y: number, score: number}>}}
 */
export function toFrame(pose, timestamp) {
  const keypoints = {};

  if (pose && Array.isArray(pose.keypoints)) {
    pose.keypoints.forEach((keypoint, index) => {
      const name = keypoint.name || KEYPOINT_NAMES[index];

      if (!name) return;

      keypoints[name] = {
        x: keypoint.x,
        y: keypoint.y,
        score: typeof keypoint.score === "number" ? keypoint.score : 0,
      };
    });
  }

  return { timestamp, keypoints };
}

/**
 * Return a keypoint only if it clears the confidence floor, otherwise null.
 * Callers treat null as "not observed in this frame".
 */
export function getKeypoint(frame, name, minScore) {
  const keypoint = frame && frame.keypoints ? frame.keypoints[name] : null;

  if (!keypoint) return null;
  if (typeof keypoint.x !== "number" || typeof keypoint.y !== "number") return null;
  if (!Number.isFinite(keypoint.x) || !Number.isFinite(keypoint.y)) return null;
  if (keypoint.score < minScore) return null;

  return keypoint;
}

/** Same as getKeypoint for a list of names; returns null if any is missing. */
export function getKeypoints(frame, names, minScore) {
  const found = {};

  for (const name of names) {
    const keypoint = getKeypoint(frame, name, minScore);

    if (!keypoint) return null;

    found[name] = keypoint;
  }

  return found;
}

/** Names of the keypoints in `names` that did not clear the confidence floor. */
export function missingKeypoints(frame, names, minScore) {
  return names.filter((name) => getKeypoint(frame, name, minScore) === null);
}

/** Mean confidence across the named keypoints, counting absent ones as zero. */
export function meanScore(frame, names) {
  if (!names.length) return 0;

  const total = names.reduce((sum, name) => {
    const keypoint = frame && frame.keypoints ? frame.keypoints[name] : null;
    return sum + (keypoint && typeof keypoint.score === "number" ? keypoint.score : 0);
  }, 0);

  return total / names.length;
}

export const SIDE_KEYPOINTS = {
  left: {
    shoulder: "left_shoulder",
    elbow: "left_elbow",
    wrist: "left_wrist",
    hip: "left_hip",
    knee: "left_knee",
    ankle: "left_ankle",
  },
  right: {
    shoulder: "right_shoulder",
    elbow: "right_elbow",
    wrist: "right_wrist",
    hip: "right_hip",
    knee: "right_knee",
    ankle: "right_ankle",
  },
};

/** The other side. Test 3 lifts one foot while the other supports. */
export function otherSide(side) {
  return side === "left" ? "right" : "left";
}
