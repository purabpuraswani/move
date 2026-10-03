/**
 * Reusable Assessment Flow component.
 *
 * Implements the standard 6-phase lifecycle required across all 3 baseline tests:
 * Instructions -> Position Yourself -> Live Setup Check -> Ready -> 3s Countdown -> Assessment -> Result.
 *
 * Ensures no counting occurs while the user is positioning themselves, provides
 * actionable human-friendly guidance, and supports clean retry resets.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import MovementDemo from "../../movementDemos/MovementDemo.jsx";
import DemonstrationVideo from "./DemonstrationVideo.jsx";
import { getExerciseVideo } from "../../movementDemos/exerciseVideos.js";
import { getMovementDemo } from "../../movementDemos/registry.js";
import { evaluatePositioning, STABLE_PREFLIGHT_FRAMES } from "../utils/positioning.js";
import { getActionableSuggestion } from "../utils/labels.js";
import { isUsableResult } from "../utils/results.js";
import {
  ActionableRetryNotice,
  GuidanceBanner,
  ProgressIndicator,
  ReasonList,
} from "./Feedback.jsx";
import {
  toArray,
  safeDisplayValue,
  normalizeRecommendation,
  normalizeEvidence,
} from "../../services/specialistData.js";

const FLOW_PHASE = {
  INSTRUCTIONS: "instructions",
  POSITIONING: "positioning",
  COUNTDOWN: "countdown",
  RECORDING: "recording",
  RESULT: "result",
};

export default function AssessmentFlow({
  testType,
  stepLabel,
  title,
  demoId,
  description,
  instructionsList = [],
  safetyNote = null,
  caveat = null,
  runner,
  engine,
  renderActiveContent,
  renderMeasurements,
  onComplete,
  onSkip,
  onCameraStateChange,
  calculateProgress,
}) {
  const [phase, setPhase] = useState(FLOW_PHASE.INSTRUCTIONS);
  const [positioning, setPositioning] = useState(() =>
    evaluatePositioning(null, testType)
  );
  const [countdown, setCountdown] = useState(3);

  const stableFramesRef = useRef(0);
  const countdownTimerRef = useRef(null);
  const [debugPhase, setDebugPhase] = useState(null);
  const [debugResult, setDebugResult] = useState(null);
  const [debugStatus, setDebugStatus] = useState(null);
  useEffect(() => {
    window.__setAssessmentFlow = (override = {}) => {
      if (override.phase !== undefined) {
        setDebugPhase(override.phase);
        setPhase(override.phase);
      }
      if (override.result !== undefined) setDebugResult(override.result);
      if (override.status !== undefined) setDebugStatus(override.status);
      if (override.positioning !== undefined) setPositioning(override.positioning);
    };
  }, []);

  const { running, start, stop, clear, guidance } = runner;
  const attempts = runner.attempts ?? 1;
  const result = debugResult !== null ? debugResult : runner.result;
  const status = debugStatus !== null ? debugStatus : runner.status;

  const effectivePhase = result ? FLOW_PHASE.RESULT : (debugPhase || phase);

  // Sync camera state for instructions (camera hidden while reading instructions)
  useEffect(() => {
    if (effectivePhase !== FLOW_PHASE.INSTRUCTIONS) return;
    onCameraStateChange?.({
      outline: null,
      countdown: null,
      trackingStatus: null,
      guidance: null,
      visible: false,
    });
  }, [effectivePhase, onCameraStateChange]);

  // Handle positioning frame evaluation
  useEffect(() => {
    if (effectivePhase !== FLOW_PHASE.POSITIONING) return undefined;

    engine?.startLoop?.();

    const outlineType = testType === "ftsst" ? "side" : testType === "shoulder" ? "upper" : "front";

    // Immediate initial sync on entering positioning
    onCameraStateChange?.({
      outline: outlineType,
      countdown: null,
      trackingStatus: "repositioning",
      guidance: null,
      visible: true,
    });

    const handleFrame = (frame) => {
      const evaluation = evaluatePositioning(frame, testType, {
        stableCount: stableFramesRef.current,
      });

      stableFramesRef.current = evaluation.stableFrames;
      setPositioning(evaluation);

      const outlineType = testType === "ftsst" ? "side" : testType === "shoulder" ? "upper" : "front";

      onCameraStateChange?.({
        outline: outlineType,
        countdown: null,
        trackingStatus: evaluation.trackingQuality,
        guidance: evaluation.guidance,
        visible: true,
      });

      // Auto-trigger countdown when positioning has been stable
      if (evaluation.ready && stableFramesRef.current >= STABLE_PREFLIGHT_FRAMES) {
        setCountdown(3);
        setPhase(FLOW_PHASE.COUNTDOWN);
      }
    };

    const unsubscribe = engine ? engine.subscribe(handleFrame) : () => {};

    return () => {
      unsubscribe();
    };
  }, [effectivePhase, testType, engine, onCameraStateChange]);

  // Handle 3-2-1 Countdown
  useEffect(() => {
    if (effectivePhase !== FLOW_PHASE.COUNTDOWN) return undefined;

    onCameraStateChange?.({
      outline: null,
      countdown: 3,
      trackingStatus: "ready",
      guidance: "Get ready...",
      visible: true,
    });

    let count = 3;
    countdownTimerRef.current = setInterval(() => {
      count -= 1;
      if (count > 0) {
        setCountdown(count);
        onCameraStateChange?.({
          outline: null,
          countdown: count,
          trackingStatus: "ready",
          guidance: "Get ready...",
          visible: true,
        });
      } else if (count === 0) {
        setCountdown("Start!");
        onCameraStateChange?.({
          outline: null,
          countdown: "Start!",
          trackingStatus: "ready",
          guidance: "Start moving now!",
          visible: true,
        });
      } else {
        clearInterval(countdownTimerRef.current);
        setCountdown(null);
        setPhase(FLOW_PHASE.RECORDING);
        onCameraStateChange?.({
          outline: null,
          countdown: null,
          trackingStatus: "tracking",
          guidance: null,
          visible: true,
        });
        start();
      }
    }, 850);

    return () => {
      if (countdownTimerRef.current) clearInterval(countdownTimerRef.current);
    };
  }, [effectivePhase, start, onCameraStateChange]);

  // Sync camera state while recording
  useEffect(() => {
    if (effectivePhase !== FLOW_PHASE.RECORDING) return;

    const trackingState = status?.trackingWarning
      ? (status.trackingState === "recovering" ? "recovering" : "repositioning")
      : "tracking";
    const activeGuidance = status?.trackingWarning ? "lost_position_briefly" : guidance();

    onCameraStateChange?.({
      outline: null,
      countdown: null,
      trackingStatus: trackingState,
      guidance: activeGuidance,
      visible: true,
    });
  }, [effectivePhase, status, guidance, onCameraStateChange]);

  // Clear camera overlay when result is produced
  // Hide camera overlay when result is produced
  useEffect(() => {
    if (!result) return;
    onCameraStateChange?.({
      outline: null,
      countdown: null,
      trackingStatus: isUsableResult(result) ? "ready" : "repositioning",
      guidance: null,
      visible: false,
    });
  }, [result, onCameraStateChange]);

  const handleStartSetup = useCallback(() => {
    stableFramesRef.current = 0;
    setPhase(FLOW_PHASE.POSITIONING);
  }, []);

  const handleRetry = useCallback(() => {
    clear();
    stableFramesRef.current = 0;
    setCountdown(null);
    setPhase(FLOW_PHASE.POSITIONING);
  }, [clear]);

  const handleBackToInstructions = useCallback(() => {
    stableFramesRef.current = 0;
    setPhase(FLOW_PHASE.INSTRUCTIONS);
    onCameraStateChange?.({
      outline: null,
      countdown: null,
      trackingStatus: null,
      guidance: null,
      visible: false,
    });
  }, [onCameraStateChange]);

  const handleManualStart = useCallback(() => {
    setCountdown(3);
    setPhase(FLOW_PHASE.COUNTDOWN);
  }, []);

  // Phase 1: Instructions
  if (phase === FLOW_PHASE.INSTRUCTIONS) {
    const demo = demoId ? getMovementDemo(demoId) : null;
    // A recorded demonstration of this same check, where one exists
    // (public/assessment-videos/). The animated figure stays as the
    // fallback, so a check with no recording is unaffected.
    const video = getExerciseVideo(demoId);

    return (
      <div className="assess-panel">
        <span className="assess-panel__step">{safeDisplayValue(stepLabel)}</span>
        <h2>{safeDisplayValue(title)}</h2>

        <DemonstrationVideo video={video} />

        {demo && (
          <div className="assess-demo-container">
            <MovementDemo demo={demo} />
          </div>
        )}

        <p className="assess-panel__desc">{safeDisplayValue(description)}</p>

        {toArray(instructionsList).length > 0 && (
          <div className="assess-instructions-block">
            <h3>How to perform this check</h3>
            <ul className="assess-panel__list">
              {toArray(instructionsList).map((item, idx) => (
                <li key={idx}>{safeDisplayValue(item?.instruction || item?.text || item)}</li>
              ))}
            </ul>
          </div>
        )}

        {safetyNote && (
          <div className="assess-panel__safety">
            <strong>Safety guidance:</strong> {safeDisplayValue(safetyNote)}
          </div>
        )}

        {caveat && <p className="assess-panel__caveat">{safeDisplayValue(caveat)}</p>}

        <div className="assess-panel__actions">
          <button type="button" className="assess-btn assess-btn--primary" onClick={handleStartSetup}>
            Start camera setup →
          </button>
          <button type="button" className="assess-btn assess-btn--ghost" onClick={onSkip}>
            Skip this check
          </button>
        </div>
      </div>
    );
  }

  // Phase 2: Positioning & Live Setup Check
  if (phase === FLOW_PHASE.POSITIONING) {
    const { checklist, actionableTip, progress } = positioning;

    return (
      <div className="assess-panel">
        <span className="assess-panel__step">{safeDisplayValue(stepLabel)} · Camera setup</span>
        <h2>Let's get you ready</h2>

        <p className="assess-setup-instruction">
          {testType === "ftsst"
            ? "Place your chair sideways to the camera so your full body is visible."
            : testType === "shoulder"
              ? "Stand where your upper body and both arms are clearly visible."
              : "Stand facing the camera with support nearby if needed."}
        </p>

        <div className="assess-checklist">
          <div className={`assess-checklist__item ${checklist?.head ? "is-checked" : ""}`}>
            <span className="assess-checklist__icon">{checklist?.head ? "✓" : "○"}</span>
            <span>Head visible</span>
          </div>
          <div className={`assess-checklist__item ${checklist?.shoulders ? "is-checked" : ""}`}>
            <span className="assess-checklist__icon">{checklist?.shoulders ? "✓" : "○"}</span>
            <span>Shoulders visible</span>
          </div>
          {testType === "shoulder" && (
            <div className={`assess-checklist__item ${checklist?.arms ? "is-checked" : ""}`}>
              <span className="assess-checklist__icon">{checklist?.arms ? "✓" : "○"}</span>
              <span>Arms & wrists visible</span>
            </div>
          )}
          {testType !== "shoulder" && (
            <>
              <div className={`assess-checklist__item ${checklist?.hips ? "is-checked" : ""}`}>
                <span className="assess-checklist__icon">{checklist?.hips ? "✓" : "○"}</span>
                <span>Hips visible</span>
              </div>
              <div className={`assess-checklist__item ${checklist?.knees ? "is-checked" : ""}`}>
                <span className="assess-checklist__icon">{checklist?.knees ? "✓" : "○"}</span>
                <span>Knees visible</span>
              </div>
              <div className={`assess-checklist__item ${checklist?.feet ? "is-checked" : ""}`}>
                <span className="assess-checklist__icon">{checklist?.feet ? "✓" : "○"}</span>
                <span>Feet visible</span>
              </div>
            </>
          )}
        </div>

        {actionableTip && (
          <div className="assess-guidance-tip">
            <span className="assess-guidance-tip__icon">💡</span>
            <span>{safeDisplayValue(actionableTip)}</span>
          </div>
        )}

        <div className="assess-preflight-progress">
          <div className="assess-preflight-progress__bar">
            <div
              className="assess-preflight-progress__fill"
              style={{ width: `${Math.min(100, Math.max(0, Math.round((Number(progress) || 0) * 100)))}%` }}
            />
          </div>
          <span className="assess-preflight-progress__label">
            {progress >= 1 ? "Great! You're in position." : "Hold still for a moment..."}
          </span>
        </div>

        <div className="assess-panel__actions">
          <button
            type="button"
            className="assess-btn assess-btn--primary"
            onClick={handleManualStart}
          >
            I'm ready · Start test
          </button>
          <button type="button" className="assess-btn assess-btn--ghost" onClick={handleBackToInstructions}>
            ← Back to instructions
          </button>
          <button type="button" className="assess-btn assess-btn--ghost" onClick={onSkip}>
            Skip this check
          </button>
        </div>
      </div>
    );
  }

  // Phase 3: Countdown
  if (phase === FLOW_PHASE.COUNTDOWN) {
    return (
      <div className="assess-panel">
        <span className="assess-panel__step">{safeDisplayValue(stepLabel)} · Starting</span>
        <h2>Get ready to begin</h2>

        <div className="assess-countdown-display">
          <span className="assess-countdown-display__number">{safeDisplayValue(countdown)}</span>
        </div>

        <p className="assess-panel__live">
          {countdown === "Start!" ? "Begin your movement!" : "Hold your position..."}
        </p>

        <div className="assess-panel__actions">
          <button type="button" className="assess-btn assess-btn--ghost" onClick={handleRetry}>
            Cancel
          </button>
        </div>
      </div>
    );
  }

  // Phase 5: Result Review (when a test attempt produces a result)
  if (result) {
    const usable = isUsableResult(result);
    const invalidReasonsList = toArray(result?.invalidReasons);
    const primaryReason = invalidReasonsList[0] || null;
    const actionableTip = getActionableSuggestion(primaryReason, testType);

    return (
      <div className="assess-panel">
        <span className="assess-panel__step">
          {safeDisplayValue(stepLabel)} · Attempt {safeDisplayValue(attempts)}
        </span>
        <h2>{usable ? `${safeDisplayValue(title)} recorded` : "We're having trouble seeing your movement"}</h2>

        {usable ? (
          <>
            {renderMeasurements && renderMeasurements(result)}
            {caveat && <p className="assess-panel__caveat">{safeDisplayValue(caveat)}</p>}
          </>
        ) : (
          <>
            <ActionableRetryNotice suggestion={safeDisplayValue(actionableTip)} />
            <ReasonList
              codes={invalidReasonsList.map((r) => (typeof r === "string" ? r : r?.code || r?.reason || safeDisplayValue(r)))}
              title="Why this attempt could not be used"
            />
            <p className="assess-panel__caveat">
              No problem — home camera tracking can take a moment to calibrate. Try adjusting your position as suggested and try again.
            </p>
          </>
        )}

        <div className="assess-panel__actions">
          {usable ? (
            <>
              <button
                type="button"
                className="assess-btn assess-btn--primary"
                onClick={() => onComplete(result)}
              >
                {stepLabel?.toLowerCase?.().includes("right")
                  ? "Continue to assessment results →"
                  : stepLabel?.toLowerCase?.().includes("left")
                    ? "Continue to right leg →"
                    : "Continue to next check →"}
              </button>
              <button type="button" className="assess-btn assess-btn--ghost" onClick={handleRetry}>
                Try again
              </button>
            </>
          ) : (
            <>
              <button type="button" className="assess-btn assess-btn--primary" onClick={handleRetry}>
                Try again
              </button>
              <button type="button" className="assess-btn assess-btn--ghost" onClick={onSkip}>
                Skip this check
              </button>
            </>
          )}
        </div>
      </div>
    );
  }

  // Phase 4: Recording / Active Movement
  if (phase === FLOW_PHASE.RECORDING || running) {
    const progressData = calculateProgress ? calculateProgress(status) : { stage: "tracking", progress: 0.5 };

    return (
      <div className="assess-panel">
        <span className="assess-panel__step">{safeDisplayValue(stepLabel)} · Recording</span>
        <h2>{safeDisplayValue(title)}</h2>

        {renderActiveContent && renderActiveContent(status)}

        <ProgressIndicator
          stage={progressData.stage}
          progress={progressData.progress}
        />

        <GuidanceBanner code={guidance()} />

        {status?.usable === false && (
          <div className="assess-guidance-warning">
            ⚠️ We lost your position briefly. Stay in frame.
          </div>
        )}

        <div className="assess-panel__actions">
          <button type="button" className="assess-btn assess-btn--ghost" onClick={stop}>
            Finish test
          </button>
        </div>
      </div>
    );
  }

  return null;
}
