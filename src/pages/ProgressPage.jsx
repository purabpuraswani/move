/**
 * Your progress, in the order a person asks about it.
 *
 *   1. Your MoveWell Score, and how it has moved
 *   2. What is improving, per area
 *   3. What changed in the plan, in the server's own words
 *   4. What the plan focuses on now
 *   5. What moved forward (the recorded series)
 *   6. What you completed
 *   7. What happens next
 *
 * Three rules shape every sentence here:
 *
 *   * Nothing is invented. Every number, label and sentence is read from the
 *     server response, through services/score.js, services/unifiedPlan.js and
 *     services/progress.js — the chrome around it is ours, the content is not.
 *   * An absence is reported as an absence. A missing reading is missing, not
 *     a decline; a single recorded point is a record, not a direction of
 *     travel; an unusable camera session is a recording problem, not a
 *     performance. Each empty state says what is missing, why it matters and
 *     what to do about it.
 *   * The Progress Agent's own machine vocabulary stays on the server. The
 *     adaptation reasons on this page are the plain-language sentences the
 *     server already wrote for a person.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

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
import ProgressLineChart from "../progress/ProgressLineChart.jsx";
import { getToken } from "../services/auth";
import { fetchExerciseResults } from "../services/exerciseResults";
import { fetchFoodLog } from "../services/foodLog";
import { fetchProgressSeries } from "../services/progress";
import {
  changeWording,
  domainChanges,
  hasScore,
  movewellScore,
  scoreChange,
  scoreFocus,
  scoreMessage,
  scoreMethod,
  scoredDomains,
  unscoredDomains,
} from "../services/score";
import { safeDisplayValue, toArray } from "../services/specialistData.js";
import { planSummary, unifiedPlan } from "../services/unifiedPlan.js";
import { fetchLatestWorkflow, hasAnyPlan, runWorkflow } from "../services/workflow";

import "./ProgressPage.css";

/** A whole number, or null. Never a computed value. */
function numberOrNull(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/** The signed change, exactly as the server sent it: "+8", "-3", "0". */
function signed(change) {
  if (typeof change !== "number" || !Number.isFinite(change)) return null;

  return `${change > 0 ? "+" : ""}${change}`;
}

/** What MoveWell measured this from. The server says which; we only word it. */
const SOURCE_LABELS = {
  measured: "Measured",
  answered: "From your answers",
};

function sourceLabel(source) {
  return SOURCE_LABELS[source] || null;
}

function formatDay(value) {
  const day = typeof value === "string" ? value.slice(0, 10) : null;

  if (!day) return null;

  const parsed = new Date(`${day}T00:00:00`);

  if (Number.isNaN(parsed.getTime())) return day;

  return parsed.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function plural(count, one, many) {
  return count === 1 ? one : many;
}

/** Whether any series or completion actually carries a recorded point. */
function seriesHasPoints(series) {
  if (!series) return false;

  const completions = numberOrNull(series.completions?.point_count) ?? 0;

  const metrics = toArray(series.movementMetrics).some(
    (metric) => (numberOrNull(metric?.point_count) ?? toArray(metric?.points).length) > 0,
  );

  return completions > 0 || metrics || toArray(series.recentCompletions).length > 0;
}

/** One area that moved, with the name the server gave it. */
function DomainChange({ entry }) {
  const change = numberOrNull(entry.change);

  if (change === null || change === 0) return null;

  const direction = changeWording(change);
  const value = numberOrNull(entry.value);
  const source = sourceLabel(entry.source);

  return (
    <li className="progress-area">
      <span className="progress-area-name">{safeDisplayValue(entry.label)}</span>

      <span className={`progress-area-move progress-area-move--${direction}`}>
        {direction} {signed(change)} points
      </span>

      <span className="progress-area-now">
        {value === null ? "No current value" : `now ${value}`}
      </span>

      {source ? <span className="mw-meta progress-area-source">{source}</span> : null}
    </li>
  );
}

/** One plan section that the server has reported a change for. */
function PlanChangeRow({ label, plan }) {
  if (!plan?.available || !plan.adaptation_reason) return null;

  const version = safeDisplayValue(plan.plan_version);

  return (
    <li className="progress-plan-change">
      <Field label={label} value={plan.adaptation_reason} />

      {version ? (
        <p className="mw-meta">Version {version} of this part of your plan.</p>
      ) : null}
    </li>
  );
}

function ProgressPage() {
  const navigate = useNavigate();

  const [workflow, setWorkflow] = useState(null);
  const [foodEntries, setFoodEntries] = useState([]);
  const [exerciseResults, setExerciseResults] = useState([]);
  const [series, setSeries] = useState(null);
  const [state, setState] = useState("loading");
  const [error, setError] = useState(null);
  const [reviewing, setReviewing] = useState(false);
  const [reviewNote, setReviewNote] = useState(null);

  const signedIn = Boolean(getToken());

  const load = useCallback(async () => {
    setState("loading");
    setError(null);

    try {
      const [latest, foodPage, exercisePage, progressSeries] = await Promise.all([
        fetchLatestWorkflow(),
        fetchFoodLog({ limit: 50 }).catch(() => ({ entries: [] })),
        fetchExerciseResults({ limit: 50 }).catch(() => ({ results: [] })),
        // The charts are a bonus on top of the counts: if this one call fails
        // the page still renders everything the other three returned.
        fetchProgressSeries().catch(() => null),
      ]);

      setWorkflow(latest);
      setFoodEntries(foodPage.entries || []);
      setExerciseResults(exercisePage.results || exercisePage.exercise_results || []);
      setSeries(progressSeries);
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

  const review = useCallback(async () => {
    const measured = exerciseResults.filter(
      (result) => result.status && result.status !== "invalid",
    ).length;

    const logged = foodEntries.length;

    setReviewing(true);
    setError(null);
    setReviewNote(null);

    try {
      // The reason names what actually happened, so the audit trail says why
      // this review ran rather than attributing it to logging that may not
      // have occurred. It is only ever sent because something was recorded.
      const reason =
        measured > 0 && logged > 0
          ? "exercise activity and food log activity recorded"
          : measured > 0
            ? "exercise activity recorded"
            : "food log activity recorded";

      const result = await runWorkflow({ progressTrigger: { reason } });

      setWorkflow(result);
      setReviewNote("Your plan has been reviewed against what you have recorded.");
    } catch (reviewError) {
      setError(reviewError.message);
    } finally {
      setReviewing(false);
    }
  }, [exerciseResults, foodEntries]);

  const planExists = hasAnyPlan(workflow);
  const summary = planSummary(workflow);
  const serverPlan = unifiedPlan(workflow);

  const score = movewellScore(workflow);
  const scoreIsAvailable = hasScore(workflow);
  const scoreValue = scoreIsAvailable ? numberOrNull(score.value) : null;
  const change = scoreChange(workflow);
  const focus = scoreFocus(workflow);
  const method = scoreMethod(workflow);
  const message = scoreMessage(workflow);
  const domainMoves = domainChanges(workflow);
  const withValue = scoredDomains(workflow);
  const withoutValue = unscoredDomains(workflow);

  // A result the camera could not measure is not evidence of performance — it
  // is evidence of a recording problem. Counting it would let an unusable
  // session look like a completed one.
  const exerciseCount = exerciseResults.length;
  const measuredExerciseCount = exerciseResults.filter(
    (result) => result.status && result.status !== "invalid",
  ).length;
  const unmeasuredExerciseCount = exerciseCount - measuredExerciseCount;

  const loggedCount = foodEntries.length;

  const hasEvidence = measuredExerciseCount > 0 || loggedCount > 0;

  const planSections = [
    { key: "exercise", label: "Movement", plan: workflow?.exercise_plan },
    { key: "nutrition", label: "Nutrition", plan: workflow?.nutrition_plan },
    { key: "behaviour", label: "Daily habits", plan: workflow?.behaviour_plan },
  ];

  const hasPlanChange = planSections.some(
    (section) => section.plan?.available && section.plan.adaptation_reason,
  );

  const recentCompletions = toArray(series?.recentCompletions);
  const movementMetrics = toArray(series?.movementMetrics);
  const progressLoaded = Boolean(series);
  const progressHasPoints = seriesHasPoints(series);

  return (
    <AppShell>
      <main className="mw-main mw-stack" id="main">
        {/* 1. Header */}
        <PageHeader
          eyebrow="Progress"
          title="Your Progress"
          lead="What you have recorded, where your score stands, and what your plan does next."
        />

        {state === "loading" ? (
          <p className="mw-loading">Reading your recorded progress…</p>
        ) : null}

        {state === "error" && !workflow ? (
          <section className="mw-card" aria-label="Progress could not be loaded">
            <SectionHeader title="We could not read your progress just now" />
            <p className="mw-lede">
              {safeDisplayValue(error) ||
                "There was a problem reaching the service. Nothing you recorded has been changed."}
            </p>
            <div className="mw-row">
              <PrimaryButton onClick={load}>Try again</PrimaryButton>
            </div>
          </section>
        ) : null}

        {state === "ready" ? (
          <>
            {error ? <p className="mw-error progress-error">{safeDisplayValue(error)}</p> : null}

            {/* 2. MoveWell Score */}
            <section className="mw-card" aria-label="MoveWell Score">
              <SectionHeader
                title="MoveWell Score"
                hint="Worked out from your own results, on the server."
              />

              {scoreIsAvailable ? (
                <>
                  <div className="progress-score">
                    <ScoreDial
                      value={scoreValue}
                      label="Your MoveWell Score"
                      caption={message}
                    />

                    <div className="progress-score-detail mw-stack mw-stack--tight">
                      {change ? (
                        <div className="progress-score-change">
                          <span className="progress-score-change-label">
                            Since your previous assessment
                          </span>

                          <span className="progress-score-change-value">
                            <span className="progress-score-change-from">{change.from}</span>
                            <span aria-hidden="true"> → </span>
                            <span className="mw-sr">to </span>
                            <span className="progress-score-change-to">{scoreValue}</span>
                          </span>

                          <span
                            className={`progress-score-change-delta progress-score-change-delta--${changeWording(change.value)}`}
                          >
                            {signed(change.value)} points
                          </span>
                        </div>
                      ) : (
                        <div className="progress-score-noprevious">
                          <p className="mw-lede">
                            MoveWell needs another completed assessment to understand your
                            trend.
                          </p>
                          <div className="mw-row">
                            <PrimaryButton onClick={() => navigate("/assessment")}>
                              Start reassessment
                            </PrimaryButton>
                          </div>
                        </div>
                      )}

                      {focus?.label ? (
                        <p className="mw-meta">
                          The area carrying the greatest need is{" "}
                          <strong>{safeDisplayValue(focus.label)}</strong>.
                        </p>
                      ) : null}
                    </div>
                  </div>

                  {method ? (
                    <DetailDrawer label="How this number is worked out">
                      <p className="mw-lede">{method}</p>

                      {withoutValue.length ? (
                        <div className="mw-stack mw-stack--tight">
                          <p className="mw-meta">
                            An area with no usable evidence is left out rather than counted
                            as zero. Nothing has been measured for:
                          </p>
                          <ul className="mw-row progress-score-missing">
                            {withoutValue.map((domain) => (
                              <li key={domain.key} className="mw-chip mw-chip--neutral">
                                {safeDisplayValue(domain.label)}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                    </DetailDrawer>
                  ) : null}
                </>
              ) : (
                <EmptyState
                  title={
                    withValue.length
                      ? "Your score is waiting on a movement check"
                      : "No MoveWell Score yet"
                  }
                  why={
                    withValue.length
                      ? "MoveWell only shows a score once a movement check has measured something. The answers you have given are kept, and they are not presented as a score because nobody measured them."
                      : "Every check contributes to the score, and no check has produced a usable measurement yet. Until one does, there is no number to follow."
                  }
                  action={
                    <PrimaryButton onClick={() => navigate("/assessment")}>
                      {withValue.length ? "Take a movement check" : "Start your assessment"}
                    </PrimaryButton>
                  }
                />
              )}
            </section>

            {/* 3. What's improving */}
            <section className="mw-card" aria-label="What's improving">
              <SectionHeader
                title="What's improving"
                hint="Only areas that have actually moved since your previous assessment."
              />

              {domainMoves.length ? (
                <ul className="progress-areas">
                  {domainMoves.map((entry) => (
                    <DomainChange key={entry.key} entry={entry} />
                  ))}
                </ul>
              ) : score?.previous ? (
                <EmptyState
                  title="No area has moved since your last assessment"
                  why="Every area MoveWell measured came out at the same value as last time. A steady result is a real one — nothing is hidden by calling it an improvement."
                  action={
                    <PrimaryButton
                      variant="ghost"
                      onClick={() => navigate("/plan")}
                    >
                      See your current plan
                    </PrimaryButton>
                  }
                />
              ) : (
                <EmptyState
                  title="There is nothing to compare yet"
                  why="MoveWell can only show what moved once two assessments can be compared. One assessment says where you are; it cannot say which way anything is going."
                  action={
                    <PrimaryButton onClick={() => navigate("/assessment")}>
                      Start reassessment
                    </PrimaryButton>
                  }
                />
              )}
            </section>

            {/* 4. What changed */}
            <section className="mw-card" aria-label="What changed">
              <SectionHeader
                title="What changed"
                hint="What your plan says about the last change it made."
              />

              {planExists ? (
                hasPlanChange ? (
                  <ul className="progress-plan-changes">
                    {planSections.map((section) => (
                      <PlanChangeRow
                        key={section.key}
                        label={section.label}
                        plan={section.plan}
                      />
                    ))}
                  </ul>
                ) : (
                  <p className="mw-lede">
                    Your plan has not needed a change yet. Nothing has moved far enough
                    since it was prepared to justify rewriting it — and a plan that was
                    rebuilt without a reason would be a change you did not need.
                  </p>
                )
              ) : (
                <EmptyState
                  title="No plan has been prepared yet"
                  why="There is no change to report, because there is no plan yet. Everything you record from here is what a first plan is built from."
                  action={
                    <PrimaryButton onClick={() => navigate("/assessment")}>
                      Start your assessment
                    </PrimaryButton>
                  }
                />
              )}
            </section>

            {/* 5. Your current focus */}
            <section className="mw-card" aria-label="Your current focus">
              <SectionHeader
                title="Your current focus"
                hint="The areas this plan is built around, as the server named them."
              />

              {summary ? (
                <div className="mw-stack mw-stack--tight">
                  <p className="progress-headline">
                    {safeDisplayValue(summary.headline) ||
                      "Your plan does not name a focus area."}
                  </p>

                  {toArray(summary.focus_areas).length ? (
                    <ul className="mw-row progress-chips">
                      {toArray(summary.focus_areas).map((area, index) => (
                        <li key={`${area}-${index}`} className="mw-chip">
                          {safeDisplayValue(area)}
                        </li>
                      ))}
                    </ul>
                  ) : null}

                  {serverPlan?.version ? (
                    <p className="mw-meta">
                      This is version {safeDisplayValue(serverPlan.version)} of your plan.
                    </p>
                  ) : null}
                </div>
              ) : (
                <EmptyState
                  title="No plan focus has been set yet"
                  why="Your focus areas come with your plan. Until one is prepared there is nothing here that would honestly stand for them."
                  action={
                    <PrimaryButton onClick={() => navigate("/plan")}>
                      Go to your plan
                    </PrimaryButton>
                  }
                />
              )}
            </section>

            {/* 6. What moved forward */}
            <section className="mw-card" aria-label="What moved forward">
              <SectionHeader
                title="What moved forward"
                hint="Drawn from what you have recorded, one point per recorded day."
              />

              {progressLoaded ? (
                progressHasPoints ? (
                  <div className="mw-stack">
                    <ProgressLineChart
                      series={series.completions}
                      title="Exercises completed per day"
                      emptyNote="Your first completed session will appear here."
                    />

                    {movementMetrics.length ? (
                      <div className="mw-grid mw-grid--two">
                        {movementMetrics.map((metric) => (
                          <ProgressLineChart
                            key={metric.metric}
                            series={metric}
                            title={metric.label}
                            unit={metric.unit}
                            emptyNote="This check has not produced a usable measurement yet."
                          />
                        ))}
                      </div>
                    ) : null}

                    <p className="mw-lede progress-honesty">
                      Each point is a day you recorded something. A check you skipped
                      contributes no point at all: it is missing from the line, not a fall
                      in it. One recorded point is a record, not a trend, so the chart says
                      so rather than drawing a line through it.
                    </p>
                  </div>
                ) : (
                  <EmptyState
                    title="Nothing recorded to draw yet"
                    why="The charts are built from sessions you complete and movement checks you save. With none recorded there is no line to draw, and a line through an empty chart would be a picture of nothing."
                    action={
                      <PrimaryButton onClick={() => navigate("/plan")}>
                        Start your first exercise
                      </PrimaryButton>
                    }
                  />
                )
              ) : (
                <EmptyState
                  title="Your recorded history could not be loaded"
                  why="Your sessions and checks are stored safely; this one request did not come back, so the charts cannot be drawn and nothing is being shown in their place."
                  action={<PrimaryButton onClick={load}>Try again</PrimaryButton>}
                />
              )}
            </section>

            {/* 7. What you completed */}
            <section className="mw-card" aria-label="What you completed">
              <SectionHeader
                title="What you completed"
                hint="Counted from what is stored against your account."
              />

              {hasEvidence ? (
                <>
                  <div className="mw-grid mw-grid--two progress-counts">
                    {measuredExerciseCount > 0 ? (
                      <div className="progress-count">
                        <span className="progress-count-value">{measuredExerciseCount}</span>
                        <span className="progress-count-label">
                          {plural(measuredExerciseCount, "exercise session", "exercise sessions")}{" "}
                          recorded
                        </span>
                      </div>
                    ) : null}

                    {loggedCount > 0 ? (
                      <div className="progress-count">
                        <span className="progress-count-value">{loggedCount}</span>
                        <span className="progress-count-label">
                          {plural(loggedCount, "meal", "meals")} logged
                        </span>
                      </div>
                    ) : null}
                  </div>

                  {unmeasuredExerciseCount > 0 ? (
                    <p className="mw-meta progress-unmeasured">
                      {unmeasuredExerciseCount}{" "}
                      {plural(unmeasuredExerciseCount, "other session", "other sessions")}{" "}
                      could not be measured by the camera, so{" "}
                      {plural(unmeasuredExerciseCount, "it is", "they are")} not counted
                      above. That is a recording problem rather than a performance — it
                      says nothing about how you did.
                    </p>
                  ) : null}

                  {recentCompletions.length ? (
                    <div className="mw-stack mw-stack--tight">
                      <h3 className="mw-h3">Your most recent sessions</h3>

                      <ul className="progress-completions">
                        {recentCompletions.map((entry, index) => {
                          const day = formatDay(entry.completedAt);
                          const unusable = entry.status === "invalid";

                          return (
                            <li
                              key={`${entry.exerciseId || "session"}-${entry.completedAt || index}`}
                              className="progress-completion"
                            >
                              <span className="progress-completion-name">
                                {safeDisplayValue(entry.exerciseName || entry.exerciseId)}
                              </span>

                              <span className="progress-completion-meta">
                                {day ? <span>{day}</span> : null}
                                {unusable ? (
                                  <StatusBadge label="Could not be measured" tone="muted" />
                                ) : (
                                  <StatusBadge
                                    label={
                                      entry.source === "manual_confirmation"
                                        ? "Self-reported"
                                        : "Measured"
                                    }
                                    tone={entry.source === "manual_confirmation" ? "neutral" : "active"}
                                  />
                                )}
                              </span>
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  ) : null}
                </>
              ) : (
                <EmptyState
                  title="Nothing recorded yet"
                  why="Every count on this page comes from what you record: a completed session, or a meal you log. Until one exists there is nothing to count, and nothing here is filled in on your behalf."
                  action={
                    <>
                      <PrimaryButton
                        onClick={() => navigate(planExists ? "/plan" : "/assessment")}
                      >
                        {planExists ? "Start your first exercise" : "Start your assessment"}
                      </PrimaryButton>
                      <PrimaryButton
                        variant="ghost"
                        onClick={() => navigate("/nutrition-check-in")}
                      >
                        Complete your nutrition check-in
                      </PrimaryButton>
                    </>
                  }
                />
              )}
            </section>

            {/* 8. What happens next */}
            <section className="mw-card mw-card--tint" aria-label="What happens next">
              <SectionHeader title="What happens next" />

              {summary?.next ? (
                <p className="mw-lede">{safeDisplayValue(summary.next)}</p>
              ) : (
                <EmptyState
                  title="MoveWell has not written a next step yet"
                  why="The next step comes with your plan, and there is no plan yet to read it from. What you record now is what the first one is prepared from."
                  action={
                    <PrimaryButton onClick={() => navigate("/plan")}>
                      Go to your plan
                    </PrimaryButton>
                  }
                />
              )}

              <div className="mw-row progress-actions">
                {/* Offered only when there is something to review. Without
                    evidence the review can only return "not enough data", so
                    the button would promise something it cannot deliver. */}
                {hasEvidence && planExists ? (
                  <PrimaryButton onClick={review} disabled={reviewing}>
                    {reviewing ? "Reviewing…" : "Review my plan against this"}
                  </PrimaryButton>
                ) : null}

                <PrimaryButton variant="ghost" onClick={() => navigate("/plan")}>
                  Back to your plan
                </PrimaryButton>
              </div>

              {reviewNote ? <p className="mw-success">{safeDisplayValue(reviewNote)}</p> : null}
            </section>
          </>
        ) : null}
      </main>
    </AppShell>
  );
}

export default ProgressPage;
