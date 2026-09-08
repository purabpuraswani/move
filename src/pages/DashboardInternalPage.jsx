import { useState } from "react";

import {
  fetchMcpStatus,
  fetchPlanHistory,
  fetchSafetyResult,
  fetchUserState,
} from "../services/dashboard";

import "./DashboardInternalPage.css";

function formatDate(value) {
  if (!value) return "—";

  try {
    return new Date(value).toLocaleString();
  } catch {
    return String(value);
  }
}

function NeedBadge({ level }) {
  const normalized = (level || "NOT_ASSESSED").toUpperCase();
  let badgeClass = "badge-neutral";
  if (normalized === "HIGH") badgeClass = "badge-danger";
  else if (normalized === "MEDIUM") badgeClass = "badge-warning";
  else if (normalized === "LOW") badgeClass = "badge-success";

  return <span className={`dash-badge ${badgeClass}`}>{normalized}</span>;
}

function NeedProfileSummary({ currentNeeds }) {
  if (!currentNeeds?.available || !currentNeeds?.data) {
    return <p className="dash-internal-empty">Need Profile has not been computed or is unavailable.</p>;
  }

  const data = currentNeeds.data;
  const overall = data.overallSummary || {};
  const dimensions = [
    { key: "mobility_need", label: "Mobility" },
    { key: "stability_need", label: "Stability" },
    { key: "functional_movement_need", label: "Functional Movement" },
    { key: "behaviour_need", label: "Sedentary Behaviour" },
    { key: "nutrition_need", label: "Nutrition" },
    { key: "exercise_need", label: "Exercise Habits" },
  ];

  return (
    <div className="dash-card">
      <h3 className="dash-card-title">Need Assessment Profile</h3>
      {overall.headline && (
        <div className="dash-summary-banner">
          <strong>Summary:</strong> {overall.headline}
        </div>
      )}

      <div className="dash-stats-grid">
        <div className="dash-stat">
          <span className="dash-stat-num">{overall.assessedCount ?? "—"}</span>
          <span className="dash-stat-desc">Dimensions Assessed</span>
        </div>
        <div className="dash-stat">
          <span className="dash-stat-num">{overall.notAssessedCount ?? "—"}</span>
          <span className="dash-stat-desc">Not Assessed</span>
        </div>
        <div className="dash-stat">
          <span className="dash-stat-num">
            {(overall.dimensionsAtHigh?.length || 0) + (overall.dimensionsAtMedium?.length || 0)}
          </span>
          <span className="dash-stat-desc">Triggering Needs</span>
        </div>
      </div>

      <table className="dash-internal-table">
        <thead>
          <tr>
            <th>Dimension</th>
            <th>Need Level</th>
            <th>Score</th>
            <th>Confidence</th>
            <th>Evidence</th>
          </tr>
        </thead>
        <tbody>
          {dimensions.map(({ key, label }) => {
            const entry = data[key] || {};
            return (
              <tr key={key}>
                <td><strong>{label}</strong></td>
                <td><NeedBadge level={entry.level} /></td>
                <td>{entry.score !== null && entry.score !== undefined ? entry.score : "—"}</td>
                <td>{entry.confidence || "—"}</td>
                <td>
                  {Array.isArray(entry.evidence) && entry.evidence.length > 0 ? (
                    <ul className="dash-evidence-list">
                      {entry.evidence.map((item, idx) => (
                        <li key={idx}>{item}</li>
                      ))}
                    </ul>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function PlanHistoryTable({ title, plans }) {
  return (
    <div className="dash-plan-block">
      <h4>{title} Specialist Plans</h4>
      {(!plans || plans.length === 0) ? (
        <p className="dash-internal-empty">No plan versions recorded for this specialist.</p>
      ) : (
        <table className="dash-internal-table">
          <thead>
            <tr>
              <th>Ver</th>
              <th>Created</th>
              <th>Goal</th>
              <th>Adaptation Reason</th>
              <th>Triggered By</th>
              <th>Selected Items</th>
            </tr>
          </thead>
          <tbody>
            {plans.map((plan) => (
              <tr key={plan.plan_id ?? `${title}-${plan.plan_version}`}>
                <td><span className="dash-badge badge-neutral">v{plan.plan_version ?? 1}</span></td>
                <td>{formatDate(plan.created_at)}</td>
                <td>{plan.goal ?? "—"}</td>
                <td>{plan.adaptation_reason ? <em>{plan.adaptation_reason}</em> : "Initial Plan"}</td>
                <td>{plan.triggered_by ?? "orchestrator"}</td>
                <td>
                  {Array.isArray(plan.selected_ids) && plan.selected_ids.length > 0
                    ? plan.selected_ids.join(", ")
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function AdherenceAndProgress({ userState }) {
  const adherence = userState?.adherence?.data;
  const progress = userState?.progress?.data;

  return (
    <div className="dash-card">
      <h3 className="dash-card-title">Adherence &amp; Progress Metrics</h3>
      <div className="dash-metrics-columns">
        <div className="dash-subcard">
          <h4>Movement Adherence</h4>
          {adherence?.movement ? (
            <ul className="dash-metric-list">
              <li><strong>Completed sessions:</strong> {adherence.movement.completed_sessions ?? 0}</li>
              <li><strong>Total reps:</strong> {adherence.movement.total_repetitions ?? 0}</li>
              <li><strong>Adherence rate:</strong> {Math.round((adherence.movement.adherence_rate ?? 0) * 100)}%</li>
            </ul>
          ) : (
            <p className="dash-internal-empty">No physical movement results recorded yet.</p>
          )}
        </div>

        <div className="dash-subcard">
          <h4>Nutrition Adherence</h4>
          {adherence?.nutrition ? (
            <ul className="dash-metric-list">
              <li><strong>Logged days:</strong> {adherence.nutrition.days_logged ?? 0}</li>
              <li><strong>Status:</strong> {adherence.nutrition.status ?? "NOT_LOGGED"}</li>
              <li><strong>Adherence rate:</strong> {Math.round((adherence.nutrition.adherence_rate ?? 0) * 100)}%</li>
            </ul>
          ) : (
            <p className="dash-internal-empty">No food logs recorded for active plan.</p>
          )}
        </div>

        <div className="dash-subcard">
          <h4>Progress &amp; Reassessment</h4>
          {progress ? (
            <ul className="dash-metric-list">
              <li>
                <strong>Reassessment status:</strong>{" "}
                <span className={`dash-badge ${progress.reassessment_required ? "badge-warning" : "badge-success"}`}>
                  {progress.reassessment_required ? "Reassessment Due" : "Up to Date"}
                </span>
              </li>
              <li><strong>Comparison:</strong> {progress.assessment_comparison?.verdict ?? "Initial cycle"}</li>
              {progress.recommendation && <li><strong>Recommendation:</strong> {progress.recommendation}</li>}
            </ul>
          ) : (
            <p className="dash-internal-empty">Baseline assessment active; comparison pending next review.</p>
          )}
        </div>
      </div>
    </div>
  );
}

function SafetyEvaluationCard({ safetyResult }) {
  if (!safetyResult?.available || !safetyResult?.safety_result) {
    return (
      <div className="dash-card">
        <h3 className="dash-card-title">Safety Gate Evaluation</h3>
        <p className="dash-internal-empty">No safety evaluation on file for this user.</p>
      </div>
    );
  }

  const res = safetyResult.safety_result;
  const status = res.status || "UNKNOWN";
  let statusBadge = "badge-neutral";
  if (status === "PASSED") statusBadge = "badge-success";
  else if (status === "FLAGGED") statusBadge = "badge-warning";
  else if (status === "BLOCKED" || status === "REFERRED") statusBadge = "badge-danger";

  return (
    <div className="dash-card">
      <h3 className="dash-card-title">Safety Gate Evaluation</h3>
      <div className="dash-safety-header">
        <div>
          <span className="dash-label">Gate Status: </span>
          <span className={`dash-badge ${statusBadge}`}>{status}</span>
        </div>
        <div>
          <span className="dash-label">Clinical Referral Required: </span>
          <span className={`dash-badge ${res.requires_referral ? "badge-danger" : "badge-success"}`}>
            {res.requires_referral ? "YES — CLINICAL REFERRAL" : "NO"}
          </span>
        </div>
      </div>

      {res.reason && <p className="dash-safety-reason"><strong>Reason:</strong> {res.reason}</p>}

      <div className="dash-safety-details">
        <div>
          <strong>Safety Flags ({res.flags?.length || 0}):</strong>
          {res.flags && res.flags.length > 0 ? (
            <ul className="dash-flag-list">
              {res.flags.map((flag, idx) => (
                <li key={idx} className="dash-flag-item">{flag}</li>
              ))}
            </ul>
          ) : (
            <p className="dash-internal-empty">None triggered.</p>
          )}
        </div>

        <div>
          <strong>Required Actions:</strong>
          {res.actions && res.actions.length > 0 ? (
            <ul className="dash-action-list">
              {res.actions.map((act, idx) => (
                <li key={idx}>{act}</li>
              ))}
            </ul>
          ) : (
            <p className="dash-internal-empty">Standard precautions apply.</p>
          )}
        </div>
      </div>
    </div>
  );
}

function McpObservabilityCard({ mcpStatus }) {
  if (!mcpStatus) return null;

  return (
    <div className="dash-card">
      <h3 className="dash-card-title">Model Context Protocol (MCP) Observability</h3>
      <div className="dash-mcp-status-header">
        <span className="dash-label">Protocol Status: </span>
        <span className={`dash-badge ${mcpStatus.mcp_package_installed ? "badge-success" : "badge-danger"}`}>
          {mcpStatus.mcp_package_installed ? "MCP Transport Active" : "Package Missing"}
        </span>
      </div>
      <p className="dash-mcp-note">{mcpStatus.status_message}</p>

      <table className="dash-internal-table">
        <thead>
          <tr>
            <th>Specialist</th>
            <th>Server Module</th>
            <th>Real FastMCP Tools</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(mcpStatus.specialists || {}).map(([agentId, info]) => (
            <tr key={agentId}>
              <td><strong>{agentId}</strong></td>
              <td><code>{info.server_module}</code></td>
              <td>
                <div className="dash-tool-tags">
                  {(info.real_tools || []).map((tool) => (
                    <span key={tool} className="dash-tool-tag">{tool}</span>
                  ))}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DashboardInternalPage() {
  const [userId, setUserId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showRawState, setShowRawState] = useState(false);

  const [stateResult, setStateResult] = useState(null);
  const [planHistory, setPlanHistory] = useState(null);
  const [safety, setSafety] = useState(null);
  const [mcpStatus, setMcpStatus] = useState(null);

  async function loadEverything(event) {
    event.preventDefault();

    if (!userId.trim()) {
      setError("Enter a user ID first.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const [stateData, historyData, safetyData, mcpData] = await Promise.all([
        fetchUserState(userId.trim()),
        fetchPlanHistory(userId.trim()),
        fetchSafetyResult(userId.trim()),
        fetchMcpStatus(),
      ]);

      setStateResult(stateData);
      setPlanHistory(historyData);
      setSafety(safetyData);
      setMcpStatus(mcpData);
    } catch (loadError) {
      setError(loadError.message || "This user's data could not be loaded.");
      setStateResult(null);
      setPlanHistory(null);
      setSafety(null);
      setMcpStatus(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="dash-internal-page">
      <div className="dash-internal-banner">Staff / Developer Observability</div>

      <h1 className="dash-page-title">Healthcare &amp; Developer Dashboard</h1>
      <p className="dash-internal-intro">
        Inspect unredacted User State, structured Need Profiles, Specialist Agent decisions,
        Safety Gate verification, and real MCP server bindings.
      </p>

      <form className="dash-internal-form" onSubmit={loadEverything}>
        <div className="dash-input-group">
          <label htmlFor="dash-internal-user-id">Patient / User ID (Mongo _id)</label>
          <input
            id="dash-internal-user-id"
            type="text"
            value={userId}
            onChange={(event) => setUserId(event.target.value)}
            placeholder="e.g. 64f1a2b3c4d5e6f7..."
          />
        </div>
        <button type="submit" className="dash-submit-btn" disabled={loading}>
          {loading ? "Inspecting…" : "Load Record"}
        </button>
      </form>

      {error && <div className="dash-error-alert">{error}</div>}

      {mcpStatus && <McpObservabilityCard mcpStatus={mcpStatus} />}

      {stateResult && (
        <>
          <div className="dash-card">
            <h3 className="dash-card-title">Patient Account Information</h3>
            {stateResult.account ? (
              <div className="dash-account-details">
                <div><strong>User ID:</strong> {stateResult.account.user_id}</div>
                <div><strong>Email:</strong> {stateResult.account.email}</div>
                <div><strong>Registered:</strong> {formatDate(stateResult.account.created_at)}</div>
                <div><strong>Staff Privileges:</strong> {stateResult.account.is_staff ? "Yes" : "No"}</div>
              </div>
            ) : (
              <p className="dash-internal-empty">No account document found.</p>
            )}
          </div>

          <NeedProfileSummary currentNeeds={stateResult.user_state?.current_needs} />

          <div className="dash-card">
            <h3 className="dash-card-title">Specialist Agent Plans &amp; Adaptation History</h3>
            {planHistory?.available ? (
              <>
                <PlanHistoryTable title="Physiotherapy" plans={planHistory.plan_history?.physio} />
                <PlanHistoryTable title="Nutrition" plans={planHistory.plan_history?.nutrition} />
                <PlanHistoryTable title="Behaviour / Habit" plans={planHistory.plan_history?.behaviour} />
              </>
            ) : (
              <p className="dash-internal-empty">{planHistory?.message || "No plan history generated yet."}</p>
            )}
          </div>

          <AdherenceAndProgress userState={stateResult.user_state} />

          <SafetyEvaluationCard safetyResult={safety} />

          <div className="dash-card">
            <div className="dash-toggle-header">
              <h3 className="dash-card-title">Underlying User State JSON</h3>
              <button
                type="button"
                className="dash-toggle-btn"
                onClick={() => setShowRawState(!showRawState)}
              >
                {showRawState ? "Hide Raw State" : "Show Raw State"}
              </button>
            </div>
            {showRawState && (
              <pre className="dash-internal-json">
                {JSON.stringify(stateResult.user_state, null, 2)}
              </pre>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export default DashboardInternalPage;
