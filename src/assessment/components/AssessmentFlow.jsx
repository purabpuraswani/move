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

  const { running, status, result, attempts, start, stop, clear, guidance } = runner;

  const effectivePhase = result ? FLOW_PHASE.RESULT : phase;

  // Handle positioning frame evaluation
  useEffect(() => {
    if (effectivePhase !== FLOW_PHASE.POSITIONING) return undefined;

    engine?.startLoop?.();

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
        });
      } else if (count === 0) {
        setCountdown("Start!");
        onCameraStateChange?.({
          outline: null,
          countdown: "Start!",
          trackingStatus: "ready",
          guidance: "Start moving now!",
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

    const trackingState = status?.trackingState || (status?.usable ? "tracking" : "recovering");
    const activeGuidance = guidance() || (status?.usable === false ? "lost_position_briefly" : null);

    onCameraStateChange?.({
      outline: null,
      countdown: null,
      trackingStatus: trackingState,
      guidance: activeGuidance ? null : null,
    });
  }, [effectivePhase, status, guidance, onCameraStateChange]);

  // Clear camera overlay when result is produced
  useEffect(() => {
    if (!result) return;
    onCameraStateChange?.({
      outline: null,
      countdown: null,
      trackingStatus: isUsableResult(result) ? "ready" : "repositioning",
      guidance: null,
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
    });
  }, [onCameraStateChange]);

  const handleManualStart = useCallback(() => {
    setCountdown(3);
    setPhase(FLOW_PHASE.COUNTDOWN);
  }, []);

  // Phase 1: Instructions
  if (phase === FLOW_PHASE.INSTRUCTIONS) {
    const demo = demoId ? getMovementDemo(demoId) : null;

    return (
      <div className="assess-panel">
        <span className="assess-panel__step">{stepLabel}</span>
        <h2>{title}</h2>

        {demo && <MovementDemo demo={demo} />}

        {safetyNote && <p className="assess-panel__safety">{safetyNote}</p>}

        <p>{description}</p>

        {instructionsList.length > 0 && (
          <ul className="assess-panel__list">
            {instructionsList.map((item, idx) => (
              <li key={idx}>{item}</li>
            ))}
          </ul>
        )}

        {caveat && <p className="assess-panel__caveat">{caveat}</p>}

        <div className="assess-panel__actions">
          <button type="button" className="assess-btn assess-btn--ghost" onClick={onSkip}>
            Skip this check
          </button>
          <button type="button" className="assess-btn assess-btn--primary" onClick={handleStartSetup}>
            Position yourself
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
        <span className="assess-panel__step">{stepLabel} · Camera setup</span>
        <h2>Let's get you ready</h2>

        <p className="assess-setup-instruction">
          {testType === "ftsst"
            ? "Place your chair sideways to the camera so your full body is visible."
            : testType === "shoulder"
              ? "Stand where your upper body and both arms are clearly visible."
              : "Stand facing the camera with support nearby if needed."}
        </p>

        <div className="assess-checklist">
          <div className={`assess-checklist__item ${checklist.head ? "is-checked" : ""}`}>
            <span className="assess-checklist__icon">{checklist.head ? "✓" : "○"}</span>
            <span>Head visible</span>
          </div>
          <div className={`assess-checklist__item ${checklist.shoulders ? "is-checked" : ""}`}>
            <span className="assess-checklist__icon">{checklist.shoulders ? "✓" : "○"}</span>
            <span>Shoulders visible</span>
          </div>
          {testType === "shoulder" && (
            <div className={`assess-checklist__item ${checklist.arms ? "is-checked" : ""}`}>
              <span className="assess-checklist__icon">{checklist.arms ? "✓" : "○"}</span>
              <span>Arms & wrists visible</span>
            </div>
          )}
          {testType !== "shoulder" && (
            <>
              <div className={`assess-checklist__item ${checklist.hips ? "is-checked" : ""}`}>
                <span className="assess-checklist__icon">{checklist.hips ? "✓" : "○"}</span>
                <span>Hips visible</span>
              </div>
              <div className={`assess-checklist__item ${checklist.knees ? "is-checked" : ""}`}>
                <span className="assess-checklist__icon">{checklist.knees ? "✓" : "○"}</span>
                <span>Knees visible</span>
              </div>
              <div className={`assess-checklist__item ${checklist.feet ? "is-checked" : ""}`}>
                <span className="assess-checklist__icon">{checklist.feet ? "✓" : "○"}</span>
                <span>Feet visible</span>
              </div>
            </>
          )}
        </div>

        {actionableTip && (
          <div className="assess-guidance-tip">
            <span className="assess-guidance-tip__icon">💡</span>
            <span>{actionableTip}</span>
          </div>
        )}

        <div className="assess-preflight-progress">
          <div className="assess-preflight-progress__bar">
            <div
              className="assess-preflight-progress__fill"
              style={{ width: `${Math.round(progress * 100)}%` }}
            />
          </div>
          <span className="assess-preflight-progress__label">
            {progress >= 1 ? "Great! You're in position." : "Hold still for a moment..."}
          </span>
        </div>

        <div className="assess-panel__actions">
          <button type="button" className="assess-btn assess-btn--ghost" onClick={handleBackToInstructions}>
            Back
          </button>
          <button type="button" className="assess-btn assess-btn--ghost" onClick={onSkip}>
            Skip this check
          </button>
          <button
            type="button"
            className="assess-btn assess-btn--primary"
            onClick={handleManualStart}
          >
            I'm ready · Start test
          </button>
        </div>
      </div>
    );
  }

  // Phase 3: Countdown
  if (phase === FLOW_PHASE.COUNTDOWN) {
    return (
      <div className="assess-panel">
        <span className="assess-panel__step">{stepLabel} · Starting</span>
        <h2>Get ready to begin</h2>

        <div className="assess-countdown-display">
          <span className="assess-countdown-display__number">{countdown}</span>
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
    const primaryReason = result.invalidReasons?.[0] || null;
    const actionableTip = getActionableSuggestion(primaryReason, testType);

    return (
      <div className="assess-panel">
        <span className="assess-panel__step">
          {stepLabel} · Attempt {attempts}
        </span>
        <h2>{usable ? `${title} recorded` : "We're having trouble seeing your movement"}</h2>

        {usable ? (
          <>
            {renderMeasurements && renderMeasurements(result)}
            {caveat && <p className="assess-panel__caveat">{caveat}</p>}
          </>
        ) : (
          <>
            <ActionableRetryNotice suggestion={actionableTip} />
            <ReasonList codes={result.invalidReasons} title="Why this attempt could not be used" />
            <p className="assess-panel__caveat">
              No problem — home camera tracking can take a moment to calibrate. Try adjusting your position as suggested and try again.
            </p>
          </>
        )}

        <div className="assess-panel__actions">
          <button type="button" className="assess-btn assess-btn--ghost" onClick={handleRetry}>
            Try again
          </button>
          <button
            type="button"
            className="assess-btn assess-btn--primary"
            onClick={() => onComplete(result)}
          >
            Continue to next check →
          </button>
        </div>
      </div>
    );
  }

  // Phase 4: Recording / Active Movement
  if (phase === FLOW_PHASE.RECORDING || running) {
    const progressData = calculateProgress ? calculateProgress(status) : { stage: "tracking", progress: 0.5 };

    return (
      <div className="assess-panel">
        <span className="assess-panel__step">{stepLabel} · Recording</span>
        <h2>{title}</h2>

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
            Stop
          </button>
        </div>
      </div>
    );
  }

  return null;
}
