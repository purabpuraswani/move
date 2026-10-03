/**
 * Instructor demonstration videos, keyed by exercise id and by baseline
 * assessment test id.
 *
 * The files live in `public/assessment-videos/` and are served statically.
 * There are three of them, and they show the three baseline movements, so
 * they cover:
 *
 *   - the three assessment checks, by both their test id (shoulder,
 *     ftsst, balance) and their demonstration id
 *     (assessment-shoulder-raise, …), since the assessment flow has
 *     the latter to hand; and
 *   - the three library exercises that are the same movement
 *     (standing-shoulder-raise, chair-sit-to-stand,
 *     supported-single-leg-stand).
 *
 * Every other exercise has NO instructor video, and `getExerciseVideo`
 * returns null for it. That is deliberate: the caller then falls back to
 * the animated stick-figure demonstration and the still diagram, which is
 * honest, rather than showing a video of a different movement. Do not map
 * an exercise to a video of something else to fill the panel.
 */

const BASE_PATH = "/assessment-videos";

/**
 * One video per movement. `movements` lists every id — exercise ids from
 * backend/exercise_library/data.py, and assessment test ids from
 * src/assessment/config/protocol.js — that this same recording
 * demonstrates.
 */
export const INSTRUCTOR_VIDEOS = Object.freeze([
  {
    file: "shoulder-raise.mp4",
    caption: "Raise both arms out to the side, as far as is comfortable, then lower them under control.",
    movements: ["shoulder", "assessment-shoulder-raise", "standing-shoulder-raise"],
  },
  {
    file: "sit-to-stand.mp4",
    caption: "Stand up fully from the chair and sit back down under control, without pushing off if you can.",
    movements: ["ftsst", "assessment-chair-sit-to-stand", "chair-sit-to-stand"],
  },
  {
    file: "one-leg-stand.mp4",
    caption: "Stand on one leg beside a support, lifting the other foot clear of the floor.",
    movements: ["balance", "assessment-one-leg-stand", "supported-single-leg-stand"],
  },
]);

const BY_MOVEMENT = Object.freeze(
  INSTRUCTOR_VIDEOS.reduce((index, entry) => {
    entry.movements.forEach((id) => {
      index[id] = { src: `${BASE_PATH}/${entry.file}`, caption: entry.caption };
    });

    return index;
  }, {}),
);

/**
 * The instructor video for an exercise id or assessment test id, or null
 * when there is none. A null return means "fall back to the existing
 * demonstration", not "error".
 */
export function getExerciseVideo(movementId) {
  if (typeof movementId !== "string" || !movementId) return null;

  return BY_MOVEMENT[movementId] || null;
}

/** Every id that has an instructor video. */
export function videoMovementIds() {
  return Object.keys(BY_MOVEMENT);
}
