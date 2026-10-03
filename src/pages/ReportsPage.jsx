/**
 * Medical reports: upload one, or start entering values by hand.
 *
 * The page states the sequence up front, because the sequence is the point. A
 * report is read automatically, then checked by the person it belongs to, and
 * only what that person confirms is used anywhere else. Nothing on this page
 * shows a value as trustworthy before that has happened.
 *
 * If automatic reading is not configured on the server, the page says so plainly
 * and offers manual entry. It does not show an empty review screen as though
 * something had been read.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  createReport,
  deleteReport,
  fetchExtractionStatus,
  fetchReports,
} from "../services/reports";
import { getToken } from "../services/auth";
import AppNavigation from "../components/AppNavigation.jsx";

import "./AssessmentPage.css";
import "./ReportsPage.css";

const STATUS_TEXT = {
  uploaded: "Uploaded, not read yet",
  processing: "Being read",
  extracted: "Read, needs checking",
  needs_review: "Needs your check",
  confirmed: "Confirmed by you",
  failed: "Could not be read",
};

const STATUS_TONE = {
  uploaded: "neutral",
  processing: "neutral",
  extracted: "review",
  needs_review: "review",
  confirmed: "confirmed",
  failed: "failed",
};

function formatDate(value) {
  if (!value) return null;

  return new Date(value).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function ReportStatus({ report }) {
  const tone = STATUS_TONE[report.status] ?? "neutral";

  return (
    <span className={`report-status report-status--${tone}`}>
      {STATUS_TEXT[report.status] ?? report.status}
    </span>
  );
}

/**
 * Progress through the review, in words rather than a bar.
 *
 * "6 of 9 checked" is what the user needs to know to decide whether to open it.
 * A percentage would imply the remaining work is proportional, and the last
 * value can easily take longer than the first eight.
 */
function ReviewProgress({ progress, status }) {
  if (!progress || progress.total === 0) return null;

  if (status === "confirmed") {
    return (
      <span className="report-progress">
        {progress.included} {progress.included === 1 ? "value" : "values"} confirmed
        {progress.rejected > 0 && `, ${progress.rejected} removed`}
      </span>
    );
  }

  const checked = progress.total - progress.pending;

  return (
    <span className="report-progress">
      {checked} of {progress.total} checked
    </span>
  );
}

function ReportsPage() {
  const navigate = useNavigate();

  const signedIn = Boolean(getToken());

  const [reports, setReports] = useState([]);
  const [total, setTotal] = useState(0);
  const [listState, setListState] = useState(() => (signedIn ? "loading" : "signed-out"));
  const [listError, setListError] = useState(null);

  const [extraction, setExtraction] = useState(null);

  const [file, setFile] = useState(null);
  const [title, setTitle] = useState("");
  const [reportDate, setReportDate] = useState("");
  const [facility, setFacility] = useState("");

  const [createState, setCreateState] = useState("idle");
  const [createError, setCreateError] = useState(null);

  const [deletingId, setDeletingId] = useState(null);

  const loadReports = useCallback(async () => {
    setListState("loading");
    setListError(null);

    try {
      const page = await fetchReports({ limit: 50 });

      setReports(page.reports);
      setTotal(page.total);
      setListState("ready");
    } catch (error) {
      setListError(error.message);
      setListState("error");
    }
  }, []);

  useEffect(() => {
    if (!signedIn) {
      return;
    }

    let cancelled = false;

    fetchReports({ limit: 50 })
      .then((page) => {
        if (!cancelled) {
          setReports(page.reports);
          setTotal(page.total);
          setListState("ready");
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setListError(error.message);
          setListState("error");
        }
      });

    // Checked once so the upload form can say up front whether the file will be
    // read automatically, rather than the user finding out after uploading.
    fetchExtractionStatus()
      .then((status) => {
        if (!cancelled) setExtraction(status);
      })
      .catch(() => {
        if (!cancelled) setExtraction(null);
      });

    return () => {
      cancelled = true;
    };
  }, [signedIn]);

  async function handleCreate(event) {
    event.preventDefault();

    if (createState === "working") return;

    setCreateState("working");
    setCreateError(null);

    try {
      const { report } = await createReport({ file, title, reportDate, facility });

      // Straight to the review screen: an uploaded report has nothing usable in
      // it yet, and the next step is always the same one.
      navigate(`/reports/${report.id}`);
    } catch (error) {
      setCreateError(error.message);
      setCreateState("idle");
    }
  }

  async function handleDelete(reportId) {
    setDeletingId(reportId);

    try {
      await deleteReport(reportId);

      setReports((current) => current.filter((report) => report.id !== reportId));
      setTotal((current) => Math.max(0, current - 1));
    } catch (error) {
      setListError(error.message);
    } finally {
      setDeletingId(null);
    }
  }

  const automatic = extraction?.available === true;

  return (
    <div className="reports-page">
      <AppNavigation backTo="/dashboard" backLabel="← Dashboard" />

      <main className="reports-main">
        <div className="reports-intro">
          <span className="reports-eyebrow">YOUR REPORTS</span>
          <h1>Add a report, then check what was read from it</h1>
          <p>
            Reports are read automatically to save you typing, but a machine
            reading a scanned document makes mistakes: a misplaced decimal point,
            a value taken from the wrong row. So nothing that is read from your
            report is used anywhere until you have checked it against your own
            copy and confirmed it.
          </p>

          <ol className="reports-steps">
            <li>
              <strong>You add the report.</strong> A PDF or a photo, or you can
              type the values in yourself.
            </li>
            <li>
              <strong>Values are read from it.</strong> These are suggestions,
              shown next to the text they came from.
            </li>
            <li>
              <strong>You check every value.</strong> Correct anything wrong,
              remove anything that should not be there.
            </li>
            <li>
              <strong>You confirm.</strong> Only from this point are the values
              used for your guidance.
            </li>
          </ol>
        </div>

        {listState === "signed-out" ? (
          <p className="reports-empty">Sign in to add and review your reports.</p>
        ) : (
          <>
            <section className="reports-panel">
              <h2>Add a report</h2>

              {extraction && !automatic && (
                <p className="reports-notice">
                  Automatic reading is not set up on this server, so a file you
                  upload will not be read for you. You can still record your
                  values by entering them yourself below.
                  {extraction.reason ? ` (${extraction.reason})` : ""}
                </p>
              )}

              <form className="reports-form" onSubmit={handleCreate}>
                <label className="reports-field">
                  <span>Report file</span>
                  <input
                    type="file"
                    accept=".pdf,.png,.jpg,.jpeg"
                    onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                  />
                  <small>
                    PDF or a clear photo. Leave this empty to type the values in
                    yourself instead.
                  </small>
                </label>

                <div className="reports-field-row">
                  <label className="reports-field">
                    <span>What is it? (optional)</span>
                    <input
                      type="text"
                      value={title}
                      maxLength={160}
                      placeholder="Blood test, annual check-up…"
                      onChange={(event) => setTitle(event.target.value)}
                    />
                  </label>

                  <label className="reports-field">
                    <span>Date on the report (optional)</span>
                    <input
                      type="date"
                      value={reportDate}
                      onChange={(event) => setReportDate(event.target.value)}
                    />
                  </label>
                </div>

                <label className="reports-field">
                  <span>Clinic or laboratory (optional)</span>
                  <input
                    type="text"
                    value={facility}
                    maxLength={120}
                    onChange={(event) => setFacility(event.target.value)}
                  />
                </label>

                {createError && <p className="reports-error">{createError}</p>}

                <div className="reports-actions">
                  <button
                    type="submit"
                    className="assess-btn assess-btn--primary"
                    disabled={createState === "working"}
                  >
                    {createState === "working"
                      ? "Working…"
                      : file
                        ? "Upload and continue"
                        : "Enter values by hand"}
                  </button>
                </div>
              </form>
            </section>

            <section className="reports-list-section">
              <h2>
                Your reports
                {total > 0 && <span className="reports-count">{total}</span>}
              </h2>

              {listState === "loading" && (
                <p className="reports-empty reports-loading">Loading your reports…</p>
              )}

              {listState === "error" && (
                <div className="reports-empty">
                  <p>Your reports could not be loaded. {listError}</p>
                  <button
                    type="button"
                    className="assess-btn assess-btn--ghost"
                    onClick={loadReports}
                  >
                    Try again
                  </button>
                </div>
              )}

              {listState === "ready" && reports.length === 0 && (
                <p className="reports-empty">
                  You have not added a report yet. Nothing here is required — the
                  movement checks and your setup answers work without one.
                </p>
              )}

              {reports.length > 0 && (
                <ul className="reports-list">
                  {reports.map((report) => (
                    <li className="report-card" key={report.id}>
                      <div className="report-card__main">
                        <h3>{report.title}</h3>

                        <p className="report-card__meta">
                          {[
                            formatDate(report.reportDate),
                            report.facility,
                            report.source === "manual_entry"
                              ? "entered by hand"
                              : report.file?.extension?.replace(".", "").toUpperCase(),
                          ]
                            .filter(Boolean)
                            .join(" · ")}
                        </p>

                        {report.extractionError && (
                          <p className="report-card__note">
                            {report.extractionError}
                          </p>
                        )}
                      </div>

                      <div className="report-card__state">
                        <ReportStatus report={report} />
                        <ReviewProgress
                          progress={report.progress}
                          status={report.status}
                        />
                      </div>

                      <div className="report-card__actions">
                        <button
                          type="button"
                          className="assess-btn assess-btn--primary"
                          onClick={() => navigate(`/reports/${report.id}`)}
                        >
                          {report.status === "confirmed" ? "View" : "Check values"}
                        </button>

                        <button
                          type="button"
                          className="report-card__delete"
                          disabled={deletingId === report.id}
                          onClick={() => handleDelete(report.id)}
                        >
                          {deletingId === report.id ? "Deleting…" : "Delete"}
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </>
        )}
      </main>
    </div>
  );
}

export default ReportsPage;
