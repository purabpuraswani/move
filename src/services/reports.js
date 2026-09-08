/**
 * Medical report API.
 *
 * The two sides of a report are kept separate here as well as on the server.
 * fetchReport returns the candidate values and the user's review of them, for
 * the review screen. fetchConfirmedReports returns only what the user has
 * confirmed, and is what any guidance feature reads.
 *
 * Nothing in this file invents a value. When automatic reading is unavailable
 * the caller is told so and the manual entry path is used instead.
 */

import { authHeader, clearSession } from "./auth";
import { apiFetch, getApiUrl } from "./api";

/**
 * Shared response handling.
 *
 * The status code is kept on the thrown error, because the report flow needs to
 * tell the cases apart: 503 means automatic reading is not set up on this
 * server, 422 means the document could not be read, and those two need
 * different things said to the user.
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
    if (!response.ok) {
      const error = new Error(fallbackMessage);
      error.status = response.status;

      throw error;
    }

    throw new Error("The server sent a response that could not be read.");
  }

  if (!response.ok) {
    const error = new Error(data?.detail || fallbackMessage);
    error.status = response.status;

    throw error;
  }

  return data;
}

function jsonHeaders() {
  return { ...authHeader(), "Content-Type": "application/json" };
}

/**
 * Upload a report file, or start one for entering values by hand.
 *
 * FormData is used rather than JSON because the file goes with it, and the
 * Content-Type header is deliberately left off: the browser sets it with the
 * multipart boundary, and overriding it breaks the upload.
 */
export async function createReport({ file = null, title = "", reportDate = "", facility = "" } = {}) {
  const body = new FormData();

  body.append("source", file ? "upload" : "manual_entry");

  if (file) body.append("file", file);
  if (title) body.append("title", title);
  if (reportDate) body.append("report_date", reportDate);
  if (facility) body.append("facility", facility);

  const response = await apiFetch(`${getApiUrl()}/api/reports`, {
    method: "POST",
    headers: authHeader(),
    body,
  });

  const data = await readResponse(response, "Your report could not be uploaded.");

  return { report: data.report, extraction: data.extraction };
}

/** Ask the server to read candidate values off the uploaded document. */
export async function extractReport(reportId) {
  const response = await apiFetch(
    `${getApiUrl()}/api/reports/${encodeURIComponent(reportId)}/extract`,
    { method: "POST", headers: authHeader() }
  );

  const data = await readResponse(
    response,
    "The report could not be read automatically."
  );

  return data.report;
}

/** Whether automatic reading is configured on this server. */
export async function fetchExtractionStatus() {
  const response = await apiFetch(`${getApiUrl()}/api/reports/extraction-status`, {
    headers: authHeader(),
  });

  return readResponse(
    response,
    "Whether reports can be read automatically could not be checked."
  );
}

/** The categories a hand-entered field may be given. */
export async function fetchFieldCategories() {
  const response = await apiFetch(`${getApiUrl()}/api/reports/field-categories`, {
    headers: authHeader(),
  });

  const data = await readResponse(response, "The field types could not be loaded.");

  return data.categories ?? [];
}

/** The user's reports, newest first, without their values. */
export async function fetchReports({ limit = 20, skip = 0 } = {}) {
  const query = new URLSearchParams({ limit: String(limit), skip: String(skip) });

  const response = await apiFetch(`${getApiUrl()}/api/reports?${query}`, {
    headers: authHeader(),
  });

  const data = await readResponse(response, "Your reports could not be loaded.");

  return { reports: data.reports ?? [], total: data.total ?? 0 };
}

/** One report, with candidate values and the review so far. */
export async function fetchReport(reportId) {
  const response = await apiFetch(
    `${getApiUrl()}/api/reports/${encodeURIComponent(reportId)}`,
    { headers: authHeader() }
  );

  const data = await readResponse(response, "That report could not be loaded.");

  return { report: data.report, extraction: data.extraction };
}

/**
 * Save the user's corrections.
 *
 * `fields` is the full list as shown on screen. Each entry carries the value the
 * user sees and whether it should be included; the server derives whether that
 * counts as accepting or correcting the candidate, so the record of what changed
 * cannot disagree with the values themselves.
 */
export async function saveReportFields(reportId, fields) {
  const response = await apiFetch(
    `${getApiUrl()}/api/reports/${encodeURIComponent(reportId)}/fields`,
    {
      method: "PUT",
      headers: jsonHeaders(),
      body: JSON.stringify({ fields }),
    }
  );

  const data = await readResponse(response, "Your changes could not be saved.");

  return data.report;
}

/** The user's statement that these values match their document. */
export async function confirmReport(reportId) {
  const response = await apiFetch(
    `${getApiUrl()}/api/reports/${encodeURIComponent(reportId)}/confirm`,
    { method: "POST", headers: authHeader() }
  );

  const data = await readResponse(response, "This report could not be confirmed.");

  return data.report;
}

/** Withdraw a confirmation so the values can be edited again. */
export async function reopenReport(reportId) {
  const response = await apiFetch(
    `${getApiUrl()}/api/reports/${encodeURIComponent(reportId)}/reopen`,
    { method: "POST", headers: authHeader() }
  );

  const data = await readResponse(response, "This report could not be reopened.");

  return data.report;
}

export async function deleteReport(reportId) {
  const response = await apiFetch(
    `${getApiUrl()}/api/reports/${encodeURIComponent(reportId)}`,
    { method: "DELETE", headers: authHeader() }
  );

  await readResponse(response, "This report could not be deleted.");

  return true;
}

/**
 * Only what the user has confirmed.
 *
 * hasConfirmedReports distinguishes "nothing confirmed yet" from "confirmed and
 * empty", which matters: a feature reading this must be able to say it has
 * nothing to work from rather than behave as though the user had no findings.
 */
export async function fetchConfirmedReports() {
  const response = await apiFetch(`${getApiUrl()}/api/reports/confirmed`, {
    headers: authHeader(),
  });

  const data = await readResponse(
    response,
    "Your confirmed report values could not be loaded."
  );

  return {
    hasConfirmedReports: Boolean(data.hasConfirmedReports),
    reportCount: data.reportCount ?? 0,
    reports: data.reports ?? [],
  };
}
