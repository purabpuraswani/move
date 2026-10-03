/**
 * Exercise Result API.
 *
 * What leaves the browser is a handful of numbers: how many repetitions, how
 * long, how much of the target was completed. The camera frames, the MoveNet
 * keypoints and the per-frame signal history stay in the browser and are
 * discarded when the page closes — the backend schema refuses anything that
 * even looks like pose data, and this service never assembles it in the first
 * place.
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
 * Submit one completed exercise.
 *
 * `status` is the honest outcome, not a grade: "completed" when the target was
 * met, "incomplete" when the user stopped early, "invalid" when the camera
 * could not see enough to measure anything. An invalid result carries no
 * measurements at all — a reading nobody could make is not a score of zero.
 */
export async function submitExerciseResult({
  exerciseId,
  status,
  startedAt,
  completedAt,
  measurements = null,
  errors = null,
  planId = null,
  source = null,
}) {
  const payload = {
    exerciseId,
    status,
    startedAt,
    completedAt,
  };

  // "camera" when MoveNet measured the session, "manual_confirmation" when
  // the user ticked the box themselves. Omitted entirely by the camera
  // flow, which the backend reads as "camera" — the two must stay
  // distinguishable in the stored history.
  if (source) {
    payload.source = source;
  }

  if (status !== "invalid" && measurements) {
    payload.measurements = measurements;
  }

  if (errors && errors.length) {
    payload.errors = errors;
  }

  // routes/exercise_results.py declares `payload` and `plan_id` as separate
  // Body(...) parameters, so they nest under those names.
  const body = { payload };

  if (planId) {
    body.plan_id = planId;
  }

  const response = await apiFetch(`${getApiUrl()}/api/exercise-results`, {
    method: "POST",
    headers: { ...authHeader(), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  return readResponse(
    response,
    "Your exercise result could not be saved just now. Please try again.",
  );
}

export async function fetchExerciseResults({ limit = 20 } = {}) {
  const response = await apiFetch(
    `${getApiUrl()}/api/exercise-results?limit=${encodeURIComponent(limit)}`,
    { headers: authHeader() },
  );

  return readResponse(
    response,
    "Your exercise history could not be loaded just now.",
  );
}

/**
 * Record "I did this one" without a camera session.
 *
 * Deliberately separate from submitExerciseResult: a manual confirmation
 * carries no measurements at all, and the backend refuses it if it does.
 * It still becomes a real, persisted exercise result, so it counts towards
 * adherence exactly like any other completed session — it is simply marked
 * as self-reported rather than measured.
 */
export async function confirmExerciseManually({ exerciseId, planId = null }) {
  const now = new Date().toISOString();

  return submitExerciseResult({
    exerciseId,
    status: "completed",
    startedAt: now,
    completedAt: now,
    planId,
    source: "manual_confirmation",
  });
}

/**
 * Undo a manual confirmation (un-ticking the box).
 *
 * Only ever used for a result this user confirmed by hand; the endpoint
 * refuses anything else, so a camera-recorded session cannot be erased
 * from the history by a mis-click in the UI.
 */
export async function deleteManualExerciseResult(resultId) {
  const response = await apiFetch(
    `${getApiUrl()}/api/exercise-results/${encodeURIComponent(resultId)}`,
    { method: "DELETE", headers: authHeader() },
  );

  if (response.status === 204) return { deleted: true };

  return readResponse(
    response,
    "That completion could not be undone just now. Please try again.",
  );
}
