/**
 * The small shared building blocks every screen is assembled from.
 *
 * They live together because each is a dozen lines of markup over the classes in
 * src/index.css, and splitting them across ten files would add import noise
 * without adding clarity. What matters is that there is exactly ONE of each: one
 * page header, one empty state, one badge, one disclosure. A screen that invents
 * its own version of these is how a product stops looking like one product.
 *
 * Nothing here holds domain knowledge. They render what they are given.
 */

import { safeDisplayValue } from "../../services/specialistData.js";

import "./primitives.css";

/** A page's title block: eyebrow, heading, optional lead, optional actions. */
export function PageHeader({ eyebrow, title, lead, actions = null, children = null }) {
  return (
    <header className="mw-page-header mw-enter">
      {eyebrow ? <span className="mw-eyebrow">{safeDisplayValue(eyebrow)}</span> : null}
      <h1 className="mw-h1 mw-page-title">{safeDisplayValue(title)}</h1>
      {lead ? <p className="mw-lede mw-page-lead">{safeDisplayValue(lead)}</p> : null}
      {children}
      {actions ? <div className="mw-row mw-page-actions">{actions}</div> : null}
    </header>
  );
}

/** A section heading, with an optional link on the right. */
export function SectionHeader({ title, hint = null, action = null }) {
  return (
    <div className="mw-section-head">
      <div>
        <h2 className="mw-h3">{safeDisplayValue(title)}</h2>
        {hint ? <p className="mw-meta">{safeDisplayValue(hint)}</p> : null}
      </div>
      {action}
    </div>
  );
}

/** The one primary action style, so a screen's main button always looks it. */
export function PrimaryButton({
  children,
  onClick = null,
  type = "button",
  variant = "primary",
  size = null,
  disabled = false,
  block = false,
  ...rest
}) {
  const classes = [
    "mw-btn",
    variant === "primary" ? "mw-btn--primary" : null,
    variant === "ghost" ? "mw-btn--ghost" : null,
    variant === "quiet" ? null : null,
    size === "small" ? "mw-btn--small" : null,
    block ? "mw-btn--block" : null,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button type={type} className={classes} onClick={onClick} disabled={disabled} {...rest}>
      {children}
    </button>
  );
}

/**
 * A status word with a colour that means something.
 *
 * `tone` is chosen by the caller from a value the server sent; the badge never
 * decides what a status means.
 */
export function StatusBadge({ label, tone = "neutral", title = null }) {
  const classes = [
    "mw-badge",
    tone === "active" ? "mw-badge--active" : null,
    tone === "warn" ? "mw-badge--warn" : null,
    tone === "danger" ? "mw-badge--danger" : null,
    tone === "muted" ? "mw-badge--muted" : null,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <span className={classes} title={title || undefined}>
      {safeDisplayValue(label)}
    </span>
  );
}

/**
 * What to tell someone when there is nothing here yet.
 *
 * All three parts are required by the product's own rule: what is missing, why
 * it matters, and what to do. An empty state with only the first is the thing
 * this component exists to prevent.
 */
export function EmptyState({ title, why = null, action = null, icon = null, tone = "quiet" }) {
  return (
    <div className={`mw-empty${tone === "warn" ? " mw-empty--warn" : ""}`}>
      {icon ? (
        <span className="mw-empty-icon" aria-hidden="true">
          {icon}
        </span>
      ) : null}
      <h3 className="mw-h3">{safeDisplayValue(title)}</h3>
      {why ? <p className="mw-lede mw-empty-why">{safeDisplayValue(why)}</p> : null}
      {action ? <div className="mw-row">{action}</div> : null}
    </div>
  );
}

/**
 * Secondary detail, folded away.
 *
 * Uses `<details>`, so it is keyboard-operable and screen-reader-announced
 * without any JavaScript of ours.
 */
export function DetailDrawer({ label = "View details", children }) {
  return (
    <details className="mw-details">
      <summary>{safeDisplayValue(label)}</summary>
      <div className="mw-details-body">{children}</div>
    </details>
  );
}

/** A labelled value, for the small facts a card shows. */
export function Field({ label, value, tone = null }) {
  const text = safeDisplayValue(value);

  if (!text) return null;

  return (
    <p className={`mw-field-row${tone ? ` mw-field-row--${tone}` : ""}`}>
      <span className="mw-field-key">{safeDisplayValue(label)}</span>
      <span className="mw-field-value">{text}</span>
    </p>
  );
}
