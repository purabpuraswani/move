/**
 * Workflow API — the orchestrator-backed MoveWell plan.
 *
 * This is the service the final MoveWell journey runs on. It replaces the
 * legacy guidance path (services/guidance.js, the Wellness Guide / Care
 * Navigator pair) as the source of the user's plan: the server decides which
 * specialists are needed, runs them, applies the Safety Gate, and returns one
 * combined result. The client never selects agents, never names them, and
 * never sees a workflow id, an agent run id, or a tool call — the response
 * shape (backend/workflow/response.py) does not contain them.
 *
 * Nothing here interprets the plan. It is passed through as the server
 * produced it, so what the user reads is what the Safety Gate approved.
 */

import { authHeader, clearSession } from "./auth";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function readResponse(response, fallbackMessage) {
  if (response.status === 401) {
    clearSession();

    throw new Error("Your session has expired. Please sign in again.");
  }

  let data = null;

  try {
    data = await response.json();
  } catch {
    const error = new Error(fallbackMessage);
    error.status = response.status;

    throw error;
  }

  if (!response.ok) {
    const error = new Error(data?.detail || fallbackMessage);
    error.status = response.status;

    throw error;
  }

  return data;
}

/**
 * Build the plan.
 *
 * `progressTrigger` is passed only when something real happened that warrants
 * a progress review — a recorded exercise result, or food logged against a
 * plan. It is never sent speculatively: the Progress Agent runs because there
 * is new evidence, not on a timer.
 */
export async function runWorkflow({ progressTrigger = null } = {}) {
  const body = progressTrigger ? { progress_trigger: progressTrigger } : {};

  const response = await fetch(`${API_URL}/api/workflow/run`, {
    method: "POST",
    headers: { ...authHeader(), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  return readResponse(
    response,
    "Your plan could not be prepared just now. Please try again shortly.",
  );
}

/**
 * The plan as it already stands, without running anything.
 *
 * Returns `{ available: false }` rather than a 404 when the user has no plan
 * yet, so "no plan yet" is an ordinary state the journey can render, not an
 * error it has to catch.
 */
export async function fetchLatestWorkflow() {
  const response = await fetch(`${API_URL}/api/workflow/latest`, {
    headers: authHeader(),
  });

  return readResponse(
    response,
    "Your plan could not be loaded just now. Please try again shortly.",
  );
}

/**
 * Plan presence and the three-state plan model.
 *
 * Both live in ./planState so they can be unit tested without importing
 * this module's `auth` dependency (which touches localStorage and cannot
 * be loaded by `node --test`). Re-exported here so every existing importer
 * of `hasAnyPlan` from this module keeps working unchanged.
 */
export { PLAN_STATES, hasAnyPlan, planState } from "./planState";
