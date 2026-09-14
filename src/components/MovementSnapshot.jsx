import "./MovementSnapshot.css";

/**
 * The dashboard's "Your latest results" panel.
 *
 * Shows each of the three baseline checks separately, from the stored session
 * (see assessment/utils/movementSnapshot.js). It never shows a combined score
 * and never rates a result; a check that was not completed says so.
 */

function formatDate(value, withYear = true) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    ...(withYear ? { year: "numeric" } : {}),
  });
}

const STATUS_MARKS = {
  completed: "✓",
  invalid: "!",
  skipped: "○",
  not_started: "○",
};

function MovementSnapshot({
  loadState,
  error,
  snapshot,
  onStartAssessment,
  onOpenSession,
  onOpenHistory,
}) {
  const ready = loadState === "ready";
  const hasSession = ready && snapshot && snapshot.state !== "none";

  const badge =
    loadState === "loading" ? "LOADING" : ready ? snapshot.badge : "UNAVAILABLE";

  return (
    <div className="score-card movement-snapshot" aria-labelledby="movement-snapshot-title">

      <div className="section-heading">
        <div>
          <span className="section-eyebrow">MOVEMENT INSIGHT</span>
          <h2 id="movement-snapshot-title">Your latest results</h2>
        </div>

        <span
          className={
            hasSession && snapshot.completed > 0
              ? "coming-pill snapshot-badge snapshot-badge--recorded"
              : "coming-pill snapshot-badge"
          }
        >
          {badge}
        </span>
      </div>


      {loadState === "loading" && (
        <p className="snapshot-message" role="status">Loading your latest results…</p>
      )}

      {loadState === "error" && (
        <p className="snapshot-message" role="alert">
          Your latest results could not be loaded. {error}
        </p>
      )}


      {ready && snapshot.state === "none" && (
        <div className="snapshot-empty">
          <h3>Your movement snapshot</h3>
          <p className="snapshot-count">No checks completed yet</p>
          <p className="snapshot-text">
            Complete your first movement check to start building your personal
            movement profile.
          </p>
          <button type="button" className="primary-button snapshot-cta" onClick={onStartAssessment}>
            Start assessment <span aria-hidden="true">→</span>
          </button>
          <p className="snapshot-disclaimer">
            These checks support movement tracking and are not a medical diagnosis.
          </p>
        </div>
      )}


      {hasSession && (
        <>
          <div className="snapshot-intro">
            <h3>Your movement snapshot</h3>

            <p className="snapshot-count">
              {snapshot.state === "complete"
                ? `${snapshot.completed} of ${snapshot.total} checks completed`
                : `${snapshot.completed} ${snapshot.completed === 1 ? "check" : "checks"} completed • ${snapshot.remaining} remaining`}
            </p>

            <p className="snapshot-text">
              <strong>Your results, shown separately.</strong>{" "}
              Your movement checks look at different areas of movement. We show
              each result separately so you can review your latest assessment
              and track changes over time.
            </p>
          </div>


          <ol
            className="snapshot-progress"
            aria-label={`Assessment progress: ${snapshot.completed} of ${snapshot.total} checks completed`}
          >
            {snapshot.tests.map((t) => (
              <li
                key={t.id}
                className={`snapshot-step snapshot-step--${t.completed ? "done" : "open"}`}
              >
                <span className="snapshot-step__mark" aria-hidden="true">
                  {STATUS_MARKS[t.status]}
                </span>
                <span className="snapshot-step__name">{t.shortTitle}</span>
                <span className="snapshot-step__status">{t.statusLabel}</span>
              </li>
            ))}
          </ol>


          <div className="snapshot-cards">
            {snapshot.tests.map((t) => (
              <article
                key={t.id}
                className={`snapshot-card${t.completed ? "" : " snapshot-card--open"}`}
                aria-labelledby={`snapshot-card-${t.id}`}
              >
                <div className="snapshot-card__head">
                  <span className="snapshot-card__icon" aria-hidden="true">{t.icon}</span>
                  <div>
                    <h4 id={`snapshot-card-${t.id}`}>{t.title}</h4>
                    <span className="snapshot-card__area">{t.area}</span>
                  </div>
                </div>

                <p className={`snapshot-card__status snapshot-card__status--${t.status}`}>
                  <span aria-hidden="true">{STATUS_MARKS[t.status]} </span>
                  {t.statusLabel}
                </p>

                {t.value && (
                  <p className="snapshot-card__value">
                    <span className="snapshot-card__label">Latest result</span>
                    {t.value}
                  </p>
                )}

                {t.details.length > 0 && (
                  <ul className="snapshot-card__details">
                    {t.details.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                )}

                {t.note && <p className="snapshot-card__note">{t.note}</p>}

                {t.previous && (
                  <p className="snapshot-card__previous">
                    Previous result: {t.previous.value}
                    {formatDate(t.previous.date, false) && ` · ${formatDate(t.previous.date, false)}`}
                  </p>
                )}

                <div className="snapshot-card__action">
                  {t.completed ? (
                    <button
                      type="button"
                      className="text-button"
                      onClick={() => onOpenSession(snapshot.sessionId)}
                      aria-label={`View details for ${t.title}`}
                    >
                      View details →
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="text-button"
                      onClick={onStartAssessment}
                      aria-label={`Complete ${t.title} in a new assessment`}
                    >
                      Complete check →
                    </button>
                  )}
                </div>
              </article>
            ))}
          </div>


          <div className="snapshot-footer">
            {formatDate(snapshot.lastUpdated) && (
              <p className="snapshot-updated">
                {snapshot.state === "complete" ? "Your latest assessment · " : ""}
                Last updated: {formatDate(snapshot.lastUpdated)}
              </p>
            )}

            <div className="snapshot-actions">
              <button type="button" className="primary-button snapshot-cta" onClick={onStartAssessment}>
                {snapshot.state === "complete" ? "Take assessment again" : "Complete remaining checks"}
                <span aria-hidden="true">→</span>
              </button>

              <button type="button" className="outline-button snapshot-secondary" onClick={onOpenHistory}>
                View all sessions
              </button>
            </div>

            {snapshot.state !== "complete" && (
              <p className="snapshot-disclaimer">Each new assessment runs all three checks.</p>
            )}

            <p className="snapshot-disclaimer">
              These checks support movement tracking and are not a medical diagnosis.
            </p>
          </div>
        </>
      )}
    </div>
  );
}

export default MovementSnapshot;
