import React, { Component, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import AppNavigation from "../components/AppNavigation.jsx";
import { getExerciseImage } from "../movementDemos/exerciseImages.js";
import FoodLogPanel from "../components/FoodLogPanel.jsx";
import BehaviourActionPanel from "../components/BehaviourActionPanel.jsx";
import { fetchLatestWorkflow } from "../services/workflow";
import { fetchProfileSummary } from "../services/profile.js";
import { profileChangedSinceWorkflow } from "../services/planState.js";
import {
  toArray,
  safeDisplayValue,
  normalizeEvidence,
  normalizeRecommendation,
  normalizeRecommendations,
  isPlainRenderable,
} from "../services/specialistData.js";
import "./SpecialistDetailPage.css";

export {
  toArray,
  safeDisplayValue,
  normalizeEvidence,
  normalizeRecommendation,
  normalizeRecommendations,
  isPlainRenderable,
};

// ─────────────────────────────────────────────────────────────────────────────
// ERROR BOUNDARY (PHASE 13)
// ─────────────────────────────────────────────────────────────────────────────

export class SpecialistErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("SpecialistDetailPage rendering error caught by boundary:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="specialist-detail-page">
          <AppNavigation backTo="/dashboard" backLabel="← Dashboard" />
          <main className="specialist-detail-main">
            <div className="specialist-card-panel specialist-error-fallback" role="alert">
              <div className="specialist-hero-avatar" style={{ margin: "0 auto 16px" }}>
                ⚠️
              </div>
              <h2 className="specialist-panel-title" style={{ justifyContent: "center" }}>
                Unable to display specialist details right now
              </h2>
              <p className="specialist-reason-text" style={{ textAlign: "center", marginBottom: "24px" }}>
                There was a problem preparing this specialist&rsquo;s recommendations. Your assessment and health data remain safely saved.
              </p>
              <div style={{ display: "flex", gap: "12px", justifyContent: "center" }}>
                <Link to="/dashboard" className="specialist-secondary-btn">
                  ← Back to Dashboard
                </Link>
                <Link to="/plan" className="specialist-action-btn">
                  See Full MoveWell Plan →
                </Link>
              </div>
            </div>
          </main>
        </div>
      );
    }
    return this.props.children;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// SPECIALIST METADATA CONFIGURATION
// ─────────────────────────────────────────────────────────────────────────────

const SPECIALIST_CONFIGS = {
  exercise: {
    id: "exercise_activity",
    alias: "exercise",
    name: "Exercise & Physical Activity Specialist",
    title: "Exercise & Physical Activity",
    subtitle: "Daily Walking, Step Volume & Sedentary Habit Pacing",
    icon: "🏃",
    focus: "Optimizing overall daily physical activity, stepping volume, and interrupting prolonged sedentary periods.",
  },
  physio: {
    id: "physio",
    alias: "physio",
    name: "Physiotherapy & Movement Specialist",
    title: "Physiotherapy & Movement",
    subtitle: "Mobility, Balance & Corrective Exercise Prescription",
    icon: "🧑‍⚕️",
    focus: "Musculoskeletal assessment, mobility restoration, joint safety, and progressive corrective exercise programming.",
  },
  nutrition: {
    id: "nutrition",
    alias: "nutrition",
    name: "Nutrition & Lifestyle Specialist",
    title: "Nutrition & Lifestyle",
    subtitle: "Dietary Quality, Hydration & Authentic Meal Evidence",
    icon: "🍎",
    focus: "Balanced dietary patterns, adequate protein distribution, optimal hydration, and whole-food nutrition.",
  },
  recovery: {
    id: "recovery",
    alias: "recovery",
    name: "Recovery & Care Specialist",
    title: "Recovery & Care",
    subtitle: "Sleep Hygiene, Rest Days & Fatigue Management",
    icon: "🌙",
    focus: "Sleep quality, restorative rest intervals, tissue recovery, and daily fatigue management.",
  },
  behaviour: {
    id: "behaviour",
    alias: "behaviour",
    name: "Behaviour & Adherence Specialist",
    title: "Behaviour & Adherence",
    subtitle: "Habit Formation, Pacing & Routine Consistency",
    icon: "🧠",
    focus: "Building resilient micro-habits, cognitive pacing, overcoming adherence friction, and long-term compliance.",
  },
  safety: {
    id: "safety",
    alias: "safety",
    name: "Safety & Clinical Escalation Specialist",
    title: "Safety & Clinical Escalation",
    subtitle: "Clinical Gatekeeping, Contraindications & Red Flags",
    icon: "🛡️",
    focus: "Authoritative clinical gatekeeper evaluating medical context, movement contraindications, and red flags before any plan reaches you.",
  },
};

const ALIAS_MAP = {
  exercise: "exercise",
  exercise_activity: "exercise",
  activity: "exercise",
  physio: "physio",
  movement: "physio",
  nutrition: "nutrition",
  recovery: "recovery",
  sleep: "recovery",
  behaviour: "behaviour",
  behavior: "behaviour",
  habits: "behaviour",
  safety: "safety",
  clinical: "safety",
};

// ─────────────────────────────────────────────────────────────────────────────
// RECOMMENDATION CARD COMPONENT (PROPERTY-BY-PROPERTY RENDERING)
// ─────────────────────────────────────────────────────────────────────────────

export function RecommendationCard({ item, isPhysio = false }) {
  if (!item) return null;

  // Ensure item is normalized into a safe structure
  const norm = normalizeRecommendation(item);
  if (!norm) return null;

  const safeTitle = safeDisplayValue(norm.title);
  const safeAction = safeDisplayValue(norm.action);
  const safeWhy = safeDisplayValue(norm.why);
  const safeTarget = safeDisplayValue(norm.target);
  const safeAdherence = safeDisplayValue(norm.adherence);
  const safeSafetyNotes = toArray(norm.safetyNotes)
    .map((s) => safeDisplayValue(s))
    .filter(Boolean);

  // Simple string recommendation
  if (norm.isSimpleString || (!safeAction && !safeWhy && norm.sets == null && norm.repetitions == null && norm.durationSeconds == null)) {
    return (
      <li className="specialist-rec-item specialist-rec-item--simple">
        <span className="specialist-rec-text">{safeTitle}</span>
      </li>
    );
  }

  const hasDosage =
    norm.sets != null || norm.repetitions != null || norm.durationSeconds != null;

  const image = isPhysio ? getExerciseImage(norm.id) : null;

  return (
    <li className="specialist-rec-item specialist-rec-card">
      {image ? (
        <img className="specialist-rec-image" src={image.src} alt={image.alt} />
      ) : null}
      <div className="specialist-rec-content">
        <div className="specialist-rec-header">
          <h4 className="specialist-rec-title">{safeTitle}</h4>
          {safeTarget && (
            <span className="specialist-rec-target-badge">{safeTarget}</span>
          )}
          {norm.difficulty != null && (
            <span className="specialist-rec-diff-badge">Level {safeDisplayValue(norm.difficulty)}</span>
          )}
        </div>

        {safeAction && (
          <p className="specialist-rec-action">
            <strong>Action:</strong> {safeAction}
          </p>
        )}

        {hasDosage && (
          <div className="specialist-rec-dosage">
            {norm.sets != null && (
              <span>
                {norm.sets} {norm.sets === 1 ? "set" : "sets"}
              </span>
            )}
            {norm.repetitions != null && <span>• {norm.repetitions} reps</span>}
            {norm.durationSeconds != null && <span>• {norm.durationSeconds}s hold</span>}
          </div>
        )}

        {safeWhy && (
          <p className="specialist-rec-why">
            <strong>Why it matters:</strong> {safeWhy}
          </p>
        )}

        {safeAdherence && (
          <p className="specialist-rec-adherence">
            <span className="specialist-rec-adherence-label">Status:</span> {safeAdherence}
          </p>
        )}

        {safeSafetyNotes.length > 0 && (
          <div className="specialist-rec-safety">
            <span className="specialist-rec-safety-icon" aria-hidden="true">
              ⚠️
            </span>
            <span>{safeSafetyNotes.join(" ")}</span>
          </div>
        )}
      </div>

      {/* No "Start exercise" here any more: this card is a
          recommendation, a reference and a completion control. The
          camera-guided session is started from the Movement panel on My
          Plan, which is the one place that owns execution. */}
    </li>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// MAIN SPECIALIST DETAIL PAGE COMPONENT
// ─────────────────────────────────────────────────────────────────────────────

function SpecialistDetailPageInner() {
  const { specialistType } = useParams();
  const navigate = useNavigate();

  const normalizedKey = ALIAS_MAP[specialistType?.toLowerCase()] || "physio";
  const config = SPECIALIST_CONFIGS[normalizedKey] || SPECIALIST_CONFIGS.physio;

  const [workflow, setWorkflow] = useState(null);
  const [profileUpdatedAt, setProfileUpdatedAt] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    Promise.allSettled([fetchLatestWorkflow(), fetchProfileSummary()])
      .then(([workflowResult, profileResult]) => {
        if (mounted) {
          if (workflowResult.status === "fulfilled") setWorkflow(workflowResult.value);
          if (profileResult.status === "fulfilled") setProfileUpdatedAt(profileResult.value.updatedAt);
          setLoading(false);
        }
      })
      .catch(() => {
        if (mounted) {
          setLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  // Look up live data for this specialist from specialists_team if present
  const rawTeam = workflow?.specialists_team;
  const teamList = Array.isArray(rawTeam)
    ? rawTeam
    : typeof rawTeam === "object" && rawTeam !== null
    ? Object.values(rawTeam)
    : [];

  const findLiveSpecialist = (key, cfg) =>
    teamList.find(
      (s) =>
        s?.id === cfg.id ||
        s?.id === key ||
        s?.alias === key ||
        (typeof s?.title === "string" && s.title.toLowerCase().includes(key))
    );

  const statusFor = (live) =>
    live?.status || (workflow?.available ? "EVALUATED_NOT_REQUIRED" : "NOT_ASSESSED");

  const workflowIsStale = Boolean(workflow?.available && profileChangedSinceWorkflow(profileUpdatedAt, workflow?.workflow_created_at));

  const liveSpecialist = workflowIsStale ? null : findLiveSpecialist(normalizedKey, config);
  const status = statusFor(liveSpecialist);
  const agentId = normalizedKey === "exercise" ? "exercise_activity" : normalizedKey;
  const journeyEntry = workflowIsStale ? null : toArray(workflow?.agent_journey).find((item) => item?.id === agentId);
  const selectionIsCurrent = journeyEntry
    ? journeyEntry.selection_status === "SELECTED" && toArray(journeyEntry.recommendations).length > 0
    : status === "ACTIVE";
  const isNotAssessed = status === "NOT_ASSESSED";
  const isActive = status === "ACTIVE" && selectionIsCurrent;
  const isInactive = !isActive;
  const statusLabel = workflowIsStale
    ? "Plan needs updating"
    : isActive
    ? safeDisplayValue(liveSpecialist?.status_label) || "Included in your plan"
    : status === "CONTEXT_REQUIRED" || journeyEntry?.selection_status === "SELECTED – CONTEXT REQUIRED"
    ? "More information needed"
    : isNotAssessed ? "No assessment data yet" : "Not included in the current plan";

  // Only saved specialist decisions are shown as findings. Catalog defaults
  // describe a domain; they are not evidence about this user.
  const reason = workflowIsStale
    ? "Your profile changed after this specialist result. Prepare an updated plan before following saved recommendations."
    : safeDisplayValue(liveSpecialist?.reason || journeyEntry?.reason)
    || "No saved specialist decision is available for this workflow.";

  // Normalize evidence safely
  let rawEvidence = liveSpecialist?.evidence ?? journeyEntry?.evidence ?? [];
  if (rawEvidence && typeof rawEvidence === "object" && !Array.isArray(rawEvidence)) {
    if (Array.isArray(rawEvidence.evidence)) {
      rawEvidence = rawEvidence.evidence;
    } else if (Array.isArray(rawEvidence.items)) {
      rawEvidence = rawEvidence.items;
    }
  }
  const evidenceList = normalizeEvidence(rawEvidence)
    .filter((item) => !/added in Phase \d+ for the .* Agent/i.test(item));

  // Evidence states the specialists report alongside their findings.
  // Both are optional: a card from an older persisted run simply has
  // neither, and renders exactly as it did before.
  const missingInformation = toArray(liveSpecialist?.missing_information)
    .concat(toArray(liveSpecialist?.missing_safety_information))
    .concat(toArray(liveSpecialist?.health_screen_missing_information))
    .concat(toArray(journeyEntry?.missing_required_information))
    .filter(Boolean);
  const notAssessedMovements = toArray(liveSpecialist?.not_assessed_movements).filter(
    (entry) => entry && entry.label
  );

  // Normalize recommendations safely
  let rawRecommendations = liveSpecialist?.recommendations ?? journeyEntry?.recommendations;
  if (rawRecommendations && typeof rawRecommendations === "object" && !Array.isArray(rawRecommendations)) {
    if (Array.isArray(rawRecommendations.recommendations)) {
      rawRecommendations = rawRecommendations.recommendations;
    } else if (Array.isArray(rawRecommendations.items)) {
      rawRecommendations = rawRecommendations.items;
    } else {
      rawRecommendations = Object.values(rawRecommendations);
    }
  }
  const rawRecArray = toArray(rawRecommendations);
  const recommendationsList = normalizeRecommendations(rawRecArray);

  // Focus description
  const rawFocus = liveSpecialist?.focus || config.focus;
  const focus = safeDisplayValue(rawFocus) || config.focus;

  // Domain specifics
  const isPhysio = normalizedKey === "physio";
  const isNutrition = normalizedKey === "nutrition";
  const isBehaviour = normalizedKey === "behaviour";
  const isExercise = normalizedKey === "exercise";
  const activityScore = journeyEntry?.findings?.activity_score;

  // Physio: extract rich programme exercises if available
  const movementSpecialist = toArray(workflow?.specialists).find(
    (s) => s?.title === "Movement" || (s?.programme && s.programme.length > 0)
  );
  const physioProgramme = normalizeRecommendations(
    toArray(movementSpecialist?.programme)
  );

  // Behaviour: extract structured habit goals for BehaviourActionPanel
  const behaviourSpecialist = toArray(workflow?.specialists).find(
    (s) => s?.title === "Behaviour" || s?.title === "Daily habits"
  );
  const behaviourFocusItems = toArray(behaviourSpecialist?.focus_items);
  const behaviourGoals = behaviourFocusItems.length > 0
    ? behaviourFocusItems
        .filter((item) => item && (item.topic_id || item.id || item.name || item.title))
        .map((item, i) => ({
          topicId: safeDisplayValue(item.topic_id || item.id) || `topic_${i}`,
          name: safeDisplayValue(item.name || item.title || item.action) || `Habit ${i + 1}`,
          action: safeDisplayValue(item.action || item.why) || "",
        }))
    : recommendationsList.map((r, i) => ({
        topicId: safeDisplayValue(r.id) || `topic_${i}`,
        name: safeDisplayValue(r.title) || `Habit ${i + 1}`,
        action: safeDisplayValue(r.action || r.why) || "",
      }));

  return (
    <div className="specialist-detail-page">
      <AppNavigation backTo="/dashboard" backLabel="← Dashboard" />

      <main className="specialist-detail-main">
        {/* Breadcrumb navigation */}
        <nav className="specialist-breadcrumb" aria-label="Breadcrumb">
          <Link to="/dashboard">Dashboard</Link>
          <span className="specialist-breadcrumb-sep">/</span>
          <Link to="/dashboard#specialists">Specialists</Link>
          <span className="specialist-breadcrumb-sep">/</span>
          <span aria-current="page">{safeDisplayValue(config.title)}</span>
        </nav>

        {/* Hero Card */}
        <header className="specialist-header-card">
          <div className="specialist-hero-avatar" aria-hidden="true">
            {config.icon}
          </div>
          <div className="specialist-hero-content">
            <div className="specialist-hero-top">
              <span className="specialist-hero-role">{safeDisplayValue(config.subtitle)}</span>
              <span
                className={`specialist-badge specialist-badge--${
                  isActive
                    ? "active"
                    : isNotAssessed
                    ? "not-assessed"
                    : "evaluated"
                }`}
              >
                {statusLabel}
              </span>
            </div>
            <h1 className="specialist-hero-title">{safeDisplayValue(config.name)}</h1>
            <p className="specialist-hero-desc">{focus}</p>
            <div className="specialist-focus-box">
              <strong>Clinical Focus:</strong> {focus}
            </div>
          </div>
        </header>

        {workflowIsStale ? (
          <section className="specialist-card-panel" aria-label="Plan needs updating">
            <h2 className="specialist-panel-title">Review your updated information</h2>
            <p className="specialist-reason-text">Saved findings and recommendations are paused because your profile changed after this result was prepared.</p>
            <Link to="/plan">Prepare an updated plan →</Link>
          </section>
        ) : null}

        {isExercise && activityScore ? (
          <section className="specialist-card-panel specialist-activity-score" aria-labelledby="activity-score-heading">
            <h2 id="activity-score-heading" className="specialist-panel-title">MoveWell Activity Indicator</h2>
            <p className="specialist-reason-text">
              {activityScore.value == null
                ? "There is not enough recorded activity information to calculate an indicator yet."
                : <><strong>{safeDisplayValue(activityScore.value)} / 100</strong> · {safeDisplayValue(activityScore.interpretation)}</>}
            </p>
            <p className="specialist-reason-text">{safeDisplayValue(activityScore.method)}</p>
            <ul className="specialist-evidence-list">
              {toArray(activityScore.components).map((component) => (
                <li className="specialist-evidence-item" key={component.metric}>
                  <span className="specialist-evidence-text">
                    {safeDisplayValue(component.label)}: {component.score == null ? "Not recorded" : `${safeDisplayValue(component.score)} / 100`}
                    {component.input_value != null ? ` · ${safeDisplayValue(component.input_value)} ${safeDisplayValue(component.unit) || ""}` : ""}
                    {component.project_marker != null ? ` · project marker ${safeDisplayValue(component.project_marker)} ${safeDisplayValue(component.unit) || ""}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {/* Detail Grid */}
        <div className="specialist-grid">
          {/* Clinical Rationale Panel */}
          <section className="specialist-card-panel" aria-labelledby="decision-heading">
            <h2 id="decision-heading" className="specialist-panel-title">
              Why this is (or is not) in your plan
            </h2>
            <p className="specialist-reason-text">{reason}</p>
          </section>

          {/* Evidence Panel */}
          <section className="specialist-card-panel" aria-labelledby="evidence-heading">
            <h2 id="evidence-heading" className="specialist-panel-title">
              Information considered
            </h2>
            {evidenceList.length > 0 ? (
              <ul className="specialist-evidence-list">
                {evidenceList.map((itemStr, idx) => (
                  <li key={idx} className="specialist-evidence-item">
                    <span className="specialist-evidence-icon" aria-hidden="true">
                      ✓
                    </span>
                    <span className="specialist-evidence-text">{safeDisplayValue(itemStr)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="specialist-reason-text">
                No supporting details were saved for this workflow yet.
              </p>
            )}

            {/*
              What this specialist still needs. The backend reports it
              (missing_information) instead of filling the gap with
              general advice, so the screen has to show it -- otherwise an
              unanswered question looks the same as a reviewed finding.
            */}
            {missingInformation.length > 0 ? (
              <div className="specialist-missing-block">
                <h3 className="specialist-missing-title">Information not yet provided</h3>
                <ul className="specialist-evidence-list">
                  {missingInformation.map((itemStr, idx) => (
                    <li key={idx} className="specialist-evidence-item">
                      <span className="specialist-evidence-icon" aria-hidden="true">
                        ?
                      </span>
                      <span className="specialist-evidence-text">
                        {safeDisplayValue(itemStr)}
                      </span>
                    </li>
                  ))}
                </ul>
                <Link to="/profile">Update your profile →</Link>
              </div>
            ) : null}

            {notAssessedMovements.length > 0 ? (
              <div className="specialist-missing-block">
                <h3 className="specialist-missing-title">Movement checks not measured</h3>
                <ul className="specialist-evidence-list">
                  {notAssessedMovements.map((entry, idx) => (
                    <li key={idx} className="specialist-evidence-item">
                      <span className="specialist-evidence-icon" aria-hidden="true">
                        ?
                      </span>
                      <span className="specialist-evidence-text">
                        {safeDisplayValue(entry?.label)} — not measured. This is not a
                        result, and nothing has been assumed from it.
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </section>

          {/* Actionable Plan / Recommendations */}
          <section className="specialist-card-panel" aria-labelledby="recommendations-heading">
            <h2 id="recommendations-heading" className="specialist-panel-title">
              Your recommendations
            </h2>

            {/* Inactive state fallback */}
            {isInactive ? (
              <div className="specialist-empty-state">
                <div className="specialist-empty-icon" aria-hidden="true">
                  ℹ️
                </div>
                <p className="specialist-empty-text">{statusLabel}</p>
                <p className="specialist-reason-text" style={{ marginTop: "8px" }}>
                  {reason}
                </p>
                {toArray(journeyEntry?.missing_required_information).length > 0 ? (
                  <div className="specialist-missing-block">
                    <h3 className="specialist-missing-title">Information needed</h3>
                    <ul className="specialist-evidence-list">
                      {toArray(journeyEntry.missing_required_information).map((item, idx) => (
                        <li className="specialist-evidence-item" key={idx}>{safeDisplayValue(item)}</li>
                      ))}
                    </ul>
                    <Link to="/profile">Update your profile →</Link>
                  </div>
                ) : null}
              </div>
            ) : (
              <>
                {/* Physio Rich Programme rendering */}
                {isPhysio && physioProgramme.length > 0 ? (
                  <div>
                    <p className="specialist-reason-text" style={{ marginBottom: "16px" }}>
                      These exercises were selected using your saved movement assessment and the exercise safety review:
                    </p>
                    <ul className="specialist-rec-list" style={{ marginBottom: "20px" }}>
                      {physioProgramme.map((ex, idx) => (
                        <RecommendationCard
                          key={ex.id || `physio_${idx}`}
                          item={ex}
                          isPhysio={true}
                        />
                      ))}
                    </ul>
                  </div>
                ) : recommendationsList.length > 0 ? (
                  <ul className="specialist-rec-list">
                    {recommendationsList.map((rec, idx) => (
                      <RecommendationCard
                        key={rec.id || `rec_${idx}`}
                        item={rec}
                        isPhysio={isPhysio}
                      />
                    ))}
                  </ul>
                ) : (
                  <p className="specialist-reason-text">
                    No specific recommendations are currently available.
                  </p>
                )}
              </>
            )}
          </section>

          {/* Interactive Tools for Nutrition or Behaviour */}
          {isNutrition && (
            <section className="specialist-card-panel" aria-labelledby="nutrition-log-heading">
              <h2 id="nutrition-log-heading" className="specialist-panel-title">
                🥗 Log a Meal for Nutrition Review
              </h2>
              <FoodLogPanel
                planAvailable={Boolean(workflow?.available)}
                planId={workflow?.id || null}
              />
            </section>
          )}

          {isBehaviour && isActive && (
            <section className="specialist-card-panel" aria-labelledby="behaviour-panel-heading">
              <h2 id="behaviour-panel-heading" className="specialist-panel-title">
                🧠 Today&rsquo;s Habit Check-in
              </h2>
              <BehaviourActionPanel
                goals={behaviourGoals}
                planId={workflow?.id || null}
              />
            </section>
          )}
        </div>

        {/* Navigation Actions */}
        <div className="specialist-nav-bar">
          <button
            type="button"
            className="specialist-secondary-btn"
            onClick={() => navigate("/dashboard")}
          >
            ← Back to Dashboard
          </button>
          <button
            type="button"
            className="specialist-action-btn"
            onClick={() => navigate("/plan")}
          >
            See full MoveWell plan →
          </button>
        </div>

      </main>
    </div>
  );
}

export default function SpecialistDetailPage() {
  return (
    <SpecialistErrorBoundary>
      <SpecialistDetailPageInner />
    </SpecialistErrorBoundary>
  );
}
