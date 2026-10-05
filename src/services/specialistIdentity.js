/**
 * Who each specialist is to the person using MoveWell.
 *
 * The five canonical specialists are, and remain, Exercise & Movement,
 * Nutrition & Lifestyle, Behaviour & Adherence, Recovery & Care and Safety &
 * Practitioner Recommendation — that is what the backend calls them and what the
 * architecture means by them. But a person is not being helped by a "domain",
 * they are being helped by a coach, so the interface introduces them that way and
 * keeps the canonical name for the places where precision matters (the team
 * list, the specialist's own page heading, the API).
 *
 * This is presentation only, keyed on the specialist id the server sent. There
 * is deliberately no sixth entry and no fallback that invents one: an unknown id
 * renders as itself.
 */

export const SPECIALIST_IDENTITY = Object.freeze({
  exercise_movement: {
    id: "exercise_movement",
    coach: "Your Movement Coach",
    canonical: "Exercise & Movement",
    role: "Personalised movement guidance",
    focusLabel: "Movement focus",
    icon: "🏃",
    accent: "movement",
  },
  nutrition_lifestyle: {
    id: "nutrition_lifestyle",
    coach: "Your Nutrition Coach",
    canonical: "Nutrition & Lifestyle",
    role: "Everyday nutrition and hydration",
    focusLabel: "Nutrition focus",
    icon: "🥗",
    accent: "nutrition",
  },
  behaviour_adherence: {
    id: "behaviour_adherence",
    coach: "Your Habit Coach",
    canonical: "Behaviour & Adherence",
    role: "Habits that hold up in a normal week",
    focusLabel: "Habit focus",
    icon: "🧠",
    accent: "behaviour",
  },
  recovery_care: {
    id: "recovery_care",
    coach: "Your Recovery Coach",
    canonical: "Recovery & Care",
    role: "Rest, sleep and pacing",
    focusLabel: "Recovery focus",
    icon: "🌙",
    accent: "recovery",
  },
  safety_practitioner: {
    id: "safety_practitioner",
    coach: "Safety Review",
    canonical: "Safety & Practitioner Recommendation",
    role: "Checks your plan before you see it",
    focusLabel: "Review",
    icon: "🛡️",
    accent: "safety",
  },
});

/** The five ids, in the order the product presents them. */
export const SPECIALIST_PRESENTATION_ORDER = [
  "exercise_movement",
  "nutrition_lifestyle",
  "behaviour_adherence",
  "recovery_care",
  "safety_practitioner",
];

/**
 * The identity for one specialist id, with the server's own title as the
 * fallback so an id this build does not know still renders as something.
 */
export function identityFor(specialistId, fallbackTitle = null) {
  const known = SPECIALIST_IDENTITY[specialistId];

  if (known) return known;

  return {
    id: specialistId || null,
    coach: fallbackTitle || "MoveWell specialist",
    canonical: fallbackTitle || "MoveWell specialist",
    role: null,
    focusLabel: "Focus",
    icon: null,
    accent: null,
  };
}

/**
 * The word for a team card's status, from the compact status the server sent.
 * The mapping is one-way and total: an unrecognised status reads as "Not
 * assessed" rather than as something reassuring.
 */
export function statusWording(teamStatus, fallbackLabel = null) {
  switch (teamStatus) {
    case "ACTIVE":
      return { label: "Active", tone: "active" };
    case "REVIEWED":
      return { label: "Reviewed", tone: "active" };
    case "MODIFIED":
      return { label: "Reviewed — precautions", tone: "warn" };
    case "PAUSED":
      return { label: "Paused", tone: "warn" };
    case "REFERRAL":
      return { label: "Referral recommended", tone: "danger" };
    case "NOT_NEEDED":
      return { label: "Not needed right now", tone: "muted" };
    case "NOT_ASSESSED":
      return { label: "Not assessed", tone: "muted" };
    default:
      return { label: fallbackLabel || "Not assessed", tone: "muted" };
  }
}
