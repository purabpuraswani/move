/**
 * The Movement Demonstration data shape.
 *
 * Phase 0 foundation only: this file defines the shape a demonstration's data
 * must have, and a small validator, so that both the three baseline assessment
 * tests (Hand/Shoulder Raise, Chair Sit-to-Stand, One-Leg Stand) and the future
 * 20-exercise library can be authored as data against the same interface,
 * rendered by the same component (MovementDemo.jsx), instead of three
 * hand-built animations plus twenty more later.
 *
 * No actual demonstration content is authored here yet. See registry.js.
 *
 * A demonstration is:
 *
 *   {
 *     movementId: "shoulder-raise",       // stable id, kebab-case
 *     title: "Shoulder Raise",
 *     category: "assessment" | "exercise",
 *     durationSeconds: 8,                  // total loop length, for pacing
 *     phases: [
 *       {
 *         id: "start",
 *         label: "Starting position",
 *         holdSeconds: 2,
 *         // A pose is described declaratively, not as a drawn illustration,
 *         // so the renderer stays the same across every movement and only
 *         // the numbers change. Angles are in degrees, 0 = arm at the side,
 *         // measured the same way protocol.js measures them, so a later
 *         // phase can drive a demonstration's pose directly from the same
 *         // constants the measurement logic already uses.
 *         pose: { armAngleDeg: { left: 0, right: 0 } },
 *       },
 *       // ...
 *     ],
 *     instructions: ["Stand facing the camera...", "..."],
 *     keyPoints: ["Move only as far as is comfortable.", "..."],
 *     commonMistakes: ["Leaning the trunk to help the arm up.", "..."],
 *     repetitions: 3,          // null for a hold-based movement (e.g. balance)
 *     reference: null,         // citation/source for the technique, filled in
 *                              // when a real exercise is authored and reviewed
 *   }
 *
 * This shape is deliberately abstract about *how* a phase is drawn. Different
 * movements will need different pose descriptions (an arm angle, a sit/stand
 * transition, a single-leg stance), and MovementDemo.jsx interprets whichever
 * fields a phase's pose provides. What is fixed is the envelope: id, label,
 * holdSeconds, pose, so a generic step sequencer can drive any of them.
 *
 * Phase 2 extends the set of pose fields MovementDemo.jsx knows how to draw,
 * without changing this envelope or this validator (a pose is still "any
 * object" as far as validateMovementDemo is concerned — see validatePhase
 * below). Every field is optional and additive; a phase's pose can combine
 * more than one when useful (e.g. a slight torso lean during a push-up).
 * The vocabulary used by the thirteen demonstrations this phase authors
 * (three baseline assessments, ten exercises):
 *
 *   - armAngleDeg: { left, right }        arms raised out to the side
 *                                         (0 = at rest, 90 = shoulder height)
 *   - stance: "standing" | "sitting"      whole-body base position
 *   - legLift: { side, liftAngleDeg }     one leg lifted forward/bent (knee
 *                                         raise, single-leg stance)
 *   - sideLegLift: { side, liftAngleDeg } one leg lifted out to the side
 *   - hipExtension: { side, liftAngleDeg } one leg lifted straight back
 *   - heelRaiseDeg                        heels lifted (calf raise)
 *   - armBendDeg: { left, right }         elbows bent (wall push-up)
 *   - leanDeg                             torso leaning forward (toward a
 *                                         wall, or into a squat/sit)
 *   - tandemStance: true                  feet placed heel-to-toe in a line
 *
 * As before, none of this is a claim that the drawn angle is clinically
 * exact — it is an illustration, authored to match each exercise's written
 * instructions (see exercise_library/data.py on the backend), not a
 * rendering of measured data.
 */

export const DEMO_CATEGORIES = Object.freeze({
  ASSESSMENT: "assessment",
  EXERCISE: "exercise",
});

/** Fields every phase must have, regardless of what its pose describes. */
const REQUIRED_PHASE_FIELDS = ["id", "label", "holdSeconds", "pose"];

/** Fields every demonstration must have. */
const REQUIRED_DEMO_FIELDS = [
  "movementId",
  "title",
  "category",
  "durationSeconds",
  "phases",
  "instructions",
  "keyPoints",
  "commonMistakes",
];

export class MovementDemoValidationError extends Error {}

function fail(message) {
  throw new MovementDemoValidationError(message);
}

/**
 * Throws MovementDemoValidationError if `demo` is not a well-formed
 * Movement Demonstration. Checks structure and the closed category
 * vocabulary; does not judge whether the pose values describe a safe or
 * accurate movement — that is a content-review question for whoever
 * authors the demo, human or otherwise (see the module docstring on
 * reviewability by a physio professional).
 */
export function validateMovementDemo(demo) {
  if (typeof demo !== "object" || demo === null || Array.isArray(demo)) {
    fail("a movement demonstration must be an object");
  }

  for (const field of REQUIRED_DEMO_FIELDS) {
    if (!(field in demo)) {
      fail(`movement demonstration is missing required field "${field}"`);
    }
  }

  if (typeof demo.movementId !== "string" || !/^[a-z0-9]+(-[a-z0-9]+)*$/.test(demo.movementId)) {
    fail("movementId must be a non-empty kebab-case string");
  }

  if (typeof demo.title !== "string" || !demo.title.trim()) {
    fail("title must be a non-empty string");
  }

  if (!Object.values(DEMO_CATEGORIES).includes(demo.category)) {
    fail(
      `category must be one of ${Object.values(DEMO_CATEGORIES).join(", ")}`
    );
  }

  if (typeof demo.durationSeconds !== "number" || demo.durationSeconds <= 0) {
    fail("durationSeconds must be a positive number");
  }

  if (!Array.isArray(demo.phases) || demo.phases.length === 0) {
    fail("phases must be a non-empty array");
  }

  demo.phases.forEach((phase, index) => validatePhase(phase, index));

  for (const field of ["instructions", "keyPoints", "commonMistakes"]) {
    if (!Array.isArray(demo[field])) {
      fail(`${field} must be an array of strings`);
    }

    if (demo[field].some((item) => typeof item !== "string" || !item.trim())) {
      fail(`${field} must contain only non-empty strings`);
    }
  }

  if (
    "repetitions" in demo &&
    demo.repetitions !== null &&
    (typeof demo.repetitions !== "number" || demo.repetitions <= 0)
  ) {
    fail("repetitions must be null or a positive number");
  }
}

function validatePhase(phase, index) {
  if (typeof phase !== "object" || phase === null) {
    fail(`phase ${index} must be an object`);
  }

  for (const field of REQUIRED_PHASE_FIELDS) {
    if (!(field in phase)) {
      fail(`phase ${index} is missing required field "${field}"`);
    }
  }

  if (typeof phase.id !== "string" || !phase.id.trim()) {
    fail(`phase ${index}.id must be a non-empty string`);
  }

  if (typeof phase.label !== "string" || !phase.label.trim()) {
    fail(`phase ${index}.label must be a non-empty string`);
  }

  if (typeof phase.holdSeconds !== "number" || phase.holdSeconds <= 0) {
    fail(`phase ${index}.holdSeconds must be a positive number`);
  }

  if (typeof phase.pose !== "object" || phase.pose === null) {
    fail(`phase ${index}.pose must be an object`);
  }
}
