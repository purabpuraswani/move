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

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getToken } from "../services/auth";
import {
  PLAN_STATES,
  fetchLatestWorkflow,
  planState,
  runWorkflow,
} from "../services/workflow";
import FoodLogPanel from "../components/FoodLogPanel.jsx";
import SpecialistPanel from "../components/SpecialistPanel.jsx";
import BehaviourActionPanel from "../components/BehaviourActionPanel.jsx";

import "./PlanPage.css";

function formatDate(value) {
  if (!value) return null;

  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) return null;

  return parsed.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

/**
 * One section of the plan.
 *
 * `items` are already plain names from the server — exercise names, nutrition
 * topics, habit goals — never ids, and never model text passed straight
 * through.
 */
function PlanSection({ title, blurb, plan, emptyHint, onOpenExercise = null }) {
  if (!plan?.available) {
    return (
      <section className="plan-section plan-section--empty">
        <h2 className="plan-section-title">{title}</h2>
        <p className="plan-empty">{plan?.message || emptyHint}</p>
      </section>
    );
  }

  const items = plan.exercises || plan.goals || [];
  const created = formatDate(plan.created_at);

  return (
    <section className="plan-section">
      <h2 className="plan-section-title">{title}</h2>
      {blurb ? <p className="plan-section-blurb">{blurb}</p> : null}

      {plan.goal ? <p className="plan-goal">{plan.goal}</p> : null}

      {/* Exercises are actionable: each one opens the page that performs it
          with the camera. Nutrition and habit goals are not -- they are things
          to do rather than things to run, so they stay as plain text instead
          of pretending to be buttons. */}
      {onOpenExercise && plan.exercise_items?.length ? (
        <ul className="plan-items">
          {plan.exercise_items.map((exercise) => (
            <li key={exercise.id} className="plan-item plan-item--action">
              <span>{exercise.name}</span>
              <button
                type="button"
                className="plan-item-start"
                onClick={() => onOpenExercise(exercise.id)}
              >
                Start
              </button>
            </li>
          ))}
        </ul>
      ) : items.length > 0 ? (
        <ul className="plan-items">
          {items.map((item) => (
            <li key={item} className="plan-item">
              {item}
            </li>
          ))}
        </ul>
      ) : null}

      {/* Shown only when the plan actually changed, and in the server's own
          words. A plan that was never adapted says nothing here rather than
          inventing a reason. */}
      {plan.adaptation_reason ? (
        <p className="plan-adaptation">
          <span className="plan-adaptation-label">What changed</span>
          {plan.adaptation_reason}
        </p>
      ) : null}

      {created ? <p className="plan-meta">Prepared {created}</p> : null}
    </section>
  );
}

function PlanPage() {
  const navigate = useNavigate();

  const [workflow, setWorkflow] = useState(null);
  const [state, setState] = useState("loading");
  const [error, setError] = useState(null);
  const [building, setBuilding] = useState(false);

  const signedIn = Boolean(getToken());

  const load = useCallback(async () => {
    setState("loading");
    setError(null);

    try {
      const latest = await fetchLatestWorkflow();

      setWorkflow(latest);
      setState("ready");
    } catch (loadError) {
      setError(loadError.message);
      setState("error");
    }
  }, []);

  useEffect(() => {
    if (!signedIn) {
      navigate("/login", { replace: true });

      return;
    }

    load();
  }, [signedIn, navigate, load]);

  const build = useCallback(async () => {
    setBuilding(true);
    setError(null);

    try {
      const result = await runWorkflow();

      setWorkflow(result);
      setState("ready");
    } catch (buildError) {
      setError(buildError.message);
    } finally {
      setBuilding(false);
    }
  }, []);

  const plan = planState(workflow);
  const planExists = plan.state === PLAN_STATES.PLAN_AVAILABLE;
  const specialists = Array.isArray(workflow?.specialists)
    ? workflow.specialists
    : [];

  // The highest plan version any involved specialist reports. Read, never
  // counted in the UI: the version is the backend's record of how many
  // times this plan has actually been rebuilt from evidence.
  const planVersion = specialists.reduce(
    (highest, specialist) => Math.max(highest, specialist.plan_version || 0),
    0,
  );

  return (
    <div className="plan-page">
      <main className="plan-main">
        <div className="plan-intro">
          <span className="plan-eyebrow">Your plan</span>
          <h1 className="plan-title">Your MoveWell plan</h1>
          <p className="plan-lead">
            Prepared from your movement assessment and anything you chose to
            confirm from a health report.
          </p>
          {planVersion ? (
            <p className="plan-version">
              Plan v{planVersion} — your plan changes when what you record
              changes.
            </p>
          ) : null}
        </div>

        {state === "loading" ? <p className="plan-status">Loading your plan…</p> : null}

        {error ? <p className="plan-error">{error}</p> : null}

        {/* State A -- nothing has produced a usable measurement yet. The
            only state in which telling the user to complete their
            assessment is a true statement. */}
        {state === "ready" && plan.state === PLAN_STATES.NEVER_RUN ? (
          <section className="plan-section plan-section--empty">
            <h2 className="plan-section-title">No plan yet</h2>
            <p className="plan-empty">
              {plan.reason ||
                "Once you have completed your movement assessment, your plan can be prepared."}
            </p>
            <div className="plan-actions">
              <button
                type="button"
                className="plan-button"
                onClick={() => navigate(plan.nextAction?.route || "/assessment")}
              >
                {plan.nextAction?.label || "Start the movement assessment"}
              </button>
              <button
                type="button"
                className="plan-button plan-button--quiet"
                onClick={build}
                disabled={building}
              >
                {building ? "Preparing…" : "Prepare my plan"}
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
        plan.state === PLAN_STATES.NO_PLAN_SAFE_OR_SUPPORTED ? (
          <section className="plan-section plan-section--empty">
            <h2 className="plan-section-title">
              No plan was created this time
            </h2>
            <p className="plan-empty">{plan.reason}</p>

            {plan.missing.length > 0 ? (
              <>
                <h3 className="plan-missing-title">
                  What could not be measured
                </h3>
                <ul className="plan-missing">
                  {plan.missing.map((item) => (
                    <li key={item.capability} className="plan-missing-item">
                      <span className="plan-missing-name">
                        {item.capability}
                      </span>
                      {item.reason ? (
                        <span className="plan-missing-reason">
                          {item.reason}
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
                  {plan.nextAction.label}
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

        {state === "ready" && planExists ? (
          <>
            {/* The safety status is the Safety Gate's own plain-language
                verdict. It sits above the plan because it qualifies
                everything below it. */}
            {workflow.safety_status ? (
              <p className="plan-safety">{workflow.safety_status}</p>
            ) : null}

            {/* The specialists who were actually involved, each showing
                what they found, why they were brought in, what they
                decided and what they are watching -- all of it read from
                the server's `specialists` block, which is assembled from
                the persisted agent output. A specialist the Orchestrator
                did not involve is simply absent, rather than present and
                empty. */}
            {specialists.length > 0
              ? specialists.map((specialist) => (
                  <SpecialistPanel
                    key={specialist.title}
                    specialist={specialist}
                    onStartExercise={(id) => navigate(`/exercise/${id}`)}
                    actionSlot={
                      specialist.title === "Daily habits" ? (
                        <BehaviourActionPanel
                          goals={(specialist.focus_items || []).filter(
                            (item) => item.topic_id,
                          ).map((item) => ({
                            topicId: item.topic_id,
                            name: item.name,
                            action: item.action,
                          }))}
                        />
                      ) : null
                    }
                  />
                ))
              : (
                <>
                  {/* An older server that does not send `specialists`
                      still renders a usable plan through the original
                      sections rather than a blank page. */}
                  <PlanSection
                    title="Movement"
                    blurb="Exercises chosen for what your assessment showed."
                    plan={workflow.exercise_plan}
                    emptyHint="No movement plan was needed this time."
                    onOpenExercise={(id) => navigate(`/exercise/${id}`)}
                  />
                  <PlanSection
                    title="Nutrition"
                    blurb="Areas to focus on, not a prescribed diet."
                    plan={workflow.nutrition_plan}
                    emptyHint="No nutrition plan was needed this time."
                  />
                  <PlanSection
                    title="Daily habits"
                    blurb="Small, repeatable things that support the rest."
                    plan={workflow.behaviour_plan}
                    emptyHint="No habit goals were set this time."
                  />
                </>
              )}

            {/* Logging lives on the same page as the plan on purpose: the
                thing you record and the thing you are following should not be
                two separate destinations. */}
            <FoodLogPanel
              planAvailable={Boolean(workflow.nutrition_plan?.available)}
            />

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
