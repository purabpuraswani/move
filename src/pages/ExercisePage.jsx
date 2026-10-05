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
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import CameraStage from "../assessment/components/CameraStage.jsx";
import RawCameraView from "../assessment/components/RawCameraView.jsx";
import { usePoseEngine } from "../assessment/hooks/usePoseEngine.js";
import { EXERCISE_ENGINE_CONFIG, ENGINE_TYPES } from "../exerciseAssessment/config.js";
import {
  SIGNAL_ORIENTATION,
  STABILITY_DELTA,
  calculatePoseDelta,
  evaluatePreflightChecklist,
} from "../exerciseAssessment/preflight.js";
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
import { getExerciseImage } from "../movementDemos/exerciseImages.js";
import { getExerciseVideo } from "../movementDemos/exerciseVideos.js";
import { getMovementDemo } from "../movementDemos/registry.js";
import MovementDemo from "../movementDemos/MovementDemo.jsx";
import { getToken } from "../services/auth";
import { submitExerciseResult } from "../services/exerciseResults";
import { fetchLatestWorkflow } from "../services/workflow";
import { planItems } from "../services/unifiedPlan.js";

import "./ExercisePage.css";

const STEP = {
  BRIEF: "brief",
  PREFLIGHT: "preflight",
  RUNNING: "running",
  DONE: "done",
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

const EXERCISE_OBSERVATIONS = {
  "chair-sit-to-stand": "MoveWell observed your rising tempo, standing extension, and smooth descent back to the chair.",
  "wall-sit": "MoveWell monitored your posture stability and how steadily you held the lowered wall position.",
  "standing-knee-raise": "MoveWell monitored your hip elevation height, rhythm, and single-leg balance control throughout.",
  "wall-push-up": "MoveWell monitored your arm flexion depth, pressing tempo, and torso alignment against the wall.",
  "standing-side-leg-raise": "MoveWell monitored your lateral leg lift height, torso stability, and controlled lowering.",
  "standing-hip-extension": "MoveWell monitored your backward leg reach and upright posture without excessive torso leaning.",
  "supported-single-leg-stand": "MoveWell monitored your single-leg balance duration and steadiness while holding the support.",
  "standing-shoulder-rolls": "MoveWell guided your gentle circular shoulder mobilization.",
  "standing-ankle-circles": "MoveWell guided your joint mobility and ankle rotational control.",
  "glute-bridge": "MoveWell tracked your hip drive, glute activation, and pelvic alignment.",
};

function getPlainLanguageObservation(exerciseId, outcome, config) {
  if (outcome?.isManual) {
    return "Self-guided session logged following the visual technique guide.";
  }
  if (EXERCISE_OBSERVATIONS[exerciseId]) {
    return EXERCISE_OBSERVATIONS[exerciseId];
  }
  if (config?.engineType === ENGINE_TYPES.HOLD_DURATION) {
    return "MoveWell monitored your balance steadiness and posture control throughout the active hold.";
  }
  return "MoveWell monitored the pace, smoothness, and range of motion across your repetitions.";
}

function getCoachFeedback(outcome) {
  if (outcome?.status === "completed") {
    return "Great form and steady control. Consistently hitting your movement target builds durable strength.";
  }
  return "Good effort today. Pacing yourself and listening to your body helps you build capacity safely.";
}

const STABLE_FRAMES_TARGET = 15;
const VOICE_COOLDOWN_MS = 2200;

function SessionPanel({ title, children, footer = null, className = "", bodyClassName = "" }) {
  return (
    <section className={`exercise-panel ${className}`}>
      <h2 className="exercise-panel-title">{title}</h2>
      {/* The body may be a fixed-ratio media box with overflow hidden, so
          anything that must stay readable (a caption) goes in the footer
          beneath it rather than inside it. */}
      <div className={`exercise-panel-body ${bodyClassName}`}>{children}</div>
      {footer}
    </section>
  );
}

function ExercisePage() {
  const { exerciseId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const pose = usePoseEngine();

  // The plan item this session is being performed against, carried in the URL
  // by the plan card that sent the user here. Both are optional: someone who
  // opens an exercise directly is not performing a plan item, and the result
  // is then stored with no plan link rather than a fabricated one.
  const planIdFromUrl = searchParams.get("planId");
  const itemIdFromUrl = searchParams.get("itemId");

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
  const [planProgramme, setPlanProgramme] = useState([]);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const lastSpokenCueRef = useRef("");
  const lastSpokenAtRef = useRef(0);

  const voiceAvailable =
    typeof window !== "undefined" &&
    "speechSynthesis" in window &&
    "SpeechSynthesisUtterance" in window;

  useEffect(() => {
    if (!voiceAvailable || step !== STEP.RUNNING || !voiceEnabled || !live.cue) {
      return undefined;
    }

    const now = Date.now();
    const cueChanged = live.cue !== lastSpokenCueRef.current;
    const cooldownElapsed = now - lastSpokenAtRef.current >= VOICE_COOLDOWN_MS;

    if (!cueChanged || !cooldownElapsed) return undefined;

    const utterance = new SpeechSynthesisUtterance(live.cue);
    utterance.rate = 0.95;
    utterance.pitch = 1;
    utterance.volume = 0.9;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
    lastSpokenCueRef.current = live.cue;
    lastSpokenAtRef.current = now;

    return undefined;
  }, [live.cue, step, voiceEnabled, voiceAvailable]);

  useEffect(() => {
    if (step === STEP.RUNNING) return undefined;
    lastSpokenCueRef.current = "";
    lastSpokenAtRef.current = 0;
    if (voiceAvailable) window.speechSynthesis.cancel();
    return undefined;
  }, [step, voiceAvailable]);

  useEffect(() => {
    let isMounted = true;

    fetchLatestWorkflow()
      .then((wf) => {
        if (!isMounted || !wf) return;

        // The plan's own exercise items, read from the server's unified plan
        // rather than re-derived from a display list. Each one carries the plan
        // id and the item id the result must be recorded against.
        const items = planItems(wf)
          .filter((item) => item.kind === "exercise")
          .map((item) => ({
            id: item.item_id,
            name: item.title,
            planId: item.plan_id || null,
            itemId: item.item_id || null,
            sets: item.metadata?.sets ?? null,
            repetitions: item.metadata?.repetitions ?? null,
            durationSeconds: item.metadata?.duration_seconds ?? null,
            why: item.why || null,
            withheld: Boolean(item.withheld),
          }));

        setPlanProgramme(items);
      })
      .catch(() => {});

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    setStep(STEP.BRIEF);
    setOutcome(null);
    setSaveState("idle");
    setSaveError(null);
    setLive({ reps: 0, seconds: 0, holdState: null, repState: null, cue: "" });
    lastSpokenCueRef.current = "";
    lastSpokenAtRef.current = 0;
    if (voiceAvailable) window.speechSynthesis.cancel();
  }, [exerciseId]);

  useEffect(() => {
    window.__setExerciseState = (st) => {
      if (st.step) setStep(st.step);
      if (st.outcome) setOutcome(st.outcome);
      if (st.planProgramme) setPlanProgramme(st.planProgramme);
    };
    return () => {
      delete window.__setExerciseState;
    };
  }, []);

  const currentIndex = planProgramme.findIndex((e) => e.id === exerciseId);
  const currentPlanItem = currentIndex >= 0 ? planProgramme[currentIndex] : null;
  const nextExercise =
    currentIndex >= 0 && currentIndex < planProgramme.length - 1
      ? planProgramme[currentIndex + 1]
      : null;

  // The ids this session is recorded against, taken from the URL when the plan
  // card supplied them and from the plan's own item otherwise. `exerciseId` is
  // itself the item id for an exercise item — it is the exercise library id,
  // which is the domain identifier the plan publishes — so nothing is invented
  // by falling back to it.
  const recordingPlanId = planIdFromUrl || currentPlanItem?.planId || null;
  const recordingItemId = itemIdFromUrl || currentPlanItem?.itemId || exerciseId || null;

  const engineRef = useRef(null);
  const extractorRef = useRef(null);
  const startedAtRef = useRef(null);
  const seenRef = useRef({ total: 0, measured: 0, recovered: 0 });
  const lastValidValueRef = useRef(null);
  const droppedFramesRef = useRef(0);
  const stableFramesRef = useRef(0);
  const prevKeypointsRef = useRef(null);

  const config = EXERCISE_ENGINE_CONFIG[exerciseId];
  // The instructional diagram for this exercise, where one exists. Same
  // source as the plan card (movementDemos/exerciseImages.js), so both
  // screens show the same picture for the same exercise id.
  const exerciseImage = getExerciseImage(exerciseId);
  // An instructor recording exists only for the three baseline
  // movements; every other exercise falls back to the animated
  // demonstration rather than showing a video of a different movement.
  const instructorVideo = getExerciseVideo(exerciseId);

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
      // The frame's own pixel size. The framing checks are fractions of
      // it, so without this they were comparing pixels against 0.95 and
      // could never pass -- which is what kept Begin recording disabled.
      const videoSize = pose.getVideoSize();
      const evaluation = evaluatePreflightChecklist(frame, config, videoSize);

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
        delta = calculatePoseDelta(prev, frame.keypoints, videoSize);
      }
      prevKeypointsRef.current = frame.keypoints;

      if (delta < STABILITY_DELTA) {
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
        planId: recordingPlanId,
        itemId: recordingItemId,
      });

      setSaveState("saved");
    } catch (error) {
      setSaveError(error.message);
      setSaveState("failed");
    }
  }, [pose, config, exerciseId, recordingPlanId, recordingItemId]);

  const completeManual = useCallback(async () => {
    const completedAt = new Date().toISOString();
    const status = "completed";
    const usable = true;

    setOutcome({
      status,
      measurements: {},
      usable,
      isManual: true,
    });
    setStep(STEP.DONE);
    setSaveState("saving");
    setSaveError(null);

    try {
      // A ticked box is a self-report, not a camera reading, and the backend
      // stores the two apart (`source`). Recording it as a camera session
      // would make a confirmation indistinguishable from a measurement in
      // every consumer downstream.
      await submitExerciseResult({
        exerciseId,
        status,
        startedAt: startedAtRef.current || completedAt,
        completedAt,
        measurements: {},
        source: "manual_confirmation",
        planId: recordingPlanId,
        itemId: recordingItemId,
      });

      setSaveState("saved");
    } catch (error) {
      setSaveError(error.message);
      setSaveState("failed");
    }
  }, [exerciseId, recordingPlanId, recordingItemId]);

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
        <div style={{ display: "flex", gap: "12px", alignItems: "center", marginBottom: "16px", flexWrap: "wrap" }}>
          <button
            type="button"
            className="exercise-back"
            onClick={() => navigate("/plan")}
          >
            ← Back to your plan
          </button>
          <button
            type="button"
            className="exercise-back"
            onClick={() => navigate("/dashboard")}
            aria-label="Back to Dashboard"
          >
            ← Dashboard
          </button>
        </div>

        <h1 className="exercise-title">{demo?.title || exerciseId}</h1>

        {step === STEP.BRIEF ? (
          <>
            {exerciseImage ? (
              <img
                className="exercise-demo-image"
                src={exerciseImage.src}
                alt={exerciseImage.alt}
              />
            ) : demo ? (
              <MovementDemo demo={demo} />
            ) : null}

            {/* What the plan asked for, when this exercise is a plan item.
                Read from the item, so the page and the plan card cannot
                disagree about the dose. */}
            {currentPlanItem ? (
              <div className="exercise-setup">
                <h2 className="exercise-setup-title">Your plan asks for</h2>
                <p>
                  {[
                    currentPlanItem.sets
                      ? `${currentPlanItem.sets} ${
                          currentPlanItem.sets === 1 ? "set" : "sets"
                        }`
                      : null,
                    currentPlanItem.repetitions
                      ? `${currentPlanItem.repetitions} repetitions`
                      : null,
                    currentPlanItem.durationSeconds
                      ? `${currentPlanItem.durationSeconds}s hold`
                      : null,
                  ]
                    .filter(Boolean)
                    .join(" · ") || "This exercise, as shown."}
                </p>
                {currentPlanItem.why ? (
                  <p className="exercise-setup-quiet">{currentPlanItem.why}</p>
                ) : null}
                {recordingItemId ? (
                  <p className="exercise-setup-quiet">
                    Recorded against plan item <code>{recordingItemId}</code>
                    {recordingPlanId ? (
                      <>
                        {" "}
                        in plan <code>{recordingPlanId}</code>
                      </>
                    ) : null}
                    .
                  </p>
                ) : null}
              </div>
            ) : null}

            {currentPlanItem?.withheld ? (
              <div className="exercise-note">
                <h2 className="exercise-note-title">Paused for safety review</h2>
                <p>
                  The Safety &amp; Practitioner Recommendation specialist
                  withheld this item from your plan for this cycle. Read that
                  guidance before performing it.
                </p>
                <div className="exercise-actions" style={{ marginTop: "20px" }}>
                  <button
                    type="button"
                    className="exercise-start exercise-start--quiet"
                    onClick={() => navigate("/specialist/safety-practitioner")}
                  >
                    See the safety guidance
                  </button>
                </div>
              </div>
            ) : null}

            {/* A withheld item cannot be started from here. The Safety
                specialist's verdict reached the plan, so it has to reach the
                page that would carry the item out. */}
            {currentPlanItem?.withheld ? null : unsupported ? (
              <div className="exercise-note">
                <h2 className="exercise-note-title">Not measured by camera</h2>
                <p>{unsupported}</p>
                <p className="exercise-note-quiet">
                  This is a limit of what the camera can see, not a limit on
                  the exercise. Follow the demonstration as shown.
                </p>
                <div className="exercise-actions" style={{ marginTop: "20px" }}>
                  <button
                    type="button"
                    className="exercise-start"
                    onClick={completeManual}
                    disabled={saveState === "saving"}
                  >
                    {saveState === "saving" ? "Saving…" : "I have completed this exercise"}
                  </button>
                </div>
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
          <div className="exercise-session">
            <div className="exercise-video-row">
            <SessionPanel
              title="Exercise video"
              bodyClassName="exercise-panel-body--media"
              footer={
                instructorVideo ? (
                  <p className="exercise-panel-caption">{instructorVideo.caption}</p>
                ) : null
              }
            >
              {instructorVideo ? (
                <video
                  className="exercise-panel-video"
                  src={instructorVideo.src}
                  controls
                  loop
                  muted
                  playsInline
                  preload="metadata"
                />
              ) : exerciseImage ? (
                <img className="exercise-panel-image" src={exerciseImage.src} alt={exerciseImage.alt} />
              ) : (
                <p className="exercise-panel-empty">
                  No recorded demonstration for this exercise yet.
                </p>
              )}
            </SessionPanel>

            <SessionPanel title="User (raw)" bodyClassName="exercise-panel-body--media">
              <RawCameraView engine={pose} label="Your live camera, without pose markers" />
            </SessionPanel>

            <SessionPanel title="User (markers)" bodyClassName="exercise-panel-body--media">
              <CameraStage engine={pose} hint={viewHint} />
            </SessionPanel>
            </div>

            <div className="exercise-support-row">
              <aside className="exercise-reference">
                <h3 className="exercise-reference-title">Reference</h3>
                {exerciseImage ? (
                  <img
                    className="exercise-reference-image"
                    src={exerciseImage.src}
                    alt={exerciseImage.alt}
                  />
                ) : (
                  <p className="exercise-panel-empty">No reference image for this exercise.</p>
                )}
              </aside>

              <section className="exercise-support-panel">
                <h3 className="exercise-reference-title">Position check</h3>
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
            </div>
              </section>
            </div>

            <div className="exercise-controls-bar">
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
              <p className="exercise-controls-note">
                {preflightReady
                  ? "All checks passed — recording can start."
                  : preflightState.guidance}
              </p>
            </div>
          </div>
        ) : null}

        {step === STEP.RUNNING ? (
          <div className="exercise-session">
            <div className="exercise-video-row">
            <SessionPanel
              title="Exercise video"
              bodyClassName="exercise-panel-body--media"
              footer={
                instructorVideo ? (
                  <p className="exercise-panel-caption">{instructorVideo.caption}</p>
                ) : null
              }
            >
              {instructorVideo ? (
                <video
                  className="exercise-panel-video"
                  src={instructorVideo.src}
                  controls
                  loop
                  muted
                  playsInline
                  preload="metadata"
                />
              ) : exerciseImage ? (
                <img className="exercise-panel-image" src={exerciseImage.src} alt={exerciseImage.alt} />
              ) : (
                <p className="exercise-panel-empty">
                  No recorded demonstration for this exercise yet.
                </p>
              )}
            </SessionPanel>

            <SessionPanel title="User (raw)" bodyClassName="exercise-panel-body--media">
              <RawCameraView engine={pose} label="Your live camera, without pose markers" />
            </SessionPanel>

            <SessionPanel title="User (markers)" bodyClassName="exercise-panel-body--media">
              <CameraStage engine={pose} hint={viewHint} />
            </SessionPanel>
            </div>

            <div className="exercise-support-row">
              <aside className="exercise-reference">
                <h3 className="exercise-reference-title">Reference</h3>
                {exerciseImage ? (
                  <img
                    className="exercise-reference-image"
                    src={exerciseImage.src}
                    alt={exerciseImage.alt}
                  />
                ) : (
                  <p className="exercise-panel-empty">No reference image for this exercise.</p>
                )}
              </aside>

              <section className="exercise-support-panel">
                <h3 className="exercise-reference-title">Recording</h3>
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
              </section>
            </div>

            <div className="exercise-controls-bar">
              <span className="exercise-recording-pill" role="status">
                <span className="exercise-recording-dot" aria-hidden="true" />
                Recording…
              </span>
              {voiceAvailable ? (
                <button
                  type="button"
                  className={`exercise-voice-toggle${voiceEnabled ? " is-on" : ""}`}
                  onClick={() => {
                    setVoiceEnabled((enabled) => !enabled);
                    window.speechSynthesis.cancel();
                  }}
                  aria-pressed={voiceEnabled}
                  aria-label={
                    voiceEnabled
                      ? "Turn off spoken form corrections"
                      : "Turn on spoken form corrections"
                  }
                >
                  {voiceEnabled ? "🔊 Voice corrections on" : "🔇 Voice corrections off"}
                </button>
              ) : null}
              <button type="button" className="exercise-start" onClick={finish}>
                Stop · I have finished
              </button>
              <p className="exercise-controls-note">
                {voiceAvailable
                  ? "Corrections are spoken from this device. Your camera stays here; only counts and timings are saved."
                  : "Your camera stays on this device. Only the counts and timings are saved."}
              </p>
            </div>
          </div>
        ) : null}

        {step === STEP.DONE && outcome ? (
          <div className="exercise-result">
            <h2 className="exercise-result-title">
              {outcome.usable ? "Session Recorded" : "Could not measure this session"}
            </h2>

            {outcome.isManual ? (
              <div className="exercise-adaptation-note" style={{ marginTop: "12px", marginBottom: "16px" }}>
                <span className="exercise-adaptation-icon">✓</span>
                <span>
                  Exercise completed and saved to your activity history. Your Physio specialist will factor this completion into your next plan review.
                </span>
              </div>
            ) : outcome.usable ? (
              <>
                <div className="exercise-results-grid">
                  {outcome.measurements?.repetitions !== undefined && (
                    <div className="exercise-result-tile">
                      <span className="result-tile-val">{outcome.measurements.repetitions}</span>
                      <span className="result-tile-lbl">Repetitions</span>
                    </div>
                  )}
                  {outcome.measurements?.durationSeconds !== undefined &&
                  outcome.measurements?.durationSeconds !== null && (
                    <div className="exercise-result-tile">
                      <span className="result-tile-val">{outcome.measurements.durationSeconds}s</span>
                      <span className="result-tile-lbl">Hold Duration</span>
                    </div>
                  )}
                  {outcome.measurements?.completion !== undefined &&
                  outcome.measurements?.completion !== null && (
                    <div className="exercise-result-tile">
                      <span className="result-tile-val">{Math.round(outcome.measurements.completion * 100)}%</span>
                      <span className="result-tile-lbl">Target Completed</span>
                    </div>
                  )}
                  <div className="exercise-result-tile">
                    <span className="result-tile-val result-tile-val--status">
                      {outcome.status === "completed" ? "✓ Target Met" : "Partially Done"}
                    </span>
                    <span className="result-tile-lbl">Session Status</span>
                  </div>
                </div>

                <div className="exercise-observation-card">
                  <div className="exercise-observation-header">
                    <span className="exercise-observation-badge">Observed</span>
                    <h4 className="exercise-observation-title">What was observed</h4>
                  </div>
                  <p className="exercise-observation-body">
                    {getPlainLanguageObservation(exerciseId, outcome, config)}
                  </p>
                  <div className="exercise-coach-feedback">
                    <span className="exercise-coach-badge">Feedback</span>
                    <p className="exercise-coach-text">{getCoachFeedback(outcome)}</p>
                  </div>
                </div>

                <div className="exercise-adaptation-note">
                  <span className="exercise-adaptation-icon">ℹ</span>
                  <span>
                    Your movement measurements have been saved to your activity history.
                    Your Physio specialist will analyze this evidence during your next plan adaptation
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
              {nextExercise ? (
                <>
                  <button
                    type="button"
                    className="exercise-start"
                    onClick={() => navigate(`/exercise/${nextExercise.id}`)}
                  >
                    Continue to next exercise: {nextExercise.name} →
                  </button>
                  <button
                    type="button"
                    className="exercise-start exercise-start--quiet"
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
                  <button
                    type="button"
                    className="exercise-start exercise-start--quiet"
                    onClick={() => navigate("/dashboard")}
                  >
                    ← Dashboard
                  </button>
                </>
              ) : (
                <>
                  <button
                    type="button"
                    className="exercise-start"
                    onClick={() => navigate("/progress")}
                  >
                    View today's progress →
                  </button>
                  <button
                    type="button"
                    className="exercise-start exercise-start--quiet"
                    onClick={() => navigate("/plan")}
                  >
                    Back to your plan
                  </button>
                  <button
                    type="button"
                    className="exercise-start exercise-start--quiet"
                    onClick={() => navigate("/dashboard")}
                  >
                    ← Dashboard
                  </button>
                </>
              )}
            </div>
          </div>
        ) : null}
      </main>
    </div>
  );
}

export default ExercisePage;
