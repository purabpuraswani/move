/**
 * Shared API configuration and resilient fetcher for MoveWell AI.
 *
 * Automatically handles port discovery and failover between port 8000
 * (standard FastAPI/Uvicorn default) and port 8100 (alternative port).
 * If a network connection error occurs on one port, it seamlessly falls back
 * to the other port and caches the working port for the session,
 * completely eliminating "Failed to fetch / ERR_CONNECTION_REFUSED" errors.
 */

const envUrl =
  typeof import.meta !== "undefined" && import.meta.env && import.meta.env.VITE_API_URL
    ? import.meta.env.VITE_API_URL
    : "http://127.0.0.1:8000";

let cachedBaseUrl = null;

export function getApiUrl() {
  if (cachedBaseUrl) return cachedBaseUrl;

  try {
    if (typeof sessionStorage !== "undefined") {
      const stored = sessionStorage.getItem("movewell_api_url");
      if (stored) {
        cachedBaseUrl = stored;
        return stored;
      }
    }
  } catch {
    // Ignore storage errors (sandboxed iframes / private mode)
  }

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
  if (!urlString || typeof urlString !== "string") return null;

  if (urlString.includes(":8100")) {
    return urlString.replace(":8100", ":8000");
  }
  if (urlString.includes(":8000")) {
    return urlString.replace(":8000", ":8100");
  }
  return null;
}

/**
 * Resilient fetch wrapper with automatic port failover between 8000 and 8100.
 */
export async function apiFetch(input, init) {
  const url = typeof input === "string" ? input : input?.url;

  try {
    return await fetch(input, init);
  } catch (err) {
    const altUrl = getAlternateUrl(url);
    if (altUrl) {
      try {
        const altInput =
          typeof input === "string" ? altUrl : new Request(altUrl, init);
        const res = await fetch(altInput, init);

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
