/**
 * Reading the MoveWell Score, and the few things a screen may say about it.
 *
 * The score is computed server-side (backend/workflow/score.py) from the user's
 * own results and arrives inside the workflow response. Nothing here computes a
 * value, band or trend: a client that could invent a score would eventually
 * invent one, and this is the one number in the product a person is asked to
 * care about.
 */

/** The score block from a workflow response, or null. */
export function movewellScore(workflow) {
  const score = workflow?.movewell_score;

  return score && typeof score === "object" ? score : null;
}

/** Whether there is a real number to show. */
export function hasScore(workflow) {
  const score = movewellScore(workflow);

  return Boolean(score?.available) && typeof score.value === "number";
}

/**
 * The score's own sentence about itself ("You're doing well overall."), or null.
 * Never paraphrased here.
 */
export function scoreMessage(workflow) {
  const score = movewellScore(workflow);

  return typeof score?.message === "string" && score.message ? score.message : null;
}

/** The current focus, as the server named it, or null. */
export function scoreFocus(workflow) {
  const focus = movewellScore(workflow)?.focus;

  return focus && focus.label ? focus : null;
}

/** The server's own one-sentence explanation of the focus, or null. */
export function focusStatement(workflow) {
  const statement = movewellScore(workflow)?.focus_statement;

  return typeof statement === "string" && statement ? statement : null;
}

/**
 * The change since the previous assessment, or null when there is nothing to
 * compare. A zero is a real answer ("measured, and it has not moved") and is
 * kept distinct from null ("no previous measurement").
 */
export function scoreChange(workflow) {
  const score = movewellScore(workflow);

  if (!score?.previous || typeof score.change !== "number") return null;

  return { value: score.change, from: score.previous.value, at: score.previous.recorded_at };
}

/**
 * The domains that moved, from the server's per-domain history. Only domains
 * with a real previous value are returned, and the direction is the server's own
 * arithmetic rather than a classification.
 */
export function domainChanges(workflow) {
  const domains = movewellScore(workflow)?.domains;

  if (!Array.isArray(domains)) return [];

  return domains
    .filter((domain) => typeof domain?.change === "number" && domain.change !== 0)
    .map((domain) => ({
      key: domain.key,
      label: domain.label,
      change: domain.change,
      value: domain.value,
      previous: domain.previous_value,
      source: domain.source,
    }))
    .sort((a, b) => Math.abs(b.change) - Math.abs(a.change));
}

/** The domains with a real value, in the server's order. */
export function scoredDomains(workflow) {
  const domains = movewellScore(workflow)?.domains;

  if (!Array.isArray(domains)) return [];

  return domains.filter((domain) => domain?.assessed && typeof domain.value === "number");
}

/** The domains the user has not been assessed for, with the server's reason. */
export function unscoredDomains(workflow) {
  const domains = movewellScore(workflow)?.domains;

  if (!Array.isArray(domains)) return [];

  return domains.filter((domain) => domain && !domain.assessed);
}

/** The method disclosure, shown wherever the number is shown prominently. */
export function scoreMethod(workflow) {
  const method = movewellScore(workflow)?.method;

  return typeof method === "string" && method ? method : null;
}

/** Words for a change, from its sign. Never a judgement of the person. */
export function changeWording(change) {
  if (typeof change !== "number") return null;
  if (change > 0) return "up";
  if (change < 0) return "down";
  return "unchanged";
}
