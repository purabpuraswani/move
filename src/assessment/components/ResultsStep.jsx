/**
 * The final screen of a session: every measurement it produced, plus the option
 * to save it.
 *
 * The results themselves are rendered by SessionResults, which is shared with
 * the history view so a saved session and a just-finished session are described
 * the same way.
 */

import SessionResults, { SessionSummaryLine } from "./SessionResults.jsx";

export default function ResultsStep({ session, onSave, saveState, saveError, onExit, onViewPlan }) {
  return (
    <div className="assess-card">
      <span className="assess-card__eyebrow">Session complete</span>
      <h1>What was measured</h1>

      <SessionSummaryLine summary={session.summary} />

      <SessionResults session={session} />

      {saveError && <p className="assess-panel__warning">{saveError}</p>}

      {!onSave && (
        <p className="assess-card__caveat">
          You are not signed in, so these measurements cannot be saved. They are on
          this screen only and will be gone once you leave it.
        </p>
      )}

      <div className="assess-card__actions">
        <button type="button" className="assess-btn assess-btn--ghost" onClick={onExit}>
          {saveState === "saved" ? "Back to dashboard" : "Leave without saving"}
        </button>

        {onSave && saveState !== "saved" && (
          <button
            type="button"
            className="assess-btn assess-btn--primary"
            disabled={saveState === "saving"}
            onClick={onSave}
          >
            {saveState === "saving" ? "Saving…" : "Save these results"}
          </button>
        )}

        {saveState === "saved" && (
          <>
            <span className="assess-saved">Saved to your account</span>
            {onViewPlan && (
              <button
                type="button"
                className="assess-btn assess-btn--primary"
                onClick={onViewPlan}
              >
                See your personalized plan →
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
