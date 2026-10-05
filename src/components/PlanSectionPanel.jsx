/**
 * One coach's part of the plan, action first.
 *
 * What the user sees, in this order:
 *
 *   1. the actions themselves — the exercise, habit, log or guidance cards
 *   2. one line saying why this coach is involved
 *   3. one useful empty state, when there is nothing to do yet
 *   4. "View details", which holds the rest: focus, decision, tracking,
 *      progress, next step, evidence, and what is still unknown
 *
 * The order is the point of this screen. Status, reasoning and evidence are
 * real and still here, but they sit behind one disclosure instead of leading:
 * a person reading their own plan wants the thing they can do today first, and
 * the audit trail second.
 *
 * Every string comes from the server's unified plan
 * (backend/workflow/response.py). This component chooses order and emphasis,
 * not content: the heading is the coach the server named for this specialist
 * id, and the body is that section's own fields. The client's own words are
 * the field labels that name what the server sent ("Tracking", "Progress").
 */

import { identityFor, statusWording } from "../services/specialistIdentity.js";
import { safeDisplayValue, toArray } from "../services/specialistData.js";
import { emptyStateOf, itemActions } from "../services/unifiedPlan.js";
import { DetailDrawer, Field } from "./ui/primitives.jsx";
import PlanActionItem from "./PlanActionItem.jsx";

import "./PlanSectionPanel.css";

/** The rows inside a server block (tracking, progress), as label/value pairs. */
function Rows({ rows }) {
  const list = toArray(rows).filter((row) => row && (row.label || row.value));

  if (!list.length) return null;

  return (
    <ul className="plan-section-rows">
      {list.map((row, index) => (
        <li key={`${row.label || "row"}-${index}`} className="plan-section-row">
          <span className="plan-section-row-label">{safeDisplayValue(row.label)}</span>
          <span className="plan-section-row-value">{safeDisplayValue(row.value)}</span>
        </li>
      ))}
    </ul>
  );
}

export default function PlanSectionPanel({
  section,
  onAction = null,
  renderSectionExtra = null,
  actionBusyFor = null,
  completion = null,
}) {
  if (!section) return null;

  const identity = identityFor(section.specialist, section.title);
  const actions = itemActions(section);
  const emptyState = emptyStateOf(section);
  const evidence = toArray(section.evidence).map(safeDisplayValue).filter(Boolean);
  const missing = toArray(section.missing).map(safeDisplayValue).filter(Boolean);
  const tracking = section.tracking || null;
  const progress = section.progress || null;
  const status = statusWording(section.team_status, section.team_status_label);

  // What the server sent that is not on the cards themselves. A section with a
  // next step but no records still has something worth opening.
  const hasDetails = Boolean(
    section.current_focus ||
      section.decision ||
      tracking?.label ||
      progress?.label ||
      section.next_step ||
      evidence.length ||
      missing.length,
  );

  return (
    <section
      id={`specialist-${section.specialist}`}
      className={`plan-section-panel mw-card mw-enter plan-section-panel--${
        section.selected ? "selected" : "reviewed"
      }`}
      aria-labelledby={`plan-section-${section.specialist}`}
    >
      <header className="plan-section-header">
        <span className="plan-section-icon" aria-hidden="true">
          {safeDisplayValue(identity.icon) || safeDisplayValue(section.icon) || "•"}
        </span>

        <div className="plan-section-heading">
          <h3 id={`plan-section-${section.specialist}`} className="plan-section-title">
            {safeDisplayValue(identity.coach)}
          </h3>
          {identity.role ? <p className="plan-section-subtitle">{identity.role}</p> : null}
        </div>

        <span className={`mw-badge plan-section-status plan-section-status--${status.tone}`}>
          {safeDisplayValue(status.label)}
        </span>
      </header>

      {/* 1. The actions. */}
      {actions.length ? (
        <>
          <ul className="plan-item-list">
            {actions.map((item, index) => (
              <PlanActionItem
                key={`${item.item_id || item.kind || "item"}-${item.position ?? index}`}
                item={item}
                onAction={onAction}
                completion={completion}
                busy={Boolean(actionBusyFor?.(item))}
              />
            ))}
          </ul>
          {renderSectionExtra ? renderSectionExtra(section) : null}
        </>
      ) : null}

      {/* 2. Why this coach is involved: one sentence, from the server. */}
      {section.short_reason ? (
        <p className="plan-section-reason">{safeDisplayValue(section.short_reason)}</p>
      ) : null}

      {/* 3. The one useful empty state — what is missing, and the single thing
          to do about it. It replaces the actions when there are none, and sits
          with them when the actions are exactly how to start. A section whose
          tracking has a record shows none: it is not empty. */}
      {emptyState && (emptyState.kind === "no_records" || !actions.length) ? (
        <div className="plan-section-empty-state">
          <p className="plan-section-empty-message">
            {safeDisplayValue(emptyState.message)}
          </p>
          {emptyState.action ? (
            <button
              type="button"
              className="mw-btn mw-btn--small plan-section-empty-button"
              onClick={() =>
                onAction?.(emptyState.action, { specialist: section.specialist })
              }
            >
              {safeDisplayValue(emptyState.action.label)}
            </button>
          ) : null}
        </div>
      ) : null}

      {/* 4. Everything else, for whoever wants it: as much detail as the
          server sent, behind one open/close. */}
      {hasDetails ? (
        <DetailDrawer label="View details">
          <div className="plan-section-details">
            <Field label="Current focus" value={section.current_focus} />
            <Field label="What MoveWell decided" value={section.decision} />

            {tracking?.label ? (
              <div className="plan-section-block">
                <h4 className="plan-section-block-title">Tracking</h4>
                <p className="plan-section-block-lead">
                  {safeDisplayValue(tracking.label)}
                </p>
                <Rows rows={tracking.rows} />
              </div>
            ) : null}

            {progress?.label ? (
              <div className="plan-section-block">
                <h4 className="plan-section-block-title">Progress</h4>
                <p className="plan-section-block-lead">
                  {safeDisplayValue(progress.label)}
                </p>
                {progress.plan_version || progress.adaptation_reason ? (
                  <p className="plan-section-meta">
                    {progress.plan_version
                      ? `Plan version ${safeDisplayValue(progress.plan_version)}`
                      : null}
                    {progress.plan_version && progress.adaptation_reason ? " — " : null}
                    {safeDisplayValue(progress.adaptation_reason)}
                  </p>
                ) : null}
                <Rows rows={progress.rows} />
              </div>
            ) : null}

            {section.next_step ? (
              <div className="plan-section-block">
                <h4 className="plan-section-block-title">What happens next</h4>
                <p className="plan-section-block-lead">
                  {safeDisplayValue(section.next_step)}
                </p>
              </div>
            ) : null}

            {evidence.length ? (
              <div className="plan-section-block">
                <h4 className="plan-section-block-title">What this was based on</h4>
                <ul className="plan-section-plain-list">
                  {evidence.map((line, index) => (
                    <li key={`${line}-${index}`}>{line}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            {missing.length ? (
              <div className="plan-section-block">
                <h4 className="plan-section-block-title">What is not known yet</h4>
                <ul className="plan-section-plain-list plan-section-plain-list--missing">
                  {missing.map((line, index) => (
                    <li key={`${line}-${index}`}>{line}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            {section.route ? (
              <a className="plan-section-link" href={section.route}>
                Open {safeDisplayValue(identity.coach)} →
              </a>
            ) : null}
          </div>
        </DetailDrawer>
      ) : section.route ? (
        <a className="plan-section-link" href={section.route}>
          Open {safeDisplayValue(identity.coach)} →
        </a>
      ) : null}
    </section>
  );
}
