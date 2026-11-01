import { useCallback, useEffect, useState } from "react";
import AppNavigation from "../components/AppNavigation.jsx";
import FoodLogPanel from "../components/FoodLogPanel.jsx";
import BehaviourActionPanel from "../components/BehaviourActionPanel.jsx";
import { fetchDailyCheckins, saveDailyCheckin } from "../services/dailyCheckins.js";
import { fetchLatestWorkflow } from "../services/workflow.js";
import { selectedInterventionAgentIds } from "../services/specialistData.js";
import "./TrackingPages.css";

const FIELDS = [
  ["sleep_hours", "Sleep", "Hours slept", "number", "0.5", "24", "recovery"],
  ["sleep_quality", "Sleep", "Sleep quality (1–5)", "number", "1", "5", "recovery"],
  ["stress_level", "Recovery", "Reported stress (1–5)", "number", "1", "5", "recovery"],
  ["recovery_difficulty", "Recovery", "Recovery felt difficult today?", "select", "", "", "recovery"],
  ["steps", "Activity", "Steps", "number", "0", "200000", "activity"],
  ["sitting_minutes", "Activity", "Sitting minutes", "number", "0", "1440", "activity"],
  ["walking_minutes", "Activity", "Walking minutes", "number", "0", "1440", "activity"],
  ["movement_breaks", "Activity", "Movement breaks", "number", "0", "100", "activity"],
  ["fruit_vegetable_servings", "Nutrition", "Fruit and vegetable servings", "number", "0", "100", "nutrition"],
  ["water_intake_ml", "Nutrition", "Water (ml)", "number", "0", "20000", "nutrition"],
];

export default function DailyTrackingPage() {
  const [values, setValues] = useState({}); const [history, setHistory] = useState([]);
  const [workflow, setWorkflow] = useState(null);
  const [error, setError] = useState(""); const [saved, setSaved] = useState(false); const [busy, setBusy] = useState(false);
  const load = useCallback(() => fetchDailyCheckins().then(data => setHistory(data.checkins || [])).catch(e => setError(e.message)), []);
  useEffect(() => { load(); fetchLatestWorkflow().then(setWorkflow).catch(() => {}); }, [load]);
  const activeAgentIds = selectedInterventionAgentIds(workflow);
  const behaviourSpecialist = (workflow?.specialists || []).find(s => s?.title === "Behaviour" || s?.title === "Daily habits");
  const behaviourGoals = activeAgentIds.has("behaviour") ? (behaviourSpecialist?.focus_items || []).map((item, i) => ({
    topicId: item?.topic_id || item?.id || `habit-${i}`,
    name: item?.name || item?.title || "Habit action",
    action: item?.action || item?.why || "",
  })).filter(item => item.topicId) : [];
  async function submit(event) {
    event.preventDefault(); const payload = Object.fromEntries(Object.entries(values).filter(([,v]) => v !== "").map(([k,v]) => [k, k === "recovery_difficulty" ? Number(v) : Number(v)]));
    if (!Object.keys(payload).length) { setError("Enter at least one value you want to record."); return; }
    setBusy(true); setError(""); setSaved(false);
    try { await saveDailyCheckin(payload); setSaved(true); setValues({}); await load(); } catch(e) { setError(e.message); } finally { setBusy(false); }
  }
  return <div className="tracking-page"><AppNavigation showBack={false}/><main className="tracking-main">
    <p className="tracking-eyebrow">Your daily record</p><h1>Activity, nutrition & recovery</h1>
    <p>Only values you enter are stored. Blank fields remain unknown; this check-in does not diagnose or score your health.</p>
    {behaviourGoals.length > 0 && <BehaviourActionPanel goals={behaviourGoals} planId={workflow?.id || null}/>}
    <form className="tracking-card tracking-form" onSubmit={submit}>
      {FIELDS.map(([id, group, label, type, min, max]) => <label key={id}><span>{group} · {label}</span>{type === "select" ? <select value={values[id] ?? ""} onChange={e => setValues(v => ({...v,[id]:e.target.value}))}><option value="">Not recorded</option><option value="1">Yes</option><option value="0">No</option></select> : <input aria-label={label} type="number" min={min} max={max} step={id === "sleep_hours" ? "0.5" : "1"} value={values[id] ?? ""} onChange={e => setValues(v => ({...v,[id]:e.target.value}))}/>}</label>)}
      {error && <p role="alert" className="tracking-error">{error}</p>}{saved && <p role="status">Saved to your daily history.</p>}<button disabled={busy}>{busy ? "Saving…" : "Save today’s check-in"}</button>
    </form>
    <FoodLogPanel planAvailable={false}/>
    <section><h2>Exercise checklist</h2><p>Exercise completions and Safety-Gate-approved recommendations are on your plan.</p><a className="tracking-link" href="/plan">Open personalized plan and exercise checklist →</a></section>
    <section><h2>Recent recorded days</h2>{history.length ? <div className="tracking-grid">{history.map(day => <article className="tracking-card" key={day.date}><h3>{day.date}</h3>{FIELDS.filter(([id]) => day[id] != null).map(([id,,label]) => <p key={id}>{label}: {id === "recovery_difficulty" ? (day[id] ? "Yes" : "No") : day[id]}</p>)}</article>)}</div> : <p>No daily check-ins recorded yet.</p>}</section>
  </main></div>;
}
