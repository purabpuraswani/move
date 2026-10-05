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


// ---------------------------------------------------------------------------
// The editable profile and the Nutrition & Lifestyle check-in
//
// The field list, the options and the allowed ranges all come from the server
// (backend/routes/profile_spec.py and backend/nutrition_library/check_in.py),
// so the editor renders what the server will accept. Nothing here decides which
// fields exist or what a valid answer is.
// ---------------------------------------------------------------------------

function sharedError(response, data, fallback) {
  if (response.status === 401) {
    clearSession();

    throw new Error("Your session has expired. Please sign in again.");
  }

  return new Error(profileErrorMessage(data?.detail) || fallback);
}

/** The editable profile: sections, each with this user's current values. */
export async function fetchProfile() {
  const response = await apiFetch(`${getApiUrl()}/api/profile`, {
    headers: authHeader(),
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw sharedError(response, data, "Your profile could not be loaded.");
  }

  return data;
}

/**
 * Save a partial change: only the fields passed are touched, so a save from one
 * section cannot wipe another.
 */
export async function updateProfile(fields) {
  const response = await apiFetch(`${getApiUrl()}/api/profile`, {
    method: "PATCH",
    headers: { ...authHeader(), "Content-Type": "application/json" },
    body: JSON.stringify({ fields }),
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw sharedError(response, data, "Your changes could not be saved.");
  }

  return data;
}

/** The six check-in questions and this user's answers to them. */
export async function fetchNutritionCheckIn() {
  const response = await apiFetch(`${getApiUrl()}/api/profile/nutrition-check-in`, {
    headers: authHeader(),
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw sharedError(
      response,
      data,
      "Your nutrition check-in could not be loaded."
    );
  }

  return data;
}

export async function saveNutritionCheckIn(answers) {
  const response = await apiFetch(`${getApiUrl()}/api/profile/nutrition-check-in`, {
    method: "PATCH",
    headers: { ...authHeader(), "Content-Type": "application/json" },
    body: JSON.stringify({ answers }),
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw sharedError(
      response,
      data,
      "Your nutrition check-in could not be saved."
    );
  }

  return data;
}
