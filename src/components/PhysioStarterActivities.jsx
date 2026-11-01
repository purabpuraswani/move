import { useEffect, useMemo, useState } from "react";
import { getExerciseImage } from "../movementDemos/exerciseImages.js";
import { fetchExerciseLibrary } from "../services/dailyCheckins.js";
import useExerciseCompletion from "../hooks/useExerciseCompletion.js";

function dosageOf(exercise) {
  return [
    exercise.sets && `${exercise.sets} sets`,
    exercise.repetitions && `${exercise.repetitions} reps`,
    exercise.duration_seconds && `${exercise.duration_seconds} seconds`,
  ].filter(Boolean).join(" · ") || "No dosage specified in the catalog.";
}

export default function PhysioStarterActivities({ missingHealthInformation = [] }) {
  const [catalogue, setCatalogue] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState("");
  const [saveError, setSaveError] = useState("");
  const completion = useExerciseCompletion();

  useEffect(() => {
    let active = true;
    fetchExerciseLibrary()
      .then(data => { if (active) setCatalogue(data.exercises || []); })
      .catch(err => { if (active) setError(err.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const exercises = useMemo(() => catalogue.filter(exercise =>
    exercise.difficulty === "beginner" &&
    (exercise.target_capability || []).includes("stability") &&
    getExerciseImage(exercise.exercise_id),
  ).slice(0, 4), [catalogue]);
  const completedCount = exercises.filter(ex => completion.completedIds.has(ex.exercise_id)).length;

  async function toggle(exerciseId, checked) {
    setSaving(exerciseId); setSaveError("");
    try {
      if (checked) await completion.markCompleted(exerciseId);
      else {
        const result = completion.resultFor(exerciseId);
        if (result?.source === "manual_confirmation") await completion.undoCompletion(result.id);
      }
    } catch (err) { setSaveError(err.message || "Completion could not be saved."); }
    finally { setSaving(""); }
  }

  return <section className="physio-starter-section" aria-labelledby="physio-starter-title">
    <div className="physio-starter-header">
      <div><span className="plan-team-eyebrow">General exercise library</span><h2 id="physio-starter-title">Beginner activities · reference only</h2></div>
      {!loading && exercises.length > 0 ? <span className="physio-starter-progress">{completedCount} of {exercises.length} marked complete today</span> : null}
    </div>
    <p className="physio-starter-notice">These catalog activities are general demonstrations, not personalized or Safety-Gate-approved exercise recommendations. Review each catalog caution and use your judgment. Personalized exercise selection is waiting for the health-screen answers below.</p>
    {missingHealthInformation.length > 0 ? <div className="physio-health-pending"><strong>Health screen incomplete — these answers are unknown:</strong><ul>{missingHealthInformation.map(item => <li key={item}>{item}</li>)}</ul><a href="/profile">Complete the health screen →</a></div> : null}
    {saveError ? <p role="alert" className="physio-starter-error">{saveError}</p> : null}
    {error ? <p role="alert" className="physio-starter-error">Exercise library could not be loaded: {error}</p> : null}
    {loading ? <p>Loading catalog activities…</p> : exercises.length === 0 ? <p>No beginner stability activities with a catalog illustration are currently available.</p> : (
      <div className="physio-starter-grid">{exercises.map(exercise => {
        const image = getExerciseImage(exercise.exercise_id);
        const completed = completion.completedIds.has(exercise.exercise_id);
        const lockedByCamera = completed && completion.resultFor(exercise.exercise_id)?.source !== "manual_confirmation";
        const checkboxId = `starter-complete-${exercise.exercise_id}`;
        return <article className="physio-starter-card" key={exercise.exercise_id}>
          <img className="physio-starter-image" src={image.src} alt={image.alt}/>
          <div className="physio-starter-card-body">
            <span className="physio-starter-reference-tag">General reference · Beginner</span>
            <h3>{exercise.name}</h3>
            <p><strong>Purpose from catalog:</strong> {[...(exercise.target_capability || []), ...(exercise.target_body_area || [])].join(", ")}</p>
            <p><strong>Equipment:</strong> {(exercise.equipment || []).join(", ") || "None listed"}</p>
            <p><strong>Catalog dosage:</strong> {dosageOf(exercise)}</p>
            <details><summary>Instructions</summary><ol>{(exercise.instructions || []).map((line, index) => <li key={index}>{line}</li>)}</ol></details>
            <div className="physio-starter-caution"><strong>Catalog caution</strong><ul>{(exercise.safety_constraints || []).map((line, index) => <li key={index}>{line}</li>)}</ul></div>
            <div className="physio-starter-check"><input id={checkboxId} type="checkbox" checked={completed} disabled={Boolean(saving) || lockedByCamera} onChange={event => toggle(exercise.exercise_id, event.target.checked)}/><label htmlFor={checkboxId}>{saving === exercise.exercise_id ? "Saving…" : lockedByCamera ? "Completed (recorded session)" : completed ? "Completed today" : "Mark as completed"}</label></div>
          </div>
        </article>;
      })}</div>
    )}
  </section>;
}
