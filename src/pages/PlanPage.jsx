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
import { useNavigate, Link } from "react-router-dom";

import { getToken } from "../services/auth";
import { fetchLatestAssessment } from "../services/assessments";
import {
  PLAN_STATES,
  fetchLatestWorkflow,
  planState,
  runWorkflow,
} from "../services/workflow";
import {
  toArray,
  safeDisplayValue,
  normalizeRecommendation,
  normalizeEvidence,
} from "../services/specialistData.js";
import FoodLogPanel from "../components/FoodLogPanel.jsx";
import SpecialistPanel from "../components/SpecialistPanel.jsx";
import SpecialistExerciseList from "../components/SpecialistExerciseList.jsx";
import useExerciseCompletion from "../hooks/useExerciseCompletion.js";
import BehaviourActionPanel from "../components/BehaviourActionPanel.jsx";
import AppNavigation from "../components/AppNavigation.jsx";

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
function PlanSection({ title, blurb, plan, emptyHint }) {
  const safeTitle = safeDisplayValue(title);
  const safeBlurb = safeDisplayValue(blurb);

  if (!plan?.available) {
    return (
      <section className="plan-section plan-section--empty">
        <h2 className="plan-section-title">{safeTitle}</h2>
        <p className="plan-empty">{safeDisplayValue(plan?.message) || safeDisplayValue(emptyHint)}</p>
      </section>
    );
  }

  const items = toArray(plan.exercises || plan.goals);
  const exerciseItems = toArray(plan.exercise_items);
  const created = formatDate(plan.created_at);
  const safeGoal = safeDisplayValue(plan.goal);
  const safeAdaptation = safeDisplayValue(plan.adaptation_reason);

  return (
    <section className="plan-section">
      <h2 className="plan-section-title">{safeTitle}</h2>
      {safeBlurb ? <p className="plan-section-blurb">{safeBlurb}</p> : null}

      {safeGoal ? <p className="plan-goal">{safeGoal}</p> : null}

      {/* Exercises are actionable: each one opens the page that performs it
          with the camera. Nutrition and habit goals are not -- they are things
          to do rather than things to run, so they stay as plain text instead
          of pretending to be buttons. */}
      {exerciseItems.length ? (
        <ul className="plan-items">
          {exerciseItems.map((exercise, idx) => (
            <li key={exercise?.id || idx} className="plan-item">
              <span>{safeDisplayValue(exercise?.name || exercise?.title)}</span>
            </li>
          ))}
        </ul>
      ) : items.length > 0 ? (
        <ul className="plan-items">
          {items.map((item, idx) => {
            const norm = normalizeRecommendation(item, idx);
            const displayText = safeDisplayValue(
              norm?.title || norm?.action || item,
            );
            return (
              <li key={norm?.id || idx} className="plan-item">
                {displayText}
              </li>
            );
          })}
        </ul>
      ) : null}

      {/* Shown only when the plan actually changed, and in the server's own
          words. A plan that was never adapted says nothing here rather than
          inventing a reason. */}
      {safeAdaptation ? (
        <p className="plan-adaptation">
          <span className="plan-adaptation-label">What changed</span>
          {safeAdaptation}
        </p>
      ) : null}

      {created ? <p className="plan-meta">Prepared {created}</p> : null}
    </section>
  );
}

function PlanPage() {
  // Today's completions, shared with the Movement panel through the one
  // exercise-results API — not a second progress store.
  const completion = useExerciseCompletion();

  const navigate = useNavigate();

  const [workflow, setWorkflow] = useState(null);
  const [latestAssessment, setLatestAssessment] = useState(null);
  const [state, setState] = useState("loading");
  const [error, setError] = useState(null);
  const [building, setBuilding] = useState(false);

  const signedIn = Boolean(getToken());

  const load = useCallback(async () => {
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
        fetchLatestWorkflow().catch((err) => {
          console.warn("fetchLatestWorkflow error:", err);
          return null;
        }),
        fetchLatestAssessment().catch((err) => {
          console.warn("fetchLatestAssessment error:", err);
          return null;
        }),
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
    if (!signedIn) {
      navigate("/login", { replace: true });

      return;
    }

    load();
  }, [signedIn, navigate, load]);

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

  const build = useCallback(async () => {
    setBuilding(true);
    setError(null);

    try {
      const result = await runWorkflow();

      setWorkflow(result);
      if (result?.assessment_summary) {
        setLatestAssessment({ summary: result.assessment_summary });
      }
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

  const localActiveSession = (() => {
    if (typeof window === "undefined" || !window.localStorage) return null;
    try {
      const raw = localStorage.getItem("movewell_active_assessment_session");
      return raw ? JSON.parse(raw) : null;
    } catch (_) {
      return null;
    }
  })();

  const assessSummary =
    workflow?.assessment_summary ||
    latestAssessment?.summary ||
    latestAssessment?.assessment?.summary ||
    localActiveSession?.session?.summary ||
    null;

  const testsCompletedCount =
    assessSummary?.testsCompleted ??
    assessSummary?.tests_completed ??
    0;

  const testsMap =
    workflow?.assessment_summary?.tests ||
    latestAssessment?.tests ||
    latestAssessment?.assessment?.tests ||
    localActiveSession?.session?.tests ||
    {};

  const isShoulderDone =
    (testsMap.shoulder?.status ?? testsMap.shoulder) === "completed";
  const isFtsstDone =
    (testsMap.ftsst?.status ?? testsMap.ftsst) === "completed";
  const isBalanceDone =
    (testsMap.balance?.status ?? testsMap.balance) === "completed";

  const isPartialAssessment = testsCompletedCount > 0 && testsCompletedCount < 3;

  const hasCompletedAssessment =
    testsCompletedCount >= 3 ||
    (isShoulderDone && isFtsstDone && isBalanceDone) ||
    assessSummary?.status === "COMPLETE";

  const hasAssessment =
    hasCompletedAssessment ||
    isPartialAssessment ||
    testsCompletedCount > 0 ||
    Boolean(latestAssessment?.assessment) ||
    (typeof latestAssessment?.total === "number" && latestAssessment.total > 0);

  // The highest plan version any involved specialist reports. Read, never
  // counted in the UI: the version is the backend's record of how many
  // times this plan has actually been rebuilt from evidence.
  const planVersion = specialists.reduce(
    (highest, specialist) => Math.max(highest, specialist.plan_version || 0),
    0,
  );

  const movementSpec = specialists.find(
    (s) => s.title === "Movement" || (s.programme && s.programme.length > 0),
  );
  const nutritionSpec = specialists.find((s) => s.title === "Nutrition");
  const behaviourSpec = specialists.find(
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
      <AppNavigation backTo="/dashboard" backLabel="← Dashboard" />
      <main className="plan-main">
        <div className="plan-breadcrumb">
          <Link
            to="/dashboard"
            className="page-back-link"
            aria-label="Back to Dashboard"
          >
            ← Dashboard
          </Link>
        </div>

        <div className="plan-intro">
          <span className="plan-eyebrow">Your plan</span>
          <h1 className="plan-title">Your MoveWell plan</h1>
          <p className="plan-lead">
            Prepared from your movement assessment and anything you chose to
            confirm from a health report.
          </p>
          {planVersion ? (
            <p className="plan-version">
              Plan v{safeDisplayValue(planVersion)} — your plan changes when what you record
              changes.
            </p>
          ) : null}
        </div>

        {state === "loading" ? <p className="plan-status">Loading your plan…</p> : null}

        {state === "error" && (
          <section className="plan-section plan-section--empty" aria-label="Plan load error">
            <h2 className="plan-section-title">We couldn't load your plan right now</h2>
            <p className="plan-empty">
              {safeDisplayValue(error) || "There was a problem communicating with the service. Your assessment measurements remain safely saved."}
            </p>
            <div className="plan-actions">
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
                onClick={build}
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
            but not all 3 are complete. Shows exact progress and preserves
            saved measurements. Never says no usable measurement exists. */}
        {state === "ready" && !planExists && isPartialAssessment ? (
          <section className="plan-section plan-section--partial" aria-label="Assessment progress">
            <div className="plan-partial-header">
              <span className="plan-partial-badge">Assessment progress</span>
              <h2 className="plan-section-title">Assessment in progress</h2>
              <p className="plan-lead">
                You've completed {safeDisplayValue(testsCompletedCount)} of 3 movement checks. Your completed measurements are saved.
              </p>
              <p className="plan-empty">
                Complete the remaining checks to build a fuller movement profile, or prepare a starter plan from your current measurements.
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

              <div className={`plan-check-row ${isFtsstDone ? "plan-check-row--done" : "plan-check-row--pending"}`}>
                <span className="plan-check-badge">{isFtsstDone ? "✓" : "○"}</span>
                <div className="plan-check-text">
                  <span className="plan-check-name">Sit-to-stand strength (Chair stand)</span>
                  <span className="plan-check-sub">{isFtsstDone ? "Recorded and saved" : (!isShoulderDone ? "Remaining" : "Next check")}</span>
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
              <button
                type="button"
                className="plan-button plan-button--quiet"
                onClick={build}
                disabled={building}
              >
                {building ? "Preparing…" : "Prepare plan from available evidence"}
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

        {state === "ready" && planExists ? (
          <>
            {/* The safety status is the Safety Gate's own plain-language
                verdict. It sits above the plan because it qualifies
                everything below it. */}
            {workflow.safety_status ? (
              <p className="plan-safety">{safeDisplayValue(workflow.safety_status)}</p>
            ) : null}

            {/* Top-Level "Your Today" Coaching Summary */}
            <section className="plan-today-glance" aria-label="Today at a glance">
              <div className="plan-today-header">
                <span className="plan-today-eyebrow">Your Today</span>
                <h2 className="plan-today-title">Today at a Glance</h2>
                <p className="plan-today-lead">
                  MoveWell coordinates your movement, nutrition, and daily habits into one continuous health-coaching program.
                </p>
              </div>

              <div className="plan-today-grid">
                {movementSpec ? (
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
            </section>

            {/* ───────────────── YOUR MOVEWELL TEAM ───────────────── */}
            <section className="plan-team-section" aria-labelledby="team-heading">
              <div className="plan-team-header">
                <span className="plan-team-eyebrow">Your MoveWell Team</span>
                <h2 id="team-heading" className="plan-team-title">Specialist Team Status</h2>
                <p className="plan-team-lead">
                  MoveWell evaluates your movement, health profile, and recovery across 6 specialized clinical domains.
                </p>
              </div>

              <div className="plan-team-grid">
                {/* The six specialist statuses come from the backend's
                    build_specialists_team(), which derives each one from
                    that user's actual evidence. There is deliberately no
                    frontend fallback list: inventing a status here would
                    mean the page could claim a specialist had "evaluated"
                    something it never saw. */}
                {toArray(workflow?.specialists_team).map((specialist, idx) => {
                  const slug =
                    specialist.id === "exercise_activity"
                      ? "exercise"
                      : specialist.id || "physio";
                  const badgeClass =
                    specialist.status === "ACTIVE"
                      ? "plan-team-card-badge--active"
                      : specialist.status === "NOT_ASSESSED"
                      ? "plan-team-card-badge--not-assessed"
                      : "plan-team-card-badge--evaluated";

                  const safeSpecTitle = safeDisplayValue(specialist.title);
                  const safeSpecSubtitle = safeDisplayValue(specialist.subtitle);
                  const safeStatusLabel = safeDisplayValue(
                    specialist.status_label || specialist.status,
                  );
                  const safeReason = safeDisplayValue(
                    specialist.reason || specialist.focus,
                  );
                  const safeIcon = safeDisplayValue(specialist.icon) || "🧑‍⚕️";

                  return (
                    <div key={specialist.id || specialist.title || idx} className="plan-team-card">
                      <div>
                        <div className="plan-team-card-head">
                          <span className="plan-team-card-icon" aria-hidden="true">
                            {safeIcon}
                          </span>
                          <div className="plan-team-card-info">
                            <h3 className="plan-team-card-title">{safeSpecTitle}</h3>
                            <div className="plan-team-card-subtitle">
                              {safeSpecSubtitle}
                            </div>
                          </div>
                        </div>

                        <span className={`plan-team-card-badge ${badgeClass}`}>
                          {safeStatusLabel}
                        </span>

                        <p className="plan-team-card-reason">
                          {safeReason}
                        </p>

                        {/* The exercises this specialist actually
                            recommended, with their own reference image and
                            the existing completion control. Reference and
                            tick-off only — starting a camera session stays
                            on the Movement panel and the exercise page. */}
                        <SpecialistExerciseList
                          exercises={specialist.exercises}
                          completion={completion}
                        />
                      </div>

                      <Link
                        to={`/specialist/${slug}`}
                        className="plan-team-card-link"
                        aria-label={`View ${safeSpecTitle} details`}
                      >
                        Specialist details →
                      </Link>
                    </div>
                  );
                })}
              </div>
            </section>

            {/* The specialists who were actually involved, each showing
                what they found, why they were brought in, what they
                decided and what they are watching -- all of it read from
                the server's `specialists` block, which is assembled from
                the persisted agent output. A specialist the Orchestrator
                did not involve is simply absent, rather than present and
                empty. */}
            {specialists.length > 0
              ? specialists.map((specialist, sIdx) => {
                  let actionSlot = null;
                  if (specialist.title === "Nutrition") {
                    actionSlot = (
                      <FoodLogPanel
                        planAvailable={true}
                        planId={workflow?.id || null}
                      />
                    );
                  } else if (
                    specialist.title === "Daily habits" ||
                    specialist.title === "Behaviour"
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
