/**
 * Skeleton overlay drawing.
 *
 * Purely a live feedback aid: it shows the user what the model can currently
 * see so they can fix their framing or lighting. Nothing drawn here is recorded,
 * and no measurement is derived from it.
 */

import { POSE } from "../config/protocol.js";

/** COCO skeleton edges, by keypoint name. */
const EDGES = [
  ["left_shoulder", "right_shoulder"],
  ["left_shoulder", "left_elbow"],
  ["left_elbow", "left_wrist"],
  ["right_shoulder", "right_elbow"],
  ["right_elbow", "right_wrist"],
  ["left_shoulder", "left_hip"],
  ["right_shoulder", "right_hip"],
  ["left_hip", "right_hip"],
  ["left_hip", "left_knee"],
  ["left_knee", "left_ankle"],
  ["right_hip", "right_knee"],
  ["right_knee", "right_ankle"],
];

const JOINTS = [
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

function visible(keypoint) {
  return (
    keypoint &&
    Number.isFinite(keypoint.x) &&
    Number.isFinite(keypoint.y) &&
    keypoint.score >= POSE.minKeypointScore
  );
}

/**
 * Draw one frame's skeleton.
 *
 * @param {CanvasRenderingContext2D} context
 * @param {{keypoints: Record<string, {x:number,y:number,score:number}>}} frame
 * @param {{width: number, height: number, usable?: boolean}} options
 */
export function drawSkeleton(context, frame, { width, height, usable = true }) {
  context.clearRect(0, 0, width, height);

  if (!frame || !frame.keypoints) return;

  const points = frame.keypoints;
  const stroke = usable ? "rgba(119, 181, 142, 0.95)" : "rgba(165, 78, 71, 0.9)";

  context.lineWidth = Math.max(2, Math.round(width / 220));
  context.strokeStyle = stroke;
  context.lineCap = "round";

  EDGES.forEach(([from, to]) => {
    const a = points[from];
    const b = points[to];

    if (!visible(a) || !visible(b)) return;

    context.beginPath();
    context.moveTo(a.x, a.y);
    context.lineTo(b.x, b.y);
    context.stroke();
  });

  const radius = Math.max(3, Math.round(width / 160));

  context.fillStyle = usable ? "rgba(23, 35, 29, 0.9)" : "rgba(165, 78, 71, 0.95)";

  JOINTS.forEach((name) => {
    const keypoint = points[name];

    if (!visible(keypoint)) return;

    context.beginPath();
    context.arc(keypoint.x, keypoint.y, radius, 0, Math.PI * 2);
    context.fill();
  });
}

/** Clear the overlay, used when the frame loop stops. */
export function clearOverlay(context, width, height) {
  context.clearRect(0, 0, width, height);
}
