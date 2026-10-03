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
import DemonstrationVideo from "../assessment/components/DemonstrationVideo.jsx";
import { getExerciseVideo } from "../movementDemos/exerciseVideos.js";
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
/** Steps where the camera preview is active. */
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

const ACTIVE_SESSION_KEY = "movewell_active_assessment_session";

function loadStoredSession() {
  if (typeof window === "undefined" || !window.localStorage) return null;
  try {
    const raw = localStorage.getItem(ACTIVE_SESSION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && parsed.session && parsed.session.sessionId) {
      return parsed;
    }
  } catch (_) {}
  return null;
}

function clearStoredSession() {
  if (typeof window === "undefined" || !window.localStorage) return;
  try {
    localStorage.removeItem(ACTIVE_SESSION_KEY);
  } catch (_) {}
}

function AssessmentPage() {
  const navigate = useNavigate();
  const engine = usePoseEngine();

  const [initialData] = useState(() => loadStoredSession());
  const [step, setStep] = useState(() => initialData?.step || STEP.INTRO);
  const [session, setSession] = useState(() => initialData?.session || createSession());
  const [chairSeatHeightCm, setChairSeatHeightCm] = useState(() => initialData?.chairSeatHeightCm ?? null);
  const [leftLeg, setLeftLeg] = useState(() => initialData?.leftLeg ?? null);
  const [finalSession, setFinalSession] = useState(() => initialData?.finalSession ?? null);
  const [signedIn] = useState(() => Boolean(getToken()));
  const [saveState, setSaveState] = useState("idle");
  const [saveError, setSaveError] = useState(null);

  const [cameraState, setCameraState] = useState({
    outline: null,
    countdown: null,
    trackingStatus: null,
    guidance: null,
    visible: false,
  });

  useEffect(() => {
    window.__setAssessStep = (newStep, options = {}) => {
      if (options.finalSession !== undefined) setFinalSession(options.finalSession);
      if (options.chairSeatHeightCm !== undefined) setChairSeatHeightCm(options.chairSeatHeightCm);
      if (options.cameraState !== undefined) setCameraState((prev) => ({ ...prev, ...options.cameraState }));
      if (options.saveState !== undefined) setSaveState(options.saveState);
      if (newStep) setStep(newStep);
    };
    window.__finishSession = finishSession;
  }, [finishSession]);

  const { connect, release, stopLoop } = engine;

  /**
   * The camera is only needed while a check is on screen. Leaving a camera step
   * stops the frame loop, and reaching the results releases the camera outright
   * rather than holding it open while the user reads.
   */
  useEffect(() => {
    if (CAMERA_STEPS.includes(step)) {
      connect();
      return;
    }

    stopLoop();

    if (step === STEP.RESULTS) release();
  }, [step, stopLoop, release, connect]);

  function persistSnapshot(updatedSession, nextStep, extra = {}) {
    const payload = {
      session: updatedSession,
      step: nextStep,
      chairSeatHeightCm: extra.chairSeatHeightCm !== undefined ? extra.chairSeatHeightCm : chairSeatHeightCm,
      leftLeg: extra.leftLeg !== undefined ? extra.leftLeg : leftLeg,
      finalSession: extra.finalSession !== undefined ? extra.finalSession : finalSession,
    };

    if (typeof window !== "undefined" && window.localStorage) {
      try {
        localStorage.setItem(ACTIVE_SESSION_KEY, JSON.stringify(payload));
      } catch (_) {}
    }

    if (signedIn && updatedSession && nextStep !== STEP.RESULTS) {
      saveAssessment(toStoredPayload(updatedSession)).catch((err) => {
        console.warn("Auto-save assessment progress failed:", err);
      });
    }
  }

  function startOver() {
    clearStoredSession();
    resetCamera();
    const fresh = createSession();
    setSession(fresh);
    setFinalSession(null);
    setChairSeatHeightCm(null);
    setLeftLeg(null);
    setStep(STEP.INTRO);
  }

  function resetCamera() {
    setCameraState({
      outline: null,
      countdown: null,
      trackingStatus: null,
      guidance: null,
      visible: false,
    });
  }

  function recordAndAdvance(testId, result, nextStep) {
    resetCamera();
    const updated = withTestResult(session, testId, result);
    setSession(updated);
    setStep(nextStep);
    persistSnapshot(updated, nextStep);
  }

  function finishSession(balanceResult) {
    resetCamera();
    const withBalance = withTestResult(session, "balance", balanceResult);
    const finalised = finaliseSession(withBalance);

    setSession(withBalance);
    setFinalSession(finalised);
    setStep(STEP.RESULTS);
    persistSnapshot(withBalance, STEP.RESULTS, { finalSession: finalised });

    if (signedIn) {
      setSaveState("saving");
      saveAssessment(toStoredPayload(finalised))
        .then(() => setSaveState("saved"))
        .catch((error) => {
          setSaveState("idle");
          setSaveError(error.message || "Your results could not be saved.");
        });
    }
  }

  function completeLeftLeg(sideResult) {
    setLeftLeg(sideResult);
    setStep(STEP.BALANCE_RIGHT);
    persistSnapshot(session, STEP.BALANCE_RIGHT, { leftLeg: sideResult });
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
   * Manual save button handler (for retrying if auto-save had an issue or when requested).
   */
  async function handleSave() {
    if (!finalSession || saveState === "saving") return;

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
    const finalised = finaliseSession(currentSession);
    setSession(currentSession);
    setFinalSession(finalised);
    setStep(STEP.RESULTS);
    persistSnapshot(currentSession, STEP.RESULTS, { finalSession: finalised });

    if (signedIn) {
      setSaveState("saving");
      saveAssessment(toStoredPayload(finalised))
        .then(() => setSaveState("saved"))
        .catch((error) => {
          setSaveState("idle");
          setSaveError(error.message || "Your results could not be saved.");
        });
    }
  }

  function exit() {
    navigate("/dashboard");
  }

  function handleExitResults() {
    clearStoredSession();
    exit();
  }

  function handleViewPlan() {
    clearStoredSession();
    navigate("/plan");
  }

  const showCamera = CAMERA_STEPS.includes(step);
  // The recording for whichever check is on screen. BALANCE_LEFT and
  // BALANCE_RIGHT are two sides of the same movement, so they share one.
  const stepVideo = getExerciseVideo(
    step === STEP.SHOULDER
      ? "shoulder"
      : step === STEP.CHAIR || step === STEP.FTSST
        ? "ftsst"
        : step === STEP.BALANCE_LEFT || step === STEP.BALANCE_RIGHT
          ? "balance"
          : null,
  );

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

        <div className="assess-header__actions">
          {initialData && step !== STEP.INTRO && step !== STEP.RESULTS && (
            <button type="button" className="assess-btn assess-btn--quiet" onClick={startOver}>
              Start over
            </button>
          )}
          {CAMERA_STEPS.includes(step) && (
            <button type="button" className="assess-btn assess-btn--quiet" onClick={skipToResults}>
              Skip to results →
            </button>
          )}
          <button
            type="button"
            className="assess-btn assess-btn--quiet"
            onClick={exit}
            aria-label="Back to Dashboard"
          >
            ← Dashboard
          </button>
        </div>
      </header>

      <main className={showCamera ? "assess-main assess-main--split" : "assess-main"}>
        {showCamera && (
          // The workspace: the user's camera and the demonstration of the
          // movement, side by side, so the movement can be watched while it
          // is performed. The step panel below carries the readiness
          // information and the controls.
          <div className="assess-workspace">
            <CameraStage
              engine={engine}
              hint={CAMERA_HINTS[step]}
              outline={cameraState.outline}
              countdown={cameraState.countdown}
              trackingStatus={cameraState.trackingStatus}
              guidance={cameraState.guidance}
              visible={cameraState.visible}
            />

            {cameraState.visible ? (
              <DemonstrationVideo video={stepVideo} />
            ) : null}
          </div>
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
              persistSnapshot(session, STEP.FTSST, { chairSeatHeightCm: height });
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
            onExit={handleExitResults}
            onViewPlan={handleViewPlan}
          />
        )}
      </main>
    </div>
  );
}

export default AssessmentPage;
