/**
 * Small presentational pieces shared by the three check panels.
 *
 * All wording here describes what the camera observed. None of it interprets
 * what an observation might mean about the person.
 */

import { describeGuidance, describeReason, describeStatus } from "../utils/labels.js";

/** Live coaching line, e.g. "Turn to face the camera". */
export function GuidanceBanner({ code }) {
  const text = describeGuidance(code);

  if (!text) return null;

  return (
    <p className="assess-guidance" role="status">
      {text}
    </p>
  );
}

/** Why an attempt could not be used, or why part of it was discarded. */
export function ReasonList({ codes, title = "Why this attempt was not usable" }) {
  if (!codes || !codes.length) return null;

  return (
    <div className="assess-reasons">
      <h4>{title}</h4>
      <ul>
        {codes.map((code) => (
          <li key={code}>{describeReason(code)}</li>
        ))}
      </ul>
    </div>
  );
}

/** Recorded / Not usable / Skipped / Not attempted. */
export function StatusPill({ status }) {
  return (
    <span className={`assess-pill assess-pill--${status}`}>{describeStatus(status)}</span>
  );
}

/** One labelled measurement, with an explicit dash when there is no value. */
export function Measurement({ label, value, note }) {
  return (
    <div className="assess-measure">
      <span className="assess-measure__label">{label}</span>
      <span className="assess-measure__value">{value}</span>
      {note && <span className="assess-measure__note">{note}</span>}
    </div>
  );
}

/** A short live counter, e.g. repetitions detected so far. */
export function LiveCounter({ label, value, total }) {
  return (
    <div className="assess-counter">
      <span className="assess-counter__value">
        {value}
        {typeof total === "number" && <span className="assess-counter__total">/{total}</span>}
      </span>
      <span className="assess-counter__label">{label}</span>
    </div>
  );
}

/**
 * Clean, non-technical progress bar.
 * Stages: Preparing... -> Tracking... -> Almost done... -> Complete ✓
 */
export function ProgressIndicator({ stage = "tracking", progress = 0 }) {
  const stageLabels = {
    preparing: "Preparing...",
    tracking: "Tracking...",
    almost_done: "Almost done...",
    complete: "Complete ✓",
  };

  const label = stageLabels[stage] || "Tracking...";
  const pct = Math.max(0, Math.min(100, Math.round(progress * 100)));

  return (
    <div className="assess-progress" role="progressbar" aria-valuenow={pct} aria-valuemin="0" aria-valuemax="100">
      <div className="assess-progress__header">
        <span className="assess-progress__label">{label}</span>
        {stage === "complete" ? (
          <span className="assess-progress__check">✓</span>
        ) : null}
      </div>
      <div className="assess-progress__bar">
        <div className="assess-progress__fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

/**
 * Empathetic failure and retry notice.
 * Never shows raw technical codes like "Too many frames lost".
 */
export function ActionableRetryNotice({ suggestion }) {
  return (
    <div className="assess-reasons assess-reasons--friendly">
      <h4>We're having trouble seeing your movement</h4>
      <p className="assess-reasons__suggestion">
        💡 <strong>Suggestion:</strong> {suggestion || "Keep your body inside the outline and try again."}
      </p>
    </div>
  );
}

/**
 * Standard continuous tracking quality indicator.
 * Values: ready | tracking | repositioning | recovering | cannot_see
 */
export function TrackingStatusBadge({ status = "tracking" }) {
  const configs = {
    ready: { label: "Ready", className: "assess-camera__badge--ready" },
    tracking: { label: "Tracking", className: "assess-camera__badge--ok" },
    repositioning: { label: "Repositioning needed", className: "assess-camera__badge--warn" },
    recovering: { label: "Recovering tracking", className: "assess-camera__badge--recovering" },
    cannot_see: { label: "Cannot see enough of your body", className: "assess-camera__badge--error" },
  };

  const config = configs[status] || configs.tracking;

  return (
    <div className={`assess-camera__badge ${config.className}`}>
      <span className="assess-camera__badge-dot" />
      <span>{config.label}</span>
    </div>
  );
}

