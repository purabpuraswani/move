/**
 * Today's habit action, and the button that actually records it.
 *
 * This is the piece that closes the behaviour evidence loop. Before it, the
 * Behaviour Specialist could set a habit goal and then had nothing to review
 * it against, so habit adherence was structurally UNKNOWN no matter what the
 * user did.
 *
 * Two things make it real rather than a button that turns green:
 *
 *   1. Pressing it POSTs to /api/behaviour-log, and the record is what the
 *      Behaviour Agent reads on the next workflow run.
 *   2. The done/not-done state is read back from the server on mount, so it
 *      survives a page reload. Nothing about "did I do this" lives in React
 *      state alone.
 *
 * Skipping is offered alongside completing, and recorded as itself. Someone
 * who chose to skip has told us something; someone who never opened the app
 * has not, and the two must not collapse into one absence.
 */

import { useCallback, useEffect, useState } from "react";

import {
  DIFFICULTIES,
  DIFFICULTY_LABELS,
  actionRecordedToday,
  fetchBehaviourActions,
  recordBehaviourAction,
} from "../services/behaviourLog";

import "./BehaviourActionPanel.css";

function BehaviourActionPanel({ goals = [], planId = null, onActionRecorded = null }) {
  const [actions, setActions] = useState([]);
  const [state, setState] = useState("loading");
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(null);

  const load = useCallback(async () => {
    if (typeof window !== "undefined" && window.__mockBehaviourActions) {
      setActions(window.__mockBehaviourActions);
      setState("ready");
      return;
    }

    setState("loading");
    setError(null);

    try {
      const data = await fetchBehaviourActions({ limit: 100 });

      setActions(data?.actions || []);
      setState("ready");
    } catch (loadError) {
      setError(loadError.message);
      setState("error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    window.__setMockBehaviourActions = (mockList) => {
      window.__mockBehaviourActions = mockList;
      setActions(mockList);
      setState("ready");
    };
    return () => {
      delete window.__setMockBehaviourActions;
    };
  }, []);

  const record = useCallback(
    async (topicId, status, difficulty) => {
      setSaving(`${topicId}:${status}`);
      setError(null);

      try {
        await recordBehaviourAction({ topicId, status, difficulty, planId });

        if (typeof onActionRecorded === "function") {
          onActionRecorded({ topicId, status, difficulty });
        }

        // Re-read rather than pushing the new record into local state: the
        // server is the source of truth for what was recorded, and this is
        // the same list a reload would show.
        await load();
      } catch (saveError) {
        setError(saveError.message);
      } finally {
        setSaving(null);
      }
    },
    [load, planId],
  );

  if (!goals.length) {
    return null;
  }

  return (
    <section className="behaviour-actions">
      <h3 className="behaviour-actions-title">Today&rsquo;s action</h3>

      {state === "loading" ? (
        <p className="behaviour-actions-status">Checking what you recorded…</p>
      ) : null}

      {error ? <p className="behaviour-actions-error">{error}</p> : null}

      <ul className="behaviour-actions-list">
        {goals.map((goal) => {
          const recorded = actionRecordedToday(actions, goal.topicId);
          const busy = saving && saving.startsWith(`${goal.topicId}:`);

          return (
            <li key={goal.topicId} className="behaviour-action">
              <span className="behaviour-action-name">
                {typeof goal.name === "string" ? goal.name : String(goal.name || "")}
              </span>
              {goal.action ? (
                <span className="behaviour-action-text">
                  {typeof goal.action === "string" ? goal.action : String(goal.action || "")}
                </span>
              ) : null}

              {recorded ? (
                <>
                  <span
                    className={
                      recorded.status === "completed"
                        ? "behaviour-action-done"
                        : "behaviour-action-done behaviour-action-done--skipped"
                    }
                  >
                    {recorded.status === "completed"
                      ? "Recorded as done today"
                      : "Recorded as skipped today"}
                    {recorded.difficulty
                      ? ` — ${DIFFICULTY_LABELS[recorded.difficulty] || recorded.difficulty}`
                      : null}
                  </span>

                  {/* Asked only after the action is recorded, so answering
                      it is never a condition of recording. A goal recorded
                      without it is a perfectly good record. */}
                  {recorded.status === "completed" && !recorded.difficulty ? (
                    <div className="behaviour-action-feedback">
                      <span className="behaviour-action-question">
                        How did that feel?
                      </span>
                      {DIFFICULTIES.map((difficulty) => (
                        <button
                          key={difficulty}
                          type="button"
                          className="behaviour-action-chip"
                          disabled={Boolean(busy)}
                          onClick={() =>
                            record(goal.topicId, "completed", difficulty)
                          }
                        >
                          {DIFFICULTY_LABELS[difficulty]}
                        </button>
                      ))}
                    </div>
                  ) : null}
                </>
              ) : (
                <div className="behaviour-action-buttons">
                  <button
                    type="button"
                    className="behaviour-action-complete"
                    disabled={Boolean(busy) || state === "loading"}
                    onClick={() => record(goal.topicId, "completed", null)}
                  >
                    {busy ? "Recording…" : "I did this"}
                  </button>
                  <button
                    type="button"
                    className="behaviour-action-skip"
                    disabled={Boolean(busy) || state === "loading"}
                    onClick={() => record(goal.topicId, "skipped", null)}
                  >
                    Skipped today
                  </button>
                </div>
              )}
            </li>
          );
        })}
      </ul>

      <p className="behaviour-actions-note">
        What you record here is what your habit plan is reviewed against.
        Nothing recorded means nothing is assumed.
      </p>
    </section>
  );
}

export default BehaviourActionPanel;
