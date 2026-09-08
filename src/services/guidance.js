/**
 * Guidance API.
 *
 * Four calls, and only one of them costs anything. fetchGuidanceStatus and
 * fetchLatestGuidance read what already exists; runGuidance is the one that asks
 * a model to write something, and it is only ever called because the user pressed
 * a button. A screen that generates on mount is a screen that spends money every
 * time somebody glances at it.
 *
 * Nothing here interprets what comes back. The withheld and failed states are
 * passed through as the server described them, because "this was written but did
 * not pass our safety rules" and "the provider could not be reached" are
 * different things to tell somebody.
 */

import { authHeader, clearSession } from "./auth";
import { apiFetch, getApiUrl } from "./api";

export const WELLNESS_AGENT = "wellness_guidance";
export const NAVIGATION_AGENT = "care_navigation";

/**
 * Shared response handling.
 *
 * The status is kept on the error for the same reason as in the report service:
 * 503 means guidance is not set up on this server and 502 means the provider had
 * a problem, and those need different wording rather than one generic failure.
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
    const error = new Error(
      response.ok ? "The server sent a response that could not be read." : fallbackMessage
    );
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

/** What each agent is, and what none of them may do. Static on the server. */
export async function fetchAgents() {
  const response = await apiFetch(`${getApiUrl()}/api/guidance/agents`, {
    headers: authHeader(),
  });

  const data = await readResponse(response, "The agent list could not be loaded.");

  return {
    agents: data.agents ?? [],
    professionalTypes: data.professionalTypes ?? [],
    disclaimer: data.disclaimer ?? "",
    safetyNote: data.safetyNote ?? "",
  };
}

/** What could be produced right now, without producing it. */
export async function fetchGuidanceStatus() {
  const response = await apiFetch(`${getApiUrl()}/api/guidance/status`, {
    headers: authHeader(),
  });

  return readResponse(
    response,
    "What your guidance could be based on could not be checked."
  );
}

/**
 * The last guidance produced, or null.
 *
 * `run.isStale` says the user's information has changed since it was written.
 * null means there was nothing to compare against, which is not the same as
 * current, so the caller has to phrase it rather than treat it as false.
 */
export async function fetchLatestGuidance() {
  const response = await apiFetch(`${getApiUrl()}/api/guidance/latest`, {
    headers: authHeader(),
  });

  const data = await readResponse(
    response,
    "Your last guidance could not be loaded."
  );

  return {
    run: data.run ?? null,
    disclaimer: data.disclaimer ?? "",
    safetyNote: data.safetyNote ?? "",
  };
}

/** Ask the agents to write guidance now. The only call that costs anything. */
export async function runGuidance() {
  const response = await apiFetch(`${getApiUrl()}/api/guidance/run`, {
    method: "POST",
    headers: authHeader(),
  });

  return readResponse(response, "Your guidance could not be generated.");
}
