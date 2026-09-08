/**
 * Two-dimensional geometry on image-plane keypoints.
 *
 * Image coordinates: x increases to the right, y increases DOWNWARD. Every
 * function here accounts for that, so "up" is negative y.
 *
 * These are projections of a three-dimensional movement onto the camera plane.
 * They describe what is observable in the image and are not anatomical joint
 * angles.
 */

const RAD_TO_DEG = 180 / Math.PI;

/** Vector from point a to point b. */
export function vector(a, b) {
  return { x: b.x - a.x, y: b.y - a.y };
}

export function magnitude(v) {
  return Math.hypot(v.x, v.y);
}

export function distance(a, b) {
  return Math.hypot(b.x - a.x, b.y - a.y);
}

export function midpoint(a, b) {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}

/**
 * Unsigned angle between two vectors, 0-180 degrees.
 * Returns null when either vector has no length, so callers never see NaN.
 */
export function angleBetween(v1, v2) {
  const m1 = magnitude(v1);
  const m2 = magnitude(v2);

  if (m1 === 0 || m2 === 0) return null;

  const cosine = (v1.x * v2.x + v1.y * v2.y) / (m1 * m2);

  // Guard against floating point pushing the cosine just outside [-1, 1].
  return Math.acos(Math.min(1, Math.max(-1, cosine))) * RAD_TO_DEG;
}

/**
 * Interior angle at `vertex` formed by the segments to `a` and `b`.
 * Used for the knee angle in the sit-to-stand test (hip-knee-ankle).
 */
export function jointAngle(a, vertex, b) {
  return angleBetween(vector(vertex, a), vector(vertex, b));
}

/**
 * Elevation of a limb segment measured from the downward vertical.
 *
 * 0 degrees is the segment hanging straight down, 90 is horizontal, 180 is
 * pointing straight up. Used for observable arm elevation in test 1.
 */
export function elevationFromDown(proximal, distal) {
  return angleBetween(vector(proximal, distal), { x: 0, y: 1 });
}

/**
 * Tilt of a segment away from the vertical axis, 0-90 degrees, sign ignored.
 * Used for trunk lean, where leaning left or right matters equally.
 */
export function tiltFromVertical(top, bottom) {
  const angle = angleBetween(vector(bottom, top), { x: 0, y: -1 });

  if (angle === null) return null;

  return angle > 90 ? 180 - angle : angle;
}

/**
 * A body-scale length in pixels, used to make pixel distances comparable
 * between people and camera distances. Mid-shoulder to mid-hip.
 */
export function torsoLength(leftShoulder, rightShoulder, leftHip, rightHip) {
  return distance(
    midpoint(leftShoulder, rightShoulder),
    midpoint(leftHip, rightHip)
  );
}

/** Ratio of shoulder width to torso length; a rotation-sensitive quantity. */
export function shoulderTorsoRatio(leftShoulder, rightShoulder, leftHip, rightHip) {
  const torso = torsoLength(leftShoulder, rightShoulder, leftHip, rightHip);

  if (torso === 0) return null;

  return distance(leftShoulder, rightShoulder) / torso;
}

/** Clamp helper used when normalising ratios for display. */
export function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

/** Round to a fixed number of decimals, preserving null. */
export function round(value, decimals = 1) {
  if (value === null || value === undefined || !Number.isFinite(value)) return null;

  const factor = 10 ** decimals;

  return Math.round(value * factor) / factor;
}
