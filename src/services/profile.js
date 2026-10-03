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


  const data = await response.json().catch(() => ({}));


  if (!response.ok) {
    throw new Error(
      profileErrorMessage(data.detail) || "Failed to save profile"
    );
  }


  return data;
}


// FastAPI sends `detail` as a string for errors a route raises, but as a list
// of {loc, msg, ...} objects when form validation fails (a missing or
// non-numeric field). Passing that list to `new Error` printed
// "[object Object],[object Object]…", so turn it into a sentence instead.
function profileErrorMessage(detail) {

  if (typeof detail === "string") return detail;

  if (Array.isArray(detail) && detail.length > 0) {

    const fields = [
      ...new Set(
        detail
          .map((item) => {
            const loc = Array.isArray(item?.loc) ? item.loc : [];
            const field = loc[loc.length - 1];
            return typeof field === "string"
              ? field.replace(/_/g, " ")
              : null;
          })
          .filter(Boolean)
      ),
    ];

    if (fields.length > 0) {
      return `Please check these fields: ${fields.join(", ")}.`;
    }

    const message = detail[0]?.msg;
    return typeof message === "string" ? message : "";
  }

  return "";
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
