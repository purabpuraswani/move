import { authHeader, clearSession } from "./auth";
import { apiFetch, getApiUrl } from "./api";

async function read(response) {
  const data = await response.json().catch(() => ({}));
  if (response.status === 401) { clearSession(); throw new Error("Please sign in again."); }
  if (!response.ok) throw new Error(data.detail || "Daily check-in could not be saved.");
  return data;
}

export async function saveDailyCheckin(values) {
  const now = new Date();
  const date = [now.getFullYear(), String(now.getMonth() + 1).padStart(2, "0"), String(now.getDate()).padStart(2, "0")].join("-");
  return read(await apiFetch(`${getApiUrl()}/api/daily-checkins`, {
    method: "POST", headers: { ...authHeader(), "Content-Type": "application/json" },
    body: JSON.stringify({ date, ...values }),
  }));
}

export async function fetchDailyCheckins() {
  return read(await apiFetch(`${getApiUrl()}/api/daily-checkins?limit=90`, { headers: authHeader() }));
}

export async function fetchExerciseLibrary() {
  const response = await apiFetch(`${getApiUrl()}/api/exercise-library`, { headers: authHeader() });
  return read(response);
}
