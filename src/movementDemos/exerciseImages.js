/**
 * Photographic-style demonstration diagrams, keyed by exercise id.
 *
 * These are the instructional images in `public/physio-exercises/`, one per
 * exercise, each showing the start position and the end position of the
 * movement. They are served as static files rather than bundled, and the
 * file name IS the exercise id (backend/exercise_library/data.py's
 * `exercise_id`) — so the mapping below cannot drift from a display name
 * someone edits later, and a missing file is a missing id, not a typo in a
 * label.
 *
 * Where an exercise has no diagram, `getExerciseImage` returns null and the
 * caller falls back to the existing animated stick-figure demonstration
 * (src/movementDemos/). Nothing here replaces that renderer; it only takes
 * precedence where a real diagram exists.
 */

const BASE_PATH = "/physio-exercises";

/**
 * Exercise id -> the file in public/physio-exercises, and what the image
 * shows. The alt text describes the two panels, because a screen-reader
 * user gets nothing from "demonstration image".
 */
export const EXERCISE_IMAGES = Object.freeze({
  "standing-knee-raise": {
    file: "standing-knee-raise.png",
    alt:
      "Two-panel diagram. Left: standing upright with both feet on the floor. " +
      "Right: standing on one leg with the opposite knee raised in front to " +
      "about hip height.",
  },
  "standing-side-leg-raise": {
    file: "standing-side-leg-raise.png",
    alt:
      "Two-panel diagram. Left: standing upright, feet together. Right: " +
      "standing on one leg with the other leg lifted straight out to the side.",
  },
  "standing-hip-extension": {
    file: "standing-hip-extension.png",
    alt:
      "Two-panel diagram. Left: standing upright, seen from the front. Right: " +
      "seen from the side, standing on one leg with the other leg extended " +
      "straight behind the body.",
  },
  "seated-marching": {
    file: "seated-marching.png",
    alt:
      "Two-panel diagram. Left: sitting upright on a chair with both feet flat " +
      "on the floor. Right: sitting upright with one knee lifted up off the " +
      "chair, as if marching.",
  },
  "wall-sit": {
    file: "wall-sit.png",
    alt:
      "Two-panel diagram, seen from the side. Left: standing upright with the " +
      "back against a wall. Right: sliding down the wall until the knees are " +
      "bent to about a right angle, holding the position.",
  },
  "glute-bridge": {
    file: "glute-bridge.png",
    alt:
      "Two-panel diagram, seen from the side. Left: lying on the back on a mat " +
      "with knees bent and feet flat. Right: the same position with the hips " +
      "lifted so the body forms a straight line from shoulders to knees.",
  },
});

/**
 * The diagram for one exercise id, or null when there is none.
 *
 * Returns `{ src, alt }` ready to put on an <img>. A null return is the
 * signal to fall back to the stick-figure demonstration, not an error.
 */
export function getExerciseImage(exerciseId) {
  if (typeof exerciseId !== "string" || !exerciseId) return null;

  const entry = EXERCISE_IMAGES[exerciseId];

  if (!entry) return null;

  return { src: `${BASE_PATH}/${entry.file}`, alt: entry.alt };
}

/** Every exercise id that has a diagram. */
export function exerciseImageIds() {
  return Object.keys(EXERCISE_IMAGES);
}
