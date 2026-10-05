/**
 * The moment after an assessment: your score, what matters most, and who is
 * helping.
 *
 * This is the product's central claim made visible in one screen — the three
 * movement checks became a score, the score named a focus, the focus brought in
 * specialists, and the specialists produced one plan. It is also where a
 * reassessment lands, which is why it says whether the plan actually changed
 * rather than implying that it must have.
 *
 * Everything shown is a server value. There is no placeholder number here: when
 * nothing has been measured the dial says so and the page asks for the
 * assessment instead of inventing a score.
 *
 * One deliberate action: if this account has never had a plan prepared, this
 * page prepares it once, because arriving here means the user just finished the
 * assessment the plan is built from. It never re-runs when a plan already
 * exists — a profile edit must not silently rebuild anything (the plan screen
 * owns that action).
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import AppShell from "../components/ui/AppShell.jsx";
import ScoreDial from "../components/ui/ScoreDial.jsx";
import SpecialistTeamCard from "../components/SpecialistTeamCard.jsx";
import {
  DetailDrawer,
  EmptyState,
  PageHeader,
  PrimaryButton,
  SectionHeader,
  StatusBadge,
} from "../components/ui/primitives.jsx";
import { getToken } from "../services/auth";
import { safeDisplayValue, toArray } from "../services/specialistData.js";
import {
  changeWording,
  focusStatement,
  hasScore,
  movewellScore,
  scoreChange,
  scoreFocus,
  scoreMessage,
  scoreMethod,
  scoredDomains,
  unscoredDomains,
} from "../services/score.js";
import { identityFor, statusWording } from "../services/specialistIdentity.js";
import {
  fetchLatestWorkflow,
  planState,
  PLAN_STATES,
  runWorkflow,
} from "../services/workflow";

import "./ResultsPage.css";

/** The domains that are worth naming as an opportunity, worst first. */
function focusDomains(workflow) {
  return scoredDomains(workflow)
    .filter((domain) => domain.level === "HIGH" || domain.level === "MEDIUM")
    .sort((a, b) => a.value - b.value);
}

/** Any plan change the server itself recorded. */
function planChanges(workflow) {
  return [
    ["Movement", workflow?.exercise_plan],
    ["Nutrition", workflow?.nutrition_plan],
    ["Daily habits", workflow?.behaviour_plan],
  ]
    .filter(([, plan]) => plan?.available && plan?.adaptation_reason)
    .map(([label, plan]) => ({ label, reason: plan.adaptation_reason, version: plan.plan_version }));
}

export default function ResultsPage() {
  const navigate = useNavigate();

  const [workflow, setWorkflow] = useState(null);
  const [state, setState] = useState("loading");
  const [error, setError] = useState(null);

  const signedIn = Boolean(getToken());

  const load = useCallback(async () => {
    setState("loading");
    setError(null);

    try {
      const latest = await fetchLatestWorkflow();
      const current = planState(latest);

      // The journey's own step: arriving here means the assessment just
      // finished, so the plan is prepared — once, and only if there is not one
      // already.
      const needsPreparing =
        current.state === PLAN_STATES.NEVER_RUN &&
        Boolean(latest?.assessment_summary?.tests_completed);

      const result = needsPreparing ? await runWorkflow() : latest;

      setWorkflow(result);
      setState("ready");
    } catch (loadError) {
      setError(loadError.message || "Your results could not be loaded just now.");
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

  const score = movewellScore(workflow);
  const available = hasScore(workflow);
  const focus = scoreFocus(workflow);
  const change = scoreChange(workflow);
  const method = scoreMethod(workflow);
  const scored = scoredDomains(workflow);
  const unscored = unscoredDomains(workflow);
  const opportunities = focusDomains(workflow);
  const team = toArray(workflow?.unified_plan?.specialists);
  const summary = workflow?.unified_plan?.summary || null;
  const changes = planChanges(workflow);
  const planReady = Boolean(workflow?.unified_plan?.available);

  return (
    <AppShell>
      <div className="mw-main results-main">
        <PageHeader
          eyebrow="Your results"
          title="Your MoveWell Score"
          lead={
            available
              ? "Built from the movement checks you just completed, and anything you have already told us."
              : "This is where your score appears once MoveWell has measured something."
          }
        />

        {state === "loading" ? <p className="mw-loading">Working out your score…</p> : null}

        {state === "error" ? (
          <EmptyState
            title="Your results could not be loaded"
            why={safeDisplayValue(error)}
            action={<PrimaryButton onClick={load}>Try again</PrimaryButton>}
          />
        ) : null}

        {state === "ready" ? (
          <>
            {/* 1. The score itself. */}
            <section className="mw-card results-score" aria-labelledby="results-score-heading">
              <h2 id="results-score-heading" className="mw-sr">
                Your MoveWell Score
              </h2>

              <ScoreDial
                value={available ? score.value : null}
                label="Your MoveWell Score"
                caption={available ? scoreMessage(workflow) : null}
              />

              {available && focus ? (
                <p className="results-focus">
                  Current focus: <strong>{safeDisplayValue(focus.label)}</strong>
                </p>
              ) : null}

              {change ? (
                <p className="results-change">
                  {change.from} → {score.value} · {change.value > 0 ? "+" : ""}
                  {change.value} since your previous assessment
                </p>
              ) : available ? (
                <p className="mw-meta">
                  A previous assessment is needed before this can show a change.
                </p>
              ) : null}

              {!available ? (
                <EmptyState
                  title="Not measured yet"
                  why="Your score comes from the three movement checks. Nothing is scored before they are done, and nothing is guessed at in the meantime."
                  action={
                    <PrimaryButton onClick={() => navigate("/assessment")}>
                      Start assessment
                    </PrimaryButton>
                  }
                />
              ) : null}

              {method ? (
                <DetailDrawer label="How this is worked out">
                  <p className="mw-lede">{safeDisplayValue(method)}</p>
                </DetailDrawer>
              ) : null}
            </section>

            {/* 2. The domains behind it. */}
            {scored.length ? (
              <section className="mw-section" aria-labelledby="results-domains-heading">
                <SectionHeader
                  title="What makes up your score"
                  hint="Each area is shown on its own, so one weak area does not hide the rest."
                />
                <div className="mw-grid mw-grid--three">
                  {scored.map((domain) => (
                    <article className="mw-card results-domain" key={domain.key}>
                      <h3 className="results-domain-label">{safeDisplayValue(domain.label)}</h3>
                      <p className="results-domain-value">{domain.value}</p>
                      <p className="mw-meta">
                        {domain.source === "measured"
                          ? "From your movement checks"
                          : "From your answers"}
                      </p>
                      {typeof domain.change === "number" && domain.change !== 0 ? (
                        <p className={`results-domain-change is-${changeWording(domain.change)}`}>
                          {domain.change > 0 ? "+" : ""}
                          {domain.change} since last time
                        </p>
                      ) : null}
                    </article>
                  ))}
                </div>

                {unscored.length ? (
                  <div className="mw-empty">
                    <h3 className="mw-h3">Not assessed yet</h3>
                    <p className="mw-lede">
                      {unscored.map((domain) => safeDisplayValue(domain.label)).join(", ")} —{" "}
                      MoveWell needs a little more information before these can be part of your
                      score. They are left out rather than counted against you.
                    </p>
                    {unscored.some((domain) => domain.key === "nutrition_need") ? (
                      <PrimaryButton onClick={() => navigate("/nutrition-check-in")}>
                        Complete nutrition check-in
                      </PrimaryButton>
                    ) : null}
                  </div>
                ) : null}
              </section>
            ) : null}

            {/* 3. What matters most right now. */}
            <section className="mw-section" aria-labelledby="results-focus-heading">
              <SectionHeader title="What matters most right now" />
              <div className="mw-card mw-card--tint">
                <h3 className="mw-h3" id="results-focus-heading">
                  {focus ? safeDisplayValue(focus.label) : "Nothing needs attention right now"}
                </h3>
                <p className="mw-lede">
                  {safeDisplayValue(focusStatement(workflow)) ||
                    "Your results did not cross the markers MoveWell uses to pick a focus area."}
                </p>

                {opportunities.length > 1 ? (
                  <ul className="results-opportunities">
                    {opportunities.slice(1).map((domain) => (
                      <li key={domain.key} className="mw-field-row">
                        <span className="mw-field-key">{safeDisplayValue(domain.label)}</span>
                        <span className="mw-field-value">
                          {domain.level === "HIGH"
                            ? "Worth working on"
                            : "A little attention would help"}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            </section>

            {/* 4. The team this brought in. */}
            {team.length ? (
              <section className="mw-section" aria-labelledby="results-team-heading">
                <SectionHeader
                  title="Your MoveWell team"
                  hint="MoveWell picks the specialists your own results call for."
                />
                <div className="mw-grid mw-grid--team">
                  {team.map((specialist) => {
                    const wording = statusWording(specialist.team_status, specialist.team_status_label);

                    return (
                      <SpecialistTeamCard
                        key={specialist.id}
                        specialist={specialist}
                        onOpen={(entry) => entry?.route && navigate(entry.route)}
                      />
                    );
                  })}
                </div>
              </section>
            ) : null}

            {/* 5. The plan, and whether it changed. */}
            {planReady ? (
              <section className="mw-section" aria-labelledby="results-plan-heading">
                <SectionHeader title={changes.length ? "Your plan has been updated" : "Your plan is ready"} />

                <div className="mw-card">
                  <p id="results-plan-heading" className="mw-lede">
                    {safeDisplayValue(summary?.headline) ||
                      "Your plan is prepared from your results and your answers."}
                  </p>

                  {toArray(summary?.focus_areas).length ? (
                    <ul className="results-chips">
                      {toArray(summary.focus_areas).map((area, index) => (
                        <li key={`${area}-${index}`} className="mw-chip">
                          {safeDisplayValue(area)}
                        </li>
                      ))}
                    </ul>
                  ) : null}

                  {changes.length ? (
                    <ul className="results-changes">
                      {changes.map((changeEntry) => (
                        <li key={changeEntry.label} className="results-change-row">
                          <span className="results-change-label">{changeEntry.label}</span>
                          <span>{safeDisplayValue(changeEntry.reason)}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mw-meta">
                      Nothing in your plan needed to change this time. That is a result in itself.
                    </p>
                  )}

                  <div className="mw-row results-plan-actions">
                    <PrimaryButton onClick={() => navigate("/plan")}>
                      See your plan
                    </PrimaryButton>
                    <PrimaryButton variant="ghost" onClick={() => navigate("/today")}>
                      Go to Today
                    </PrimaryButton>
                  </div>
                </div>
              </section>
            ) : (
              <EmptyState
                title="No plan was needed this time"
                why="Your results did not show an area MoveWell would build a plan around. Nothing here is a finding about your health — it is a plan with nothing to add yet."
                action={
                  <PrimaryButton onClick={() => navigate("/assessment")}>
                    Reassess later
                  </PrimaryButton>
                }
              />
            )}

            {/* 6. What happens next, in the product's own words. */}
            <section className="mw-card mw-card--quiet results-next" aria-labelledby="results-next-heading">
              <SectionHeader title="What happens next" />
              <p className="mw-lede" id="results-next-heading">
                {safeDisplayValue(summary?.next) ||
                  "Complete your activities. MoveWell uses what you record and your next assessment to adapt the plan after this one."}
              </p>
              <DetailDrawer label="What each specialist is doing">
                <ul className="results-team-detail">
                  {toArray(workflow?.unified_plan?.sections).map((section) => {
                    const identity = identityFor(section.specialist, section.title);
                    const wording = statusWording(section.team_status, section.team_status_label);

                    return (
                      <li key={section.specialist} className="results-team-detail-row">
                        <span className="results-team-detail-name">
                          {safeDisplayValue(identity.coach)}
                        </span>
                        <StatusBadge label={wording.label} tone={wording.tone} />
                        <span className="results-team-detail-reason">
                          {safeDisplayValue(section.short_reason)}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              </DetailDrawer>
            </section>
          </>
        ) : null}
      </div>
    </AppShell>
  );
}
