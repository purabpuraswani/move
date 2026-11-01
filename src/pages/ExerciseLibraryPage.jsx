import { useEffect, useMemo, useState } from "react";
import AppNavigation from "../components/AppNavigation.jsx";
import { fetchExerciseLibrary } from "../services/dailyCheckins.js";
import { getExerciseImage } from "../movementDemos/exerciseImages.js";
import "./TrackingPages.css";

export default function ExerciseLibraryPage() {
  const [items, setItems] = useState([]);
  const [category, setCategory] = useState("all");
  const [error, setError] = useState("");
  useEffect(() => { fetchExerciseLibrary().then(data => setItems(data.exercises || [])).catch(e => setError(e.message)); }, []);
  const categories = useMemo(() => [...new Set(items.map(x => x.category))], [items]);
  const visible = items.filter(item => category === "all" || item.category === category);
  return <div className="tracking-page"><AppNavigation showBack={false}/><main className="tracking-main">
    <p className="tracking-eyebrow">Movement reference</p><h1>Exercise library</h1>
    <p>Browse the general exercise catalog. Library entries are for reference; only recommendations included in your personalized plan have passed your plan’s safety review.</p>
    {error && <p role="alert">{error}</p>}
    <label>Category <select value={category} onChange={e => setCategory(e.target.value)}><option value="all">All categories</option>{categories.map(c => <option key={c}>{c}</option>)}</select></label>
    <div className="tracking-grid">{visible.map(ex => { const image = getExerciseImage(ex.exercise_id); return <article className="tracking-card" key={ex.exercise_id}>
      {image && <img src={image.src} alt={image.alt} style={{width:"100%",maxHeight:220,objectFit:"contain",borderRadius:12,background:"#071c17"}}/>}
      <span className="tracking-badge">General library · {ex.difficulty}</span><h2>{ex.name}</h2><p>{ex.category.replaceAll("_", " ")}</p>
      <p><strong>Targets:</strong> {[...(ex.target_body_area || []), ...(ex.target_capability || [])].join(", ")}</p>
      <p><strong>Equipment:</strong> {ex.equipment?.join(", ") || "None listed"}</p>
      {(ex.sets || ex.repetitions || ex.duration_seconds) && <p><strong>Catalog dosage:</strong> {[ex.sets && `${ex.sets} sets`, ex.repetitions && `${ex.repetitions} reps`, ex.duration_seconds && `${ex.duration_seconds}s`].filter(Boolean).join(" · ")}</p>}
      <ol>{(ex.instructions || []).map((line, i) => <li key={i}>{line}</li>)}</ol>
      <p className="tracking-safety"><strong>Safety notes:</strong> {ex.safety_constraints?.join(" ")}</p>
      <p className="tracking-muted">MoveNet measurement: {ex.movenet_support?.implemented ? "available for this exercise" : "not available; self-guided reference only"}</p>
    </article>; })}</div>
    <a className="tracking-link" href="/plan">← Return to personalized plan</a>
  </main></div>;
}
