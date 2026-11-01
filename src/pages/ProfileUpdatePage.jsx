import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import AppNavigation from "../components/AppNavigation.jsx";
import { fetchEditableProfile, updateProfileFields } from "../services/profile.js";
import "./ProfileUpdatePage.css";

const GROUPS = [
  { title: "Nutrition", fields: [
    ["meal_pattern", "Typical meal pattern", "select", [["regular", "Usually regular"], ["irregular", "Often irregular"], ["skips_meals", "I often skip meals"]]],
    ["fruit_vegetable_servings", "Fruit and vegetable servings per day", "number"],
    ["water_glasses_per_day", "Glasses of water per day", "number"],
    ["processed_food_frequency", "Packaged or processed foods", "select", [["rarely", "Rarely"], ["sometimes", "Sometimes"], ["often", "Often"], ["daily", "Daily"]]],
    ["food_preferences", "Food preferences", "list"],
    ["dietary_restrictions", "Dietary restrictions", "list"],
    ["food_allergies", "Food allergies", "list"],
    ["nutrition_goals", "Nutrition goals", "list"],
  ]},
  { title: "Behaviour and routines", fields: [
    ["daily_steps", "Typical daily steps", "number"],
    ["sleep_hours", "Typical sleep hours per night", "number"],
    ["sleep_quality", "Typical sleep quality", "select", [["poor", "Poor"], ["average", "Average"], ["good", "Good"]]],
    ["stress_level", "Reported stress level", "select", [["low", "Low"], ["moderate", "Moderate"], ["high", "High"]]],
    ["recovery_difficulties", "Recovery difficulties", "list"],
    ["daily_sitting_hours", "Hours sitting on a typical day", "number"],
    ["daily_screen_hours", "Hours using screens on a typical day", "number"],
    ["exercise_days", "Exercise days in a typical week", "number"],
    ["exercise_minutes", "Typical exercise session length (minutes)", "number"],
    ["work_type", "Typical work or daily activity setting", "text"],
    ["behaviour_motivation", "What motivates you to build a movement habit?", "text"],
    ["preferred_habits", "Movement habits you prefer", "list"],
    ["daily_routines", "Daily routines that could anchor a habit", "list"],
    ["reported_behaviour_barriers", "Barriers to physical activity", "list"],
    ["preferred_habit_changes", "Habit changes you would like to try", "list"],
  ]},
];

const LIST_FIELDS = new Set(GROUPS.flatMap(group => group.fields.filter((f) => f[2] === "list").map((f) => f[0])));
const HEALTH_FIELDS = [
  ["diabetes", "Diabetes"], ["hypertension", "High blood pressure"],
  ["heart_condition", "Heart condition"], ["previous_injury", "Previous injury"],
  ["joint_pain", "Current joint pain"], ["back_neck_pain", "Current back or neck pain"],
];

function ProfileUpdatePage() {
  const [values, setValues] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetchEditableProfile().then(({ profile }) => setValues(profile || {}))
      .catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, []);

  const update = (key, value) => setValues(current => ({ ...current, [key]: value }));
  const submit = async (event) => {
    event.preventDefault(); setError(""); setSaved(false); setSaving(true);
    try {
      const patch = {};
      for (const group of GROUPS) for (const [key, , type] of group.fields) {
        const value = values[key];
        if (value === undefined) continue;
        if (value === null || value === "") { patch[key] = null; continue; }
        patch[key] = LIST_FIELDS.has(key)
          ? (Array.isArray(value) ? value : String(value).split(",").map(x => x.trim()).filter(Boolean))
          : type === "number" ? Number(value) : value;
        if (LIST_FIELDS.has(key) && Array.isArray(patch[key]) && patch[key].length === 1 && patch[key][0].toLowerCase() === "none") patch[key] = [];
      }
      patch.health = Object.fromEntries([
        ...HEALTH_FIELDS.map(([key]) => [key, values.health?.[key] || null]),
        ["other_conditions", values.health?.other_conditions || null],
      ]);
      await updateProfileFields(patch);
      setSaved(true);
    } catch (e) { setError(e.message); }
    finally { setSaving(false); }
  };

  return <><AppNavigation /><main className="profile-edit-page">
    <Link to="/dashboard">← Dashboard</Link>
    <h1>Update your profile</h1>
    <p>Update the information used to personalize future plans. Blank answers stay unknown; enter “none” to explicitly report no restrictions, allergies, or barriers. Saved plans are not changed.</p>
    {loading ? <p>Loading your profile…</p> : <form onSubmit={submit}>
      {GROUPS.map(group => <section key={group.title}>
        <h2>{group.title}</h2>
        <div className="form-grid">{group.fields.map(([key, label, type, options]) => {
          const value = values[key];
          const shown = LIST_FIELDS.has(key) ? (Array.isArray(value) ? value.join(", ") : value || "") : value ?? "";
          return <label className="input-group" key={key} htmlFor={`profile-${key}`}>{label}
            {type === "select" ? <select id={`profile-${key}`} value={shown} onChange={e => update(key, e.target.value)}>
              <option value="">Unknown / prefer not to answer</option>{options.map(([optionValue, optionLabel]) => <option key={optionValue} value={optionValue}>{optionLabel}</option>)}
            </select> : <input id={`profile-${key}`} type={type === "number" ? "number" : "text"} min={type === "number" ? 0 : undefined} value={shown} onChange={e => update(key, e.target.value)} placeholder={LIST_FIELDS.has(key) ? "Separate multiple answers with commas" : "Leave blank if unknown"} />}
          </label>;
        })}</div>
      </section>)}
      <section>
        <h2>Health information for exercise safety</h2>
        <p>These answers help the Physiotherapy specialist check whether exercises can be evaluated. Unknown answers stay unknown.</p>
        <div className="form-grid">
          {HEALTH_FIELDS.map(([key, label]) => <label className="input-group" key={key} htmlFor={`profile-health-${key}`}>{label}
            <select id={`profile-health-${key}`} value={values.health?.[key] || ""} onChange={e => update("health", { ...(values.health || {}), [key]: e.target.value || null })}>
              <option value="">Unknown / prefer not to answer</option>
              <option value="yes">Yes</option><option value="no">No</option><option value="prefer_not_to_say">Prefer not to say</option>
            </select>
          </label>)}
          <label className="input-group" htmlFor="profile-health-other">Other health conditions
            <input id="profile-health-other" type="text" value={values.health?.other_conditions || ""} onChange={e => update("health", { ...(values.health || {}), other_conditions: e.target.value })} placeholder="Leave blank if unknown; enter none if none" />
          </label>
        </div>
      </section>
      {error && <p role="alert">{error}</p>}{saved && <p role="status">Profile updated. Your next plan run will use these answers.</p>}
      <button type="submit" disabled={saving}>{saving ? "Saving…" : "Save profile"}</button>
    </form>}
  </main></>;
}

export default ProfileUpdatePage;
