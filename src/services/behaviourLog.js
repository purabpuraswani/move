/**
 * Behaviour action API.
 *
 * What the user records is what is stored: which habit goal, whether they
 * did it or skipped it, and optionally how it felt. Nothing is scored here
 * and no adherence figure is sent — the server refuses one outright, because
 * a client that could post a rate could post a number nothing happened to
 * produce. How it is going is worked out from the records themselves.
 *
 * An absence of records is never reported as a failure to do the habit. It
 * is an absence of recording, and the server's adherence code treats it that
 * way (NOT_LOGGED, distinct from NOT_ADHERED) — the same distinction the food
 * log already keeps.
 *
 * This is also what makes a completed action survive a page reload: the
 * button's state is read back from the server, not held in React.
 */

import { authHeader, clearSession } from "./auth";
import { apiFetch, getApiUrl } from "./api";

/** The three answers to "how did that feel", as the server accepts them. */
export const DIFFICULTIES = ["easy", "manageable", "difficult"];

export const DIFFICULTY_LABELS = {
  easy: "Easy",
  manageable: "Manageable",
  difficult: "Difficult",
};

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
 * Record that the user did — or deliberately skipped — one habit goal.
 *
 * `status` is "completed" or "skipped". Skipping is a real answer worth
 * recording: someone who chose to skip and someone who never opened the app
 * are different people, and only one of them has told us anything.
 */
export async function recordBehaviourAction({
  topicId,
  status = "completed",
  difficulty = null,
  notes = null,
  planId = null,
}) {
  const payload = { topic_id: topicId, status };

  if (difficulty) {
    payload.difficulty = difficulty;
  }

  if (notes && notes.trim()) {
    payload.notes = notes.trim();
  }

  // routes/behaviour_log.py accepts the same nested shape as the food log
  // route, so the two services read the same way.
  const body = { payload };

  if (planId) {
    body.plan_id = planId;
  }

  const response = await apiFetch(`${getApiUrl()}/api/behaviour-log`, {
    method: "POST",
    headers: { ...authHeader(), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  return readResponse(
    response,
    "That could not be recorded just now. Please try again.",
  );
}

/** The user's recorded actions, newest first. */
export async function fetchBehaviourActions({ limit = 100 } = {}) {
  const response = await apiFetch(
    `${getApiUrl()}/api/behaviour-log?limit=${encodeURIComponent(limit)}`,
    { headers: authHeader() },
  );

  return readResponse(
    response,
    "Your recorded actions could not be loaded just now.",
  );
}

/**
 * Was this habit goal already recorded today?
 *
 * Pure, and exported so it can be tested without a browser. Returns the
 * matching action or null. "Today" is the viewer's own local day, which is
 * the day they are living in — the record's own UTC timestamp is what is
 * stored, and this only decides what the button should say right now.
 */
export function actionRecordedToday(actions, topicId, now = new Date()) {
  if (!Array.isArray(actions)) {
    return null;
  }

  const sameDay = (value) => {
    const recorded = new Date(value);

    if (Number.isNaN(recorded.getTime())) {
      return false;
    }

    return (
      recorded.getFullYear() === now.getFullYear() &&
      recorded.getMonth() === now.getMonth() &&
      recorded.getDate() === now.getDate()
    );
  };

  return (
    actions.find(
      (action) => action?.topicId === topicId && sameDay(action?.recordedAt),
    ) || null
  );
}
