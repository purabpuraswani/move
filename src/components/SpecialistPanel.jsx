import { useEffect, useState } from "react";

import MovementDemo from "../movementDemos/MovementDemo.jsx";
import { getMovementDemo } from "../movementDemos/registry.js";
import { fetchExerciseResults } from "../services/exerciseResults";
import {
  normalizeRecommendation,
  safeDisplayValue,
  toArray,
} from "../services/specialistData.js";
import "./SpecialistPanel.css";

function Section({ title, children, className = "" }) {
  if (!children) return null;
  return (
    <section className={`specialist-block ${className}`}>
      <h3 className="specialist-block-title">{title}</h3>
      {children}
    </section>
  );
}

function Finding({ finding }) {
  if (!finding) return null;
  const capability = safeDisplayValue(finding.capability);
  const verdict = safeDisplayValue(finding.finding);
  const evidence = toArray(finding.evidence);

  return (
    <li className={finding.measured ? "specialist-finding" : "specialist-finding specialist-finding--unmeasured"}>
      <div className="specialist-finding-head">
        <span className="specialist-finding-name">{capability}</span>
        <span className="specialist-finding-verdict">{verdict}</span>
      </div>
      {evidence.length ? (
        <ul className="specialist-evidence">
          {evidence.map((line, index) => <li key={index}>{safeDisplayValue(line)}</li>)}
        </ul>
      ) : null}
    </li>
  );
}

function prescriptionOf(exercise) {
  const parts = [];
  if (exercise.sets) parts.push(`${exercise.sets} sets`);
  if (exercise.repetitions) parts.push(`${exercise.repetitions} reps`);
  if (exercise.duration_seconds) parts.push(`${exercise.duration_seconds} seconds`);
  return parts.join(" · ") || null;
}

function ExerciseCard({ exercise, isCompletedToday = false, lastResult = null, onStart }) {
  const [showDemo, setShowDemo] = useState(false);
  const prescription = prescriptionOf(exercise);
  const demo = getMovementDemo(`exercise-${exercise.id}`);
  const watching = toArray(exercise.watching);
  const isCameraGuided = watching.length > 0 && !watching.includes("whether you mark it as done");

  return (
    <li className={`specialist-exercise-card ${isCompletedToday ? "specialist-exercise-card--completed" : ""}`}>
      <div className="specialist-exercise-top">
        <div className="specialist-exercise-main-info">
          <div className="specialist-exercise-title-row">
            <h4 className="specialist-exercise-name">{safeDisplayValue(exercise.name)}</h4>
            {isCompletedToday ? <span className="specialist-completed-pill">✓ Done today</span> : null}
          </div>
          {exercise.target ? <p className="specialist-exercise-target"><span className="specialist-target-label">Focus:</span> {safeDisplayValue(exercise.target)}</p> : null}
        </div>
        {exercise.change && exercise.change !== "Added" ? <span className="specialist-tag">{safeDisplayValue(exercise.change)}</span> : null}
      </div>

      {exercise.why ? <p className="specialist-exercise-why">{safeDisplayValue(exercise.why)}</p> : null}

      <div className="specialist-exercise-pills">
        {prescription ? <span className="specialist-pill specialist-pill--metric" title="Prescribed volume">{prescription}</span> : null}
        {exercise.difficulty ? <span className="specialist-pill specialist-pill--level" title="Difficulty level">{safeDisplayValue(exercise.difficulty)}</span> : null}
        <span className={`specialist-pill ${isCameraGuided ? "specialist-pill--camera" : "specialist-pill--manual"}`} title="Guidance mode">
          {isCameraGuided ? "📷 Camera guided" : "✓ Guided practice"}
        </span>
      </div>

      {isCompletedToday && lastResult?.measurements ? (
        <div className="specialist-recorded-today-summary">
          <span className="recorded-summary-icon">✓</span>
          <span className="recorded-summary-text">
            Recorded session: {lastResult.measurements.repetitions ? `${lastResult.measurements.repetitions} reps` : ""}
            {lastResult.measurements.repetitions && lastResult.measurements.durationSeconds ? " · " : ""}
            {lastResult.measurements.durationSeconds ? `${lastResult.measurements.durationSeconds}s hold` : ""}
          </span>
        </div>
      ) : null}

      {toArray(exercise.safety).length ? (
        <div className="specialist-exercise-safety-callout">
          <span className="specialist-safety-icon" aria-hidden="true">⚠️</span>
          <div className="specialist-safety-body">
            <strong>Safety note:</strong>
            {toArray(exercise.safety).map((note, index) => <span key={index} className="specialist-safety-line">{safeDisplayValue(note)}</span>)}
          </div>
        </div>
      ) : null}

      {exercise.progression || exercise.regression ? (
        <div className="specialist-exercise-adjustments">
          {exercise.progression ? <div className="specialist-adj-row"><span className="specialist-adj-label">Make it harder:</span><span className="specialist-adj-text">{safeDisplayValue(exercise.progression)}</span></div> : null}
          {exercise.regression ? <div className="specialist-adj-row"><span className="specialist-adj-label">Make it easier:</span><span className="specialist-adj-text">{safeDisplayValue(exercise.regression)}</span></div> : null}
        </div>
      ) : null}

      {demo ? (
        <div className="specialist-demo-container">
          <button type="button" className="specialist-demo-toggle-btn" onClick={() => setShowDemo(!showDemo)}>
            {showDemo ? "Hide demonstration ▲" : "View demonstration preview ▼"}
          </button>
          {showDemo ? <div className="specialist-inline-demo"><MovementDemo demo={demo} /></div> : null}
        </div>
      ) : null}

      <div className="specialist-exercise-cta-row">
        <button type="button" className={`specialist-start-btn ${isCompletedToday ? "specialist-start-btn--completed" : ""}`} onClick={() => onStart(exercise.id)}>
          {isCompletedToday ? "Repeat exercise ↻" : "Start exercise →"}
        </button>
      </div>
    </li>
  );
}

function FindingsBlock({ findings, label }) {
  if (!findings.length) return null;
  return (
    <div className="specialist-baseline-context">
      <span className="specialist-context-label">{label}</span>
      <div className="specialist-findings-grid">
        {findings.map((finding, index) => (
          <div key={index} className={`specialist-finding-pill ${finding.measured ? "" : "specialist-finding-pill--unmeasured"}`}>
            <span className="finding-pill-cap">{safeDisplayValue(finding.capability)}:</span>
            <span className="finding-pill-res">{safeDisplayValue(finding.finding)}</span>
          </div>
        ))}
      </div>
      {findings.some((finding) => !finding.measured || finding.finding === "Not measured") ? (
        <div className="specialist-unmeasured-notice"><span className="unmeasured-notice-icon">ℹ</span><span>Some capabilities were not fully observed during baseline testing.</span></div>
      ) : null}
    </div>
  );
}

function LearningBlock({ learning, subject }) {
  return learning.length ? (
    <div className="specialist-learning-evidence">
      <span className="specialist-evidence-title">Recorded {subject} evidence:</span>
      <ul className="specialist-learning-list">
        {learning.map((item, index) => <li key={index} className="specialist-learning-item"><span className="learning-item-icon">📊</span><span>{safeDisplayValue(item)}</span></li>)}
      </ul>
    </div>
  ) : <p className="specialist-learning-empty">No {subject} sessions recorded yet today.</p>;
}

function ChangesBlock({ changes, variant = "" }) {
  if (!changes.length) return null;
  return (
    <div className={`specialist-adaptation-banner${variant ? ` specialist-adaptation-banner--${variant}` : ""}`}>
      <div className="specialist-adaptation-banner-head"><h4 className="adaptation-title">Recent routine adjustments</h4></div>
      <ul className="specialist-changes-list">
        {changes.map((change, index) => {
          const exercise = safeDisplayValue(change?.exercise);
          const action = safeDisplayValue(change?.change);
          const reason = safeDisplayValue(change?.reason);
          return (
            <li key={index} className="specialist-change-card">
              <div className="change-card-title-row"><strong className="change-exercise-name">{exercise || "Routine adjustment"}</strong><span className={`change-action-tag change-action-tag--${action.toLowerCase()}`}>{action}</span></div>
              {reason ? <p className="change-reason-text">{reason}</p> : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function RecordingGuidance({ items, open, onToggle }) {
  return (
    <div className="specialist-recording-guidance">
      <button type="button" className="specialist-disclosure-toggle" onClick={onToggle}>{open ? "Hide recording guidance ▲" : "View recording guidance ▼"}</button>
      {open ? <ul className="specialist-asks-list">{items.map((item, index) => <li key={index}>{safeDisplayValue(item)}</li>)}</ul> : null}
    </div>
  );
}

function SpecialistPanel({ specialist, onStartExercise = null, actionSlot = null }) {
  const [showRecordingGuidance, setShowRecordingGuidance] = useState(false);
  const [completedExerciseIds, setCompletedExerciseIds] = useState(new Set());
  const [todayResults, setTodayResults] = useState([]);

  useEffect(() => {
    let active = true;
    if (specialist?.completedExerciseIds) {
      setCompletedExerciseIds(new Set(specialist.completedExerciseIds));
      return undefined;
    }
    if (typeof window !== "undefined" && window.__mockCompletedExerciseIds) {
      setCompletedExerciseIds(new Set(window.__mockCompletedExerciseIds));
      return undefined;
    }
    fetchExerciseResults({ limit: 50 }).then((response) => {
      if (!active || !response?.results) return;
      const results = toArray(response.results);
      setTodayResults(results);
      const today = new Date().toISOString().slice(0, 10);
      setCompletedExerciseIds(new Set(results.filter((result) => result.status === "completed" || result.status === "incomplete").filter((result) => safeDisplayValue(result.completedAt).startsWith(today)).map((result) => result.exerciseId)));
    }).catch(() => {});
    return () => { active = false; };
  }, [specialist]);

  useEffect(() => {
    window.__setCompletedExerciseIds = (ids) => setCompletedExerciseIds(new Set(ids));
    return () => { delete window.__setCompletedExerciseIds; };
  }, []);

  if (!specialist) return null;

  const {
    title,
    goal,
    what_i_found: rawFindings,
    working_on: rawWorkingOn,
    why_this_programme: whyProgramme,
    why_involved: whyInvolved,
    programme: rawProgramme,
    focus_items: rawFocusItems,
    today: rawToday,
    need_from_you: rawNeedFromYou,
    learning: rawLearning,
    watching: rawWatching,
    changes: rawChanges,
    plan_version: planVersion,
    next_review: nextReview,
  } = specialist;

  const findings = toArray(rawFindings);
  const workingOn = toArray(rawWorkingOn);
  const programme = toArray(rawProgramme);
  const focusItems = toArray(rawFocusItems);
  const today = toArray(rawToday);
  const needFromYou = toArray(rawNeedFromYou);
  const learning = toArray(rawLearning);
  const watching = toArray(rawWatching);
  const changes = toArray(rawChanges);
  const safeTitle = safeDisplayValue(title);
  const safeGoal = safeDisplayValue(goal);
  const safeRationale = safeDisplayValue(whyProgramme || whyInvolved);
  const safeNextReview = safeDisplayValue(nextReview);
  const isMovement = safeTitle === "Movement" || programme.length > 0;
  const isNutrition = safeTitle === "Nutrition";
  const isBehaviour = safeTitle === "Daily habits" || safeTitle === "Behaviour";
  const subject = isNutrition ? "nutrition" : isBehaviour ? "habit" : "exercise";

  if (isMovement) {
    const totalCount = programme.length;
    const completedCount = programme.filter((exercise) => completedExerciseIds.has(exercise?.id)).length;
    const progressPercentage = totalCount ? Math.round((completedCount / totalCount) * 100) : 0;
    return (
      <article id="specialist-movement" className="specialist specialist--movement">
        <header className="specialist-coaching-head"><div className="specialist-coaching-brand"><span className="specialist-coaching-badge">Movement plan • Physio</span><h2 className="specialist-coaching-title">Your movement plan</h2></div>{planVersion ? <span className="specialist-version-pill">Plan v{safeDisplayValue(planVersion)}</span> : null}</header>
        <section className="specialist-today-hero"><div className="specialist-today-header"><span className="specialist-section-eyebrow">Today</span><h3 className="specialist-today-heading">Today's Movement Session</h3></div>{safeGoal ? <p className="specialist-coaching-goal">{safeGoal}</p> : null}<div className="specialist-daily-progress-card"><div className="specialist-progress-row"><span className="specialist-progress-label">Today's completion</span><span className="specialist-progress-fraction"><strong>{completedCount}</strong> of {totalCount} {totalCount === 1 ? "exercise" : "exercises"} completed</span></div><div className="specialist-progress-bar-track"><div className="specialist-progress-bar-fill" style={{ width: `${progressPercentage}%` }} /></div></div></section>
        <section className="specialist-coaching-section specialist-focus-section"><div className="specialist-section-header"><span className="specialist-section-eyebrow">Your Focus</span><h3 className="specialist-section-title">What we're working on</h3></div>{workingOn.length ? <ul className="specialist-chips">{workingOn.map((item, index) => <li key={index} className="specialist-chip">{safeDisplayValue(item)}</li>)}</ul> : null}{safeRationale ? <p className="specialist-rationale-text">{safeRationale}</p> : null}<FindingsBlock findings={findings} label="From your baseline assessment:" /></section>
        <section className="specialist-coaching-section specialist-exercises-section"><div className="specialist-section-header specialist-exercises-header-row"><div><span className="specialist-section-eyebrow">Your Exercises</span><h3 className="specialist-section-title">Prescribed Movements</h3></div><span className="specialist-exercise-count-tag">{programme.length} {programme.length === 1 ? "movement" : "movements"}</span></div>{programme.length ? <ul className="specialist-exercises-list">{programme.map((exercise, index) => <ExerciseCard key={exercise?.id || index} exercise={exercise} isCompletedToday={completedExerciseIds.has(exercise?.id)} lastResult={todayResults.find((result) => result.exerciseId === exercise?.id)} onStart={onStartExercise || (() => {})} />)}</ul> : <div className="specialist-empty-programme"><p className="specialist-text--quiet">No specific exercises scheduled for today.</p></div>}</section>
        <section className="specialist-coaching-section specialist-learning-section"><div className="specialist-section-header"><span className="specialist-section-eyebrow">Adaptive Intelligence</span><h3 className="specialist-section-title">What MoveWell is learning from you</h3></div><LearningBlock learning={learning} subject={subject} /></section>
        <section className="specialist-coaching-section specialist-next-section"><div className="specialist-section-header"><span className="specialist-section-eyebrow">The Adaptive Loop</span><h3 className="specialist-section-title">What happens next</h3></div>{safeNextReview ? <p className="specialist-review-timeline"><strong>Your review cycle:</strong> {safeNextReview}</p> : null}{planVersion > 1 ? <ChangesBlock changes={changes} /> : null}{needFromYou.length ? <RecordingGuidance items={needFromYou} open={showRecordingGuidance} onToggle={() => setShowRecordingGuidance(!showRecordingGuidance)} /> : null}</section>
      </article>
    );
  }

  const layout = isNutrition ? "nutrition" : "behaviour";
  return (
    <article id={isNutrition ? "specialist-nutrition" : "specialist-daily-habits"} className={`specialist specialist--${layout}`}>
      <header className="specialist-coaching-head"><div className="specialist-coaching-brand"><span className={`specialist-coaching-badge specialist-coaching-badge--${layout}`}>{isNutrition ? "Nutrition focus • Nutrition" : "Daily habit focus • Behaviour"}</span><h2 className="specialist-coaching-title">{isNutrition ? "Your nutrition focus" : "Your daily habit focus"}</h2></div>{planVersion ? <span className="specialist-version-pill">Plan v{safeDisplayValue(planVersion)}</span> : null}</header>
      <section className={`specialist-today-hero specialist-today-hero--${layout}`}><div className="specialist-today-header"><span className="specialist-section-eyebrow">Today</span><h3 className="specialist-today-heading">{isNutrition ? "Today's Nutrition Focus" : "Today's Habit Action"}</h3></div>{safeGoal ? <p className="specialist-coaching-goal">{safeGoal}</p> : null}{today.length ? <ul className="specialist-today-actions-list">{today.map((item, index) => <li key={index} className="specialist-today-action-item"><span className="today-action-icon" aria-hidden="true">{isNutrition ? "🥗" : "🎯"}</span><span>{safeDisplayValue(item)}</span></li>)}</ul> : null}</section>
      <section className="specialist-coaching-section specialist-focus-section"><div className="specialist-section-header"><span className="specialist-section-eyebrow">Your Focus</span><h3 className="specialist-section-title">{isNutrition ? "What we're working on" : "Habit formation & routine focus"}</h3></div>{workingOn.length ? <ul className="specialist-chips">{workingOn.map((item, index) => <li key={index} className={`specialist-chip specialist-chip--${layout}`}>{safeDisplayValue(item)}</li>)}</ul> : null}{safeRationale ? <p className="specialist-rationale-text">{safeRationale}</p> : null}{focusItems.length ? <ul className="specialist-focus-cards-list">{focusItems.map((item, index) => { const normalized = normalizeRecommendation(item); const name = safeDisplayValue(normalized.title || normalized.name); const action = safeDisplayValue(normalized.action); const why = safeDisplayValue(normalized.why); const adherence = safeDisplayValue(normalized.adherence); return <li key={index} className="specialist-focus-card"><div className="specialist-focus-card-top"><h4 className="specialist-focus-card-name">{name}</h4>{adherence ? <span className="specialist-adherence-pill">{adherence}</span> : null}</div>{action ? <p className="specialist-focus-card-action"><strong>{isNutrition ? "Daily focus:" : "Action:"}</strong> {action}</p> : null}{why ? <p className="specialist-focus-card-why">{why}</p> : null}</li>; })}</ul> : null}<FindingsBlock findings={findings} label="From your intake & assessment:" /></section>
      <section className="specialist-coaching-section specialist-actions-section"><div className="specialist-section-header"><span className="specialist-section-eyebrow">Your Actions</span><h3 className="specialist-section-title">{isNutrition ? "Record your meals" : "Record today's habit"}</h3></div>{actionSlot}</section>
      <section className="specialist-coaching-section specialist-learning-section"><div className="specialist-section-header"><span className="specialist-section-eyebrow">Adaptive Intelligence</span><h3 className="specialist-section-title">What MoveWell is learning from your {subject}s</h3></div><LearningBlock learning={learning} subject={subject} /></section>
      <section className="specialist-coaching-section specialist-next-section"><div className="specialist-section-header"><span className="specialist-section-eyebrow">The Adaptive Loop</span><h3 className="specialist-section-title">What happens next</h3></div>{safeNextReview ? <p className="specialist-review-timeline"><strong>Your review cycle:</strong> {safeNextReview}</p> : null}{planVersion > 1 ? <ChangesBlock changes={changes} variant={layout} /> : null}{needFromYou.length ? <RecordingGuidance items={needFromYou} open={showRecordingGuidance} onToggle={() => setShowRecordingGuidance(!showRecordingGuidance)} /> : null}</section>
    </article>
  );
}

export default SpecialistPanel;
