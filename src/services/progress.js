/**
 * The progress series the Progress page plots.
 *
 * One request for everything the page charts. The backend
 * (backend/routes/progress.py) builds it from stored exercise results,
 * stored assessments and the user's stored plan versions — nothing is
 * derived in the browser, so a number shown here is a number that was
 * recorded.
 *
 * Each series arrives with its own `plottable` flag and `point_count`.
 * Callers must honour the flag rather than counting points themselves:
 * the threshold for "this is a trend" belongs in one place
 * (progress_agent/series.py's MIN_POINTS_FOR_TREND), not in every
 * component that draws a line.
 */

import { authHeader, clearSession } from "./auth";
import { apiFetch, getApiUrl } from "./api";

async function readResponse(response, fallbackMessage) {
  if (response.status === 401) {
    clearSession();

    throw new Error("Your session has expired. Please sign in again.");
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

export async function fetchProgressSeries({ limit = 200 } = {}) {
  const response = await apiFetch(
    `${getApiUrl()}/api/progress/series?limit=${encodeURIComponent(limit)}`,
    { headers: authHeader() },
  );

  return readResponse(
    response,
    "Your progress could not be loaded just now.",
  );
}
