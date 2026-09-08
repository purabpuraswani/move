/**
 * Performing one exercise from the plan, with the camera.
 *
 * This page is the link that was missing. `src/exerciseAssessment/` — the rep
 * counter, the hold timer and their per-exercise configuration — existed but
 * was imported by nothing, so no user could ever reach it and no exercise
 * result was ever produced. `/api/exercise-results` existed with no caller for
 * the same reason. This screen connects them:
 *
 *   plan -> demonstration -> camera -> MoveNet -> signal -> engine ->
 *   structured result -> API -> Progress Agent
 *
 * What runs per frame is deterministic geometry (signals.js) and a threshold
 * state machine (the engines). No model is consulted while the user moves; the
 * agents receive the finished summary, never the frames.
 *
 * Privacy: frames and keypoints stay in this component and are never
 * accumulated. Only the engine's summary — counts and durations — is sent.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import CameraStage from "../assessment/components/CameraStage.jsx";
import { usePoseEngine } from "../assessment/hooks/usePoseEngine.js";
import { EXERCISE_ENGINE_CONFIG, ENGINE_TYPES } from "../exerciseAssessment/config.js";
import {
  createExerciseAssessmentEngine,
  ExerciseNotSupportedError,
} from "../exerciseAssessment/index.js";
import {
  SignalNotAvailableError,
  getSignalExtractor,
} from "../exerciseAssessment/signals.js";
import { HOLD_STATE } from "../exerciseAssessment/holdDurationEngine.js";
import { REP_STATE } from "../assessment/utils/peaks.js";
import { shoulderTorsoRatio } from "../assessment/utils/geometry.js";
import { getMovementDemo } from "../movementDemos/registry.js";
import MovementDemo from "../movementDemos/MovementDemo.jsx";
import { getToken } from "../services/auth";
import { submitExerciseResult } from "../services/exerciseResults";

import "./ExercisePage.css";

const STEP = {
  BRIEF: "brief",
  PREFLIGHT: "preflight",
  RUNNING: "running",
  DONE: "done",
};

const SIGNAL_ORIENTATION = {
  kneeExtensionAngleDeg: "side",
  kneeFlexionAngleDeg: "side",
  hipFlexionAngleDeg: "front",
  hipAbductionAngleDeg: "front",
  hipExtensionAngleDeg: "side",
  elbowFlexionAngleDeg: "side",
  armElevationAngleDeg: "front",
  liftedFootHeightRatio: "front",
};

const SIGNAL_BODY_SCOPE = {
  elbowFlexionAngleDeg: "upper",
  armElevationAngleDeg: "upper",
  kneeExtensionAngleDeg: "full",
  kneeFlexionAngleDeg: "full",
  hipFlexionAngleDeg: "full",
  hipAbductionAngleDeg: "full",
  hipExtensionAngleDeg: "full",
  liftedFootHeightRatio: "full",
};

const VIEW_GUIDANCE = {
  kneeExtensionAngleDeg: "Stand side-on to the camera, whole body in frame.",
  kneeFlexionAngleDeg: "Stand side-on to the camera, whole body in frame.",
  hipFlexionAngleDeg: "Face the camera, whole body in frame.",
  hipAbductionAngleDeg: "Face the camera, whole body in frame.",
  hipExtensionAngleDeg: "Stand side-on to the camera, whole body in frame.",
  elbowFlexionAngleDeg: "Stand side-on to the camera, upper body in frame.",
  armElevationAngleDeg: "Face the camera, upper body in frame.",
  liftedFootHeightRatio: "Face the camera, whole body in frame.",
};

const STABLE_FRAMES_TARGET = 15;
const PREFLIGHT_CONFIDENCE = 0.55;

function evaluatePreflightChecklist(frame, config) {
  if (!frame?.keypoints || !config) {
    return {
      ready: false,
      guidance: "Position yourself in front of the camera.",
      checklist: { visible: false, orientation: false, margins: false, stable: false },
    };
  }

  const signal = config.signal;
  const orientationReq = SIGNAL_ORIENTATION[signal] || "front";
  const scope = SIGNAL_BODY_SCOPE[signal] || "full";
  const kp = frame.keypoints;

  // 1. Joints visibility
  const armJointsLeft = ["left_shoulder", "left_elbow", "left_wrist"];
  const armJointsRight = ["right_shoulder", "right_elbow", "right_wrist"];
  const legJointsLeft = ["left_hip", "left_knee", "left_ankle"];
  const legJointsRight = ["right_hip", "right_knee", "right_ankle"];

  if (scope === "upper") {
    const hasLeftArm = armJointsLeft.every((j) => (kp[j]?.score ?? 0) >= PREFLIGHT_CONFIDENCE);
    const hasRightArm = armJointsRight.every((j) => (kp[j]?.score ?? 0) >= PREFLIGHT_CONFIDENCE);
    const hasShoulders = (kp.left_shoulder?.score ?? 0) >= PREFLIGHT_CONFIDENCE &&
                         (kp.right_shoulder?.score ?? 0) >= PREFLIGHT_CONFIDENCE;
    const isVisible = hasShoulders && (hasLeftArm || hasRightArm);
    if (!isVisible) {
      return {
        ready: false,
        guidance: "Ensure your upper body and arms are clearly in view.",
        checklist: { visible: false, orientation: false, margins: false, stable: false },
      };
    }
  } else {
    const hasShoulder = (kp.left_shoulder?.score ?? 0) >= PREFLIGHT_CONFIDENCE ||
                        (kp.right_shoulder?.score ?? 0) >= PREFLIGHT_CONFIDENCE;
    const hasHips = (kp.left_hip?.score ?? 0) >= PREFLIGHT_CONFIDENCE ||
                    (kp.right_hip?.score ?? 0) >= PREFLIGHT_CONFIDENCE;
    const hasLeftLeg = legJointsLeft.every((j) => (kp[j]?.score ?? 0) >= PREFLIGHT_CONFIDENCE);
    const hasRightLeg = legJointsRight.every((j) => (kp[j]?.score ?? 0) >= PREFLIGHT_CONFIDENCE);
    const isVisible = hasShoulder && hasHips && (hasLeftLeg || hasRightLeg);
    if (!isVisible) {
      return {
        ready: false,
        guidance: "Step back so your full body (head to feet) is in view.",
        checklist: { visible: false, orientation: false, margins: false, stable: false },
      };
    }
  }

  // 2. Margin checks (clipping check)
  const leftAnkle = kp.left_ankle;
  const rightAnkle = kp.right_ankle;
  const leftShoulder = kp.left_shoulder;
  const rightShoulder = kp.right_shoulder;

  if (scope === "full") {
    const maxAnkleY = Math.max(
      leftAnkle?.score >= PREFLIGHT_CONFIDENCE ? leftAnkle.y : 0,
      rightAnkle?.score >= PREFLIGHT_CONFIDENCE ? rightAnkle.y : 0
    );
    if (maxAnkleY > 0.95) {
      return {
        ready: false,
        guidance: "Step back to fit whole body into frame.",
        checklist: { visible: true, orientation: false, margins: false, stable: false },
      };
    }
  }

  const minShoulderY = Math.min(
    leftShoulder?.score >= PREFLIGHT_CONFIDENCE ? leftShoulder.y : 1,
    rightShoulder?.score >= PREFLIGHT_CONFIDENCE ? rightShoulder.y : 1
  );
  if (minShoulderY < 0.05) {
    return {
      ready: false,
      guidance: "Adjust camera tilt so your shoulders are within frame.",
      checklist: { visible: true, orientation: false, margins: false, stable: false },
    };
  }

  // 3. Orientation check (shoulder-to-torso ratio)
  let orientationOk = true;
  let orientationMsg = null;
  const hasTorso = (kp.left_shoulder?.score ?? 0) >= 0.35 &&
                   (kp.right_shoulder?.score ?? 0) >= 0.35 &&
                   (kp.left_hip?.score ?? 0) >= 0.35 &&
                   (kp.right_hip?.score ?? 0) >= 0.35;

  if (hasTorso) {
    const ratio = shoulderTorsoRatio(
      kp.left_shoulder,
      kp.right_shoulder,
      kp.left_hip,
      kp.right_hip
    );

    if (ratio !== null) {
      if (orientationReq === "side" && ratio > 0.42) {
        orientationOk = false;
        orientationMsg = "Turn side-on to the camera.";
      } else if (orientationReq === "front" && ratio < 0.36) {
        orientationOk = false;
        orientationMsg = "Turn to face the camera directly.";
      }
    }
  }

  if (!orientationOk) {
    return {
      ready: false,
      guidance: orientationMsg,
      checklist: { visible: true, orientation: false, margins: true, stable: false },
    };
  }

  return {
    ready: true,
    guidance: "Hold steady...",
    checklist: { visible: true, orientation: true, margins: true, stable: false },
  };
}

function calculatePoseDelta(prevKp, currKp) {
  const joints = ["left_shoulder", "right_shoulder", "left_hip", "right_hip"];
  let totalDelta = 0;
  let count = 0;
  joints.forEach((j) => {
    if (prevKp[j] && currKp[j]) {
      totalDelta += Math.hypot(currKp[j].x - prevKp[j].x, currKp[j].y - prevKp[j].y);
      count += 1;
    }
  });
  return count > 0 ? totalDelta / count : 1;
}

function ExercisePage() {
  const { exerciseId } = useParams();
  const navigate = useNavigate();
  const pose = usePoseEngine();

  const [step, setStep] = useState(STEP.BRIEF);
  const [live, setLive] = useState({ reps: 0, seconds: 0, holdState: null, repState: null, cue: "" });
  const [saveState, setSaveState] = useState("idle");
  const [saveError, setSaveError] = useState(null);
  const [outcome, setOutcome] = useState(null);
  const [preflightReady, setPreflightReady] = useState(false);
  const [preflightState, setPreflightState] = useState({
    guidance: "Position yourself in front of the camera.",
    checklist: { visible: false, orientation: false, margins: false, stable: false },
    stabilityProgress: 0,
  });

  const engineRef = useRef(null);
  const extractorRef = useRef(null);
  const startedAtRef = useRef(null);
  const seenRef = useRef({ total: 0, measured: 0, recovered: 0 });
  const lastValidValueRef = useRef(null);
  const droppedFramesRef = useRef(0);
  const stableFramesRef = useRef(0);
  const prevKeypointsRef = useRef(null);

  const config = EXERCISE_ENGINE_CONFIG[exerciseId];
  const demo = useMemo(() => {
    try {
      return getMovementDemo(`exercise-${exerciseId}`);
    } catch {
      return null;
    }
  }, [exerciseId]);

  const staticUnsupported = useMemo(() => {
    if (!config) {
      return (
        "This exercise is not measured by camera. Follow the demonstration and " +
        "count your own repetitions."
      );
    }

    try {
      getSignalExtractor(config.signal);
      return null;
    } catch (error) {
      if (error instanceof SignalNotAvailableError) {
        return error.message;
      }
      throw error;
    }
  }, [config]);

  const [runtimeUnsupported, setRuntimeUnsupported] = useState(null);
  const unsupported = runtimeUnsupported || staticUnsupported;

  const signedIn = Boolean(getToken());

  useEffect(() => {
    if (!signedIn) navigate("/login", { replace: true });
  }, [signedIn, navigate]);

  useEffect(() => {
    if (config && !unsupported) {
      try {
        extractorRef.current = getSignalExtractor(config.signal);
      } catch {
        extractorRef.current = null;
      }
    } else {
      extractorRef.current = null;
    }
  }, [config, unsupported]);

  const onFrame = useCallback(
    (frame) => {
      const engine = engineRef.current;
      const extract = extractorRef.current;

      if (!engine || !extract) return;

      seenRef.current.total += 1;
      let value = extract(frame);
      if (value === null) {
        if (lastValidValueRef.current !== null && droppedFramesRef.current < 3) {
          droppedFramesRef.current += 1;
          value = lastValidValueRef.current;
          seenRef.current.recovered = (seenRef.current.recovered || 0) + 1;
        } else {
          droppedFramesRef.current += 1;
          return;
        }
      } else {
        droppedFramesRef.current = 0;
        lastValidValueRef.current = value;
        seenRef.current.measured += 1;
      }

      const pushed = engine.push(value, frame.timestamp);
      const summary = engine.summary();

      if (config.engineType === ENGINE_TYPES.REP_COUNTING) {
        let cue = "Maintain smooth, controlled pacing.";
        if (pushed?.state === REP_STATE.ACTIVE) {
          cue = "Reaching top range — good control!";
        } else if (pushed?.event === "completed") {
          cue = "Repetition counted! Return to start.";
        }
        setLive({
          reps: summary.repetitions,
          seconds: summary.durationSeconds ?? 0,
          holdState: null,
          repState: pushed?.state ?? null,
          cue,
        });
      } else {
        let cue = "Find and settle into the hold position.";
        if (pushed?.state === HOLD_STATE.HOLDING) {
          cue = "Holding form — keep breathing steadily!";
        } else if (pushed?.state === HOLD_STATE.STABILIZING) {
          cue = "Getting steady — hold still...";
        }
        setLive({
          reps: 0,
          seconds: summary.durationSeconds ?? 0,
          holdState: pushed?.state ?? null,
          repState: null,
          cue,
        });
      }
    },
    [config],
  );

  useEffect(() => {
    if (step !== STEP.RUNNING) return undefined;
    return pose.subscribe(onFrame);
  }, [step, pose, onFrame]);

  useEffect(() => {
    if (step !== STEP.PREFLIGHT || !config) return undefined;

    return pose.subscribe((frame) => {
      const evaluation = evaluatePreflightChecklist(frame, config);

      if (!evaluation.ready) {
        stableFramesRef.current = 0;
        prevKeypointsRef.current = frame.keypoints;
        setPreflightReady(false);
        setPreflightState({
          guidance: evaluation.guidance,
          checklist: evaluation.checklist,
          stabilityProgress: 0,
        });
        return;
      }

      // Check keypoint movement stability
      const prev = prevKeypointsRef.current;
      let delta = 0;
      if (prev) {
        delta = calculatePoseDelta(prev, frame.keypoints);
      }
      prevKeypointsRef.current = frame.keypoints;

      if (delta < 0.04) {
        stableFramesRef.current += 1;
      } else {
        stableFramesRef.current = Math.max(0, stableFramesRef.current - 2);
      }

      const progress = Math.min(100, Math.round((stableFramesRef.current / STABLE_FRAMES_TARGET) * 100));
      const isReady = stableFramesRef.current >= STABLE_FRAMES_TARGET;

      setPreflightReady(isReady);
      setPreflightState({
        guidance: isReady ? "Ready! Click Begin recording." : `Hold steady... (${progress}%)`,
        checklist: {
          ...evaluation.checklist,
          stable: isReady,
        },
        stabilityProgress: progress,
      });
    });
  }, [step, config, pose]);

  const openPreflight = useCallback(() => {
    setPreflightReady(false);
    stableFramesRef.current = 0;
    prevKeypointsRef.current = null;
    setPreflightState({
      guidance: "Position yourself in front of the camera.",
      checklist: { visible: false, orientation: false, margins: false, stable: false },
      stabilityProgress: 0,
    });
    setStep(STEP.PREFLIGHT);
    pose.connect();
    pose.startLoop();
  }, [pose]);

  const start = useCallback(() => {
    if (!preflightReady) return;
    try {
      engineRef.current = createExerciseAssessmentEngine(exerciseId);
    } catch (error) {
      if (error instanceof ExerciseNotSupportedError) {
        setRuntimeUnsupported(error.message);
        return;
      }
      throw error;
    }

    seenRef.current = { total: 0, measured: 0, recovered: 0 };
    lastValidValueRef.current = null;
    droppedFramesRef.current = 0;
    startedAtRef.current = new Date().toISOString();

    setLive({ reps: 0, seconds: 0, holdState: null, repState: null, cue: "Get started" });
    setStep(STEP.RUNNING);
  }, [exerciseId, preflightReady]);

  const finish = useCallback(async () => {
    pose.stopLoop();
    pose.release();

    const engine = engineRef.current;
    const summary = engine ? engine.summary() : null;
    const seen = seenRef.current;

    const effectiveMeasured = seen.measured + (seen.recovered || 0);
    const usable = seen.total > 0 && effectiveMeasured / seen.total >= 0.4;
    const completedAt = new Date().toISOString();

    let status;
    let measurements = null;
    let errors = null;

    if (!usable) {
      status = "invalid";
      errors = ["camera_could_not_measure"];
    } else {
      measurements = {};

      if (config.engineType === ENGINE_TYPES.REP_COUNTING) {
        measurements.repetitions = summary.repetitions;

        if (summary.durationSeconds !== null) {
          measurements.durationSeconds = summary.durationSeconds;
        }

        if (summary.completion !== null) {
          measurements.completion = summary.completion;
        }

        status =
          summary.completion !== null && summary.completion >= 1
            ? "completed"
            : "incomplete";
      } else {
        measurements.durationSeconds = summary.durationSeconds;

        if (summary.completion !== null) {
          measurements.completion = summary.completion;
        }

        status =
          summary.completion !== null && summary.completion >= 1
            ? "completed"
            : "incomplete";
      }
    }

    setOutcome({ status, measurements, usable });
    setStep(STEP.DONE);
    setSaveState("saving");
    setSaveError(null);

    try {
      await submitExerciseResult({
        exerciseId,
        status,
        startedAt: startedAtRef.current,
        completedAt,
        measurements,
        errors,
      });

      setSaveState("saved");
    } catch (error) {
      setSaveError(error.message);
      setSaveState("failed");
    }
  }, [pose, config, exerciseId]);

  const viewHint = config ? VIEW_GUIDANCE[config.signal] : null;

  return (
    <div className="exercise-page">
      <main className="exercise-main">
        <button
          type="button"
          className="exercise-back"
          onClick={() => navigate("/plan")}
        >
          ← Back to your plan
        </button>

        <h1 className="exercise-title">{demo?.title || exerciseId}</h1>

        {step === STEP.BRIEF ? (
          <>
            {demo ? <MovementDemo demo={demo} /> : null}

            {unsupported ? (
              <div className="exercise-note">
                <h2 className="exercise-note-title">Not measured by camera</h2>
                <p>{unsupported}</p>
                <p className="exercise-note-quiet">
                  This is a limit of what the camera can see, not a limit on
                  the exercise. Follow the demonstration as shown.
                </p>
              </div>
            ) : (
              <>
                {viewHint ? (
                  <div className="exercise-setup">
                    <h2 className="exercise-setup-title">Camera setup</h2>
                    <p>{viewHint}</p>
                    <p className="exercise-setup-quiet">
                      Your camera stays on this device. Nothing from the video
                      is uploaded — only how many repetitions you did and how
                      long they took.
                    </p>
                  </div>
                ) : null}

                <button type="button" className="exercise-start" onClick={openPreflight}>
                  Check camera setup
                </button>
              </>
            )}
          </>
        ) : null}

        {step === STEP.PREFLIGHT ? (
          <>
            <CameraStage engine={pose} hint={viewHint} />

            <div className="exercise-setup">
              <h2 className="exercise-setup-title">Camera preflight check</h2>

              <div
                className={`exercise-guidance-banner ${
                  preflightReady ? "exercise-guidance-banner--ready" : ""
                }`}
              >
                <span className="exercise-guidance-icon">{preflightReady ? "✓" : "ℹ"}</span>
                <span className="exercise-guidance-text">{preflightState.guidance}</span>
              </div>

              <div className="exercise-checklist">
                <div className={`exercise-check-item ${preflightState.checklist.visible ? "is-passed" : ""}`}>
                  <span className="exercise-check-status">{preflightState.checklist.visible ? "✓" : "○"}</span>
                  <span>Required joints visible (confidence &gt; 0.55)</span>
                </div>
                <div className={`exercise-check-item ${preflightState.checklist.margins ? "is-passed" : ""}`}>
                  <span className="exercise-check-status">{preflightState.checklist.margins ? "✓" : "○"}</span>
                  <span>Framing boundaries (not cut off at edges)</span>
                </div>
                <div className={`exercise-check-item ${preflightState.checklist.orientation ? "is-passed" : ""}`}>
                  <span className="exercise-check-status">{preflightState.checklist.orientation ? "✓" : "○"}</span>
                  <span>
                    Orientation: {SIGNAL_ORIENTATION[config.signal] === "side" ? "Side-on to camera" : "Facing camera directly"}
                  </span>
                </div>
                <div className={`exercise-check-item ${preflightState.checklist.stable ? "is-passed" : ""}`}>
                  <span className="exercise-check-status">{preflightState.checklist.stable ? "✓" : "○"}</span>
                  <span>Hold position steady (~1.5s): {preflightState.stabilityProgress}%</span>
                </div>
              </div>

              <div className="exercise-stability-track">
                <div
                  className="exercise-stability-fill"
                  style={{ width: `${preflightState.stabilityProgress}%` }}
                />
              </div>

              <div className="exercise-actions">
                <button
                  type="button"
                  className="exercise-start"
                  onClick={start}
                  disabled={!preflightReady}
                >
                  Begin recording
                </button>
                <button
                  type="button"
                  className="exercise-start exercise-start--quiet"
                  onClick={() => {
                    pose.stopLoop();
                    pose.release();
                    setStep(STEP.BRIEF);
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          </>
        ) : null}

        {step === STEP.RUNNING ? (
          <>
            <CameraStage engine={pose} hint={viewHint} />

            <div className="exercise-live">
              {config.engineType === ENGINE_TYPES.REP_COUNTING ? (
                <div className="exercise-metric">
                  <span className="exercise-metric-value">{live.reps}</span>
                  <span className="exercise-metric-label">
                    of {config.targetRepetitions} repetitions
                  </span>
                  <div className="exercise-phase-badge">
                    Phase: {live.repState === REP_STATE.ACTIVE ? "Extending / Active" : "Lowering / Reset"}
                  </div>
                </div>
              ) : (
                <div className="exercise-metric">
                  <span className="exercise-metric-value">
                    {Math.round(live.seconds)}s
                  </span>
                  <span className="exercise-metric-label">
                    {live.holdState === HOLD_STATE.HOLDING
                      ? "holding form"
                      : live.holdState === HOLD_STATE.STABILIZING
                        ? "getting steady"
                        : "find the position"}
                  </span>
                  <div className="exercise-phase-badge">
                    Phase:{" "}
                    {live.holdState === HOLD_STATE.HOLDING
                      ? "Holding Form"
                      : live.holdState === HOLD_STATE.STABILIZING
                        ? "Stabilizing"
                        : "Target Position"}
                  </div>
                </div>
              )}

              {live.cue ? (
                <div className="exercise-cue-banner">
                  <span className="exercise-cue-label">Form Cue:</span> {live.cue}
                </div>
              ) : null}
            </div>

            <button type="button" className="exercise-start" onClick={finish}>
              I have finished
            </button>
          </>
        ) : null}

        {step === STEP.DONE && outcome ? (
          <div className="exercise-result">
            <h2 className="exercise-result-title">
              {outcome.usable ? "Session Recorded" : "Could not measure this session"}
            </h2>

            {outcome.usable ? (
              <>
                <ul className="exercise-result-list">
                  {outcome.measurements?.repetitions !== undefined ? (
                    <li>
                      <strong>Repetitions:</strong> {outcome.measurements.repetitions}
                    </li>
                  ) : null}
                  {outcome.measurements?.durationSeconds !== undefined &&
                  outcome.measurements?.durationSeconds !== null ? (
                    <li>
                      <strong>Hold duration:</strong> {outcome.measurements.durationSeconds}s
                    </li>
                  ) : null}
                  {outcome.measurements?.completion !== undefined &&
                  outcome.measurements?.completion !== null ? (
                    <li>
                      <strong>Completion:</strong> {Math.round(outcome.measurements.completion * 100)}%
                    </li>
                  ) : null}
                  <li>
                    <strong>Status:</strong> {outcome.status === "completed" ? "Target reached" : "Completed partially"}
                  </li>
                </ul>
                <div className="exercise-adaptation-note">
                  <span className="exercise-adaptation-icon">ℹ</span>
                  <span>
                    Your movement measurements have been saved to your activity history.
                    The Progress Agent will analyze this data during your next plan adaptation
                    to adjust intensity and exercises safely.
                  </span>
                </div>
              </>
            ) : (
              <p className="exercise-result-quiet">
                The camera could not see enough of you to measure this
                reliably, so nothing was scored. That is a recording problem,
                not a reflection of how you did.
              </p>
            )}

            {saveState === "saving" ? <p className="exercise-status-text">Saving results…</p> : null}
            {saveState === "saved" ? (
              <p className="exercise-saved">
                ✓ Saved to your profile. This will be factored into your next plan review.
              </p>
            ) : null}
            {saveState === "failed" ? (
              <p className="exercise-error">{saveError}</p>
            ) : null}

            <div className="exercise-actions">
              <button
                type="button"
                className="exercise-start"
                onClick={() => navigate("/plan")}
              >
                Back to your plan
              </button>
              <button
                type="button"
                className="exercise-start exercise-start--quiet"
                onClick={() => navigate("/progress")}
              >
                See your progress
              </button>
            </div>
          </div>
        ) : null}
      </main>
    </div>
  );
}

export default ExercisePage;
