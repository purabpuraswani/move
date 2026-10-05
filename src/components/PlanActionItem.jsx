/**
 * One action in the plan, as a card a person can act on.
 *
 * Everything on it is presentation of what the server sent: the exercise's own
 * library image (keyed on the item's own id, so it cannot show a different
 * movement), the prescription, the focus, the reason, the state of this item's
 * tracking, and the button — whose label, kind and route all come from
 * `item.action`.
 *
 * Two things are deliberately folded away rather than printed on every card:
 * the progression and regression guidance (behind "How to progress / make it
 * easier"), and any repeated "nothing recorded yet" line (the section shows one
 * useful empty state instead, and a card with no records says nothing at all).
 * A safety note appears only on an item the Safety review actually touched, and
 * a withheld item says so and offers no second way to record it as done.
 */

import { useState } from "react";

import { getExerciseImage } from "../movementDemos/exerciseImages.js";
import { safeDisplayValue, toArray } from "../services/specialistData.js";
import {
  actionOf,
  dosageOf,
  exerciseIdOf,
  progressOf,
  safetyNoteOf,
  trackingOf,
} from "../services/unifiedPlan.js";

import "./PlanSectionPanel.css";

/**
 * "I did this", for an exercise the camera is not being used for. A self-report
 * — stored with `source: "manual_confirmation"` and no measurements — which is
 * why it can be un-ticked while a camera-recorded session cannot.
 */
function ManualCompletion({ exerciseId, planId, itemId, completion }) {
  const [busy, setBusy] = useState(false);

  if (!completion || !exerciseId) return null;

  const done = Boolean(completion.completedIds?.has(exerciseId));
  const result = completion.resultFor?.(exerciseId) || null;
  const manualResultId = result?.source === "manual_confirmation" ? result.id : null;
  const lockedByCamera = done && !manualResultId;
  const checkboxId = `plan-item-done-${exerciseId}`;

  async function toggle(event) {
    setBusy(true);

    try {
      if (event.target.checked) {
        await completion.markCompleted?.(exerciseId, { planId, itemId });
      } else if (manualResultId) {
        await completion.undoCompletion?.(manualResultId);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="plan-item-check">
      <input
        type="checkbox"
        id={checkboxId}
        checked={done}
        disabled={busy || lockedByCamera}
        onChange={toggle}
      />
      <label htmlFor={checkboxId}>
        {lockedByCamera
          ? "Completed (recorded session)"
          : done
            ? "Completed"
            : "Done without the camera"}
      </label>
    </div>
  );
}

function TrackingLine({ tracking }) {
  // Only shown when there is something to say. "Nothing recorded yet" on every
  // card is the repetition this screen removes; the section says it once, with
  // something to do about it.
  if (!tracking?.recorded) return null;

  return (
    <p className="plan-item-tracking">
      <span>{safeDisplayValue(tracking.label)}</span>
      {tracking.summary ? (
        <span className="plan-item-tracking-detail">{safeDisplayValue(tracking.summary)}</span>
      ) : null}
    </p>
  );
}

function ProgressLine({ progress }) {
  const direction = safeDisplayValue(progress?.direction);

  // Nothing recorded, or not enough to compare, says nothing here.
  if (!progress?.label || ["NOT_RECORDED", "NOT_ENOUGH_DATA"].includes(direction)) {
    return null;
  }

  return (
    <p className={`plan-item-progress plan-item-progress--${String(direction).toLowerCase()}`}>
      {safeDisplayValue(progress.label)}
    </p>
  );
}

export default function PlanActionItem({ item, onAction = null, completion = null, busy = false }) {
  if (!item) return null;

  const action = actionOf(item);
  const exerciseId = exerciseIdOf(item);
  const image = exerciseId ? getExerciseImage(exerciseId) : null;
  const dosage = dosageOf(item);
  const tracking = trackingOf(item);
  const progress = progressOf(item);
  const safety = safetyNoteOf(item);
  const metadata = item.metadata || {};
  const safetyNotes = toArray(metadata.safety_notes).map(safeDisplayValue).filter(Boolean);
  const withheld = Boolean(item.withheld) || Boolean(safety?.withheld);
  const hasGuidance = Boolean(metadata.progression || metadata.regression);

  return (
    <li
      className={`plan-item mw-card mw-card--flat plan-item--${
        safeDisplayValue(item.kind) || "action"
      }${withheld ? " plan-item--withheld" : ""}`}
    >
      {image ? (
        <img className="plan-item-image" src={image.src} alt={image.alt} loading="lazy" />
      ) : null}

      <div className="plan-item-body">
        <div className="plan-item-head">
          <h4 className="plan-item-title">{safeDisplayValue(item.title)}</h4>
          {dosage ? <span className="mw-chip plan-item-dosage">{safeDisplayValue(dosage)}</span> : null}
        </div>

        {item.target ? (
          <p className="plan-item-focus">
            <span className="plan-item-field-label">Focus</span>
            <span>{safeDisplayValue(item.target)}</span>
          </p>
        ) : null}

        {item.detail && item.detail !== dosage ? (
          <p className="plan-item-detail">{safeDisplayValue(item.detail)}</p>
        ) : null}

        {item.why ? <p className="plan-item-why">{safeDisplayValue(item.why)}</p> : null}

        {/* The one safety note an item gets, and only when this item was
            actually touched by the review. */}
        {safety ? (
          <p className={`plan-item-safety${safety.withheld ? " plan-item-safety--withheld" : ""}`}>
            🛡️ {safeDisplayValue(safety.text)}
          </p>
        ) : safetyNotes.length ? (
          <p className="plan-item-safety">⚠️ {safetyNotes[0]}</p>
        ) : null}

        <TrackingLine tracking={tracking} />
        <ProgressLine progress={progress} />

        {hasGuidance ? (
          <details className="plan-item-guidance-block">
            <summary>How to progress or make it easier</summary>
            {metadata.progression ? (
              <p className="plan-item-guidance">
                <strong>Harder:</strong> {safeDisplayValue(metadata.progression)}
              </p>
            ) : null}
            {metadata.regression ? (
              <p className="plan-item-guidance">
                <strong>Easier:</strong> {safeDisplayValue(metadata.regression)}
              </p>
            ) : null}
          </details>
        ) : null}

        {action ? (
          <div className="plan-item-actions">
            <button
              type="button"
              className={`mw-btn mw-btn--small${
                action.kind === "withheld" ? " mw-btn--ghost" : " mw-btn--primary"
              }`}
              disabled={busy}
              onClick={() => onAction?.(action, item)}
            >
              {safeDisplayValue(action.label)}
            </button>
          </div>
        ) : null}

        {/* A withheld item must not offer a second way to record it as done. */}
        {!withheld ? (
          <ManualCompletion
            exerciseId={exerciseId}
            planId={item.plan_id}
            itemId={item.item_id}
            completion={completion}
          />
        ) : null}
      </div>
    </li>
  );
}
