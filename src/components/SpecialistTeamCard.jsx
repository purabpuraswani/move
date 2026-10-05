/**
 * One of the five specialists, as a compact team card.
 *
 * The card answers two questions and stops: *who is on my team* and *is this
 * one doing anything right now*. So it shows the coach — the person, from
 * services/specialistIdentity.js — their role, the server's compact status,
 * and one line of why. No exercise list, no paragraph of reasoning, no
 * evidence: the specialist's own page answers "what do they want me to do".
 *
 * Selection and accent are presentation only. Which coach is which, and what
 * they mean by "not needed right now", both come from the server's card
 * (`team_status`, `team_status_label`, `short_reason`) — this component never
 * decides participation and never writes a sentence of its own.
 *
 * Emphasis is the third thing the card does: a specialist working on this
 * plan is lifted, a specialist that was reviewed and needed nothing is
 * quieter, and one that has not been assessed is quieter still and visibly
 * provisional — but neither ever reads as broken.
 */

import { StatusBadge, PrimaryButton } from "./ui/primitives.jsx";
import { identityFor, statusWording } from "../services/specialistIdentity.js";
import { safeDisplayValue } from "../services/specialistData.js";

import "./SpecialistTeamCard.css";

/** The card's emphasis, from the server's compact status. */
function modifierFor(teamStatus) {
  if (teamStatus === "ACTIVE") return "active";
  if (teamStatus === "NOT_ASSESSED") return "not-assessed";
  if (teamStatus === "NOT_NEEDED") return "not-needed";

  return "reviewed";
}

export default function SpecialistTeamCard({ specialist, onOpen = null }) {
  if (!specialist || !specialist.id) return null;

  const identity = identityFor(specialist.id, specialist.title);
  const wording = statusWording(specialist.team_status, specialist.team_status_label);
  const reason = safeDisplayValue(specialist.short_reason);
  const selected = Boolean(specialist.selected);

  const classes = [
    "mw-card",
    "team-card",
    `team-card--${modifierFor(specialist.team_status)}`,
    identity.accent ? `team-card--accent-${identity.accent}` : "team-card--accent-none",
  ].join(" ");

  return (
    <article className={classes} data-specialist={specialist.id}>
      <div className="team-card-head">
        {identity.icon ? (
          <span className="team-card-icon" aria-hidden="true">
            {identity.icon}
          </span>
        ) : null}

        <div className="team-card-names">
          <h3 className="team-card-title">{identity.coach}</h3>
          {/* The canonical name is the precise one the plan, the API and the
              coach's own page use. It stays in the card for whoever needs to
              match them up — and is not repeated visually, because the coach's
              name is what a person is looking for. */}
          <p className="mw-sr">{identity.canonical}</p>
          {identity.role ? <p className="team-card-subtitle">{identity.role}</p> : null}
        </div>
      </div>

      <div className="team-card-foot">
        <StatusBadge label={wording.label} tone={wording.tone} />
        {selected ? <span className="team-card-flag">In your plan</span> : null}
      </div>

      {reason ? <p className="team-card-reason">{reason}</p> : null}

      <div className="team-card-actions">
        <PrimaryButton variant="ghost" size="small" onClick={() => onOpen?.(specialist)}>
          View
          <span className="mw-sr"> {identity.coach}</span>
          <span aria-hidden="true">→</span>
        </PrimaryButton>
      </div>
    </article>
  );
}
