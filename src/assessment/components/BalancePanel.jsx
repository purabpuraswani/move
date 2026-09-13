import { useCallback } from "react";

import {
  SingleLegStanceTest,
  BALANCE_PHASE,
} from "../tests/balance/balanceLogic.js";
import { BALANCE, POSE } from "../config/protocol.js";
import { useTestRunner } from "../hooks/useTestRunner.js";
import { describeEndReason, formatSeconds } from "../utils/labels.js";
import { Measurement } from "./Feedback.jsx";
import AssessmentFlow from "./AssessmentFlow.jsx";

const PHASE_HINT = {
  [BALANCE_PHASE.WAITING]: "Lift one foot when you feel steady.",
  [BALANCE_PHASE.STABILISING]: "Hold it there…",
  [BALANCE_PHASE.TIMING]: "Timing. Hold as long as you comfortably can.",
  [BALANCE_PHASE.DONE]: "Hold complete! Processing your results…",
};

export default function BalancePanel({
  engine,
  supportSide,
  onComplete,
  onSkip,
  onCameraStateChange,
}) {
  const createTest = useCallback(
    () => new SingleLegStanceTest({
      supportSide,
      config: { ...BALANCE, maxRecoveryMs: POSE.maxRecoveryMs },
    }),
    [supportSide]
  );

  const isFinished = useCallback((test) => test.isDone(), []);
  const onAbort = useCallback((test, timestamp) => test.stop(timestamp), []);
  const finishArgs = useCallback(({ attempts }) => ({ attempts }), []);

  const runner = useTestRunner({ engine, createTest, isFinished, onAbort, finishArgs });

  const supportLabel = supportSide === "left" ? "left" : "right";
  const liftLabel = supportSide === "left" ? "right" : "left";

  const calculateProgress = useCallback((status) => {
    const phase = status?.phase;
    const elapsed = status?.elapsedMs || 0;
    const maxDuration = BALANCE.maxDurationMs;

    if (phase === BALANCE_PHASE.DONE) {
      return { stage: "complete", progress: 1.0 };
    }
    if (phase === BALANCE_PHASE.TIMING) {
      const pct = Math.min(1, elapsed / maxDuration);
      return {
        stage: pct >= 0.85 ? "almost_done" : "tracking",
        progress: pct,
      };
    }
    if (phase === BALANCE_PHASE.STABILISING) {
      return { stage: "preparing", progress: 0.3 };
    }
    return { stage: "preparing", progress: 0.1 };
  }, []);

  const renderActiveContent = useCallback((status) => {
    const phase = status?.phase ?? BALANCE_PHASE.WAITING;

    return (
      <>
        <div className="assess-panel__timer">
          {phase === BALANCE_PHASE.TIMING ? formatSeconds(status?.elapsedMs ?? 0, 1) : "—"}
        </div>

        <p className="assess-panel__live">{PHASE_HINT[phase]}</p>

        <p className="assess-panel__caveat">
          Put your foot down or hold on to something the moment you feel unsteady.
          Stopping is recorded as stopping, not as a failure.
        </p>
      </>
    );
  }, []);

  const renderMeasurements = useCallback((result) => {
    return (
      <div className="assess-panel__measures">
        <Measurement
          label="Time held"
          value={formatSeconds(result.holdDurationMs)}
          note={
            result.reachedMaxDuration
              ? `Reached the ${BALANCE.maxDurationMs / 1000} second maximum for this check`
              : describeEndReason(result.endReason)
                ? `Ended because ${describeEndReason(result.endReason)}`
                : null
          }
        />
      </div>
    );
  }, []);

  return (
    <AssessmentFlow
      testType="balance"
      stepLabel={`Assessment 3 of 3 · ${supportLabel === "left" ? "Left" : "Right"} leg`}
      title={`One-Leg Stand (${supportLabel === "left" ? "Left" : "Right"} leg)`}
      demoId="assessment-one-leg-stand"
      safetyNote="Only do this if you feel safe. Stand next to a wall, worktop, or sturdy chair so you have something to hold. You can skip this check entirely and the rest of your results are unaffected."
      description={`Face the camera, then lift your ${liftLabel} foot off the floor and stand on your ${supportLabel} leg with your eyes open. Hold it for as long as you comfortably can, up to ${BALANCE.maxDurationMs / 1000} seconds.`}
      instructionsList={[
        "Keep your eyes open and look ahead.",
        "Put your foot down as soon as you feel unsteady.",
        "Timing starts once the position has been held briefly, not the instant your foot leaves the floor.",
      ]}
      caveat="This is how long the camera could see you holding the position. It is not a measure of balance ability, and it says nothing about fall risk."
      runner={runner}
      engine={engine}
      renderActiveContent={renderActiveContent}
      renderMeasurements={renderMeasurements}
      onComplete={onComplete}
      onSkip={onSkip}
      onCameraStateChange={onCameraStateChange}
      calculateProgress={calculateProgress}
    />
  );
}

