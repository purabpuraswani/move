/**
 * Your MoveWell plan.
 *
 * The page answers six questions, in this order, and nothing else:
 *
 *   1. What is this plan about?      — one sentence, from the server
 *   2. Does anything need care?      — the safety review, compact
 *   3. Who is on my team?            — five compact cards, no exercise lists
 *   4. What do I do?                 — the actions, coach by coach
 *   5. Where is nothing known yet?   — the server's own empty state, once each
 *   6. How did this get decided?     — the collaboration flow, then the summary
 *
 * Everything the server sends is still here; what changed is what leads.
 * Statuses, reasoning, evidence and "what is not known yet" live behind each
 * section's "View details", because a person reading their plan wants their
 * actions first and an audit trail second.
 *
 * The page composes nothing. The summary, the five cards, every action button,
 * every empty state and the collaboration steps all come from `unified_plan`
 * (backend/workflow/response.py). Which of the three plan states applies is the
 * server's decision too, read through services/planState.js.
 *
 * There is deliberately no "This week" section: the response carries no weekly
 * structure — no weekday, no session count, no per-week wording — so inventing
 * one would be inventing a schedule. If the server ever sends one, it belongs
 * here, and nowhere before that.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getToken } from "../services/auth";
import { fetchLatestAssessment } from "../services/assessments";
import {
  PLAN_STATES,
  fetchLatestWorkflow,
  planState,
  runWorkflow,
} from "../services/workflow";
import { safeDisplayValue, toArray } from "../services/specialistData.js";
import { identityFor, statusWording } from "../services/specialistIdentity.js";
import {
  actionOf,
  actionSections,
  allSections,
  collaboration,
  habitGoals,
  pendingSections,
  planSummary,
  safetyNeedsAttention,
  sectionPlanId,
  teamCards,
  unifiedPlan,
} from "../services/unifiedPlan.js";
import FoodLogPanel from "../components/FoodLogPanel.jsx";
import BehaviourActionPanel from "../components/BehaviourActionPanel.jsx";
import CollaborationTimeline from "../components/CollaborationTimeline.jsx";
import PlanSectionPanel from "../components/PlanSectionPanel.jsx";
import AppShell from "../components/ui/AppShell.jsx";
import {
  EmptyState,
  PageHeader,
  PrimaryButton,
  SectionHeader,
  StatusBadge,
} from "../components/ui/primitives.jsx";
import useExerciseCompletion from "../hooks/useExerciseCompletion.js";

import "./PlanPage.css";

/** "Oct 1, 2026", or null when the server sent no usable date. */
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
 * How a status the server sent should read.
 *
 * This chooses a colour, never a word: the label is always the server's own.
 * The vocabulary is the team status one (services/specialistIdentity.js), which
 * is what the Safety block uses too.
 */
function toneForStatus(status) {
  switch (status) {
    case "ACTIVE":
    case "REVIEWED":
    case "ALLOW":
      return "active";
    case "MODIFIED":
    case "MODIFY":
    case "PAUSED":
    case "PAUSE":
      return "warn";
    case "REFERRAL":
    case "REFER":
      return "danger";
    default:
      return "muted";
  }
}

/** The focus areas, as the server's own words, in chips. */
function FocusChips({ areas, className = "" }) {
  const list = toArray(areas).filter(Boolean);

  if (!list.length) return null;

  return (
    <ul className={`plan-focus-chips${className ? ` ${className}` : ""}`}>
      {list.map((area, index) => (
        <li key={`${safeDisplayValue(area)}-${index}`} className="mw-chip">
          {safeDisplayValue(area)}
        </li>
      ))}
    </ul>
  );
}

/** One of the five coaches: name, role, status, one reason, and a way in. */
function TeamCard({ card, section, onOpen }) {
  const identity = identityFor(card.id, card.title);
  const status = statusWording(card.team_status, card.team_status_label);
  const route = safeDisplayValue(section?.route);
  const reason =
    safeDisplayValue(section?.short_reason) ||
    safeDisplayValue(card.short_reason) ||
    safeDisplayValue(card.reason);

  return (
    <article className="plan-team-card mw-card mw-card--flat">
      <div className="plan-team-card-head">
        <span className="plan-team-card-icon" aria-hidden="true">
          {safeDisplayValue(identity.icon) || safeDisplayValue(card.icon) || "•"}
        </span>
        <div className="plan-team-card-info">
          <h3 className="plan-team-card-title">{safeDisplayValue(identity.coach)}</h3>
          {identity.role ? <p className="plan-team-card-role">{identity.role}</p> : null}
        </div>
      </div>

      <StatusBadge label={status.label} tone={toneForStatus(card.team_status)} />

      {reason ? <p className="plan-team-card-reason">{reason}</p> : null}

      {route ? (
        <div className="plan-team-card-actions">
          <PrimaryButton size="small" variant="ghost" onClick={() => onOpen(route)}>
            View
          </PrimaryButton>
        </div>
      ) : null}
    </article>
  );
}

function PlanPage() {
  const navigate = useNavigate();

  const [workflow, setWorkflow] = useState(null);
  const [latestAssessment, setLatestAssessment] = useState(null);
  const [state, setState] = useState("loading");
  const [error, setError] = useState(null);
  const [building, setBuilding] = useState(false);

  const signedIn = Boolean(getToken());

  // Today's exercise completions, from the one store both this page and the
  // exercise page write through.
  const completion = useExerciseCompletion({ enabled: signedIn });

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

  const serverPlan = unifiedPlan(workflow);
  const summary = planSummary(workflow);
  const team = teamCards(workflow);
  const actionBlocks = actionSections(workflow);
  const pending = pendingSections(workflow);
  const collab = collaboration(workflow);
  const safety = serverPlan?.safety || null;
  const safetyImportant = safetyNeedsAttention(serverPlan);
  const planVersion = serverPlan?.version || null;
  const generatedAt = formatDate(serverPlan?.generated_at || workflow?.generated_at);

  const handleAction = useCallback(
    (action) => {
      if (action?.anchor) {
        const target = document.querySelector(action.anchor);

        if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });

        return;
      }

      if (action?.route) navigate(action.route);
    },
    [navigate],
  );

  const localActiveSession = (() => {
    if (typeof window === "undefined" || !window.localStorage) return null;
    try {
      const raw = localStorage.getItem("movewell_active_assessment_session");
      return raw ? JSON.parse(raw) : null;
    } catch {
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
    assessSummary?.testsCompleted ?? assessSummary?.tests_completed ?? 0;

  // "Some of it is recorded, but not all of it" — enough to say so, not enough
  // to be the never-started state.
  const isPartialAssessment = testsCompletedCount > 0 && testsCompletedCount < 3;

  /** The recording control for a section, chosen by the server's action kind. */
  const renderSectionExtra = useCallback((section) => {
    const kinds = new Set(
      toArray(section.actions).map((item) => actionOf(item)?.kind).filter(Boolean),
    );

    if (kinds.has("complete_habit")) {
      return (
        <BehaviourActionPanel goals={habitGoals(section)} planId={sectionPlanId(section)} />
      );
    }

    if (kinds.has("log_nutrition")) {
      return <FoodLogPanel planAvailable planId={sectionPlanId(section)} />;
    }

    return null;
  }, []);

  const sections = allSections(workflow);
  const sectionById = (id) =>
    sections.find((entry) => entry?.specialist === id) || null;

  // The Safety review's status, in the words the team card uses for it. The
  // raw code (MODIFY, REFER) is a machine value and never reaches the screen.
  const safetyCard = team.find((card) => card?.id === "safety_practitioner") || null;
  const safetyWording = safetyCard
    ? statusWording(safetyCard.team_status, safetyCard.team_status_label)
    : null;

  const renderPlan = () => (
    <div className="mw-stack plan-flow">
      {/* 2. Safety: a card when it changed something, one quiet line when it did
          not, and never the same paragraph a second time. */}
      {safety ? (
        safetyImportant ? (
          <section className="mw-card plan-safety" aria-label="Safety review">
            <div className="plan-safety-content">
              <div className="mw-row plan-safety-head">
                <StatusBadge
                  label={
                    safetyWording?.label || safeDisplayValue(safety.status)
                  }
                  tone={toneForStatus(safety.status)}
                />
                <h2 className="mw-h3 plan-safety-title">Safety review</h2>
              </div>

              {safety.message ? (
                <p className="mw-lede plan-safety-message">
                  {safeDisplayValue(safety.message)}
                </p>
              ) : null}

              {safety.reason ? (
                <p className="mw-meta plan-safety-reason">
                  {safeDisplayValue(safety.reason)}
                </p>
              ) : null}

              <div className="mw-row">
                <PrimaryButton
                  size="small"
                  onClick={() => navigate("/specialist/safety-practitioner")}
                >
                  View safety guidance
                </PrimaryButton>
              </div>
            </div>
          </section>
        ) : (
          <p className="mw-meta plan-safety-quiet">
            <span aria-hidden="true">🛡️ </span>
            {safeDisplayValue(safety.message) || safeDisplayValue(safety.reason)}
          </p>
        )
      ) : null}

      {/* 3. The team: exactly five compact cards. No exercise lists here — the
          actions are further down, in their own coach's block. */}
      {team.length ? (
        <section className="mw-section">
          <SectionHeader title="Your MoveWell team" />
          <div className="mw-grid mw-grid--team">
            {team.map((card, index) => (
              <TeamCard
                key={card?.id || card?.title || index}
                card={card}
                section={sectionById(card?.id)}
                onOpen={(route) => navigate(route)}
              />
            ))}
          </div>
        </section>
      ) : null}

      {/* 4. The actions, coach by coach: actions, one line of reason, details. */}
      {actionBlocks.length ? (
        <section className="mw-section plan-today">
          <SectionHeader title="Today" />
          <div className="mw-stack">
            {actionBlocks.map((section) => (
              <PlanSectionPanel
                key={section.specialist}
                section={section}
                onAction={handleAction}
                renderSectionExtra={renderSectionExtra}
                completion={completion}
              />
            ))}
          </div>
        </section>
      ) : null}

      {/* 5. Where nothing is known yet: once per part of the plan, with the
          action that would give it something. */}
      {pending.length ? (
        <section className="mw-section">
          <SectionHeader title="Still to assess" />
          <div className="mw-grid mw-grid--two">
            {pending.map((section) => (
              <PlanSectionPanel
                key={section.specialist}
                section={section}
                onAction={handleAction}
                completion={completion}
              />
            ))}
          </div>
        </section>
      ) : null}

      {/* 6. How it was decided. */}
      <CollaborationTimeline collaboration={collab} onAction={handleAction} />

      {/* The summary: what this plan is for, and what happens next. */}
      {summary ? (
        <section className="mw-card mw-card--tint plan-synthesis">
          <h2 className="mw-h3 plan-synthesis-title">Your MoveWell summary</h2>

          <FocusChips areas={summary.focus_areas} className="plan-synthesis-focus" />

          {summary.next ? (
            <div className="plan-synthesis-next mw-stack mw-stack--tight">
              <span className="mw-eyebrow">Next</span>
              <p className="mw-lede">{safeDisplayValue(summary.next)}</p>
            </div>
          ) : null}
        </section>
      ) : null}

      <div className="mw-row plan-actions">
        <PrimaryButton onClick={build} disabled={building}>
          {building ? "Checking…" : "Check for an updated plan"}
        </PrimaryButton>
        <PrimaryButton variant="ghost" onClick={() => navigate("/progress")}>
          See your progress
        </PrimaryButton>
      </div>
    </div>
  );

  return (
    <AppShell>
      <div className="mw-main plan-main">
        <PageHeader
          eyebrow="Your plan"
          title="Your MoveWell plan"
          lead={
            state === "ready" && (planExists || team.length > 0)
              ? safeDisplayValue(summary?.headline)
              : safeDisplayValue(plan.reason)
          }
        >
          {state === "ready" && (planExists || team.length > 0) ? (
            <FocusChips areas={summary?.focus_areas} />
          ) : null}

          {planVersion || generatedAt ? (
            <p className="mw-meta plan-version">
              {planVersion ? `Plan version ${safeDisplayValue(planVersion)}` : null}
              {planVersion && generatedAt ? " · " : null}
              {generatedAt ? `prepared ${generatedAt}` : null}
            </p>
          ) : null}
        </PageHeader>

        {state === "loading" ? (
          <p className="mw-meta mw-loading">
            {safeDisplayValue(workflow?.message) || "Loading your plan…"}
          </p>
        ) : null}

        {state === "error" ? (
          <EmptyState
            title="We couldn't load your plan right now"
            why={
              safeDisplayValue(error) ||
              "Your assessment measurements remain safely saved."
            }
            tone="warn"
            action={<PrimaryButton onClick={load}>Try again</PrimaryButton>}
          />
        ) : null}

        {state === "ready" && planExists && isPartialAssessment ? (
          <EmptyState
            title={`${testsCompletedCount} of 3 checks recorded`}
            why={safeDisplayValue(plan.reason)}
            action={
              <div className="mw-row">
                <PrimaryButton onClick={() => navigate("/assessment")}>
                  Continue assessment
                </PrimaryButton>
                <PrimaryButton variant="ghost" onClick={build} disabled={building}>
                  {building ? "Preparing…" : "Prepare a plan from what is recorded"}
                </PrimaryButton>
              </div>
            }
          />
        ) : null}

        {state === "ready" && !planExists && !isPartialAssessment ? (
          <EmptyState
            title="No plan to follow yet"
            why={safeDisplayValue(plan.reason)}
            action={
              plan.nextAction ? (
                <PrimaryButton onClick={() => navigate(plan.nextAction.route)}>
                  {safeDisplayValue(plan.nextAction.label)}
                </PrimaryButton>
              ) : null
            }
          />
        ) : null}

        {state === "ready" && planExists ? renderPlan() : null}
      </div>
    </AppShell>
  );
}

export default PlanPage;
