/**
 * The camera preview and skeleton overlay.
 *
 * Mounted once for the whole assessment, so the camera and the model are never
 * opened twice. The preview is mirrored for comfort; the pixels handed to the
 * model are not mirrored, so left and right stay correctly labelled.
 */

import { useEffect, useRef, useState } from "react";

import { ENGINE_STATE, describePoseError } from "../pose/poseEngine.js";
import { drawSkeleton } from "../pose/skeleton.js";
import { POSE } from "../config/protocol.js";

const TRACKED_JOINTS = [
  "left_shoulder",
  "right_shoulder",
  "left_elbow",
  "right_elbow",
  "left_hip",
  "right_hip",
  "left_knee",
  "right_knee",
  "left_ankle",
  "right_ankle",
];

/** Below this many visible joints the framing is probably wrong. */
const MIN_VISIBLE_JOINTS = 6;

/** Badge updates a few times a second; the measurement still sees every frame. */
const BADGE_INTERVAL_MS = 250;

export default function CameraStage({
  engine,
  hint,
  outline = null,
  countdown = null,
  trackingStatus = null,
  guidance = null,
}) {
  const { videoRef, subscribe, state, error, getFps, retry } = engine;
  const canvasRef = useRef(null);
  const badgeUpdatedRef = useRef(0);

  const [tracking, setTracking] = useState({ visible: 0, fps: null });

  useEffect(() => {
    const canvas = canvasRef.current;

    if (!canvas) return undefined;

    const context = canvas.getContext("2d");

    const handleFrame = (frame) => {
      const video = videoRef.current;
      const width = video?.videoWidth || 0;
      const height = video?.videoHeight || 0;

      if (!width || !height) return;

      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }

      let visible = 0;

      TRACKED_JOINTS.forEach((name) => {
        const keypoint = frame.keypoints[name];

        if (keypoint && keypoint.score >= POSE.minKeypointScore) visible += 1;
      });

      drawSkeleton(context, frame, {
        width,
        height,
        usable: visible >= MIN_VISIBLE_JOINTS,
      });

      if (frame.timestamp - badgeUpdatedRef.current >= BADGE_INTERVAL_MS) {
        badgeUpdatedRef.current = frame.timestamp;
        setTracking({ visible, fps: getFps() });
      }
    };

    return subscribe(handleFrame);
  }, [subscribe, videoRef, getFps]);

  const connecting =
    state === ENGINE_STATE.LOADING_MODEL || state === ENGINE_STATE.STARTING_CAMERA;

  const wellFramed = tracking.visible >= MIN_VISIBLE_JOINTS;

  const resolvedStatus = trackingStatus || (wellFramed ? "tracking" : "repositioning");

  const badgeLabels = {
    ready: "🟢 Ready",
    tracking: "🟢 Tracking",
    repositioning: "🟡 Repositioning needed",
    recovering: "🟡 Recovering tracking",
    cannot_see: "🔴 Cannot see enough of your body",
  };

  const badgeClass = {
    ready: "assess-camera__badge--ready",
    tracking: "assess-camera__badge--ok",
    repositioning: "assess-camera__badge--warn",
    recovering: "assess-camera__badge--recovering",
    cannot_see: "assess-camera__badge--error",
  };

  return (
    <div className="assess-camera">
      <div className="assess-camera__frame">
        <video
          ref={videoRef}
          className="assess-camera__video"
          playsInline
          muted
          autoPlay
        />
        <canvas ref={canvasRef} className="assess-camera__overlay" />

        {/* Pre-test Body Silhouette Overlay */}
        {outline && !connecting && !error && (
          <div className="assess-camera__silhouette-container" aria-hidden="true">
            <svg
              className="assess-camera__silhouette"
              viewBox="0 0 400 500"
              preserveAspectRatio="xMidYMid meet"
            >
              {outline === "side" ? (
                // Side orientation outline for chair sit-to-stand
                <g stroke="rgba(255, 255, 255, 0.45)" strokeWidth="2.5" fill="none" strokeDasharray="6 6">
                  {/* Head */}
                  <circle cx="200" cy="70" r="32" />
                  {/* Torso */}
                  <path d="M 200 102 L 195 240" />
                  {/* Arms folded */}
                  <path d="M 198 140 L 220 170 L 195 190" />
                  {/* Seated thigh & shin */}
                  <path d="M 195 240 L 270 245 L 270 390 L 295 400" />
                  {/* Chair guide */}
                  <path d="M 155 250 L 250 250 M 165 170 L 165 400 M 235 250 L 235 400" stroke="rgba(119, 181, 142, 0.5)" strokeWidth="3" />
                </g>
              ) : outline === "upper" ? (
                // Upper body outline for shoulder raise
                <g stroke="rgba(255, 255, 255, 0.45)" strokeWidth="2.5" fill="none" strokeDasharray="6 6">
                  {/* Head */}
                  <circle cx="200" cy="85" r="38" />
                  {/* Torso */}
                  <path d="M 140 145 Q 200 135 260 145 L 245 320 L 155 320 Z" />
                  {/* Arms raised outwards guides */}
                  <path d="M 140 145 L 70 170 L 40 230" />
                  <path d="M 260 145 L 330 170 L 360 230" />
                </g>
              ) : (
                // Standard full body front-facing outline
                <g stroke="rgba(255, 255, 255, 0.45)" strokeWidth="2.5" fill="none" strokeDasharray="6 6">
                  {/* Head */}
                  <circle cx="200" cy="70" r="34" />
                  {/* Neck & Shoulders */}
                  <path d="M 145 130 Q 200 120 255 130" />
                  {/* Torso */}
                  <path d="M 150 130 L 160 260 L 240 260 L 250 130" />
                  {/* Arms */}
                  <path d="M 145 130 L 120 230 L 115 310" />
                  <path d="M 255 130 L 280 230 L 285 310" />
                  {/* Legs */}
                  <path d="M 175 260 L 170 380 L 165 460" />
                  <path d="M 225 260 L 230 380 L 235 460" />
                </g>
              )}
            </svg>
            <div className="assess-camera__silhouette-tag">Place your body here</div>
          </div>
        )}

        {/* 3-2-1 Countdown Overlay */}
        {countdown !== null && (
          <div className="assess-camera__countdown-overlay">
            <div className="assess-camera__countdown-number" key={countdown}>
              {countdown}
            </div>
            <div className="assess-camera__countdown-sub">
              {countdown === "Start!" ? "Begin movement now" : "Get ready..."}
            </div>
          </div>
        )}

        {connecting && (
          <div className="assess-camera__cover">
            <span className="assess-camera__spinner" aria-hidden="true" />
            <p>
              {state === ENGINE_STATE.LOADING_MODEL
                ? "Loading the pose model in your browser…"
                : "Starting your camera…"}
            </p>
          </div>
        )}

        {error && (
          <div className="assess-camera__cover assess-camera__cover--error">
            <p>{describePoseError(error.code)}</p>
            <button
              type="button"
              className="assess-btn assess-btn--primary"
              onClick={retry}
            >
              Try again
            </button>
          </div>
        )}

        {!connecting && !error && (
          <div className={`assess-camera__badge ${badgeClass[resolvedStatus] || "assess-camera__badge--ok"}`}>
            {badgeLabels[resolvedStatus] || "Tracking"}
          </div>
        )}

        {!connecting && !error && tracking.fps !== null && (
          <div className="assess-camera__fps">{Math.round(tracking.fps)} fps</div>
        )}
      </div>

      {(guidance || hint) && (
        <p className="assess-camera__hint">
          {guidance || hint}
        </p>
      )}

      <p className="assess-camera__note">
        Everything you see here runs on your own device. No video, image, or frame
        is uploaded or saved — only the final numbers from each check.
      </p>
    </div>
  );
}

