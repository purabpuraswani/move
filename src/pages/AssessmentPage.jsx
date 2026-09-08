/**
 * The assessment flow.
 *
 * Order: introduction, safety and scope, check 1, chair setup, check 2, check 3
 * on each leg, then the raw results.
 *
 * The camera and the pose model are opened once, here, and shared by all three
 * checks. The camera is not requested until the user has accepted the safety and
 * privacy notice.
 *
 * This page holds the session object and moves between steps. It contains no
 * measurement logic of its own, and it never converts a skipped or unusable
 * check into a number.
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { usePoseEngine } from "../assessment/hooks/usePoseEngine.js";
import CameraStage from "../assessment/components/CameraStage.jsx";
import ShoulderPanel from "../assessment/components/ShoulderPanel.jsx";
import FtsstPanel from "../assessment/components/FtsstPanel.jsx";
import BalancePanel from "../assessment/components/BalancePanel.jsx";
import ResultsStep from "../assessment/components/ResultsStep.jsx";
import { ChairSetupStep, IntroStep, SafetyStep } from "../assessment/components/Steps.jsx";
import {
  combineBalanceResults,
  skippedSide,
} from "../assessment/tests/balance/balanceLogic.js";
import {
  createSession,
  finaliseSession,
  skippedResult,
  toStoredPayload,
  withTestResult,
} from "../assessment/utils/results.js";
import { saveAssessment } from "../services/assessments";
import { getToken } from "../services/auth";

import "./AssessmentPage.css";

const STEP = {
  INTRO: "intro",
  SAFETY: "safety",
  SHOULDER: "shoulder",
  CHAIR: "chair",
  FTSST: "ftsst",
  BALANCE_LEFT: "balance_left",
  BALANCE_RIGHT: "balance_right",
  RESULTS: "results",
};

/** Steps where the camera preview is on screen. */
const CAMERA_STEPS = [
  STEP.SHOULDER,
  STEP.CHAIR,
  STEP.FTSST,
  STEP.BALANCE_LEFT,
  STEP.BALANCE_RIGHT,
];

const CAMERA_HINTS = {
  [STEP.SHOULDER]: "Stand facing the camera with your whole body in the frame.",
  [STEP.CHAIR]: "Place the chair side-on to the camera while you measure it.",
  [STEP.FTSST]: "The camera needs to see your hip, knee, and ankle from the side.",
  [STEP.BALANCE_LEFT]: "Face the camera, with something steady within reach.",
  [STEP.BALANCE_RIGHT]: "Face the camera, with something steady within reach.",
};

function AssessmentPage() {
  const navigate = useNavigate();
  const engine = usePoseEngine();

  const [step, setStep] = useState(STEP.INTRO);
  const [session, setSession] = useState(() => createSession());
  const [chairSeatHeightCm, setChairSeatHeightCm] = useState(null);
  const [leftLeg, setLeftLeg] = useState(null);
  const [finalSession, setFinalSession] = useState(null);
  const [signedIn] = useState(() => Boolean(getToken()));
  const [saveState, setSaveState] = useState("idle");
  const [saveError, setSaveError] = useState(null);

  const [cameraState, setCameraState] = useState({
    outline: null,
    countdown: null,
    trackingStatus: null,
    guidance: null,
  });

  const { connect, release, stopLoop } = engine;

  /**
   * The camera is only needed while a check is on screen. Leaving a camera step
   * stops the frame loop, and reaching the results releases the camera outright
   * rather than holding it open while the user reads.
   */
  useEffect(() => {
    if (CAMERA_STEPS.includes(step)) return;

    stopLoop();

    if (step === STEP.RESULTS) release();
  }, [step, stopLoop, release]);

  function resetCamera() {
    setCameraState({
      outline: null,
      countdown: null,
      trackingStatus: null,
      guidance: null,
    });
  }

  function recordAndAdvance(testId, result, nextStep) {
    resetCamera();
    setSession((current) => withTestResult(current, testId, result));
    setStep(nextStep);
  }

  function finishSession(balanceResult) {
    resetCamera();
    const withBalance = withTestResult(session, "balance", balanceResult);

    setSession(withBalance);
    setFinalSession(finaliseSession(withBalance));
    setStep(STEP.RESULTS);
  }

  function completeLeftLeg(sideResult) {
    setLeftLeg(sideResult);
    setStep(STEP.BALANCE_RIGHT);
  }

  function completeRightLeg(sideResult) {
    finishSession(combineBalanceResults(leftLeg ?? skippedSide("left"), sideResult));
  }

  /**
   * Saving is a deliberate action, not automatic.
   *
   * Only the measurements go to the server: toStoredPayload() is the single
   * description of a session the backend accepts, and it contains no frames and
   * no keypoint sequence. A failure is reported as a failure; the results stay
   * on screen so the user does not lose them.
   */
  async function handleSave() {
    if (!finalSession) return;

    setSaveState("saving");
    setSaveError(null);

    try {
      await saveAssessment(toStoredPayload(finalSession));

      setSaveState("saved");
    } catch (error) {
      setSaveState("idle");
      setSaveError(error.message || "Your results could not be saved.");
    }
  }

  function skipToResults() {
    resetCamera();
    let currentSession = session;
    if (!currentSession.tests.shoulder || currentSession.tests.shoulder.status === "not_started") {
      currentSession = withTestResult(currentSession, "shoulder", skippedResult("shoulder"));
    }
    if (!currentSession.tests.ftsst || currentSession.tests.ftsst.status === "not_started") {
      currentSession = withTestResult(currentSession, "ftsst", skippedResult("ftsst"));
    }
    if (!currentSession.tests.balance || currentSession.tests.balance.status === "not_started") {
      const skippedBalance = combineBalanceResults(leftLeg ?? skippedSide("left"), skippedSide("right"));
      currentSession = withTestResult(currentSession, "balance", skippedBalance);
    }
    setSession(currentSession);
    setFinalSession(finaliseSession(currentSession));
    setStep(STEP.RESULTS);
  }

  function exit() {
    navigate("/dashboard");
  }

  const showCamera = CAMERA_STEPS.includes(step);

  return (
    <div className="assess-page">
      <header className="assess-header">
        <button type="button" className="assess-header__logo" onClick={exit}>
          <span className="assess-header__mark">M</span>
          <span>
            MoveWell<small>AI</small>
          </span>
        </button>

        <span className="assess-header__title">Movement check</span>

        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
          {CAMERA_STEPS.includes(step) && (
            <button type="button" className="assess-btn assess-btn--quiet" onClick={skipToResults}>
              Skip to results →
            </button>
          )}
          <button type="button" className="assess-btn assess-btn--quiet" onClick={exit}>
            Exit
          </button>
        </div>
      </header>

      <main className={showCamera ? "assess-main assess-main--split" : "assess-main"}>
        {showCamera && (
          <CameraStage
            engine={engine}
            hint={CAMERA_HINTS[step]}
            outline={cameraState.outline}
            countdown={cameraState.countdown}
            trackingStatus={cameraState.trackingStatus}
            guidance={cameraState.guidance}
          />
        )}

        {step === STEP.INTRO && (
          <>
            {!signedIn && (
              <p className="assess-signin-note">
                You are not signed in. You can still run the checks and see your
                measurements, but they cannot be saved to your account.
              </p>
            )}
            <IntroStep onContinue={() => setStep(STEP.SAFETY)} onExit={exit} />
          </>
        )}

        {step === STEP.SAFETY && (
          <SafetyStep
            onExit={() => setStep(STEP.INTRO)}
            onAccept={() => {
              connect();
              setStep(STEP.SHOULDER);
            }}
          />
        )}

        {step === STEP.SHOULDER && (
          <ShoulderPanel
            engine={engine}
            onComplete={(result) => recordAndAdvance("shoulder", result, STEP.CHAIR)}
            onSkip={() => recordAndAdvance("shoulder", skippedResult("shoulder"), STEP.CHAIR)}
            onCameraStateChange={setCameraState}
          />
        )}

        {step === STEP.CHAIR && (
          <ChairSetupStep
            onContinue={(height) => {
              setChairSeatHeightCm(height);
              setStep(STEP.FTSST);
            }}
            onSkip={() => recordAndAdvance("ftsst", skippedResult("ftsst"), STEP.BALANCE_LEFT)}
          />
        )}

        {step === STEP.FTSST && (
          <FtsstPanel
            engine={engine}
            chairSeatHeightCm={chairSeatHeightCm}
            onComplete={(result) => recordAndAdvance("ftsst", result, STEP.BALANCE_LEFT)}
            onSkip={() => recordAndAdvance("ftsst", skippedResult("ftsst"), STEP.BALANCE_LEFT)}
            onCameraStateChange={setCameraState}
          />
        )}

        {step === STEP.BALANCE_LEFT && (
          <BalancePanel
            engine={engine}
            supportSide="left"
            onComplete={completeLeftLeg}
            onSkip={() => completeLeftLeg(skippedSide("left"))}
            onCameraStateChange={setCameraState}
          />
        )}

        {step === STEP.BALANCE_RIGHT && (
          <BalancePanel
            engine={engine}
            supportSide="right"
            onComplete={completeRightLeg}
            onSkip={() => completeRightLeg(skippedSide("right"))}
            onCameraStateChange={setCameraState}
          />
        )}

        {step === STEP.RESULTS && finalSession && (
          <ResultsStep
            session={finalSession}
            onSave={signedIn ? handleSave : undefined}
            saveState={saveState}
            saveError={saveError}
            onExit={exit}
            onViewPlan={() => navigate("/plan")}
          />
        )}
      </main>
    </div>
  );
}

export default AssessmentPage;
