/**
 * The final screen of a session: every measurement it produced, plus the option
 * to save it.
 *
 * The results themselves are rendered by SessionResults, which is shared with
 * the history view so a saved session and a just-finished session are described
 * the same way.
 */

import SessionResults, { SessionSummaryLine } from "./SessionResults.jsx";

export default function ResultsStep({ session, onSave, saveState, saveError, onExit, onViewPlan, onRetryPlan, onRetake }) {
  return (
    <div className="assess-card">
      <span className="assess-card__eyebrow">Session complete</span>
      <h1>What was measured</h1>

      <SessionSummaryLine summary={session.summary} />

      <SessionResults session={session} />

      {saveError && <p className="assess-panel__warning">{saveError}</p>}

      {saveState === "planning" && (
        <p className="assess-card__caveat" role="status" aria-live="polite">
          Results saved and verified. MoveWell is selecting relevant specialists and running the required workflow and safety checks.
        </p>
      )}

      {saveState === "plan_error" && (
        <p className="assess-card__caveat" role="status">
          Your assessment is saved. Plan generation failed, so no plan is being shown as ready.
        </p>
      )}

      {saveState === "saved_incomplete" && (
        <p className="assess-card__caveat" role="status">
          These results are saved, but both Shoulder Raise and One-Leg Stand need usable measurements before personalized plan generation can start.
        </p>
      )}

      {!onSave && (
        <p className="assess-card__caveat">
          You are not signed in, so these measurements cannot be saved. They are on
          this screen only and will be gone once you leave it.
        </p>
      )}

      <div className="assess-card__actions">
        <button type="button" className="assess-btn assess-btn--ghost" onClick={onExit}>
          {["saved", "planning", "plan_error", "saved_incomplete"].includes(saveState)
            ? "Back to dashboard"
            : "Leave without saving"}
        </button>

        {onSave && ["idle", "saving"].includes(saveState) && (
          <button
            type="button"
            className="assess-btn assess-btn--primary"
            disabled={saveState === "saving"}
            onClick={onSave}
          >
            {saveState === "saving" ? "Saving…" : saveError ? "Retry saving" : "Save these results"}
          </button>
        )}

        {saveState === "saved" && (
          <div className="assess-card__saved-group">
            <span className="assess-saved">✓ Saved to your account</span>
            {onViewPlan && (
              <button
                type="button"
                className="assess-btn assess-btn--primary"
                onClick={onViewPlan}
              >
                See your personalized plan →
              </button>
            )}
          </div>
        )}

        {saveState === "planning" && (
          <span className="assess-saved">✓ Saved to your account</span>
        )}

        {saveState === "plan_error" && (
          <button type="button" className="assess-btn assess-btn--primary" onClick={onRetryPlan}>
            Retry plan generation
          </button>
        )}

        {saveState === "saved_incomplete" && (
          <button type="button" className="assess-btn assess-btn--primary" onClick={onRetake}>
            Repeat movement assessment
          </button>
        )}
      </div>
    </div>
  );
}
