/**
 * Shared API configuration and resilient fetcher for MoveWell AI.
 *
 * Local development uses the MoveWell backend on port 8100.
 */

const envUrl =
  typeof import.meta !== "undefined" && import.meta.env && import.meta.env.VITE_API_URL
    ? import.meta.env.VITE_API_URL
    : "http://127.0.0.1:8100";

let cachedBaseUrl = null;

export function getApiUrl() {
  if (cachedBaseUrl) return cachedBaseUrl;

  return envUrl;
}

export function setWorkingApiUrl(url) {
  cachedBaseUrl = url;
  try {
    if (typeof sessionStorage !== "undefined") {
      sessionStorage.setItem("movewell_api_url", url);
    }
  } catch {
    // Ignore storage errors
  }
}

export function getAlternateUrl(urlString) {
  // There is one local backend endpoint; do not silently retry port 8000.
  return null;
}

// Default budget for the small, database-backed endpoints. It is deliberately
// short so a dead backend surfaces quickly instead of hanging a screen.
export const DEFAULT_TIMEOUT_MS = 2500;

// The orchestrator-backed plan run is not one of those endpoints: it calls the
// AI provider for every specialist the server decides is required, and the
// backend allows AI_REQUEST_TIMEOUT_SECONDS (90s) per call. Aborting it after
// the default budget cancelled every real plan run before it could return.
export const WORKFLOW_RUN_TIMEOUT_MS = 180000;

function withTimeout(init, timeoutMs) {
  if (typeof AbortSignal !== "undefined" && typeof AbortSignal.timeout === "function") {
    const timeoutSignal = AbortSignal.timeout(timeoutMs);
    if (!init?.signal) {
      return { ...init, signal: timeoutSignal };
    }
    if (typeof AbortSignal.any === "function") {
      return { ...init, signal: AbortSignal.any([init.signal, timeoutSignal]) };
    }
  }
  return init;
}

/**
 * Fetch wrapper for the configured backend endpoint.
 *
 * `timeoutMs` overrides DEFAULT_TIMEOUT_MS for the slow endpoints (see
 * WORKFLOW_RUN_TIMEOUT_MS).
 */
export async function apiFetch(input, init, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const url = typeof input === "string" ? input : input?.url;

  try {
    return await fetch(input, withTimeout(init, timeoutMs));
  } catch (err) {
    const altUrl = getAlternateUrl(url);
    if (altUrl) {
      try {
        const altInput =
          typeof input === "string" ? altUrl : new Request(altUrl, init);
        const res = await fetch(altInput, withTimeout(init, timeoutMs));

        // Record successful port failover
        const currentBase = getApiUrl();
        const altBase = getAlternateUrl(currentBase);
        if (altBase) {
          setWorkingApiUrl(altBase);
        }
        return res;
      } catch {
        // Fallback failed as well; proceed to throw initial error
      }
    }
    throw err;
  }
}
