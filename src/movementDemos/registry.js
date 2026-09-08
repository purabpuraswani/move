/**
 * Where every Movement Demonstration's data lives, keyed by movementId.
 *
 * Empty through Phase 1 on purpose. Phase 2 populates it with thirteen
 * demonstrations, authored in content.js and registered by importing that
 * file once for its side effect (done in App.jsx, before any panel needs
 * to look one up — not imported from this file, to avoid a circular
 * import: content.js itself imports registerMovementDemo from here): the
 * three baseline assessments — assessment-shoulder-raise,
 * assessment-chair-sit-to-stand, assessment-one-leg-stand — wired into
 * ShoulderPanel.jsx / FtsstPanel.jsx / BalancePanel.jsx's idle state, before
 * camera activation; and one demonstration per Exercise Library entry
 * (backend/exercise_library/data.py's ten exercises, matched by
 * demonstration_id). As with the exercise content itself, this is authored
 * directly from each exercise's own written instructions, not invented
 * freehand, and — per the project's safety principle — is a candidate for
 * healthcare/physio review before being treated as final content.
 *
 * getMovementDemo() and listMovementDemos() are written so every panel or
 * exercise card reaches the same data source, rather than each one holding
 * its own copy.
 */

import { validateMovementDemo } from "./schema.js";

/** @type {Record<string, import("./schema.js").MovementDemo>} */
const REGISTRY = {};

/**
 * Register a demonstration. Validates it first, so a malformed entry fails
 * at registration time (during development) rather than at render time (in
 * front of a user).
 */
export function registerMovementDemo(demo) {
  validateMovementDemo(demo);

  if (REGISTRY[demo.movementId]) {
    throw new Error(
      `a movement demonstration with id "${demo.movementId}" is already registered`
    );
  }

  REGISTRY[demo.movementId] = demo;
}

export function getMovementDemo(movementId) {
  return REGISTRY[movementId] ?? null;
}

export function listMovementDemos(category) {
  const all = Object.values(REGISTRY);

  return category ? all.filter((demo) => demo.category === category) : all;
}
