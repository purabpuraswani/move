/**
 * How the five specialists produced ONE plan.
 *
 * The steps come from the server (`unified_plan.collaboration`), built from the
 * same decisions the sections show. What this component controls is only how
 * that reads: a calm vertical flow — what MoveWell looked at, then each coach's
 * one-line contribution, then the single plan those contributions became.
 *
 * A specialist the server reports as `participated: false` looks clearly
 * quieter and is marked as not part of the plan, so its sentence ("Not needed
 * right now", "Not assessed yet") is read as a statement about the plan rather
 * than as advice. Where the user can do something about that — complete the
 * check-in, take the assessment — the step carries the server's own action as a
 * small button.
 *
 * Not a chat, not a transcript, not a diagram of how this is built: no prompts,
 * no reasoning, no internal vocabulary. Every sentence here is the server's.
 */

import { identityFor } from "../services/specialistIdentity.js";
import { safeDisplayValue } from "../services/specialistData.js";

import "./CollaborationTimeline.css";

function modifierFor(step) {
  if (step.kind === "assessment") return "input";
  if (step.kind === "synthesis") return "synthesis";

  return step.participated ? "contributor" : "inactive";
}

/** The step's coach, from the specialist identity this build knows. */
function identityOf(step) {
  return step.specialist ? identityFor(step.specialist, step.title) : null;
}

/** What to call a step: the coach's name where there is one, the server's own
 * title otherwise (the input step, the synthesis step). */
function nameOf(step) {
  const identity = identityOf(step);

  return identity?.coach || safeDisplayValue(step.title) || null;
}

function IconOf(step) {
  const identity = identityOf(step);

  return identity?.icon || safeDisplayValue(step.icon) || "•";
}

export default function CollaborationTimeline({ collaboration, onAction = null }) {
  const steps = Array.isArray(collaboration?.steps) ? collaboration.steps : [];

  if (!steps.length) return null;

  const title = safeDisplayValue(collaboration.title) || "How your MoveWell team worked";

  return (
    <section className="collab" aria-labelledby="collab-heading">
      <header className="collab-header">
        <span className="mw-eyebrow">Behind your plan</span>
        <h2 id="collab-heading" className="mw-h3 collab-title">
          {title}
        </h2>
        {collaboration.intro ? (
          <p className="mw-lede collab-intro">{safeDisplayValue(collaboration.intro)}</p>
        ) : null}
      </header>

      <ol className="collab-flow">
        {steps.map((step, index) => {
          const modifier = modifierFor(step);
          const identity = identityOf(step);
          const name = nameOf(step);
          const summary = safeDisplayValue(step.summary);
          const actionLabel = safeDisplayValue(step.action?.label);
          const inactive = modifier === "inactive";

          const classes = [
            "collab-step",
            `collab-step--${modifier}`,
            identity?.accent ? `collab-step--accent-${identity.accent}` : null,
          ]
            .filter(Boolean)
            .join(" ");

          return (
            <li key={`${step.kind}-${step.specialist || index}`} className={classes}>
              <div className="collab-node" aria-hidden="true">
                {IconOf(step)}
              </div>

              <div className="collab-body">
                <p className="collab-step-name">{name}</p>

                {inactive ? (
                  <p className="collab-step-label">Not part of this plan</p>
                ) : null}

                {summary ? <p className="collab-step-summary">{summary}</p> : null}

                {actionLabel ? (
                  <div className="collab-step-actions">
                    <button
                      type="button"
                      className="mw-btn mw-btn--small collab-step-action"
                      onClick={() => onAction?.(step.action, step)}
                    >
                      {actionLabel}
                    </button>
                  </div>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
