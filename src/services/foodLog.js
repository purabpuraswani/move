/**
 * Food log API.
 *
 * What the user records is what is stored: a meal, a food name, an
 * approximate portion, and optionally a note. No nutrient values are
 * calculated here and none are asked of the user — nutrient data has a
 * defined provenance on the server side (IFCT 2017, ICMR-NIN 2024, and the
 * secondary sources), and a number typed into a text box in the browser is
 * not one of them.
 *
 * An absence of entries is never reported as a failure to eat well. It is an
 * absence of logging, and the adherence code on the server treats it that way
 * (NOT_LOGGED, distinct from NOT_ADHERED).
 */

import { authHeader, clearSession } from "./auth";
import { apiFetch, getApiUrl } from "./api";

export const MEALS = ["breakfast", "lunch", "dinner", "snack"];

export const MEAL_LABELS = {
  breakfast: "Breakfast",
  lunch: "Lunch",
  dinner: "Dinner",
  snack: "Snack",
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

export async function logFood({ meal, foodName, quantity, notes, planId = null }) {
  // The server's field is `quantity` and it is free text on purpose --
  // "1 bowl", "2 rotis", "half a plate". It is never parsed into a number
  // here, and the user is never asked for grams.
  const payload = {
    meal,
    food_name: foodName,
    quantity,
  };

  if (notes && notes.trim()) {
    payload.notes = notes.trim();
  }

  // routes/food_log.py declares `payload` and `plan_id` as two separate
  // Body(...) parameters, so the request body nests them under those names
  // rather than being the entry itself.
  const body = { payload };

  // Sent only when known: an entry tied to the plan it was logged against
  // is what makes per-plan adherence possible later. Guessing a plan_id
  // would attribute logging to a plan the user was not following.
  if (planId) {
    body.plan_id = planId;
  }

  const response = await apiFetch(`${getApiUrl()}/api/food-log`, {
    method: "POST",
    headers: { ...authHeader(), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  return readResponse(
    response,
    "That entry could not be saved just now. Please try again.",
  );
}

export async function fetchFoodLog({ limit = 20 } = {}) {
  const response = await apiFetch(
    `${getApiUrl()}/api/food-log?limit=${encodeURIComponent(limit)}`,
    { headers: authHeader() },
  );

  return readResponse(
    response,
    "Your food log could not be loaded just now.",
  );
}
