/**
 * The assessment flow.
 *
 * Order: introduction, safety and scope, shoulder movement, one-leg stand on
 * each leg, then the raw results.
 *
 * The camera and the pose model are opened once, here, and shared by both
 * checks. The camera is not requested until the user has accepted the safety and
 * privacy notice.
 *
 * This page holds the session object and moves between steps. It contains no
 * measurement logic of its own, and it never converts a skipped or unusable
 * check into a number.
 */

import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { usePoseEngine } from "../assessment/hooks/usePoseEngine.js";
import CameraStage from "../assessment/components/CameraStage.jsx";
import DemonstrationVideo from "../assessment/components/DemonstrationVideo.jsx";
import { getExerciseVideo } from "../movementDemos/exerciseVideos.js";
import ShoulderPanel from "../assessment/components/ShoulderPanel.jsx";
import BalancePanel from "../assessment/components/BalancePanel.jsx";
import ResultsStep from "../assessment/components/ResultsStep.jsx";
import { IntroStep, SafetyStep } from "../assessment/components/Steps.jsx";
import {
  combineBalanceResults,
  skippedSide,
} from "../assessment/tests/balance/balanceLogic.js";
import {
  buildSessionSummary,
  createSession,
  finaliseSession,
  notStartedResult,
  skippedResult,
  assessmentCompletion,
  withTestResult,
} from "../assessment/utils/results.js";
import { saveAssessmentForWorkflow } from "../assessment/utils/submission.js";
import { saveAssessment } from "../services/assessments";
import { runWorkflow } from "../services/workflow";
import { getToken } from "../services/auth";

import "./AssessmentPage.css";

const STEP = {
  INTRO: "intro",
  SAFETY: "safety",
  SHOULDER: "shoulder",
  BALANCE_LEFT: "balance_left",
  BALANCE_RIGHT: "balance_right",
  RESULTS: "results",
};

/** Steps where the camera preview is on screen. */
/** Steps where the camera preview is active. */
const CAMERA_STEPS = [
  STEP.SHOULDER,
  STEP.BALANCE_LEFT,
  STEP.BALANCE_RIGHT,
];

const CAMERA_HINTS = {
  [STEP.SHOULDER]: "Stand facing the camera with your whole body in the frame.",
  [STEP.BALANCE_LEFT]: "Move the laptop/webcam far enough away to frame your whole body, including both feet. Face the camera beside stable support.",
  [STEP.BALANCE_RIGHT]: "Keep your whole body, including both feet, in view. Face the camera beside stable support.",
};

const ACTIVE_SESSION_KEY = "movewell_active_assessment_session";

function loadStoredSession() {
  if (typeof window === "undefined" || !window.localStorage) return null;
  try {
    const raw = localStorage.getItem(ACTIVE_SESSION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && parsed.session && parsed.session.sessionId) {
      const keepCurrentAssessments = (candidate) => {
        if (!candidate?.tests) return candidate;
        const tests = {
          shoulder: candidate.tests.shoulder ?? notStartedResult("shoulder"),
          balance: candidate.tests.balance ?? notStartedResult("balance"),
        };
        return { ...candidate, tests, summary: buildSessionSummary(tests) };
      };
      parsed.session = keepCurrentAssessments(parsed.session);
      parsed.finalSession = keepCurrentAssessments(parsed.finalSession);
      if (parsed.step === "ftsst") parsed.step = "balance_left";
      delete parsed.chairSeatHeightCm;
      return parsed;
    }
  } catch {
    // Ignore malformed or unavailable local session data.
  }
  return null;
}

function clearStoredSession() {
  if (typeof window === "undefined" || !window.localStorage) return;
  try {
    localStorage.removeItem(ACTIVE_SESSION_KEY);
  } catch {
    // Storage may be disabled by the browser.
  }
}

function AssessmentPage() {
  const navigate = useNavigate();
  const engine = usePoseEngine();

  const [initialData] = useState(() => loadStoredSession());
  const [step, setStep] = useState(() => initialData?.step || STEP.INTRO);
  const [session, setSession] = useState(() => initialData?.session || createSession());
  const [leftLeg, setLeftLeg] = useState(() => initialData?.leftLeg ?? null);
  const [finalSession, setFinalSession] = useState(() => initialData?.finalSession ?? null);
  const [signedIn] = useState(() => Boolean(getToken()));
  const [saveState, setSaveState] = useState("idle");
  const [saveError, setSaveError] = useState(null);
  const savedAssessmentRef = useRef(null);
  const saveInFlightRef = useRef(false);
  const workflowInFlightRef = useRef(false);

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
      leftLeg: extra.leftLeg !== undefined ? extra.leftLeg : leftLeg,
      finalSession: extra.finalSession !== undefined ? extra.finalSession : finalSession,
    };

    if (typeof window !== "undefined" && window.localStorage) {
      try {
        localStorage.setItem(ACTIVE_SESSION_KEY, JSON.stringify(payload));
      } catch {
        // The assessment can continue when local persistence is unavailable.
      }
    }

  }

  function startOver() {
    clearStoredSession();
    resetCamera();
    const fresh = createSession();
    setSession(fresh);
    setFinalSession(null);
    setLeftLeg(null);
    setSaveState("idle");
    setSaveError(null);
    savedAssessmentRef.current = null;
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

  async function generatePlan(savedAssessment) {
    if (workflowInFlightRef.current) return;
    workflowInFlightRef.current = true;
    setSaveState("planning");
    setSaveError(null);
    try {
      const result = await runWorkflow({
        idempotencyKey: `assessment-${savedAssessment.sessionId}`,
      });
      clearStoredSession();
      navigate("/plan", {
        replace: true,
        state: { workflowResult: { ...result, available: true }, savedAssessment },
      });
    } catch (error) {
      setSaveState("plan_error");
      setSaveError(error.message || "Your assessment was saved, but your plan could not be prepared.");
    } finally {
      workflowInFlightRef.current = false;
    }
  }

  async function saveAndContinue(candidateSession) {
    if (!candidateSession || saveInFlightRef.current || !signedIn) return;
    saveInFlightRef.current = true;
    setSaveState("saving");
    setSaveError(null);
    try {
      const { saved, workflow } = await saveAssessmentForWorkflow(candidateSession, {
        save: saveAssessment,
        onSaved: (confirmed) => {
          savedAssessmentRef.current = confirmed;
          setFinalSession({
            ...candidateSession,
            sessionId: confirmed.sessionId,
            protocolVersion: confirmed.protocolVersion,
            startedAt: confirmed.startedAt,
            completedAt: confirmed.completedAt,
            tests: confirmed.tests,
            summary: {
              testsCompleted: confirmed.summary?.testsCompleted ?? 0,
              testsInvalid: confirmed.summary?.testsInvalid ?? 0,
              testsSkipped: confirmed.summary?.testsSkipped ?? 0,
              testsNotStarted: confirmed.summary?.testsNotStarted ?? 0,
              hasAnyUsableResult: Boolean(confirmed.summary?.hasAnyUsableResult),
              status: confirmed.summary?.status ?? "NONE_COMPLETED",
            },
          });
          setSaveState(assessmentCompletion(confirmed).complete ? "planning" : "saved_incomplete");
        },
        runWorkflow: async ({ idempotencyKey }) => {
          workflowInFlightRef.current = true;
          try {
            return await runWorkflow({ idempotencyKey });
          } finally {
            workflowInFlightRef.current = false;
          }
        },
      });
      if (!workflow) return;
      clearStoredSession();
      navigate("/plan", {
        replace: true,
        state: { workflowResult: { ...workflow, available: true }, savedAssessment: saved },
      });
    } catch (error) {
      const wasSaved = savedAssessmentRef.current?.sessionId === candidateSession.sessionId;
      setSaveState(wasSaved ? "plan_error" : "idle");
      setSaveError(error.message || "Your results could not be saved.");
    } finally {
      saveInFlightRef.current = false;
    }
  }

  function finishSession(balanceResult) {
    resetCamera();
    const withBalance = withTestResult(session, "balance", balanceResult);
    const finalised = finaliseSession(withBalance);

    setSession(withBalance);
    setFinalSession(finalised);
    setStep(STEP.RESULTS);
    persistSnapshot(withBalance, STEP.RESULTS, { finalSession: finalised });

    if (signedIn) void saveAndContinue(finalised);
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
   * Only the measurements go to the server: the submission helper uses the
   * single stored-payload builder, and it contains no frames or keypoint
   * sequence. A failure is reported as a failure; the results stay
   * on screen so the user does not lose them.
   * Manual save button handler (for retrying if auto-save had an issue or when requested).
   */
  async function handleSave() {
    if (!finalSession || saveState === "saving" || saveState === "planning") return;
    await saveAndContinue(finalSession);
  }

  async function handleRetryPlan() {
    const saved = savedAssessmentRef.current;
    if (saved) await generatePlan(saved);
  }

  function skipToResults() {
    resetCamera();
    let currentSession = session;
    if (!currentSession.tests.shoulder || currentSession.tests.shoulder.status === "not_started") {
      currentSession = withTestResult(currentSession, "shoulder", skippedResult("shoulder"));
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

    if (signedIn) void saveAndContinue(finalised);
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
            onComplete={(result) => recordAndAdvance("shoulder", result, STEP.BALANCE_LEFT)}
            onSkip={() => recordAndAdvance("shoulder", skippedResult("shoulder"), STEP.BALANCE_LEFT)}
            onCameraStateChange={setCameraState}
          />
        )}

        {step === STEP.BALANCE_LEFT && (
          <BalancePanel
            key="balance-left"
            engine={engine}
            supportSide="left"
            onComplete={completeLeftLeg}
            onSkip={() => completeLeftLeg(skippedSide("left"))}
            onCameraStateChange={setCameraState}
          />
        )}

        {step === STEP.BALANCE_RIGHT && (
          <BalancePanel
            key="balance-right"
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
            onRetryPlan={handleRetryPlan}
            onRetake={startOver}
          />
        )}
      </main>
    </div>
  );
}

export default AssessmentPage;
