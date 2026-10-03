/**
 * The exercises a specialist recommended, as reference cards.
 *
 * Reference and completion only: the image to recognise the movement by,
 * the prescription, and the existing "mark as completed" control. There
 * is deliberately no Start button, camera or pose view here — starting a
 * camera-guided session belongs to the Movement panel and the exercise
 * page, and duplicating it would mean two routes into one recording
 * system.
 *
 * The checkbox writes through the shared completion hook, so a tick here
 * and a tick on the Movement panel are the same record: one manual
 * confirmation, never a fabricated measurement.
 */

import { getExerciseImage } from "../movementDemos/exerciseImages.js";
import { safeDisplayValue, toArray } from "../services/specialistData.js";

function dosageOf(exercise) {
  const parts = [];

  if (exercise.sets) parts.push(`${exercise.sets} sets`);
  if (exercise.repetitions) parts.push(`${exercise.repetitions} reps`);
  if (exercise.duration_seconds) parts.push(`${exercise.duration_seconds}s hold`);

  return parts.join(" · ") || null;
}

function ExerciseReference({ exercise, completion }) {
  const image = getExerciseImage(exercise.id);
  const dosage = dosageOf(exercise);
  const isCompleted = completion?.completedIds?.has(exercise.id) ?? false;
  const result = completion?.resultFor?.(exercise.id) || null;
  const manualResultId = result?.source === "manual_confirmation" ? result.id : null;
  // A camera session is a measurement; it is not undone with a checkbox.
  const lockedByCamera = isCompleted && !manualResultId;
  const checkboxId = `plan-complete-${exercise.id}`;

  async function handleToggle(event) {
    if (event.target.checked) {
      await completion?.markCompleted?.(exercise.id);
    } else if (manualResultId) {
      await completion?.undoCompletion?.(manualResultId);
    }
  }

  return (
    <li className={`plan-exercise-ref${isCompleted ? " plan-exercise-ref--done" : ""}`}>
      {image ? (
        <img className="plan-exercise-ref-image" src={image.src} alt={image.alt} />
      ) : null}

      <div className="plan-exercise-ref-body">
        <h4 className="plan-exercise-ref-name">{safeDisplayValue(exercise.name)}</h4>

        {exercise.target ? (
          <p className="plan-exercise-ref-meta">
            <span className="plan-exercise-ref-label">Focus:</span>{" "}
            {safeDisplayValue(exercise.target)}
          </p>
        ) : null}

        {dosage ? <p className="plan-exercise-ref-meta">{dosage}</p> : null}

        {exercise.difficulty ? (
          <p className="plan-exercise-ref-meta">
            {safeDisplayValue(exercise.difficulty)}
          </p>
        ) : null}

        {toArray(exercise.safety).length ? (
          <p className="plan-exercise-ref-safety">
            ⚠️ {toArray(exercise.safety).map(safeDisplayValue).join(" ")}
          </p>
        ) : null}

        <div className="plan-exercise-ref-check">
          <input
            type="checkbox"
            id={checkboxId}
            checked={isCompleted}
            disabled={lockedByCamera}
            onChange={handleToggle}
          />
          <label htmlFor={checkboxId}>
            {lockedByCamera
              ? "Completed (recorded session)"
              : isCompleted
                ? "Completed"
                : "Mark as completed"}
          </label>
        </div>
      </div>
    </li>
  );
}

export default function SpecialistExerciseList({ exercises, completion }) {
  const list = toArray(exercises).filter((entry) => entry && entry.id);

  if (!list.length) return null;

  return (
    <ul className="plan-exercise-ref-list">
      {list.map((exercise) => (
        <ExerciseReference
          key={exercise.id}
          exercise={exercise}
          completion={completion}
        />
      ))}
    </ul>
  );
}
