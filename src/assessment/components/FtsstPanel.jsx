import { useCallback } from "react";

import { FiveTimesSitToStandTest, FTSST_PHASE } from "../tests/ftsst/ftsstLogic.js";
import { FTSST } from "../config/protocol.js";
import { useTestRunner } from "../hooks/useTestRunner.js";
import { formatSeconds } from "../utils/labels.js";
import { LiveCounter, Measurement, ReasonList } from "./Feedback.jsx";
import AssessmentFlow from "./AssessmentFlow.jsx";

const PHASE_HINT = {
  [FTSST_PHASE.SELECTING_SIDE]: "Finding the best view of your legs…",
  [FTSST_PHASE.RISING]: "Standing up",
  [FTSST_PHASE.STANDING]: "Fully standing",
  [FTSST_PHASE.DESCENDING]: "Sitting down",
};

export default function FtsstPanel({
  engine,
  chairSeatHeightCm,
  onComplete,
  onSkip,
  onCameraStateChange,
}) {
  const createTest = useCallback(
    () => new FiveTimesSitToStandTest({ chairSeatHeightCm }),
    [chairSeatHeightCm]
  );

  const isFinished = useCallback((test) => test.isComplete() || test.isTimedOut(), []);

  const runner = useTestRunner({ engine, createTest, isFinished });

  const calculateProgress = useCallback((status) => {
    const reps = status?.repetitions || 0;
    const required = FTSST.requiredRepetitions;

    if (reps >= required) {
      return { stage: "complete", progress: 1.0 };
    }
    if (reps >= required - 1) {
      return { stage: "almost_done", progress: 0.85 };
    }
    if (reps > 0) {
      return { stage: "tracking", progress: reps / required };
    }
    return { stage: "preparing", progress: 0.15 };
  }, []);

  const renderActiveContent = useCallback((status) => {
    const repetitions = status?.repetitions ?? 0;
    const phase = status?.phase;
    const counting =
      phase &&
      phase !== FTSST_PHASE.SELECTING_SIDE &&
      phase !== FTSST_PHASE.WAITING_FOR_SEATED;

    return (
      <>
        <div className="assess-panel__counters">
          <LiveCounter
            label="Stands detected"
            value={repetitions}
            total={FTSST.requiredRepetitions}
          />
        </div>

        {counting && (
          <p className="assess-panel__live">
            <span className="assess-dot" aria-hidden="true" />
            {PHASE_HINT[phase] ?? "Recording"}
          </p>
        )}

        <ol className="assess-panel__list">
          <li>Sit down first, so your starting position can be seen.</li>
          <li>Fold your arms across your chest and keep them there.</li>
          <li>Stand fully upright and sit back down, five times, at your own pace.</li>
        </ol>
      </>
    );
  }, []);

  const renderMeasurements = useCallback((result) => {
    const { repetitionsDetected, requiredRepetitions, completionTimeMs } =
      result.measurements;

    return (
      <>
        <div className="assess-panel__measures">
          <Measurement
            label="Time for five stands"
            value={formatSeconds(completionTimeMs)}
            note="From leaving the seat to the fifth stand"
          />
          <Measurement
            label="Stands detected"
            value={`${repetitionsDetected} of ${requiredRepetitions}`}
          />
          <Measurement
            label="Side measured"
            value={result.setup?.measuredSide === "right" ? "Right" : "Left"}
            note="Whichever side the camera saw most clearly"
          />
        </div>

        {result.setup?.warnings?.length > 0 && (
          <ReasonList codes={result.setup.warnings} title="Setup notes" />
        )}
      </>
    );
  }, []);

  return (
    <AssessmentFlow
      testType="ftsst"
      stepLabel="Check 2 of 3"
      title="Sit to stand"
      demoId="assessment-chair-sit-to-stand"
      description="Turn your chair so the camera sees you from the side, with your hips, knees, and ankles all inside the frame. Sit down, then stand up and sit back down five times at your own pace."
      instructionsList={[
        "Use a stable chair without wheels, against a wall if possible.",
        "Fold your arms across your chest so you do not push off the seat.",
        "Stop straight away if you feel unsteady, dizzy, or any pain.",
      ]}
      caveat={`Chair height recorded for this attempt: ${
        typeof chairSeatHeightCm === "number" ? `${chairSeatHeightCm} cm` : "not provided"
      }. The timing starts and stops automatically when knee angle crosses thresholds.`}
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

