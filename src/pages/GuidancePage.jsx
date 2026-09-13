/**
 * Your AI team.
 *
 * Three things happen on this page, in this order: it says what the agents can
 * work from, it lets the user ask for guidance, and it shows what came back.
 *
 * Two decisions shape it.
 *
 * Nothing is generated on arrival. Opening the page reads the last run and the
 * current state, both cheap; writing new guidance costs a model call and happens
 * only when the user presses the button. A page that generates on mount also
 * generates when somebody hits back.
 *
 * Every state of every agent is shown as itself. Guidance that was withheld for
 * breaking the safety rules is not the same as a provider that could not be
 * reached, which is not the same as a user who has nothing recorded yet. Folding
 * those into one "unavailable" would hide the one case where something was
 * written and deliberately not shown.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getToken } from "../services/auth";
import {
  NAVIGATION_AGENT,
  WELLNESS_AGENT,
  fetchGuidanceStatus,
  fetchLatestGuidance,
  runGuidance,
} from "../services/guidance";
import {
  toArray,
  safeDisplayValue,
  normalizeRecommendation,
  normalizeEvidence,
} from "../services/specialistData.js";

import "./AssessmentPage.css";
import "./GuidancePage.css";

// What the user can do about a gap. The wording and the destination belong here
// rather than on the server, which only names the action.
const ACTIONS = {
  record_assessment: { label: "Record a movement check", to: "/assessment" },
  complete_profile: { label: "Answer the setup questions", to: "/onboarding" },
  add_report: { label: "Add a medical report", to: "/reports" },
  confirm_report: { label: "Check and confirm your report values", to: "/reports" },
};

const STAGE_STATES = {
  complete: { label: "In use", tone: "good" },
  waiting_for_your_confirmation: { label: "Waiting for you", tone: "wait" },
  not_configured: { label: "Not set up here", tone: "off" },
  no_reports: { label: "Nothing added yet", tone: "off" },
  ready: { label: "Ready", tone: "good" },
  runs_after_wellness_guidance: { label: "Runs second", tone: "wait" },
  blocked: { label: "Cannot run", tone: "off" },
};

const TEST_STATUS_LABELS = {
  completed: "measured",
  invalid: "not usable",
  skipped: "skipped",
  not_started: "not reached",
};

function formatWhen(value) {
  if (!value) return "an unknown time";

  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return "an unknown time";
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch (_) {
    return "an unknown time";
  }
}

/**
 * What a piece of guidance was written from.
 *
 * Counts and statuses, never the readings themselves. Those live on the pages
 * that own them, and a second copy here would be the same health information in
 * a second place.
 */
function Basis({ context }) {
  if (!context) return null;

  const tests = toArray(context.movementTests);

  return (
    <div className="guide-basis">
      <h3>What this was written from</h3>

      <ul>
        <li>
          {context.profileAvailable
            ? `Your setup answers (${safeDisplayValue(context.profileFieldCount)} answered).`
            : "Your setup answers were not available."}
        </li>

        <li>
          {context.movementAvailable
            ? `A movement check from ${formatWhen(context.movementCompletedAt)}.`
            : "No usable movement observations."}
          {tests.length > 0 && (
            <span className="guide-basis__tests">
              {tests.map((test, idx) => (
                <span className="guide-basis__test" key={test?.id || idx}>
                  {safeDisplayValue(test?.name)}: {safeDisplayValue(TEST_STATUS_LABELS[test?.status] ?? test?.status)}
                </span>
              ))}
            </span>
          )}
        </li>

        <li>
          {context.confirmedReportCount > 0
            ? `${safeDisplayValue(context.confirmedReportCount)} confirmed report${
                context.confirmedReportCount === 1 ? "" : "s"
              }.`
            : "No confirmed report values."}
          {context.unconfirmedReportCount > 0 && (
            <>
              {" "}
              {safeDisplayValue(context.unconfirmedReportCount)} report
              {context.unconfirmedReportCount === 1 ? " is" : "s are"} still
              waiting for you to confirm, and nothing from{" "}
              {context.unconfirmedReportCount === 1 ? "it" : "them"} was used.
            </>
          )}
        </li>
      </ul>
    </div>
  );
}

/** The wellness agent's output, as written. */
function WellnessOutput({ output }) {
  if (!output) return null;

  const opening = safeDisplayValue(output.opening);
  const closing = safeDisplayValue(output.closing);
  const observations = toArray(output.observations);
  const focusAreas = toArray(output.focusAreas);
  const habits = toArray(output.habits);
  const missingInformation = toArray(output.missingInformation);

  return (
    <>
      {opening && <p className="guide-lede">{opening}</p>}

      {observations.length > 0 && (
        <section className="guide-block">
          <h3>What was observed</h3>

          <dl className="guide-observations">
            {observations.map((item, idx) => (
              <div className="guide-observation" key={item?.heading || idx}>
                <dt>{safeDisplayValue(item?.heading || item?.title || item)}</dt>
                <dd>{safeDisplayValue(item?.detail || item?.description || item?.why)}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {focusAreas.length > 0 && (
        <section className="guide-block">
          <h3>Worth some attention</h3>

          <div className="guide-areas">
            {focusAreas.map((area, idx) => (
              <article className="guide-area" key={area?.title || idx}>
                <h4>{safeDisplayValue(area?.title || area?.name)}</h4>

                {area?.whyThisCameUp && (
                  <p className="guide-area__why">{safeDisplayValue(area.whyThisCameUp)}</p>
                )}

                <ul>
                  {toArray(area?.suggestions).map((suggestion, sIdx) => {
                    const norm = normalizeRecommendation(suggestion, sIdx);
                    const text = safeDisplayValue(norm?.title || norm?.action || suggestion);
                    return <li key={norm?.id || sIdx}>{text}</li>;
                  })}
                </ul>
              </article>
            ))}
          </div>
        </section>
      )}

      {habits.length > 0 && (
        <section className="guide-block">
          <h3>General habits</h3>

          <ul className="guide-list">
            {habits.map((habit, idx) => {
              const norm = normalizeRecommendation(habit, idx);
              const text = safeDisplayValue(norm?.title || norm?.action || habit);
              return <li key={norm?.id || idx}>{text}</li>;
            })}
          </ul>
        </section>
      )}

      {missingInformation.length > 0 && (
        <section className="guide-block guide-block--gaps">
          <h3>What was missing</h3>

          <ul className="guide-list">
            {missingInformation.map((gap, idx) => (
              <li key={idx}>{safeDisplayValue(gap?.reason || gap?.capability || gap)}</li>
            ))}
          </ul>
        </section>
      )}

      {closing && <p className="guide-closing">{closing}</p>}
    </>
  );
}

/** The care navigation agent's output. Roles are labelled by the server. */
function NavigationOutput({ output }) {
  if (!output) return null;

  const opening = safeDisplayValue(output.opening);
  const considerations = toArray(output.considerations);
  const questionsToAsk = toArray(output.questionsToAsk);
  const limitations = toArray(output.limitations);

  return (
    <>
      {opening && <p className="guide-lede">{opening}</p>}

      {considerations.length > 0 && (
        <section className="guide-block">
          <h3>People you might talk to</h3>

          <div className="guide-people">
            {considerations.map((item, idx) => (
              <article className="guide-person" key={item?.professionalType || idx}>
                <h4>{safeDisplayValue(item?.label || item?.professionalType)}</h4>
                {item?.note ? (
                  <p className="guide-person__note">{safeDisplayValue(item.note)}</p>
                ) : null}
                {item?.whatTheyCouldLookAt ? (
                  <p>{safeDisplayValue(item.whatTheyCouldLookAt)}</p>
                ) : null}

                {item?.whyItCameUp ? (
                  <p className="guide-person__why">{safeDisplayValue(item.whyItCameUp)}</p>
                ) : null}
              </article>
            ))}
          </div>
        </section>
      )}

      {questionsToAsk.length > 0 && (
        <section className="guide-block">
          <h3>Questions you could take with you</h3>

          <ul className="guide-list guide-list--questions">
            {questionsToAsk.map((question, idx) => (
              <li key={idx}>{safeDisplayValue(question?.question || question?.text || question)}</li>
            ))}
          </ul>
        </section>
      )}

      {limitations.length > 0 && (
        <section className="guide-block guide-block--gaps">
          <h3>What this tool could not tell you</h3>

          <ul className="guide-list">
            {limitations.map((limit, idx) => (
              <li key={idx}>{safeDisplayValue(limit?.reason || limit?.limitation || limit)}</li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

/**
 * One agent's result, in whichever state it came back in.
 *
 * The withheld case is the reason this wrapper exists. It says plainly that
 * something was written and not shown, and names what was wrong with it without
 * repeating the sentence that was wrong.
 */
function AgentResult({ title, subtitle, result, children }) {
  const state = result?.state ?? "not_run";

  return (
    <section className={`guide-panel guide-panel--${state}`}>
      <header className="guide-panel__head">
        <div>
          <h2>{safeDisplayValue(title)}</h2>
          <p>{safeDisplayValue(subtitle)}</p>
        </div>

        {result?.retriedAfterRuleBreak && state === "ok" && (
          <span className="guide-tag">Rewritten once to stay within the rules</span>
        )}
      </header>

      {state === "ok" && children}

      {state === "withheld_by_safety_rules" && (
        <div className="guide-withheld">
          <p>{safeDisplayValue(result?.message)}</p>

          {toArray(result?.brokenRules).length > 0 && (
            <ul className="guide-list">
              {toArray(result.brokenRules).map((rule, idx) => (
                <li key={idx}>It {safeDisplayValue(rule?.rule || rule?.message || rule)}.</li>
              ))}
            </ul>
          )}

          <p className="guide-withheld__hint">
            Generating again may produce something acceptable. Nothing was edited
            to get around the rules.
          </p>
        </div>
      )}

      {state === "failed" && (
        <p className="guide-note guide-note--bad">{safeDisplayValue(result?.message)}</p>
      )}

      {state === "not_run" && <p className="guide-note">{safeDisplayValue(result?.message)}</p>}
    </section>
  );
}

/** What each agent may and may not do, from the server's own list. */
function AgentLimits({ agents }) {
  const [open, setOpen] = useState(false);
  const agentList = toArray(agents);

  if (agentList.length === 0) return null;

  return (
    <section className="guide-limits">
      <button
        type="button"
        className="guide-limits__toggle"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        {open ? "Hide" : "Show"} what each agent may and may not do
      </button>

      {open && (
        <div className="guide-limits__body">
          {agentList.map((agent, idx) => (
            <article className="guide-limit" key={agent?.id || idx}>
              <h3>
                <span className="guide-limit__stage">{safeDisplayValue(agent?.stage)}</span>
                {safeDisplayValue(agent?.name)}
              </h3>

              <p className="guide-limit__role">{safeDisplayValue(agent?.role)}</p>

              <div className="guide-limit__columns">
                <div>
                  <h4>It can</h4>
                  <ul>
                    {toArray(agent?.canDo).map((item, cIdx) => (
                      <li key={cIdx}>{safeDisplayValue(item?.description || item?.action || item)}</li>
                    ))}
                  </ul>
                </div>

                <div>
                  <h4>It cannot</h4>
                  <ul className="guide-limit__cannot">
                    {toArray(agent?.cannotDo).map((item, cIdx) => (
                      <li key={cIdx}>{safeDisplayValue(item?.description || item?.action || item)}</li>
                    ))}
                  </ul>
                </div>
              </div>

              {agent?.note && <p className="guide-limit__note">{safeDisplayValue(agent.note)}</p>}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function GuidancePage() {
  const navigate = useNavigate();

  const signedIn = Boolean(getToken());

  const [pageState, setPageState] = useState(() => (signedIn ? "loading" : "signed-out"));
  const [pageError, setPageError] = useState(null);

  const [status, setStatus] = useState(null);
  const [run, setRun] = useState(null);
  const [notice, setNotice] = useState(null);

  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState(null);

  const load = useCallback(async () => {
    setPageState("loading");
    setPageError(null);

    try {
      // Both reads are cheap and neither triggers a model call, so they go
      // together and the page opens in one state rather than two.
      const [statusData, latest] = await Promise.all([
        fetchGuidanceStatus(),
        fetchLatestGuidance(),
      ]);

      setStatus(statusData);
      setRun(latest.run);
      setPageState("ready");
    } catch (error) {
      setPageError(error.message);
      setPageState("error");
    }
  }, []);

  useEffect(() => {
    if (!signedIn) {
      return;
    }

    let ignore = false;

    Promise.all([
      fetchGuidanceStatus(),
      fetchLatestGuidance(),
    ])
      .then(([statusData, latest]) => {
        if (!ignore) {
          setStatus(statusData);
          setRun(latest.run);
          setPageState("ready");
        }
      })
      .catch((error) => {
        if (!ignore) {
          setPageError(error.message);
          setPageState("error");
        }
      });

    return () => {
      ignore = true;
    };
  }, [signedIn]);

  async function generate() {
    setRunning(true);
    setRunError(null);
    setNotice(null);

    try {
      const result = await runGuidance();

      // Fresh output is current by definition, so it carries no staleness.
      setRun({ ...result, isStale: false });

      if (result.saved === false) {
        setNotice(
          "This guidance could not be saved, so it will not be here when you " +
            "come back. Everything shown was still produced from your own " +
            "information."
        );
      }

      // The plan travels with the result, so the page reflects what the run
      // actually worked from rather than what was true when it was opened.
      setStatus((current) =>
        current ? { ...current, plan: result.plan, context: result.context } : current
      );
    } catch (error) {
      setRunError(error.message);
    } finally {
      setRunning(false);
    }
  }

  const plan = status?.plan;
  const disclaimer = status?.disclaimer;
  const safetyNote = status?.safetyNote;

  const wellness = run?.agents?.[WELLNESS_AGENT];
  const navigation = run?.agents?.[NAVIGATION_AGENT];

  const canRun = Boolean(plan?.canRun) && !running;

  return (
    <div className="guide-page">
      <header className="assess-header">
        <button
          type="button"
          className="assess-header__logo"
          onClick={() => navigate("/dashboard")}
        >
          <span className="assess-header__mark">M</span>
          <span>
            MoveWell<small>AI</small>
          </span>
        </button>

        <span className="assess-header__title">Your AI team</span>

        <button
          type="button"
          className="assess-btn assess-btn--quiet"
          onClick={() => navigate("/dashboard")}
        >
          Dashboard
        </button>
      </header>

      <main className="guide-main">
        <div className="guide-intro">
          <span className="guide-eyebrow">GUIDANCE</span>
          <h1>Guidance written from your own information</h1>
          <p>
            Two agents work here. One reflects back what your movement check
            showed and what you confirmed from your report, and suggests general
            habits. The other suggests the kind of professional you might raise
            something with, and questions to take with you. Neither can diagnose
            anything, decide what a result means, or tell you whether something
            is urgent.
          </p>
        </div>

        {pageState === "signed-out" && (
          <p className="guide-empty">Sign in to use your AI team.</p>
        )}

        {pageState === "loading" && (
          <p className="guide-empty">Checking what your agents can work from…</p>
        )}

        {pageState === "error" && (
          <div className="guide-empty">
            <p>This page could not be loaded. {safeDisplayValue(pageError)}</p>
            <button
              type="button"
              className="assess-btn assess-btn--ghost"
              onClick={load}
            >
              Try again
            </button>
          </div>
        )}

        {pageState === "ready" && plan && (
          <>
            <section className="guide-state">
              <h2>Where things stand</h2>

              <ol className="guide-stages">
                {toArray(plan?.stages).map((stage, idx) => {
                  const stageState = typeof stage?.state === "string" ? stage.state : stage?.state?.status || "";
                  const shape = STAGE_STATES[stageState] ?? {
                    label: safeDisplayValue(stageState || stage?.state),
                    tone: "off",
                  };

                  return (
                    <li className="guide-stage" key={stage?.id || idx}>
                      <span className="guide-stage__number">{safeDisplayValue(stage?.stage)}</span>

                      <span className="guide-stage__body">
                        <span className="guide-stage__name">{safeDisplayValue(stage?.name)}</span>
                        {stage?.note && (
                          <span className="guide-stage__note">{safeDisplayValue(stage.note)}</span>
                        )}
                      </span>

                      <span className={`guide-pill guide-pill--${shape.tone}`}>
                        {safeDisplayValue(shape.label)}
                      </span>
                    </li>
                  );
                })}
              </ol>

              {toArray(plan?.blockers).length > 0 && (
                <div className="guide-blockers">
                  {toArray(plan.blockers).map((blocker, bIdx) => (
                    <p key={bIdx}>{safeDisplayValue(blocker?.message || blocker?.reason || blocker)}</p>
                  ))}
                </div>
              )}

              {toArray(plan?.notes).length > 0 && (
                <ul className="guide-list guide-list--notes">
                  {toArray(plan.notes).map((note, nIdx) => (
                    <li key={nIdx}>{safeDisplayValue(note?.message || note?.note || note)}</li>
                  ))}
                </ul>
              )}

              {toArray(plan?.suggestedActions).length > 0 && (
                <div className="guide-actions">
                  {toArray(plan.suggestedActions).map((action, aIdx) => {
                    const actionKey = typeof action === "string" ? action : action?.type || action?.action || action?.id;
                    const shape = ACTIONS[actionKey];

                    if (!shape) return null;

                    return (
                      <button
                        type="button"
                        className="assess-btn assess-btn--ghost"
                        key={actionKey || aIdx}
                        onClick={() => navigate(shape.to)}
                      >
                        {safeDisplayValue(shape.label)}
                      </button>
                    );
                  })}
                </div>
              )}

              <div className="guide-run">
                <button
                  type="button"
                  className="assess-btn assess-btn--primary"
                  disabled={!canRun}
                  onClick={generate}
                >
                  {running
                    ? "Writing your guidance…"
                    : run
                      ? "Generate again"
                      : "Generate my guidance"}
                </button>

                {running && (
                  <p className="guide-note">
                    This takes a few moments. Two agents run one after the other.
                  </p>
                )}

                {!plan.canRun && (
                  <p className="guide-note">
                    Nothing is generated until there is something honest to write
                    from.
                  </p>
                )}

                {runError && (
                  <p className="guide-note guide-note--bad">{safeDisplayValue(runError)}</p>
                )}
              </div>
            </section>

            {notice && <p className="guide-note guide-note--bad">{safeDisplayValue(notice)}</p>}

            {!run && (
              <p className="guide-empty">
                No guidance has been generated yet. Nothing is written until you
                ask for it.
              </p>
            )}

            {run && (
              <>
                <div className="guide-meta">
                  <p>
                    Written {safeDisplayValue(formatWhen(run?.generatedAt))}
                    {run?.model ? ` by ${safeDisplayValue(run.model)}` : ""}.
                  </p>

                  {run.isStale === true && (
                    <p className="guide-stale">
                      Your information has changed since this was written.
                      Generate again to include what is new.
                    </p>
                  )}
                </div>

                <Basis context={run.context} />

                <AgentResult
                  title="Wellness guide"
                  subtitle="Reflects back what was observed, and suggests general habits."
                  result={wellness}
                >
                  {wellness?.output && <WellnessOutput output={wellness.output} />}
                </AgentResult>

                <AgentResult
                  title="Care navigator"
                  subtitle="Options you may consider, and questions you could ask."
                  result={navigation}
                >
                  {navigation?.output && (
                    <NavigationOutput output={navigation.output} />
                  )}
                </AgentResult>
              </>
            )}

            <AgentLimits agents={status?.agents ?? []} />

            <footer className="guide-footer">
              {safetyNote && <p className="guide-safety">{safeDisplayValue(safetyNote)}</p>}
              {disclaimer && <p className="guide-disclaimer">{safeDisplayValue(disclaimer)}</p>}
            </footer>
          </>
        )}
      </main>
    </div>
  );
}

export default GuidancePage;
