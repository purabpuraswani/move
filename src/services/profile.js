import { authHeader, clearSession } from "./auth";
import { apiFetch, getApiUrl } from "./api";


export async function completeProfile(formData) {

  const response = await apiFetch(
    `${getApiUrl()}/api/profile/complete`,
    {
      method: "POST",

      // Content-Type is intentionally not set: the browser adds the correct
      // multipart boundary for FormData on its own.
      headers: authHeader(),

      body: formData,
    }
  );


  if (response.status === 401) {

    clearSession();

    throw new Error(
      "Your session has expired. Please sign in again."
    );

  }


  const data = await response.json();


  if (!response.ok) {
    throw new Error(
      data.detail || "Failed to save profile"
    );
  }


  return data;
}


/**
 * The lifestyle answers the user gave during onboarding.
 *
 * Returns { complete, profile, updatedAt }. complete is false when the user has
 * not filled in onboarding yet, and the caller must show that as "nothing yet"
 * rather than as zeros. These are self-reported answers, not measurements.
 */
export async function fetchProfileSummary() {

  const response = await apiFetch(
    `${getApiUrl()}/api/profile/summary`,
    {
      headers: authHeader(),
    }
  );


  if (response.status === 401) {

    clearSession();

    throw new Error(
      "Your session has expired. Please sign in again."
    );

  }


  const data = await response.json();


  if (!response.ok) {
    throw new Error(
      data.detail || "Your profile could not be loaded."
    );
  }


  return {
    complete: Boolean(data.complete),
    profile: data.profile ?? null,
    updatedAt: data.updatedAt ?? null,
  };
}
