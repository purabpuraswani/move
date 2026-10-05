/**
 * One specialist's page — one of the five coaches, opened up.
 *
 * The page reads the matching section out of the server's `unified_plan`, so it
 * shows exactly what the plan screen shows for this specialist and nothing that
 * the server did not send: why they are involved, what they are focused on, what
 * they decided, the actions themselves, what has been recorded, and the next
 * step. There is no per-specialist copy in this file — no default rationale, no
 * fallback recommendation list, no "clinical focus" paragraph shown to everybody
 * whatever their evidence. A specialist who was not assessed gets the server's
 * own empty state and the action that would assess it.
 *
 * The page is arranged the way a person reads a coach, not the way a system
 * reports one: who this is, why they are here, what they are working on, what
 * they decided, what to do, what it produced, and what happens next. The audit
 * trail — the evidence behind the decision, what is still unknown, the plan
 * version and why it was adapted — lives behind one "View details".
 *
 * An unrecognised specialist in the URL is reported as unrecognised, with a link
 * back to the plan, rather than being silently redirected to one of the five and
 * showing that one's evidence under the wrong heading.
 */

import { Component, useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import AppShell from "../components/ui/AppShell.jsx";
import {
  PrimaryButton,
  SectionHeader,
  StatusBadge,
  EmptyState,
  DetailDrawer,
} from "../components/ui/primitives.jsx";
import BehaviourActionPanel from "../components/BehaviourActionPanel.jsx";
import FoodLogPanel from "../components/FoodLogPanel.jsx";
import PlanActionItem from "../components/PlanActionItem.jsx";
import useExerciseCompletion from "../hooks/useExerciseCompletion.js";
import { fetchLatestWorkflow } from "../services/workflow";
import { identityFor, statusWording } from "../services/specialistIdentity.js";
import { safeDisplayValue, toArray } from "../services/specialistData.js";
import {
  actionOf,
  canonicalSpecialistId,
  collaboration,
  emptyStateOf,
  habitGoals,
  itemActions,
  sectionFor,
  sectionPlanId,
  teamCards,
} from "../services/unifiedPlan.js";

import "./SpecialistDetailPage.css";

/* -------------------------------------------------------------------------
   Reading the server's section without adding anything to it
   ------------------------------------------------------------------------- */

/** The per-item rows the server sent, minus the ones that only say there is
 * nothing there yet. `NOT_RECORDED` and `NOT_ENOUGH_DATA` are real values, but
 * printing the phrase "nothing recorded" against every item is the repetition
 * this screen exists to avoid — the section says it once, in its own words. */
function usefulRows(rows) {
  return toArray(rows)
    .filter((row) => row && safeDisplayValue(row.label) && safeDisplayValue(row.value))
    .filter((row) => !/nothing recorded|not enough|no .*recorded/i.test(String(row.value)))
    .map((row) => ({ label: safeDisplayValue(row.label), value: safeDisplayValue(row.value) }));
}

/**
 * A line of the server's tracking or progress wording, or null when it is one of
 * the two values that mean "there is nothing to report here": the screen should
 * say nothing rather than print `NOT_RECORDED` or `NOT_ENOUGH_DATA` in words.
 */
function usefulText(status, value) {
  if (status === "NOT_RECORDED" || status === "NOT_ENOUGH_DATA") return null;

  const text = safeDisplayValue(value);

  if (!text) return null;
  if (/^nothing recorded|^no .*recorded yet|not enough .* to compare/i.test(text)) return null;

  return text;
}

function Rows({ rows }) {
  const list = usefulRows(rows);

  if (!list.length) return null;

  return (
    <dl className="specialist-rows">
      {list.map((row, index) => (
        <div className="specialist-row" key={`${row.label}-${index}`}>
          <dt className="specialist-row-label">{row.label}</dt>
          <dd className="specialist-row-value">{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** The constraints from somewhere else that apply to this specialist's domain.
 * A constraint whose `applies_to` names this specialist IS the collaboration —
 * there is nothing to infer and nothing to add when it does not. */
function constraintsFor(plan, specialistId) {
  return toArray(plan?.constraints).filter((constraint) => {
    if (!constraint || !constraint.source || constraint.source === specialistId) return false;

    const applies = Array.isArray(constraint.applies_to)
      ? constraint.applies_to
      : [constraint.applies_to];

    return applies.includes(specialistId);
  });
}

/* -------------------------------------------------------------------------
   The page
   ------------------------------------------------------------------------- */

export class SpecialistErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("SpecialistDetailPage rendering error caught by boundary:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <AppShell backTo="/plan" backLabel="Your plan">
          <div className="mw-main specialist-main">
            <div className="mw-card specialist-error-fallback" role="alert">
              <h1 className="mw-h2">This specialist could not be shown</h1>
              <p className="mw-lede">
                There was a problem preparing this specialist&rsquo;s page. Your
                assessment, answers and recorded sessions are unaffected.
              </p>
              <div className="mw-row">
                <Link className="mw-btn mw-btn--primary" to="/plan">
                  Back to your plan
                </Link>
              </div>
            </div>
          </div>
        </AppShell>
      );
    }

    return this.props.children;
  }
}

/**
 * The page itself. `workflow` is optional and exists so the page can be
 * rendered against a known plan — the same server shape — without reaching for
 * the network. In the product it is never passed and the plan is fetched on
 * mount, exactly as before.
 */
export function SpecialistDetailPageInner({ workflow: providedWorkflow = null }) {
  const { specialistType } = useParams();
  const navigate = useNavigate();

  const canonical = canonicalSpecialistId(specialistType);

  const [workflow, setWorkflow] = useState(providedWorkflow);
  const [state, setState] = useState(providedWorkflow ? "ready" : "loading");

  const completion = useExerciseCompletion();

  useEffect(() => {
    if (!providedWorkflow) {
      let mounted = true;

      fetchLatestWorkflow()
        .then((data) => {
          if (!mounted) return;
          setWorkflow(data);
          setState("ready");
        })
        .catch(() => {
          if (mounted) setState("error");
        });

      return () => {
        mounted = false;
      };
    }

    return undefined;
  }, [providedWorkflow]);

  /** Follow the action the server put on an item: its route when there is one,
   * the anchor it names otherwise. Nothing here decides where an action goes. */
  const handleAction = useCallback(
    (action) => {
      if (!action) return;

      if (action.route) {
        navigate(action.route);
        return;
      }

      if (action.anchor && typeof document !== "undefined") {
        document.querySelector(action.anchor)?.scrollIntoView({ behavior: "smooth" });
      }
    },
    [navigate],
  );

  /** The recording panels, for the two sections whose actions are records rather
   * than a route: a habit completed, a meal logged. */
  const renderSectionExtra = useCallback((target) => {
    const kinds = new Set(
      itemActions(target)
        .map((item) => actionOf(item)?.kind)
        .filter(Boolean),
    );

    if (kinds.has("complete_habit")) {
      return (
        <BehaviourActionPanel goals={habitGoals(target)} planId={sectionPlanId(target)} />
      );
    }

    if (kinds.has("log_nutrition")) {
      return <FoodLogPanel planAvailable planId={sectionPlanId(target)} />;
    }

    return null;
  }, []);

  /* No specialist by that name ------------------------------------------- */

  if (!canonical) {
    return (
      <AppShell backTo="/plan" backLabel="Your plan">
        <div className="mw-main specialist-main">
          <div className="mw-stack mw-enter">
            <div className="mw-card specialist-error-fallback" role="alert">
              <h1 className="mw-h1">No specialist by that name</h1>
              <p className="mw-lede">
                MoveWell has five specialists — Exercise &amp; Movement,
                Nutrition &amp; Lifestyle, Behaviour &amp; Adherence, Recovery
                &amp; Care, and Safety &amp; Practitioner Recommendation. This
                link does not name one of them, so there is nothing to show
                rather than something guessed at.
              </p>
              <div className="mw-row">
                <Link className="mw-btn mw-btn--primary" to="/plan">
                  See your plan
                </Link>
              </div>
            </div>
          </div>
        </div>
      </AppShell>
    );
  }

  /* Loading -------------------------------------------------------------- */

  if (state === "loading") {
    return (
      <AppShell backTo="/plan" backLabel="Your plan">
        <div className="mw-main specialist-main">
          <p className="mw-lede mw-loading">Loading this specialist…</p>
        </div>
      </AppShell>
    );
  }

  /* Ready ---------------------------------------------------------------- */

  const section = sectionFor(workflow, canonical);
  const card = teamCards(workflow).find((entry) => entry.id === canonical) || null;
  const plan = workflow?.unified_plan || null;

  const identity = identityFor(canonical, section?.title || card?.title);
  const teamStatus = section?.team_status || card?.team_status;
  const wording = statusWording(teamStatus, section?.team_status_label || card?.team_status_label);

  const actions = itemActions(section);
  const emptyState = emptyStateOf(section);
  const missing = toArray(section?.missing).map(safeDisplayValue).filter(Boolean);
  const evidence = toArray(section?.evidence).map(safeDisplayValue).filter(Boolean);

  const tracking = section?.tracking || null;
  const progress = section?.progress || null;
  const trackingLabel = usefulText(tracking?.status, tracking?.label);
  const progressLabel = usefulText(progress?.direction, progress?.label);
  const progressRows = usefulRows(progress?.rows);
  const progressMeta = progress?.plan_version
    ? `Plan version ${safeDisplayValue(progress.plan_version)}`
    : null;

  const involved = Boolean(section?.selected);
  const constraints = involved && section ? constraintsFor(plan, section.specialist) : [];

  /** This specialist's own step in the collaboration flow. `participated` is the
   * server's word for whether it contributed this cycle — the page uses it to
   * say "not part of this plan" rather than presenting a quiet domain as a
   * decision. */
  const collaborationStep =
    collaboration(workflow)?.steps?.find(
      (step) => step.kind === "specialist" && step.specialist === section?.specialist,
    ) || null;
  const contributed = collaborationStep ? Boolean(collaborationStep.participated) : involved;

  const hasDetails = Boolean(
    evidence.length || missing.length || progressMeta || progress?.adaptation_reason,
  );

  const accentClass = identity.accent ? `specialist-accent-${identity.accent}` : "specialist-accent-none";

  return (
    <AppShell backTo="/plan" backLabel="Your plan">
      <div className="mw-main specialist-main">
        <div className={`mw-stack mw-enter ${accentClass}`}>
          {/* Who this is */}
          <header className="mw-card mw-card--tint specialist-header">
            {identity.icon ? (
              <span className="specialist-header-icon" aria-hidden="true">
                {identity.icon}
              </span>
            ) : null}

            <div className="specialist-header-body">
              <span className="mw-eyebrow">Your MoveWell team</span>
              <h1 className="mw-h1 specialist-header-name">{identity.coach}</h1>
              <p className="mw-meta">{identity.canonical}</p>
              {identity.role ? <p className="mw-lede specialist-header-role">{identity.role}</p> : null}

              <div className="mw-row specialist-header-status">
                <StatusBadge label={wording.label} tone={wording.tone} />
                {involved ? (
                  <span className="mw-meta">In your plan</span>
                ) : (
                  <span className="mw-meta">Not part of this plan</span>
                )}
              </div>
            </div>
          </header>

          {state === "error" ? (
            <div className="mw-card" role="alert">
              <h2 className="mw-h3">This specialist could not be loaded</h2>
              <p className="mw-lede">
                There was a problem reaching the service. Nothing you have
                recorded has been changed.
              </p>
              <div className="mw-row">
                <Link className="mw-btn" to="/plan">
                  Back to your plan
                </Link>
              </div>
            </div>
          ) : null}

          {state === "ready" && !section ? (
            <div className="mw-card">
              <h2 className="mw-h3">Nothing has been prepared for this specialist yet</h2>
              <p className="mw-lede">
                No plan has been prepared for this account yet, so this
                specialist has no finding to show. Preparing your plan will let
                it review your own evidence.
              </p>
              <div className="mw-row">
                <Link className="mw-btn mw-btn--primary" to="/plan">
                  Go to your plan
                </Link>
              </div>
            </div>
          ) : null}

          {section ? (
            <>
              {/* Why this specialist is involved */}
              {section.short_reason ? (
                <section className="mw-section" aria-label="Why this specialist is involved">
                  <SectionHeader
                    title={
                      contributed
                        ? "Why this specialist is involved"
                        : "Why this specialist is not involved"
                    }
                  />
                  <div className="mw-card">
                    <p className="mw-lede">{safeDisplayValue(section.short_reason)}</p>
                  </div>
                </section>
              ) : null}

              {/* What they are working on */}
              {section.current_focus ? (
                <section className="mw-section" aria-label="Current focus">
                  <SectionHeader title={identity.focusLabel || "Current focus"} />
                  <div className="mw-card mw-card--tint">
                    <p className="mw-lede">{safeDisplayValue(section.current_focus)}</p>
                  </div>
                </section>
              ) : null}

              {/* What they decided */}
              {section.decision ? (
                <section className="mw-section" aria-label="What MoveWell decided">
                  <SectionHeader title="What MoveWell decided" />
                  <div className="mw-card">
                    <p className="mw-lede">{safeDisplayValue(section.decision)}</p>
                  </div>
                </section>
              ) : null}

              {/* What to do */}
              {actions.length || (emptyState && !actions.length) ? (
                <section
                  className="mw-section"
                  aria-label="Your actions"
                  id={`specialist-${section.specialist}`}
                >
                  <SectionHeader
                    title="Your actions"
                    hint={
                      actions.length
                        ? `${actions.length} ${actions.length === 1 ? "action" : "actions"} from this specialist`
                        : null
                    }
                  />

                  {actions.length ? (
                    <>
                      <ul className="specialist-action-list">
                        {actions.map((item, index) => (
                          <PlanActionItem
                            key={`${item.item_id || item.kind || "item"}-${item.position ?? index}`}
                            item={item}
                            onAction={handleAction}
                            completion={completion}
                          />
                        ))}
                      </ul>
                      {renderSectionExtra(section)}
                    </>
                  ) : emptyState ? (
                    <EmptyState
                      title={safeDisplayValue(emptyState.message) || "Nothing here yet"}
                      action={
                        emptyState.action?.label ? (
                          <PrimaryButton
                            onClick={() => handleAction(emptyState.action)}
                            disabled={!emptyState.action.route && !emptyState.action.anchor}
                          >
                            {emptyState.action.label}
                          </PrimaryButton>
                        ) : null
                      }
                    />
                  ) : null}
                </section>
              ) : null}

              {/* What it has produced so far */}
              {trackingLabel || progressLabel || progressRows.length ? (
                <section className="mw-section" aria-label="Result and progress">
                  <SectionHeader title="Result and progress" />

                  <div className="mw-card specialist-progress">
                    {trackingLabel ? (
                      <div className="specialist-progress-block">
                        <h3 className="specialist-block-title">Recorded so far</h3>
                        <p className="mw-lede">{trackingLabel}</p>
                        {tracking?.summary ? (
                          <p className="mw-meta">{safeDisplayValue(tracking.summary)}</p>
                        ) : null}
                        <Rows rows={tracking?.rows} />
                      </div>
                    ) : null}

                    {progressLabel ? (
                      <div className="specialist-progress-block">
                        <h3 className="specialist-block-title">Where that is going</h3>
                        <p className="mw-lede">{progressLabel}</p>
                      </div>
                    ) : null}

                    {progressRows.length ? (
                      <div className="specialist-progress-block">
                        <Rows rows={progressRows} />
                      </div>
                    ) : null}
                  </div>
                </section>
              ) : null}

              {/* What happens next */}
              {section.next_step ? (
                <section className="mw-section" aria-label="Next">
                  <SectionHeader title="Next" />
                  <div className="mw-card">
                    <p className="mw-lede">{safeDisplayValue(section.next_step)}</p>
                  </div>
                </section>
              ) : null}

              {/* Where another specialist's decision reaches into this one.
                  Shown only when the server says it applies here. */}
              {constraints.length ? (
                <section className="mw-section specialist-collab">
                  <ul className="specialist-collab-list">
                    {constraints.map((constraint, index) => {
                      const source = identityFor(constraint.source).coach;

                      return (
                        <li
                          className="mw-card specialist-collab-item"
                          key={`${constraint.source}-${constraint.type || index}`}
                        >
                          <p className="specialist-collab-line">
                            Working with <strong>{source}</strong>
                          </p>
                          {constraint.reason ? (
                            <p className="mw-lede">{safeDisplayValue(constraint.reason)}</p>
                          ) : null}
                          {toArray(constraint.actions).length ? (
                            <DetailDrawer label="What was asked of it">
                              <ul className="specialist-plain-list">
                                {toArray(constraint.actions)
                                  .map(safeDisplayValue)
                                  .filter(Boolean)
                                  .map((line, lineIndex) => (
                                    <li key={`${line}-${lineIndex}`}>{line}</li>
                                  ))}
                              </ul>
                            </DetailDrawer>
                          ) : null}
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ) : null}

              {/* Everything that is not the first thing a person needs. */}
              {hasDetails ? (
                <DetailDrawer label="View details">
                  {evidence.length ? (
                    <div className="specialist-detail-block">
                      <h3 className="specialist-block-title">What this was based on</h3>
                      <ul className="specialist-plain-list">
                        {evidence.map((line, index) => (
                          <li key={`${line}-${index}`}>{line}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {missing.length ? (
                    <div className="specialist-detail-block">
                      <h3 className="specialist-block-title">What is not known yet</h3>
                      <ul className="specialist-plain-list specialist-plain-list--quiet">
                        {missing.map((line, index) => (
                          <li key={`${line}-${index}`}>{line}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {progressMeta || progress?.adaptation_reason ? (
                    <div className="specialist-detail-block">
                      <h3 className="specialist-block-title">This plan</h3>
                      {progressMeta ? <p className="mw-meta">{progressMeta}</p> : null}
                      {progress?.adaptation_reason ? (
                        <p className="mw-meta">{safeDisplayValue(progress.adaptation_reason)}</p>
                      ) : null}
                    </div>
                  ) : null}
                </DetailDrawer>
              ) : null}
            </>
          ) : null}
        </div>
      </div>
    </AppShell>
  );
}

export default function SpecialistDetailPage() {
  return (
    <SpecialistErrorBoundary>
      <SpecialistDetailPageInner />
    </SpecialistErrorBoundary>
  );
}
