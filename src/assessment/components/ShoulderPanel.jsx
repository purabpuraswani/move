import { useCallback } from "react";

import { ShoulderAbductionTest } from "../tests/shoulder/shoulderLogic.js";
import { POSE, SHOULDER } from "../config/protocol.js";
import { useTestRunner } from "../hooks/useTestRunner.js";
import { formatDegrees } from "../utils/labels.js";
import { LiveCounter, Measurement } from "./Feedback.jsx";
import AssessmentFlow from "./AssessmentFlow.jsx";

export default function ShoulderPanel({ engine, onComplete, onSkip, onCameraStateChange }) {
  const createTest = useCallback(
    () => new ShoulderAbductionTest({ ...SHOULDER, maxRecoveryMs: POSE.maxRecoveryMs }),
    []
  );
  const isFinished = useCallback(
    (test) => test.hasEnoughRepetitions() || test.isTrackingFailed(),
    []
  );

  const runner = useTestRunner({ engine, createTest, isFinished });

  const calculateProgress = useCallback((status) => {
    const left = status?.repetitions?.left || 0;
    const right = status?.repetitions?.right || 0;
    const required = SHOULDER.requiredRepetitions;

    if (left >= required && right >= required) {
      return { stage: "complete", progress: 1.0 };
    }
    if (left >= required - 1 || right >= required - 1) {
      return { stage: "almost_done", progress: 0.85 };
    }
    if (left > 0 || right > 0) {
      return { stage: "tracking", progress: 0.5 };
    }
    return { stage: "preparing", progress: 0.2 };
  }, []);

  const renderActiveContent = useCallback(
    (status) => {
      const repetitions = status?.repetitions ?? { left: 0, right: 0 };
      const live = status?.live ?? { left: null, right: null };

      return (
        <>
          <div className="assess-panel__counters">
            <LiveCounter
              label="Left repetitions"
              value={repetitions.left}
              total={SHOULDER.requiredRepetitions}
            />
            <LiveCounter
              label="Right repetitions"
              value={repetitions.right}
              total={SHOULDER.requiredRepetitions}
            />
          </div>

          <div className="assess-panel__live assess-panel__live--split">
            <span className="assess-panel__live-item">Left now: <strong>{formatDegrees(live.left)}</strong></span>
            <span className="assess-panel__live-divider">·</span>
            <span className="assess-panel__live-item">Right now: <strong>{formatDegrees(live.right)}</strong></span>
          </div>

          <ol className="assess-panel__list">
            <li>Raise both arms out sideways, as far as is comfortable.</li>
            <li>Lower them fully back to your sides.</li>
            <li>Repeat until both counters reach {SHOULDER.requiredRepetitions}.</li>
          </ol>
        </>
      );
    },
    []
  );

  const renderMeasurements = useCallback((result) => {
    const { left, right, observableDifferenceDeg } = result.measurements;

    return (
      <div className="assess-panel__measures">
        <Measurement
          label="Left arm, observed elevation"
          value={formatDegrees(left.finalElevationDeg)}
          note={`${left.repetitionCount} of ${SHOULDER.requiredRepetitions} repetitions`}
        />
        <Measurement
          label="Right arm, observed elevation"
          value={formatDegrees(right.finalElevationDeg)}
          note={`${right.repetitionCount} of ${SHOULDER.requiredRepetitions} repetitions`}
        />
        <Measurement
          label="Difference between sides"
          value={formatDegrees(observableDifferenceDeg)}
          note="Observed in the camera image only"
        />
      </div>
    );
  }, []);

  return (
    <AssessmentFlow
      testType="shoulder"
      stepLabel="Check 1 of 3"
      title="Shoulder movement"
      stepLabel="Assessment 1 of 3"
      title="Hand / Shoulder Raise"
      demoId="assessment-shoulder-raise"
      description={`Stand facing the camera with your whole body in the frame, arms relaxed at your sides. Stand still for a moment first, then raise both arms out to the side and lower them again, ${SHOULDER.requiredRepetitions} times.`}
      instructionsList={[
        "Face the camera, feet about hip width apart.",
        "Move only as far as is comfortable. Stop if anything hurts.",
        "Keep your body upright rather than leaning to help the arm up.",
      ]}
      caveat="This records the angle of your upper arm as the camera sees it. It is not a clinical range of motion measurement."
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

