/**
 * Internal healthcare/developer observability dashboard API.
 *
 * Every one of these calls a route gated by the backend's
 * require_staff_user dependency: a non-staff account gets a 403 from the
 * server itself. This file adds no gating of its own on the frontend --
 * the enforcement that matters lives on the server, exactly as documented
 * in routes/dashboard.py.
 *
 * These responses are the real, unredacted internal shapes (unlike
 * services/*.js's patient-facing calls) -- this file is not meant to be
 * used by ordinary account screens.
 */

import { authHeader, clearSession } from "./auth";
import { apiFetch, getApiUrl } from "./api";

async function readResponse(response, fallbackMessage) {
  if (response.status === 401) {
    clearSession();

    throw new Error("Your session has expired. Please sign in again.");
  }

  if (response.status === 403) {
    throw new Error("This account does not have staff access to the internal dashboard.");
  }

  let data;

  try {
    data = await response.json();
  } catch {
    if (!response.ok) throw new Error(fallbackMessage);

    throw new Error("The server sent a response that could not be read.");
  }

  if (!response.ok) {
    throw new Error(data?.detail || fallbackMessage);
  }

  return data;
}

/** The full, unredacted User State for one user, plus safe account info. */
export async function fetchUserState(userId) {
  const response = await apiFetch(`${getApiUrl()}/api/dashboard/users/${encodeURIComponent(userId)}/state`, {
    headers: authHeader(),
  });

  return readResponse(response, "This user's state could not be loaded.");
}

/** Every historical plan version across physio/nutrition/behaviour. */
export async function fetchPlanHistory(userId) {
  const response = await apiFetch(
    `${getApiUrl()}/api/dashboard/users/${encodeURIComponent(userId)}/plan-history`,
    { headers: authHeader() }
  );

  return readResponse(response, "This user's plan history could not be loaded.");
}

/** The persisted Safety Result from this user's last workflow run. */
export async function fetchSafetyResult(userId) {
  const response = await apiFetch(
    `${getApiUrl()}/api/dashboard/users/${encodeURIComponent(userId)}/safety`,
    { headers: authHeader() }
  );

  return readResponse(response, "This user's safety result could not be loaded.");
}

/** Real MCP integration status for every specialist server. */
export async function fetchMcpStatus() {
  const response = await apiFetch(`${getApiUrl()}/api/dashboard/mcp-status`, {
    headers: authHeader(),
  });

  return readResponse(response, "MCP status could not be loaded.");
}
