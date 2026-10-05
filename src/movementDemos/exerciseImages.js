/**
 * Demonstration imagery, keyed by exercise id.
 *
 * Two kinds of asset, and the difference matters:
 *
 *   `public/physio-exercises/<id>.png`
 *       Instructional diagrams drawn for this project, each showing the start
 *       position and the end position of one movement. The file name IS the
 *       exercise id (backend/exercise_library/data.py's `exercise_id`), so the
 *       mapping cannot drift from a display name someone edits later.
 *
 *   `public/physio-exercises/external/<id>_<frame>.jpg`
 *       Photographs of real people performing the movement, taken from
 *       free-exercise-db (https://github.com/yuhonas/free-exercise-db), which
 *       is released into the public domain under the Unlicense. Only
 *       movements whose depiction genuinely matches this library's own
 *       instructions are mapped, and each was inspected before being kept: a
 *       heel raise photographed with dumbbells, or a hamstring stretch
 *       photographed with a strap and a bent rear leg, is a different setup
 *       from the exercise this library describes and was therefore left out
 *       rather than used as a near-enough picture.
 *
 * Where an exercise has no entry, `getExerciseImage` returns null and the
 * caller falls back to the existing animated stick-figure demonstration
 * (src/movementDemos/). Nothing here replaces that renderer; it only takes
 * precedence where a genuine asset exists.
 */

const BASE_PATH = "/physio-exercises";

/**
 * Exercise id -> the file in public/physio-exercises, and what the image
 * shows. The alt text describes what is actually visible, because a
 * screen-reader user gets nothing from "demonstration image" — and because alt
 * text that describes a different position from the photograph is its own kind
 * of wrong.
 */
export const EXERCISE_IMAGES = Object.freeze({
  "standing-knee-raise": {
    file: "standing-knee-raise.png",
    kind: "diagram",
    alt:
      "Two-panel diagram. Left: standing upright with both feet on the floor. " +
      "Right: standing on one leg with the opposite knee raised in front to " +
      "about hip height.",
  },
  "standing-side-leg-raise": {
    file: "standing-side-leg-raise.png",
    kind: "diagram",
    alt:
      "Two-panel diagram. Left: standing upright, feet together. Right: " +
      "standing on one leg with the other leg lifted straight out to the side.",
  },
  "standing-hip-extension": {
    file: "standing-hip-extension.png",
    kind: "diagram",
    alt:
      "Two-panel diagram. Left: standing upright, seen from the front. Right: " +
      "seen from the side, standing on one leg with the other leg extended " +
      "straight behind the body.",
  },
  "seated-marching": {
    file: "seated-marching.png",
    kind: "diagram",
    alt:
      "Two-panel diagram. Left: sitting upright on a chair with both feet flat " +
      "on the floor. Right: sitting upright with one knee lifted up off the " +
      "chair, as if marching.",
  },
  "wall-sit": {
    file: "wall-sit.png",
    kind: "diagram",
    alt:
      "Two-panel diagram, seen from the side. Left: standing upright with the " +
      "back against a wall. Right: sliding down the wall until the knees are " +
      "bent to about a right angle, holding the position.",
  },
  "glute-bridge": {
    file: "glute-bridge.png",
    kind: "diagram",
    alt:
      "Two-panel diagram, seen from the side. Left: lying on the back on a mat " +
      "with knees bent and feet flat. Right: the same position with the hips " +
      "lifted so the body forms a straight line from shoulders to knees.",
  },

  // Photographic demonstrations, one frame each — the frame that shows the
  // position the exercise asks for.
  "standing-shoulder-raise": {
    file: "external/standing-shoulder-raise_0.jpg",
    kind: "photo",
    alt:
      "Photograph: a person standing upright facing the camera with both arms " +
      "raised straight out to the sides at shoulder height, elbows extended.",
  },
  "standing-overhead-reach": {
    file: "external/standing-overhead-reach_1.jpg",
    kind: "photo",
    alt:
      "Photograph: a person standing upright with both arms raised straight " +
      "overhead and the hands together, lower back not arched and no equipment " +
      "in use.",
  },
  "standing-trunk-rotation": {
    file: "external/standing-trunk-rotation_0.jpg",
    kind: "photo",
    alt:
      "Photograph: a person standing with the hips and feet facing forward " +
      "while the upper body is rotated to one side, holding a large exercise " +
      "ball in front of the chest. MoveWell's own instructions ask for the " +
      "arms relaxed or crossed instead of holding a ball; the rotation shown is " +
      "the movement.",
  },
  "standing-ankle-circles": {
    file: "external/standing-ankle-circles_0.jpg",
    kind: "photo",
    alt:
      "Photograph, lower body only: one foot planted flat on the floor and the " +
      "other lifted clear of it with the foot angled down, the position from " +
      "which the ankle is circled.",
  },
  "seated-knee-extension": {
    file: "external/seated-knee-extension_1.jpg",
    kind: "photo",
    alt:
      "Photograph: a person sitting upright on a stable chair with one knee " +
      "straightened so the foot is lifted out in front, the other foot still " +
      "flat on the floor and the hands resting on the chair.",
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
