/**
 * TODAY — the first screen of MoveWell.
 *
 * The page answers seven questions, in this order, and nothing else:
 *
 *   1. Who is this for?              — a greeting, and one true sentence
 *   2. How am I doing?               — the MoveWell Score, one number
 *   3. What matters today?           — at most three of the plan's actions
 *   4. What has changed?             — the score change, and the movers
 *   5. Who is working on this?       — the five coaches, compact
 *   6. How far through am I?         — what is recorded, from the plan's items
 *   7. Does anything need care?      — the safety review, only when it did
 *
 * Everything a person reads here is read from the server
 * (backend/workflow/response.py) through the readers in src/services. This file
 * composes: it chooses order and emphasis. It never computes a score, a trend, a
 * percentage or a status, and where the server sent nothing it says so instead
 * of filling the gap in.
 *
 * The only two things here that are not the server's own: the time of day in
 * the greeting (the clock), and the fixed labels that name what the server sent
 * ("MoveWell Score", "Today's focus", "Plan progress") — the same kind of label
 * every other screen in the product uses.
 *
 * The day's actions are the plan screen's own action card
 * (components/PlanActionItem.jsx), reused deliberately: it already resolves the
 * item's dosage, its server-decided button and today's self-report tick, so
 * Today cannot show a different dosage or a different button from the plan it
 * came from.
 */

import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import PlanActionItem from "../components/PlanActionItem.jsx";
import AppShell from "../components/ui/AppShell.jsx";
import ScoreDial from "../components/ui/ScoreDial.jsx";
import {
  DetailDrawer,
  EmptyState,
  Field,
  PageHeader,
  PrimaryButton,
  SectionHeader,
  StatusBadge,
} from "../components/ui/primitives.jsx";
import useExerciseCompletion from "../hooks/useExerciseCompletion.js";

import { fetchLatestAssessment } from "../services/assessments";
import { getToken } from "../services/auth";
import { fetchProfile } from "../services/profile";
import {
  domainChanges,
  focusStatement,
  hasScore,
  movewellScore,
  scoreChange,
  scoreFocus,
  scoreMessage,
  scoreMethod,
} from "../services/score.js";
import { safeDisplayValue, toArray } from "../services/specialistData.js";
import { identityFor, statusWording } from "../services/specialistIdentity.js";
import {
  actionSections,
  allSections,
  emptyStateOf,
  itemActions,
  pendingSections,
  planItems,
  planSummary,
  safetyNeedsAttention,
  teamCards,
  trackingOf,
  unifiedPlan,
} from "../services/unifiedPlan.js";
import { PLAN_STATES, fetchLatestWorkflow, planState } from "../services/workflow";

import "./TodayPage.css";

/** The three tracking statuses a plan item can carry (workflow/response.py). */
const TRACKING_COMPLETED = "COMPLETED";
const TRACKING_RECORDED = "RECORDED";
const TRACKING_NOT_RECORDED = "NOT_RECORDED";

/** How many of the plan's actions the day shows. The plan screen has the rest. */
const FOCUS_LIMIT = 3;

/** The greeting, from the clock. The only thing on this page not from data. */
function greetingFor(hour) {
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";

  return "Good evening";
}

/**
 * The account's own name, first word only, or null.
 *
 * The name lives in the profile's `basic` section (backend/routes/profile.py),
 * and is absent far more often than not — a missing name is not an error, and
 * the greeting simply does not use one.
 */
function firstNameOf(profile) {
  const basic = toArray(profile?.sections).find(
    (section) => section?.key === "basic",
  );
  const field = toArray(basic?.fields).find((entry) => entry?.key === "name");
  const name = safeDisplayValue(field?.value);

  if (typeof name !== "string") return null;

  return name.split(/\s+/)[0] || null;
}

/** "+8" for a rise, "-3" for a fall, "0" for no movement. */
function signedNumber(value) {
  if (typeof value !== "number") return null;

  return `${value > 0 ? "+" : ""}${value}`;
}

/** The item's own tracking status, or null when it carries none. */
function trackingStatusOf(item) {
  const status = trackingOf(item)?.status;

  return typeof status === "string" ? status : null;
}

/**
 * The day's actions: the first items of the plan, in the server's own order
 * (services/unifiedPlan.js::actionSections). Never re-ordered, and never
 * completed with an action the server did not send.
 */
function todaysFocus(workflow, limit) {
  return actionSections(workflow)
    .flatMap((section) =>
      itemActions(section).map((item) => ({ section, item })),
    )
    .slice(0, limit);
}

/** Those items gathered under the coach who asked for them, in the same order. */
function byCoach(entries) {
  const groups = [];

  for (const entry of entries) {
    const last = groups[groups.length - 1];

    if (last && last.section.specialist === entry.section.specialist) {
      last.items.push(entry.item);
    } else {
      groups.push({ section: entry.section, items: [entry.item] });
    }
  }

  return groups;
}

/**
 * One block of the page, named for screen readers by its own heading.
 *
 * The visible heading is the shared SectionHeader; the element
 * `aria-labelledby` points at is the small wrapper around it, because
 * SectionHeader's `<h2>` takes no id of its own. Pointing at the wrapper gives
 * the region exactly the heading's words — nothing added.
 */
function TodaySection({ id, title, className = "", children }) {
  return (
    <section
      className={`mw-section${className ? ` ${className}` : ""}`}
      aria-labelledby={id}
    >
      <div id={id}>
        <SectionHeader title={title} />
      </div>
      {children}
    </section>
  );
}

function TodayPage() {
  const navigate = useNavigate();

  // A harness that has handed this page a recorded response (the same
  // `window.__mockWorkflow` the plan screen reads) gets the day on the first
  // frame, instead of a flash of the loading state before the effect runs.
  const mocked =
    typeof window !== "undefined" ? window.__mockWorkflow || null : null;

  const [workflow, setWorkflow] = useState(mocked);
  const [profile, setProfile] = useState(null);
  const [assessment, setAssessment] = useState(null);
  const [state, setState] = useState(mocked ? "ready" : "loading");
  const [error, setError] = useState(null);

  const signedIn = Boolean(getToken());

  // Today's completions, from the one store this page and the exercise page
  // both write through — so the tick beside an exercise is the real record.
  const completion = useExerciseCompletion({ enabled: signedIn });

  const load = useCallback(async () => {
    if (typeof window !== "undefined" && window.__mockWorkflow) {
      setWorkflow(window.__mockWorkflow);
      setState("ready");
      return;
    }

    setState("loading");
    setError(null);

    try {
      const [latestWorkflow, latestProfile, latestAssessment] = await Promise.all([
        // The day itself: if this cannot be read, the page says so.
        fetchLatestWorkflow(),
        // The greeting's name, and whether an assessment has ever been
        // recorded. Both are additions to the day, so neither is allowed to
        // take the day down with it.
        fetchProfile().catch((profileError) => {
          console.warn("fetchProfile error:", profileError);
          return null;
        }),
        fetchLatestAssessment().catch((assessmentError) => {
          console.warn("fetchLatestAssessment error:", assessmentError);
          return null;
        }),
      ]);

      if (typeof window !== "undefined" && window.__mockWorkflow) return;

      setWorkflow(latestWorkflow);
      setProfile(latestProfile);
      setAssessment(latestAssessment);
      setState("ready");
    } catch (loadError) {
      if (typeof window !== "undefined" && window.__mockWorkflow) return;

      setError(loadError.message || "We couldn't load your day right now.");
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

  // The same test hook the plan screen exposes, so a harness can render this
  // page from a recorded response without a backend.
  useEffect(() => {
    if (typeof window === "undefined") return undefined;

    window.__setTodayWorkflow = (nextWorkflow) => {
      window.__mockWorkflow = nextWorkflow;
      setWorkflow(nextWorkflow);
      setError(null);
      setState("ready");
    };

    return () => {
      delete window.__setTodayWorkflow;
    };
  }, []);

  /**
   * Where a plan item's own button goes.
   *
   * The label, the route and the kind are the server's (item.action). A
   * `panel` action — logging a meal, recording a habit — has no route of its
   * own: the panel that records it is composed on the plan screen, which is
   * where the server's own anchors point (`#specialist-…`), so the day sends
   * the user there rather than pretending to record it here.
   */
  const handleAction = useCallback(
    (action) => {
      if (action?.anchor) {
        const target = document.querySelector(action.anchor);

        if (target) {
          target.scrollIntoView({ behavior: "smooth", block: "start" });

          return;
        }

        navigate("/plan");

        return;
      }

      if (action?.route) {
        navigate(action.route);

        return;
      }

      navigate("/plan");
    },
    [navigate],
  );

  const plan = planState(workflow);
  const serverPlan = unifiedPlan(workflow);
  const summary = planSummary(workflow);
  const sections = allSections(workflow);
  const team = teamCards(workflow);
  const items = planItems(workflow);
  const movers = domainChanges(workflow);
  const change = scoreChange(workflow);
  const focus = scoreFocus(workflow);
  const method = scoreMethod(workflow);

  const scored = hasScore(workflow);
  const scoreValue = scored ? movewellScore(workflow).value : null;
  const message = scored ? safeDisplayValue(scoreMessage(workflow)) : null;

  const safety = serverPlan?.safety || null;
  const safetyImportant = safetyNeedsAttention(serverPlan);

  const sectionById = (id) =>
    sections.find((section) => section?.specialist === id) || null;

  const assessmentSummary =
    workflow?.assessment_summary ||
    assessment?.assessment?.summary ||
    assessment?.summary ||
    null;
  const testsCompleted =
    typeof assessmentSummary?.tests_completed === "number"
      ? assessmentSummary.tests_completed
      : 0;
  const hasAssessment =
    testsCompleted > 0 ||
    Boolean(assessment?.assessment) ||
    (typeof assessment?.total === "number" && assessment.total > 0);

  // "Nothing has been measured yet, and no assessment is recorded": the only
  // state in which the day is an invitation rather than a set of numbers.
  const newHere = plan.state === PLAN_STATES.NEVER_RUN && !hasAssessment;

  const greeting = greetingFor(new Date().getHours());
  const firstName = firstNameOf(profile);

  const lead = (() => {
    if (plan.state === PLAN_STATES.NEVER_RUN) {
      // There is no plan headline worth repeating yet: either the assessment
      // was recorded and is waiting to be built from, which the server says in
      // its own words, or nothing has been measured and the day says so.
      return hasAssessment
        ? safeDisplayValue(plan.reason)
        : "Start with your movement assessment — it is what your plan is built from.";
    }

    return (
      safeDisplayValue(summary?.headline) ||
      focusStatement(workflow) ||
      safeDisplayValue(plan.reason)
    );
  })();

  const focusGroups = byCoach(todaysFocus(workflow, FOCUS_LIMIT));

  // What to say when the plan has nothing for today. The server says it first,
  // for whichever part of the plan is still waiting on the user.
  const focusEmpty = (() => {
    const waiting = pendingSections(workflow)[0] || null;

    if (waiting) {
      const identity = identityFor(waiting.specialist, waiting.title);
      const empty = emptyStateOf(waiting);

      return {
        icon: identity.icon,
        title: identity.coach,
        why: safeDisplayValue(empty?.message),
        action: empty?.action || null,
      };
    }

    return {
      icon: null,
      title: "Nothing to do today",
      why: safeDisplayValue(plan.reason),
      action: plan.nextAction || null,
    };
  })();

  const changeFrom =
    change && typeof change.from === "number" ? change.from : null;
  const changeTo = typeof scoreValue === "number" ? scoreValue : null;
  const changeLine = change
    ? change.value === 0
      ? "no change since your previous assessment"
      : `${signedNumber(change.value)} since your previous assessment`
    : null;

  const totalActions = items.length;
  const completedActions = items.filter(
    (item) => trackingStatusOf(item) === TRACKING_COMPLETED,
  ).length;
  const recordedActions = items.filter((item) => {
    const status = trackingStatusOf(item);

    return status === TRACKING_COMPLETED || status === TRACKING_RECORDED;
  }).length;
  const recordedSections = sections.filter(
    (section) =>
      itemActions(section).length > 0 &&
      section?.tracking?.status &&
      section.tracking.status !== TRACKING_NOT_RECORDED,
  );
  const anythingRecorded = recordedActions > 0 || recordedSections.length > 0;

  const safetySection = sectionById("safety_practitioner");
  const safetyCard =
    team.find((card) => card?.id === "safety_practitioner") || null;
  const safetyWording = statusWording(
    safetySection?.team_status,
    safetySection?.team_status_label || safetyCard?.status_label,
  );

  const renderDay = () => (
    <div className="mw-stack today-flow">
      {/* 2. The score: one number, its own sentence, and the change when there
          is a previous assessment to compare it with. */}
      <TodaySection
        id="today-score"
        title="MoveWell Score"
        className="mw-card today-score"
      >
        <div className="today-score-body">
          <ScoreDial value={scoreValue} label="Your MoveWell Score" />

          {scored ? (
            <>
              {message ? (
                <p className="mw-lede today-score-message">{message}</p>
              ) : null}

              {focus ? (
                <p className="today-score-focus">
                  Current focus: <strong>{safeDisplayValue(focus.label)}</strong>
                </p>
              ) : null}

              {changeLine ? (
                <p className="today-change">
                  {changeFrom !== null && changeTo !== null
                    ? `${changeFrom} → ${changeTo} · `
                    : null}
                  {changeLine}
                </p>
              ) : null}
            </>
          ) : (
            <>
              <p className="mw-lede today-score-message">
                Complete your assessment to understand your current state.
              </p>
              <PrimaryButton onClick={() => navigate("/assessment")}>
                Start assessment
              </PrimaryButton>
            </>
          )}
        </div>

        {method ? (
          <DetailDrawer label="How this is worked out">
            <p className="mw-lede">{safeDisplayValue(method)}</p>
          </DetailDrawer>
        ) : null}
      </TodaySection>

      {/* 3. Today's focus: at most three of the plan's own actions, in its own
          order, each under the coach who asked for it. */}
      <TodaySection id="today-focus" title="Today's focus">
        {focusGroups.length ? (
          <>
            {focusGroups.map((group) => {
              const identity = identityFor(
                group.section.specialist,
                group.section.title,
              );

              return (
                <div key={group.section.specialist} className="today-focus-group">
                  <p className="today-focus-coach">
                    <span aria-hidden="true">
                      {safeDisplayValue(identity.icon) || "•"}
                    </span>
                    {safeDisplayValue(identity.coach)}
                  </p>

                  <ul className="plan-item-list today-focus-list">
                    {group.items.map((item, index) => (
                      <PlanActionItem
                        key={`${item.item_id || item.kind || "item"}-${
                          item.position ?? index
                        }`}
                        item={item}
                        onAction={handleAction}
                        completion={completion}
                      />
                    ))}
                  </ul>
                </div>
              );
            })}

            <Link className="mw-section-link" to="/plan">
              View plan
            </Link>
          </>
        ) : (
          <EmptyState
            icon={focusEmpty.icon}
            title={focusEmpty.title}
            why={focusEmpty.why}
            action={
              focusEmpty.action ? (
                <PrimaryButton onClick={() => handleAction(focusEmpty.action)}>
                  {safeDisplayValue(focusEmpty.action.label)}
                </PrimaryButton>
              ) : (
                <PrimaryButton onClick={() => navigate("/plan")}>
                  View plan
                </PrimaryButton>
              )
            }
          />
        )}
      </TodaySection>

      {/* 4. Your progress: two real measurements compared, or an honest "not
          yet". A zero-change is reported as no change, never as progress. */}
      {newHere ? null : (
        <TodaySection id="today-progress" title="Your progress">
          {changeLine ? (
            <div className="mw-stack mw-stack--tight">
              <p className="today-progress-values">
                {changeFrom !== null && changeTo !== null
                  ? `${changeFrom} → ${changeTo}`
                  : changeLine}
              </p>
              {changeFrom !== null && changeTo !== null ? (
                <p className="mw-lede">{changeLine}</p>
              ) : null}
            </div>
          ) : null}

          {movers.length ? (
            <ul className="today-movers">
              {movers.map((move) => (
                <li key={move.key || move.label}>
                  <Field
                    label={safeDisplayValue(move.label)}
                    value={signedNumber(move.change)}
                  />
                </li>
              ))}
            </ul>
          ) : null}

          {!changeLine && !movers.length ? (
            <EmptyState
              title="Complete another assessment to see your progress."
              action={
                <PrimaryButton onClick={() => navigate("/assessment")}>
                  Start reassessment
                </PrimaryButton>
              }
            />
          ) : null}
        </TodaySection>
      )}

      {/* 5. The team: five compact cards, and no exercise lists — the actions
          are above, under their own coach. */}
      {team.length ? (
        <TodaySection id="today-team" title="Your MoveWell team">
          <ul className="mw-grid mw-grid--team today-team">
            {team.map((card, index) => {
              const section = sectionById(card?.id);
              const identity = identityFor(card?.id, card?.title);
              const wording = statusWording(
                section?.team_status,
                section?.team_status_label,
              );
              const route =
                safeDisplayValue(section?.route) || safeDisplayValue(card?.route);
              const reason = safeDisplayValue(section?.short_reason);
              const specialistRole = identity.role || safeDisplayValue(card?.subtitle);

              const body = (
                <>
                  <span className="today-team-head">
                    <span className="today-team-icon" aria-hidden="true">
                      {safeDisplayValue(identity.icon) ||
                        safeDisplayValue(card?.icon) ||
                        "•"}
                    </span>
                    <span className="today-team-name">
                      {safeDisplayValue(identity.coach)}
                    </span>
                  </span>

                  {specialistRole ? (
                    <span className="mw-meta today-team-role">
                      {specialistRole}
                    </span>
                  ) : null}

                  <StatusBadge label={wording.label} tone={wording.tone} />

                  {reason ? (
                    <span className="today-team-reason">{reason}</span>
                  ) : null}
                </>
              );

              return (
                <li
                  key={card?.id || card?.title || index}
                  className="today-team-item"
                >
                  {route ? (
                    <Link
                      className="mw-card mw-card--flat today-team-card"
                      to={route}
                    >
                      {body}
                    </Link>
                  ) : (
                    <div className="mw-card mw-card--flat today-team-card">
                      {body}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </TodaySection>
      ) : null}

      {/* 6. Plan progress: counted from the items' own tracking, and from each
          section's, in the server's words. No percentage is computed here. */}
      <TodaySection id="today-plan" title="Plan progress">
        {totalActions === 0 ? (
          <p className="mw-lede">There are no actions in your plan yet.</p>
        ) : anythingRecorded ? (
          <p className="today-plan-count">
            Today's plan — {completedActions} of {totalActions} actions completed
          </p>
        ) : (
          <p className="mw-lede">
            Nothing has been recorded against your plan yet.
          </p>
        )}

        {recordedSections.length ? (
          <div className="today-plan-tracking">
            {recordedSections.map((section) => (
              <Field
                key={section.specialist}
                label={section.title}
                value={section.tracking.label}
              />
            ))}
          </div>
        ) : null}

        <Link className="mw-section-link" to="/plan">
          View plan
        </Link>
      </TodaySection>

      {/* 7. Safety: only when the verdict changed something. An approved plan
          says nothing here at all. */}
      {safetyImportant && safety ? (
        <TodaySection
          id="today-safety"
          title="Safety review"
          className="mw-card today-safety"
        >
          <div className="mw-row">
            <StatusBadge label={safetyWording.label} tone={safetyWording.tone} />
          </div>

          {safety.message ? (
            <p className="mw-lede">{safeDisplayValue(safety.message)}</p>
          ) : null}

          <div className="mw-row">
            <Link
              className="mw-btn mw-btn--primary"
              to="/specialist/safety-practitioner"
            >
              View safety guidance
            </Link>
          </div>
        </TodaySection>
      ) : null}
    </div>
  );

  return (
    <AppShell>
      <div className="mw-main mw-main--narrow today-page mw-stack">
        <PageHeader
          eyebrow="Today"
          title={firstName ? `${greeting}, ${firstName}` : greeting}
          lead={state === "ready" ? lead : null}
        />

        {state === "loading" ? (
          <p className="mw-loading">Loading your day…</p>
        ) : null}

        {state === "error" ? (
          <EmptyState
            tone="warn"
            title="We couldn't load your day right now"
            why={
              safeDisplayValue(error) ||
              "Your plan and your assessment are safe — this was a problem reading them."
            }
            action={<PrimaryButton onClick={load}>Try again</PrimaryButton>}
          />
        ) : null}

        {state === "ready" ? renderDay() : null}
      </div>
    </AppShell>
  );
}

export default TodayPage;
