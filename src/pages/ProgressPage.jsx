/**
 * What you have done, and what changed because of it.
 *
 * This page answers the questions the plan screen cannot: did anything
 * actually change, and why. It reads the same workflow state the plan does,
 * and asks the server to run a progress review only when there is real
 * evidence to review — recorded exercise results or logged food. It never
 * triggers a review speculatively, because a review with nothing new to look
 * at can only conclude "not enough data", and asking repeatedly would just
 * spend model calls to be told so again.
 *
 * The honesty rule this page is built around: an absence of data is reported
 * as an absence of data. If nothing has been recorded, this page says exactly
 * that. It does not draw a trend through two points, it does not describe a
 * user as having fallen behind because they did not write something down, and
 * it shows no internal reasoning — only the plain-language adaptation reason
 * the server already produced.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getToken } from "../services/auth";
import { fetchExerciseResults } from "../services/exerciseResults";
import { fetchFoodLog } from "../services/foodLog";
import { fetchLatestWorkflow, hasAnyPlan, runWorkflow } from "../services/workflow";

import "./ProgressPage.css";

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
 * A plan section's change history, as far as the response exposes it.
 *
 * Only `adaptation_reason` is shown, and only when the server set one. A plan
 * that has never been adapted says so; it does not get a manufactured
 * "no changes yet — keep going!" that implies a review happened.
 */
function ChangeRow({ label, plan }) {
  if (!plan?.available) {
    return null;
  }

  const created = formatDate(plan.created_at);

  return (
    <li className="progress-change">
      <span className="progress-change-label">{label}</span>

      {plan.adaptation_reason ? (
        <span className="progress-change-reason">{plan.adaptation_reason}</span>
      ) : (
        <span className="progress-change-none">
          This part of your plan has not been changed since it was prepared.
        </span>
      )}

      {created ? <span className="progress-change-date">{created}</span> : null}
    </li>
  );
}

function ProgressPage() {
  const navigate = useNavigate();

  const [workflow, setWorkflow] = useState(null);
  const [foodEntries, setFoodEntries] = useState([]);
  const [exerciseResults, setExerciseResults] = useState([]);
  const [state, setState] = useState("loading");
  const [error, setError] = useState(null);
  const [reviewing, setReviewing] = useState(false);
  const [reviewNote, setReviewNote] = useState(null);

  const signedIn = Boolean(getToken());


  useEffect(() => {
    if (!signedIn) {
      navigate("/login", { replace: true });

      return;
    }

    let ignore = false;

    Promise.all([
      fetchLatestWorkflow(),
      fetchFoodLog({ limit: 50 }).catch(() => ({ entries: [] })),
      fetchExerciseResults({ limit: 50 }).catch(() => ({ results: [] })),
    ])
      .then(([latest, foodPage, exercisePage]) => {
        if (!ignore) {
          setWorkflow(latest);
          setFoodEntries(foodPage.entries || []);
          setExerciseResults(exercisePage.results || exercisePage.exercise_results || []);
          setState("ready");
        }
      })
      .catch((loadError) => {
        if (!ignore) {
          setError(loadError.message);
          setState("error");
        }
      });

    return () => {
      ignore = true;
    };
  }, [signedIn, navigate]);

  const loggedCount = foodEntries.length;
  const exerciseCount = exerciseResults.length;

  // A result the camera could not measure is not evidence of performance --
  // it is evidence of a recording problem. Counting it would let an unusable
  // session look like a completed one.
  const measuredExerciseCount = exerciseResults.filter(
    (result) => result.status && result.status !== "invalid",
  ).length;

  const hasEvidence = loggedCount > 0 || measuredExerciseCount > 0;

  const review = useCallback(async () => {
    setReviewing(true);
    setError(null);
    setReviewNote(null);

    try {
      // The trigger says why a review is warranted, in the server's own
      // vocabulary. It is only sent because something was actually recorded.
      // The reason names what actually happened, so the audit trail says why
      // this review ran rather than attributing it to logging that may not
      // have occurred.
      const reason =
        measuredExerciseCount > 0 && loggedCount > 0
          ? "exercise activity and food log activity recorded"
          : measuredExerciseCount > 0
            ? "exercise activity recorded"
            : "food log activity recorded";

      const result = await runWorkflow({ progressTrigger: { reason } });

      setWorkflow(result);
      setReviewNote(
        "Your plan has been reviewed against what you have recorded.",
      );
    } catch (reviewError) {
      setError(reviewError.message);
    } finally {
      setReviewing(false);
    }
  }, [measuredExerciseCount, loggedCount]);

  const planExists = hasAnyPlan(workflow);

  return (
    <div className="progress-page">
      <main className="progress-main">
        <div className="progress-intro">
          <span className="progress-eyebrow">Progress</span>
          <h1 className="progress-title">How things are going</h1>
          <p className="progress-lead">
            What you have recorded, and what has changed in your plan as a
            result.
          </p>
        </div>

        {state === "loading" ? (
          <p className="progress-status">Loading…</p>
        ) : null}

        {error ? <p className="progress-error">{error}</p> : null}

        {state === "ready" ? (
          <>
            <section className="progress-card">
              <h2 className="progress-card-title">What you have recorded</h2>

              {hasEvidence ? (
                <ul className="progress-counts">
                  {measuredExerciseCount > 0 ? (
                    <li>
                      {measuredExerciseCount}{" "}
                      {measuredExerciseCount === 1 ? "exercise" : "exercises"}{" "}
                      recorded
                      {exerciseCount > measuredExerciseCount
                        ? ` (${exerciseCount - measuredExerciseCount} the camera could not measure)`
                        : ""}
                      .
                    </li>
                  ) : null}
                  {loggedCount > 0 ? (
                    <li>
                      {loggedCount} {loggedCount === 1 ? "meal" : "meals"} logged.
                    </li>
                  ) : null}
                </ul>
              ) : (
                <p className="progress-empty">
                  Nothing recorded yet. Your plan can only be reviewed against
                  things you have actually logged, so there is nothing to
                  compare at this stage — that is not a setback, just an
                  absence of data.
                </p>
              )}
            </section>

            {planExists ? (
              <section className="progress-card">
                <h2 className="progress-card-title">What changed in your plan</h2>

                <ul className="progress-changes">
                  <ChangeRow label="Movement" plan={workflow.exercise_plan} />
                  <ChangeRow label="Nutrition" plan={workflow.nutrition_plan} />
                  <ChangeRow label="Daily habits" plan={workflow.behaviour_plan} />
                </ul>
              </section>
            ) : (
              <section className="progress-card">
                <h2 className="progress-card-title">No plan yet</h2>
                <p className="progress-empty">
                  Once you have a plan, this is where you will see what changed
                  in it and why.
                </p>
              </section>
            )}

            {reviewNote ? <p className="progress-note">{reviewNote}</p> : null}

            <div className="progress-actions">
              {/* Offered only when there is something to review. Without
                  evidence the review can only return "not enough data", so
                  the button would promise something it cannot deliver. */}
              {hasEvidence && planExists ? (
                <button
                  type="button"
                  className="progress-button"
                  onClick={review}
                  disabled={reviewing}
                >
                  {reviewing ? "Reviewing…" : "Review my plan against this"}
                </button>
              ) : null}

              <button
                type="button"
                className="progress-button progress-button--quiet"
                onClick={() => navigate("/plan")}
              >
                Back to your plan
              </button>
            </div>
          </>
        ) : null}
      </main>
    </div>
  );
}

export default ProgressPage;
