/**
 * Assessment results API.
 *
 * Only the numbers the browser measured are sent. No video, image, frame, or
 * keypoint sequence is included, because none of those ever leave the device;
 * the payload comes from toStoredPayload(), which is the only thing allowed to
 * describe a session to the server.
 */

import { authHeader, clearSession } from "./auth";
import { apiFetch, getApiUrl } from "./api";

/**
 * Shared response handling.
 *
 * A 401 clears the stored session, because a token the server rejects is worse
 * than no token: it makes every later request fail in a way that looks like a
 * server fault.
 */
async function readResponse(response, fallbackMessage) {
  if (response.status === 401) {
    clearSession();

    throw new Error("Your session has expired. Please sign in again.");
  }

  let data;

  try {
    data = await response.json();
  } catch {
    // A non-JSON body means the server or a proxy failed before reaching the
    // route. There is nothing useful to read out of it.
    if (!response.ok) throw new Error(fallbackMessage);

    throw new Error("The server sent a response that could not be read.");
  }

  if (!response.ok) {
    throw new Error(data?.detail || fallbackMessage);
  }

  return data;
}

function jsonHeaders() {
  return { ...authHeader(), "Content-Type": "application/json" };
}

/** Save one completed session. Returns the stored assessment. */
export async function saveAssessment(payload) {
  const response = await apiFetch(`${getApiUrl()}/api/assessments`, {
    method: "POST",
    headers: jsonHeaders(),
    body: JSON.stringify(payload),
  });

  const data = await readResponse(response, "Your results could not be saved.");

  return data.assessment;
}

/**
 * The most recent session, or null.
 *
 * A user who has never completed one is not an error case: null means "no
 * assessment yet", which the UI must show as such rather than as zeros.
 */
export async function fetchLatestAssessment() {
  const response = await apiFetch(`${getApiUrl()}/api/assessments/latest`, {
    headers: authHeader(),
  });

  const data = await readResponse(
    response,
    "Your latest results could not be loaded."
  );

  return { assessment: data.assessment ?? null, total: data.total ?? 0 };
}

/** Sessions, newest first, without their measurements. */
export async function fetchAssessmentHistory({ limit = 20, skip = 0 } = {}) {
  const query = new URLSearchParams({ limit: String(limit), skip: String(skip) });

  const response = await apiFetch(`${getApiUrl()}/api/assessments?${query}`, {
    headers: authHeader(),
  });

  const data = await readResponse(
    response,
    "Your assessment history could not be loaded."
  );

  return {
    assessments: data.assessments ?? [],
    total: data.total ?? 0,
  };
}

/** One full session, including its measurements. */
export async function fetchAssessment(assessmentId) {
  const response = await apiFetch(
    `${getApiUrl()}/api/assessments/${encodeURIComponent(assessmentId)}`,
    { headers: authHeader() }
  );

  const data = await readResponse(response, "That assessment could not be loaded.");

  return data.assessment;
}
