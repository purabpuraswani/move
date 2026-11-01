/**
 * Your MoveWell plan — one plan, not three agent replies.
 *
 * This is the screen the final MoveWell journey ends at, and it replaces the
 * legacy guidance page as the place a user reads what to do. The important
 * difference is not visual. On the old page two agents were named and their
 * outputs shown side by side, which made the user's job to reconcile them. On
 * this one the server has already decided which specialists were needed, run
 * only those, combined their approved output and passed it through the Safety
 * Gate — so what arrives here is a single plan, and it is presented as one.
 *
 * Attribution still exists; it is just not the user's problem. The server
 * keeps source_agent on every recommendation for audit, and the internal
 * dashboard shows it. Nothing on this page names an agent, a workflow, an MCP
 * server or a tool call, and the API response deliberately does not contain
 * them (backend/workflow/response.py).
 *
 * Where a section is empty, it says so plainly rather than hiding. "No
 * nutrition plan yet" is information; a missing section is just confusing.
 *
 * The same principle, one level up, is why this page has three empty
 * states rather than one. It used to have a single "No plan yet" block
 * telling every user without a plan to go and complete the assessment they
 * had in fact already completed. Which of the three applies is the
 * server's decision (backend/workflow/response.py), read here through
 * services/planState.js; this page never infers it and never writes the
 * explanation itself.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";

import { getToken } from "../services/auth";
import { fetchLatestAssessment } from "../services/assessments";
import { fetchProfileSummary } from "../services/profile.js";
import {
  PLAN_STATES,
  fetchLatestWorkflow,
  planState,
  runWorkflow,
} from "../services/workflow";
import {
  profileChangedSinceWorkflow as isProfileNewerThanWorkflow,
  shouldGenerateWorkflowForAssessment,
  workflowMatchesAssessment,
} from "../services/planState.js";
import { measuredResultsForAssessment, measurementValue } from "../services/assessmentDisplay.js";
import {
  toArray,
  safeDisplayValue,
  normalizeRecommendation,
  selectedInterventionAgentIds,
  agentIdForSpecialistCard,
} from "../services/specialistData.js";
import FoodLogPanel from "../components/FoodLogPanel.jsx";
import SpecialistPanel from "../components/SpecialistPanel.jsx";
import BehaviourActionPanel from "../components/BehaviourActionPanel.jsx";
import { getExerciseImage } from "../movementDemos/exerciseImages.js";
import AppNavigation from "../components/AppNavigation.jsx";

import "./PlanPage.css";

function completionLabel(value) {
  if (value === "COMPLETED") return "Completed";
  if (value === "NOT_RECORDED" || !value) return "Not recorded yet";
  return safeDisplayValue(String(value).replaceAll("_", " "));
}

function PlanPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const navigationResult = location.state?.workflowResult ?? null;
  const workflowKeyRef = useRef(null);
  const autoRunKeyRef = useRef(null);

  const [workflow, setWorkflow] = useState(() => navigationResult);
  const [latestAssessment, setLatestAssessment] = useState(() =>
    location.state?.savedAssessment ? { assessment: location.state.savedAssessment, total: 1 } : null
  );
  const [profileUpdatedAt, setProfileUpdatedAt] = useState(null);
  const [state, setState] = useState(() => navigationResult ? "ready" : "loading");
  const [error, setError] = useState(null);
  const [building, setBuilding] = useState(false);

  const signedIn = Boolean(getToken());

  const load = useCallback(async () => {
    autoRunKeyRef.current = null;
    if (typeof window !== "undefined" && window.__mockWorkflow) {
      setWorkflow(window.__mockWorkflow);
      if (window.__mockWorkflow.assessment_summary) {
        setLatestAssessment({ summary: window.__mockWorkflow.assessment_summary });
      }
      setState("ready");
      return;
    }

    setState("loading");
    setError(null);

    try {
      const [latestWf, latestAssess] = await Promise.all([
        fetchLatestWorkflow(),
        fetchLatestAssessment(),
      ]);

      if (typeof window !== "undefined" && window.__mockWorkflow) return;
      setWorkflow(latestWf);
      setLatestAssessment(latestAssess);
      setState("ready");
    } catch (loadError) {
      if (typeof window !== "undefined" && window.__mockWorkflow) return;
      setError(loadError.message || "We couldn't load your plan right now.");
      setState("error");
    }
  }, []);

  useEffect(() => {
    if (!signedIn) return;
    fetchProfileSummary().then((summary) => setProfileUpdatedAt(summary.updatedAt)).catch(() => {});
  }, [signedIn]);

  useEffect(() => {
    if (!signedIn) {
      navigate("/login", { replace: true });

      return;
    }

    if (navigationResult) return;
    load();
  }, [signedIn, navigate, load, navigationResult]);

  useEffect(() => {
    window.__setPlanWorkflow = (wf, assess = null) => {
      window.__mockWorkflow = wf;
      setWorkflow(wf);
      if (assess !== null) {
        setLatestAssessment(assess);
      } else if (wf?.assessment_summary) {
        setLatestAssessment({ summary: wf.assessment_summary });
      } else {
        setLatestAssessment(null);
      }
      setError(null);
      setState("ready");
    };
    return () => {
      delete window.__setPlanWorkflow;
    };
  }, []);

  const build = useCallback(async (options = {}) => {
    setBuilding(true);
    setState("building");
    setError(null);

    if (!workflowKeyRef.current) {
      workflowKeyRef.current = options.idempotencyKey
        || globalThis.crypto?.randomUUID?.()
        || `plan-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    }

    try {
      const result = await runWorkflow({ idempotencyKey: workflowKeyRef.current });

      setWorkflow({ ...result, available: true });
      if (result?.assessment_summary) {
        setLatestAssessment((current) => current?.assessment
          ? current
          : { summary: result.assessment_summary });
      }
      workflowKeyRef.current = null;
      setState("ready");
    } catch (buildError) {
      setError(buildError.message || "The workflow could not be completed.");
      setState("error");
    } finally {
      setBuilding(false);
    }
  }, []);

  useEffect(() => {
    if (state !== "ready" || building) return;
    const saved = latestAssessment?.assessment;
    if (!shouldGenerateWorkflowForAssessment(workflow, saved)) return;

    const key = `assessment-${saved.sessionId}`;
    if (autoRunKeyRef.current === key) return;
    autoRunKeyRef.current = key;
    workflowKeyRef.current = key;
    void build({ idempotencyKey: key });
  }, [state, building, latestAssessment, workflow, build]);

  const rawPlan = planState(workflow);
  const workflowMatchesLatest = workflowMatchesAssessment(workflow, latestAssessment?.assessment);
  const plan = workflowMatchesLatest
    ? rawPlan
    : {
        state: PLAN_STATES.NEVER_RUN,
        reason: "The latest saved assessment has not yet been processed into a workflow result.",
        nextAction: { route: "/assessment", label: "Complete the movement assessment" },
        missing: [],
      };
  const planExists = plan.state === PLAN_STATES.PLAN_AVAILABLE || plan.state === PLAN_STATES.STARTER_GUIDANCE_AVAILABLE;
  const profileChangedSinceWorkflow = Boolean(workflow?.available && isProfileNewerThanWorkflow(profileUpdatedAt, workflow?.workflow_created_at));
  const planIsCurrent = planExists && !profileChangedSinceWorkflow;
  const starterGuidanceAvailable = plan.state === PLAN_STATES.STARTER_GUIDANCE_AVAILABLE
    || (!workflow?.exercise_plan?.available && toArray(workflow?.agent_journey)
      .find(agent => agent.id === "physio")?.selection_status === "SELECTED – CONTEXT REQUIRED");
  const physioJourney = toArray(workflow?.agent_journey).find(agent => agent.id === "physio");
  const physioTeam = toArray(workflow?.specialists_team).find(specialist => specialist.id === "physio");
  const physioNeedsHealthInformation = physioTeam?.health_screen_status === "INCOMPLETE"
    && toArray(physioTeam?.health_screen_missing_information).length > 0;
  const activeAgentIds = profileChangedSinceWorkflow ? new Set() : selectedInterventionAgentIds(workflow);
  const teamActiveIds = new Set(toArray(workflow?.specialists_team)
    .filter((item) => item?.status === "ACTIVE")
    .map((item) => item.id));
  const visibleAgentIds = new Set([...activeAgentIds].filter((id) => teamActiveIds.has(id)));
  const unifiedActivities = toArray(workflow?.unified_plan?.activities)
    .filter((item) => visibleAgentIds.has(item?.responsible_specialist));
  const trackingTasks = toArray(workflow?.unified_plan?.tracking_tasks)
    .filter((item) => visibleAgentIds.has(item?.responsible_specialist));
  const clarificationAgentIds = new Set(Object.entries(profileChangedSinceWorkflow ? {} : workflow?.selection_explanations || {})
    .filter(([, explanation]) => explanation?.selection_status === "SELECTED – CONTEXT REQUIRED")
    .map(([agentId]) => agentId));
  const clarificationTasks = toArray(workflow?.unified_plan?.clarification_tasks)
    .filter((item) => clarificationAgentIds.has(item?.specialist));
  const specialists = Array.isArray(workflow?.specialists)
    ? workflow.specialists
    : [];
  const contextRequired = Object.entries(profileChangedSinceWorkflow ? {} : workflow?.selection_explanations || {})
    .filter(([, explanation]) => explanation?.selection_status === "SELECTED – CONTEXT REQUIRED")
    .map(([agentId, explanation]) => ({ agentId, ...explanation }));

  const assessSummary =
    latestAssessment?.assessment?.summary || latestAssessment?.summary || null;

  const testsMap =
    latestAssessment?.assessment?.tests || latestAssessment?.tests || {};

  const isShoulderDone =
    (testsMap.shoulder?.status ?? testsMap.shoulder) === "completed";
  const isBalanceDone =
    (testsMap.balance?.status ?? testsMap.balance) === "completed";

  // Derive progress from the active checks so a historical summary cannot
  // keep the current flow incomplete.
  const hasActiveTestStatuses = Object.prototype.hasOwnProperty.call(testsMap, "shoulder")
    || Object.prototype.hasOwnProperty.call(testsMap, "balance");
  const summaryCompletedCount = assessSummary?.testsCompleted ?? assessSummary?.tests_completed ?? 0;
  const activeTestsCompletedCount = hasActiveTestStatuses
    ? [isShoulderDone, isBalanceDone].filter(Boolean).length
    : Math.min(2, summaryCompletedCount);
  const testsTotal = 2;
  const measuredResults = measuredResultsForAssessment(
    latestAssessment?.assessment,
    latestAssessment?.assessment ? null : latestAssessment?.summary || workflow?.assessment_summary,
  );

  const isPartialAssessment = activeTestsCompletedCount > 0 && activeTestsCompletedCount < testsTotal;

  const hasCompletedAssessment =
    activeTestsCompletedCount === testsTotal;

  const hasAssessment =
    hasCompletedAssessment ||
    isPartialAssessment ||
    activeTestsCompletedCount > 0 ||
    Boolean(latestAssessment?.assessment) ||
    (typeof latestAssessment?.total === "number" && latestAssessment.total > 0);

  // The highest plan version any involved specialist reports. Read, never
  // counted in the UI: the version is the backend's record of how many
  // times this plan has actually been rebuilt from evidence.
  const activeSpecialists = specialists.filter((specialist) => {
    const agentId = agentIdForSpecialistCard(specialist);
    return agentId && visibleAgentIds.has(agentId);
  });
  const planVersion = activeSpecialists.reduce(
    (highest, specialist) => Math.max(highest, specialist.plan_version || 0),
    0,
  );

  const movementSpec = activeSpecialists.find(
    (s) => s.title === "Movement" || (s.programme && s.programme.length > 0),
  );
  const nutritionSpec = activeSpecialists.find((s) => s.title === "Nutrition" || s.title === "Nutrition & Lifestyle");
  const behaviourSpec = activeSpecialists.find(
    (s) => s.title === "Daily habits" || s.title === "Behaviour",
  );
  const totalExercises =
    movementSpec?.programme?.length ||
    workflow?.exercise_plan?.exercise_count ||
    0;

  const nutritionTodayDesc = (() => {
    if (!nutritionSpec) return "";
    const firstToday = toArray(nutritionSpec.today)[0];
    if (firstToday) {
      const norm = normalizeRecommendation(firstToday);
      const text = safeDisplayValue(norm?.action || norm?.title || firstToday);
      if (text) return text;
    }
    return (
      safeDisplayValue(nutritionSpec.goal) ||
      "Log meals as you eat to provide authentic intake evidence."
    );
  })();

  const behaviourTodayDesc = (() => {
    if (!behaviourSpec) return "";
    const firstToday = toArray(behaviourSpec.today)[0];
    if (firstToday) {
      const norm = normalizeRecommendation(firstToday);
      const text = safeDisplayValue(norm?.action || norm?.title || firstToday);
      if (text) return text;
    }
    return (
      safeDisplayValue(behaviourSpec.goal) ||
      "Track today's habit and share how it felt."
    );
  })();

  return (
    <div className="plan-page">
      <AppNavigation showBack={false} />
      <main className="plan-main">
        <div className="plan-intro">
          <span className="plan-eyebrow">Your plan</span>
          <h1 className="plan-title">Your MoveWell plan</h1>
          <p className="plan-lead">
            Prepared using your saved movement assessment and profile answers.
            Information you have not provided stays unknown.
          </p>
          {planVersion ? (
            <p className="plan-version">
              Plan v{safeDisplayValue(planVersion)} — your plan changes when what you record
              changes.
            </p>
          ) : null}
        </div>

        {state === "loading" ? <p className="plan-status">Loading your plan…</p> : null}
        {state === "building" ? (
          <p className="plan-status" role="status" aria-live="polite">
            Assessment saved. MoveWell is selecting relevant specialists and executing the required workflow and safety checks…
          </p>
        ) : null}

        {state === "ready" && profileChangedSinceWorkflow ? (
          <section className="plan-section plan-section--empty" aria-label="Plan needs updating">
            <h2 className="plan-section-title">Your profile changed after this plan was prepared</h2>
            <p className="plan-empty">Saved recommendations are paused until they are reviewed against your updated answers. Your measurements and previous plan history are preserved.</p>
            <div className="plan-actions">
              <Link className="plan-button plan-button--quiet" to="/profile">Review your profile</Link>
              <button type="button" className="plan-button" onClick={() => build()} disabled={building}>
                {building ? "Preparing…" : "Prepare an updated plan"}
              </button>
            </div>
          </section>
        ) : null}

        {state === "ready" && contextRequired.length > 0 ? (
          <section className="plan-section plan-section--empty" aria-label="More information needed">
            <h2 className="plan-section-title">More information needed for some recommendations</h2>
            <p className="plan-empty">These specialists were reviewed. Their dedicated pages explain what is known and what information is still needed before a personalized plan can be prepared.</p>
            <ul className="plan-missing">
              {contextRequired.map((item) => (
                <li className="plan-missing-item" key={item.agentId}>
                  <span className="plan-missing-name">{safeDisplayValue(item.agent_identifier || item.agentId)}</span>
                  <span className="plan-missing-reason">
                    {toArray(item.missing_required_information).map(safeDisplayValue).join(", ")}
                  </span>
                  <Link to="/profile">Update profile →</Link>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {state === "ready" && planIsCurrent && physioNeedsHealthInformation ? (
          <section className="plan-section plan-section--empty" aria-label="Physiotherapy information needed">
            <h2 className="plan-section-title">Information needed before exercise recommendations</h2>
            <p className="plan-empty">Your movement assessment raised a Physiotherapy review. Personalized exercises are deferred while the health-screen answers below remain unknown. No exercise has been presented as approved.</p>
            {toArray(physioJourney?.evidence).length > 0 ? <ul className="plan-items">{physioJourney.evidence.map((item, index) => <li className="plan-item" key={index}>{safeDisplayValue(item)}</li>)}</ul> : null}
            <p className="plan-empty">Still unknown: {toArray(physioTeam.health_screen_missing_information).map(safeDisplayValue).join(", ")}</p>
            <Link to="/profile">Complete the health screen →</Link>
          </section>
        ) : null}

        {state === "error" && (
          <section className="plan-section plan-section--empty" aria-label="Plan load error">
            <h2 className="plan-section-title">We couldn't prepare your plan right now</h2>
            <p className="plan-empty">
              {safeDisplayValue(error) || "There was a problem communicating with the service. Your assessment measurements remain safely saved."}
            </p>
            <div className="plan-actions">
              <button type="button" className="plan-button plan-button--quiet" onClick={() => navigate("/exercise-library")}>Browse exercise library</button>
              <button type="button" className="plan-button plan-button--quiet" onClick={() => navigate("/daily-tracking")}>Record today’s activity, nutrition & recovery</button>
              <button
                type="button"
                className="plan-button"
                onClick={load}
              >
                Try again
              </button>
            </div>
          </section>
        )}

        {/* State 1 -- NO ASSESSMENT EXISTS
            Display: "No movement assessment yet"
                     "Complete your movement assessment before preparing a plan."
                     [ Start assessment ] */}
        {state === "ready" &&
        !planExists &&
        !isPartialAssessment &&
        !hasAssessment &&
        plan.state === PLAN_STATES.NEVER_RUN ? (
          <section className="plan-section plan-section--empty" aria-label="No movement assessment">
            <h2 className="plan-section-title">No movement assessment yet</h2>
            <p className="plan-empty">
              Complete your movement assessment before preparing a plan.
            </p>
            <div className="plan-actions">
              <button
                type="button"
                className="plan-button"
                onClick={() => navigate(plan.nextAction?.route || "/assessment")}
              >
                Start assessment
              </button>
            </div>
          </section>
        ) : null}

        {/* State 2 -- ASSESSMENT EXISTS + PLAN NEVER RUN
            Display: "No plan yet"
                     "Your movement assessment is saved and ready."
                     "Prepare your personalized MoveWell plan based on your latest assessment results."
                     [ Prepare my plan ] */}
        {state === "ready" &&
        !planExists &&
        !isPartialAssessment &&
        hasCompletedAssessment &&
        plan.state === PLAN_STATES.NEVER_RUN ? (
          <section className="plan-section plan-section--empty" aria-label="Assessment ready">
            <h2 className="plan-section-title">No plan yet</h2>
            <p className="plan-lead">
              Your movement assessment is saved and ready.
            </p>
            <p className="plan-empty">
              Prepare your personalized MoveWell plan based on your latest assessment results.
            </p>
            <div className="plan-actions">
              <button
                type="button"
                className="plan-button"
                onClick={() => build()}
                disabled={building}
              >
                {building ? "Preparing…" : "Prepare my plan"}
              </button>
            </div>
          </section>
        ) : null}

        {/* State A fallback -- assessment attempted but no usable measurements */}
        {state === "ready" &&
        !planExists &&
        !isPartialAssessment &&
        hasAssessment &&
        !hasCompletedAssessment &&
        plan.state === PLAN_STATES.NEVER_RUN ? (
          <section className="plan-section plan-section--empty" aria-label="Assessment unusable">
            <h2 className="plan-section-title">No plan yet</h2>
            <p className="plan-empty">
              {safeDisplayValue(plan.reason) ||
                "No movement assessment has produced a usable measurement yet, so there is nothing to build a plan from."}
            </p>
            <div className="plan-actions">
              <button
                type="button"
                className="plan-button"
                onClick={() => navigate(plan.nextAction?.route || "/assessment")}
              >
                {safeDisplayValue(plan.nextAction?.label) || "Redo the movement assessment"}
              </button>
            </div>
          </section>
        ) : null}

        {/* State PARTIAL -- at least one valid assessment measurement exists,
            but not both active checks are complete. Shows exact progress and preserves
            saved measurements. Never says no usable measurement exists. */}
        {state === "ready" && !planExists && isPartialAssessment ? (
          <section className="plan-section plan-section--partial" aria-label="Assessment progress">
            <div className="plan-partial-header">
              <span className="plan-partial-badge">Assessment progress</span>
              <h2 className="plan-section-title">Assessment in progress</h2>
              <p className="plan-lead">
                You've completed {safeDisplayValue(activeTestsCompletedCount)} of {testsTotal} movement checks. Your completed measurements are saved.
              </p>
              <p className="plan-empty">
                Complete the remaining checks before a personalized plan can be generated.
              </p>
            </div>

            <div className="plan-partial-checklist">
              <div className={`plan-check-row ${isShoulderDone ? "plan-check-row--done" : "plan-check-row--pending"}`}>
                <span className="plan-check-badge">{isShoulderDone ? "✓" : "○"}</span>
                <div className="plan-check-text">
                  <span className="plan-check-name">Upper-body mobility (Shoulder raise)</span>
                  <span className="plan-check-sub">{isShoulderDone ? "Recorded and saved" : "Remaining"}</span>
                </div>
              </div>

              <div className={`plan-check-row ${isBalanceDone ? "plan-check-row--done" : "plan-check-row--pending"}`}>
                <span className="plan-check-badge">{isBalanceDone ? "✓" : "○"}</span>
                <div className="plan-check-text">
                  <span className="plan-check-name">Standing balance (One-leg stand)</span>
                  <span className="plan-check-sub">{isBalanceDone ? "Recorded and saved" : "Remaining"}</span>
                </div>
              </div>
            </div>

            <div className="plan-actions">
              <button
                type="button"
                className="plan-button"
                onClick={() => navigate("/assessment")}
              >
                Continue assessment →
              </button>
            </div>
          </section>
        ) : null}

        {/* State C -- the workflow ran against real evidence and produced
            no plan. This is a result, and it is reported as one: what could
            not be measured, in Need Assessment's own words, and the single
            thing that would change the answer. It never says the
            assessment has not been done. */}
        {state === "ready" &&
        plan.state === PLAN_STATES.NO_PLAN_SAFE_OR_SUPPORTED &&
        !isPartialAssessment ? (
          <section className="plan-section plan-section--empty">
            <h2 className="plan-section-title">
              No plan was created this time
            </h2>
            <p className="plan-empty">{safeDisplayValue(plan.reason)}</p>

            {toArray(plan.missing).length > 0 ? (
              <>
                <h3 className="plan-missing-title">
                  What could not be measured
                </h3>
                <ul className="plan-missing">
                  {toArray(plan.missing).map((item, idx) => (
                    <li key={item?.capability || idx} className="plan-missing-item">
                      <span className="plan-missing-name">
                        {safeDisplayValue(item?.capability || item)}
                      </span>
                      {item?.reason ? (
                        <span className="plan-missing-reason">
                          {safeDisplayValue(item.reason)}
                        </span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </>
            ) : null}

            <div className="plan-actions">
              {plan.nextAction ? (
                <button
                  type="button"
                  className="plan-button"
                  onClick={() => navigate(plan.nextAction.route)}
                >
                  {safeDisplayValue(plan.nextAction.label)}
                </button>
              ) : null}
              <button
                type="button"
                className="plan-button plan-button--quiet"
                onClick={build}
                disabled={building}
              >
                {building ? "Checking…" : "Check again"}
              </button>
            </div>
          </section>
        ) : null}

        {state === "ready" && !profileChangedSinceWorkflow && unifiedActivities.length ? (
          <section className="plan-section" aria-label="Unified wellness plan">
            <h2 className="plan-section-title">Your unified wellness plan</h2>
            <p className="plan-lead">Start with the activities and recommendations below. Personalized recommendations have passed the final Safety Gate; general maintenance activities are clearly labelled.</p>
            <ul className="plan-unified-activities">
              {unifiedActivities.map((activity) => (
                <li key={activity.id}>
                  {activity.exercise_id && getExerciseImage(activity.exercise_id) ? <img className="plan-exercise-ref-image" src={getExerciseImage(activity.exercise_id).src} alt={getExerciseImage(activity.exercise_id).alt} /> : null}
                  <strong>{safeDisplayValue(activity.title)}</strong>
                  <span>{safeDisplayValue(activity.specialist_name)}</span>
                  {activity.instruction ? <p>{safeDisplayValue(activity.instruction)}</p> : null}
                  {activity.reason ? <p>{safeDisplayValue(activity.reason)}</p> : null}
                  {activity.frequency ? <p><strong>Frequency / dosage:</strong> {safeDisplayValue(activity.frequency)}</p> : null}
                  {toArray(activity.evidence).length ? <p><strong>Evidence:</strong> {activity.evidence.map(safeDisplayValue).join("; ")}</p> : null}
                  {toArray(activity.instructions).length ? <details><summary>Instructions</summary><ol>{activity.instructions.map((step, index) => <li key={index}>{safeDisplayValue(step)}</li>)}</ol></details> : null}
                  {toArray(activity.equipment).length ? <p><strong>Equipment:</strong> {activity.equipment.map(safeDisplayValue).join(", ")}</p> : null}
                  {toArray(activity.safety_notes).length ? <p><strong>Safety / limitations:</strong> {activity.safety_notes.map(safeDisplayValue).join("; ")}</p> : null}
                  <small>{activity.type === "personalized_recommendation" ? "Safety Gate approved · personalized" : "General maintenance · not personalized"} · {completionLabel(activity.completion_state)}</small>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {state === "ready" && !profileChangedSinceWorkflow && trackingTasks.length ? (
          <section className="plan-section" aria-label="Supporting tracking tasks">
            <h2 className="plan-section-title">Supporting tracking tasks</h2>
            <p className="plan-lead">These records help specialists review your next plan. They are separate from activities to follow.</p>
            <ul className="plan-unified-activities">{trackingTasks.map((task, index) => <li key={task.id || index}>
              <strong>{safeDisplayValue(task.title || task.action)}</strong>
              <span>{safeDisplayValue(task.specialist_name)}</span>
              {task.instruction || task.action ? <p>{safeDisplayValue(task.instruction || task.action)}</p> : null}
              {task.reason ? <p>{safeDisplayValue(task.reason)}</p> : null}
              <small>Tracking task · {completionLabel(task.completion_state)}</small>
            </li>)}</ul>
          </section>
        ) : null}

        {state === "ready" && !profileChangedSinceWorkflow && clarificationTasks.length ? (
          <section className="plan-section" aria-label="Clarification tasks">
            <h2 className="plan-section-title">Information needed before personalization</h2>
            <ul>{clarificationTasks.map((task, index) => <li key={`${task.specialist}-${index}`}><strong>{safeDisplayValue(task.specialist)}:</strong> {safeDisplayValue(task.information)} <Link to="/profile">Update information →</Link></li>)}</ul>
          </section>
        ) : null}

        {state === "ready" && planIsCurrent ? (
          <>
            {/* The safety status is the Safety Gate's own plain-language
                verdict. It sits above the plan because it qualifies
                everything below it. */}
            {workflow.safety_status ? (
              <p className="plan-safety">{safeDisplayValue(workflow.safety_status)}</p>
            ) : null}

            <section className="plan-section" aria-label="Plan overview">
              <h2 className="plan-section-title">What MoveWell learned</h2>
              <p className="plan-section-blurb">Your plan uses your saved profile, completed movement checks, and recorded activity. Missing information stays unknown.</p>
              {assessSummary ? <div>
                <strong>Latest movement session · {assessSummary.tests_completed ?? assessSummary.testsCompleted ?? 0} of 2 checks complete</strong>
                {Object.keys(measuredResults).length ? <ul className="plan-items">{Object.entries(measuredResults).map(([test, result]) => <li key={test} className="plan-item">
                  <strong>{test === "shoulder" ? "Shoulder Raise" : "One-Leg Stand"}:</strong>{" "}
                  {Object.entries(result.measurements || {}).filter(([side]) => ["left", "right"].includes(side)).map(([side, value]) => {
                    const measured = measurementValue(test, value);
                    return measured == null ? null : `${side}: ${new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(measured)} ${result.unit || ""}`;
                  }).filter(Boolean).join(" · ") || "No usable measurement in this saved session."}
                </li>)}</ul> : <p>No usable measurements are available in the latest session yet.</p>}
              </div> : <p>No movement assessment has been saved yet.</p>}
              {unifiedActivities.length > 0 ? <p>Current plan focus: {safeDisplayValue(unifiedActivities.slice(0, 3).map(item => item.title).filter(Boolean).join(" · "))}</p> : null}
            </section>

            {/* Top-Level "Your Today" Coaching Summary */}
            {activeSpecialists.length > 0 ? <section className="plan-today-glance" aria-label="Today at a glance">
              <div className="plan-today-header">
                <span className="plan-today-eyebrow">Your Today</span>
                <h2 className="plan-today-title">Today at a Glance</h2>
                <p className="plan-today-lead">
                  MoveWell coordinates your movement, nutrition, and daily habits into one continuous health-coaching program.
                </p>
              </div>

              <div className="plan-today-grid">
                {movementSpec && (!starterGuidanceAvailable || totalExercises > 0) ? (
                  <div className="plan-today-card plan-today-card--movement">
                    <div className="plan-today-card-head">
                      <span className="plan-today-card-badge plan-today-card-badge--movement">
                        Movement • Physio
                      </span>
                      <span className="plan-today-card-stat">
                        {totalExercises} {totalExercises === 1 ? "exercise" : "exercises"}
                      </span>
                    </div>
                    <h3 className="plan-today-card-title">Prescribed Movement</h3>
                    <p className="plan-today-card-desc">
                      {safeDisplayValue(movementSpec.goal) || "Targeted exercises selected for your physical capability profile."}
                    </p>
                    <a href="#specialist-movement" className="plan-today-card-link">
                      View exercises ↓
                    </a>
                  </div>
                ) : null}

                {nutritionSpec ? (
                  <div className="plan-today-card plan-today-card--nutrition">
                    <div className="plan-today-card-head">
                      <span className="plan-today-card-badge plan-today-card-badge--nutrition">
                        Nutrition focus • Nutrition
                      </span>
                    </div>
                    <h3 className="plan-today-card-title">Nutrition & Meals</h3>
                    <p className="plan-today-card-desc">
                      {nutritionTodayDesc}
                    </p>
                    <a href="#specialist-nutrition" className="plan-today-card-link">
                      Log a meal ↓
                    </a>
                  </div>
                ) : null}

                {behaviourSpec ? (
                  <div className="plan-today-card plan-today-card--behaviour">
                    <div className="plan-today-card-head">
                      <span className="plan-today-card-badge plan-today-card-badge--behaviour">
                        Daily habits • Behaviour
                      </span>
                    </div>
                    <h3 className="plan-today-card-title">Daily Habit Action</h3>
                    <p className="plan-today-card-desc">
                      {behaviourTodayDesc}
                    </p>
                    <a href="#specialist-daily-habits" className="plan-today-card-link">
                      Record habit ↓
                    </a>
                  </div>
                ) : null}
              </div>
            </section> : null}

            <section className="plan-section" aria-labelledby="specialist-plans-title">
              <h2 id="specialist-plans-title" className="plan-section-title">Your Specialist Plans</h2>
              {activeSpecialists.length > 0
              ? activeSpecialists.map((specialist, sIdx) => {
                  let actionSlot = null;
                  if (agentIdForSpecialistCard(specialist) === "nutrition") {
                    actionSlot = (
                      <FoodLogPanel
                        planAvailable={true}
                        planId={workflow?.id || null}
                      />
                    );
                  } else if (
                    agentIdForSpecialistCard(specialist) === "behaviour"
                  ) {
                    const focusItems = toArray(specialist.focus_items);
                    const goals = focusItems
                      .map((item, idx) => {
                        const norm = normalizeRecommendation(item, idx);
                        const topicId = item?.topic_id || norm?.id;
                        const name = safeDisplayValue(norm?.title || item?.name);
                        const action = safeDisplayValue(norm?.action || item?.action);
                        return { topicId, name, action };
                      })
                      .filter((g) => g.topicId && (g.name || g.action));

                    actionSlot = (
                      <BehaviourActionPanel
                        goals={goals}
                        planId={workflow?.id || null}
                      />
                    );
                  }

                  return (
                    <SpecialistPanel
                      key={specialist?.id || specialist?.title || sIdx}
                      specialist={specialist}
                      actionSlot={actionSlot}
                    />
                  );
                })
              : <p className="plan-empty">No specialist-specific activities were selected from the information available this time. Your saved measurements and history remain available in Progress.</p>}
            </section>

            <div className="plan-actions">
              <button
                type="button"
                className="plan-button plan-button--quiet"
                onClick={build}
                disabled={building}
              >
                {building ? "Checking…" : "Check for an updated plan"}
              </button>
              <button
                type="button"
                className="plan-button plan-button--quiet"
                onClick={() => navigate("/progress")}
              >
                See your progress
              </button>
            </div>
          </>
        ) : null}
      </main>
    </div>
  );
}

export default PlanPage;
