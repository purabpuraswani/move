/**
 * Checking what was read from one report, and confirming it.
 *
 * This screen is the trust boundary. To the left of it is a machine's reading of
 * a document; to the right is what the person who owns the document says it
 * actually says. The design follows from that:
 *
 * Every value shows what was read and where it was read from, so the user is
 * checking against evidence rather than being asked to trust a number.
 *
 * The candidate stays visible after a correction. Overwriting it would hide the
 * fact that the machine got it wrong, which is exactly the information worth
 * keeping.
 *
 * Confirming is a separate, labelled action, and it is refused until every value
 * has been dealt with. Saving progress does not confirm anything.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import {
  confirmReport,
  extractReport,
  fetchFieldCategories,
  fetchReport,
  reopenReport,
  saveReportFields,
} from "../services/reports";
import { getToken } from "../services/auth";

import "./AssessmentPage.css";
import "./ReportsPage.css";

/**
 * The editable copy of one field.
 *
 * A field that has not been reviewed starts from the candidate value, so the
 * user is correcting a suggestion rather than transcribing from scratch. Once
 * reviewed, their own value is what comes back.
 */
function toDraft(field) {
  const reviewed = field.review?.decision !== "pending";

  return {
    key: field.key,
    label: field.label,
    category: field.category,
    value: (reviewed ? field.review?.value : field.candidate?.value) ?? "",
    unit: (reviewed ? field.review?.unit : field.candidate?.unit) ?? "",
    printedReferenceRange:
      (reviewed
        ? field.review?.printedReferenceRange
        : field.candidate?.printedReferenceRange) ?? "",
    include: field.review?.decision !== "rejected",
    isNew: false,
  };
}

function toPayload(draft) {
  return {
    key: draft.key,
    label: draft.label,
    category: draft.category,
    value: draft.value,
    unit: draft.unit,
    printed_reference_range: draft.printedReferenceRange,
    include: draft.include,
  };
}

function slugify(label, existingKeys) {
  const base =
    label
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .slice(0, 56) || "value";

  let key = base;
  let suffix = 2;

  while (existingKeys.has(key)) {
    key = `${base}_${suffix}`;
    suffix += 1;
  }

  return key;
}

/**
 * How legible the transcription was, in words.
 *
 * A raw number invites the reader to treat it as a probability that the value is
 * medically meaningful, which it is not: it describes how clearly the text could
 * be read off the page and nothing else.
 */
function confidenceText(confidence) {
  if (confidence === null || confidence === undefined) return null;

  if (confidence >= 0.9) return "read clearly";
  if (confidence >= 0.7) return "mostly clear";
  if (confidence >= 0.4) return "hard to read — check carefully";

  return "barely legible — check carefully";
}

function CandidateEvidence({ candidate }) {
  const hasAnything =
    candidate?.value || candidate?.quotedText || candidate?.printedReferenceRange;

  if (!hasAnything) {
    return (
      <p className="field-evidence field-evidence--none">
        Nothing was read for this one. You entered it yourself.
      </p>
    );
  }

  const legibility = confidenceText(candidate.confidence);

  return (
    <div className="field-evidence">
      <p className="field-evidence__read">
        Read as{" "}
        <strong>
          {candidate.value}
          {candidate.unit ? ` ${candidate.unit}` : ""}
        </strong>
        {candidate.page ? ` on page ${candidate.page}` : ""}
        {legibility ? ` · ${legibility}` : ""}
      </p>

      {candidate.quotedText && (
        <p className="field-evidence__quote">“{candidate.quotedText}”</p>
      )}

      {candidate.printedReferenceRange && (
        <p className="field-evidence__range">
          Range printed on your report: {candidate.printedReferenceRange}
          <span className="field-evidence__range-note">
            This is copied from your document. It is not a target set by this
            application, and nothing here compares your value against it.
          </span>
        </p>
      )}
    </div>
  );
}

function FieldRow({ draft, field, categories, onChange, onRemoveNew }) {
  const corrected =
    field &&
    draft.include &&
    (draft.value ?? "").trim() !== (field.candidate?.value ?? "").trim();

  return (
    <li className={`field-row${draft.include ? "" : " field-row--excluded"}`}>
      <div className="field-row__head">
        {draft.isNew ? (
          <input
            type="text"
            className="field-row__label-input"
            value={draft.label}
            maxLength={120}
            placeholder="What is this value called?"
            onChange={(event) => onChange({ label: event.target.value })}
          />
        ) : (
          <h3>{draft.label}</h3>
        )}

        <label className="field-row__include">
          <input
            type="checkbox"
            checked={draft.include}
            onChange={(event) => onChange({ include: event.target.checked })}
          />
          <span>Keep this value</span>
        </label>
      </div>

      {field && <CandidateEvidence candidate={field.candidate} />}

      <div className="field-row__inputs">
        <label>
          <span>Value</span>
          <input
            type="text"
            value={draft.value}
            maxLength={500}
            disabled={!draft.include}
            onChange={(event) => onChange({ value: event.target.value })}
          />
        </label>

        <label>
          <span>Unit</span>
          <input
            type="text"
            value={draft.unit}
            maxLength={40}
            disabled={!draft.include}
            placeholder="g/dL"
            onChange={(event) => onChange({ unit: event.target.value })}
          />
        </label>

        <label>
          <span>Range printed on the report</span>
          <input
            type="text"
            value={draft.printedReferenceRange}
            maxLength={120}
            disabled={!draft.include}
            placeholder="optional"
            onChange={(event) =>
              onChange({ printedReferenceRange: event.target.value })
            }
          />
        </label>

        {draft.isNew && (
          <label>
            <span>Type</span>
            <select
              value={draft.category}
              onChange={(event) => onChange({ category: event.target.value })}
            >
              {categories.map((category) => (
                <option key={category.value} value={category.value}>
                  {category.label}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      <div className="field-row__foot">
        {corrected && (
          <span className="field-row__changed">
            Changed from what was read
          </span>
        )}

        {!draft.include && (
          <span className="field-row__excluded-note">
            This value will not be kept or used.
          </span>
        )}

        {draft.isNew && (
          <button
            type="button"
            className="field-row__remove"
            onClick={onRemoveNew}
          >
            Remove this row
          </button>
        )}
      </div>
    </li>
  );
}

function ReportReviewPage() {
  const { reportId } = useParams();
  const navigate = useNavigate();

  const signedIn = Boolean(getToken());

  const [report, setReport] = useState(null);
  const [extraction, setExtraction] = useState(null);
  const [drafts, setDrafts] = useState([]);
  const [categories, setCategories] = useState([]);

  const [loadState, setLoadState] = useState(() => (signedIn ? "loading" : "signed-out"));
  const [loadError, setLoadError] = useState(null);

  const [busy, setBusy] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [savedNote, setSavedNote] = useState(null);

  const applyReport = useCallback((next) => {
    setReport(next);
    setDrafts((next.fields ?? []).map(toDraft));
  }, []);


  useEffect(() => {
    if (!signedIn) {
      return;
    }

    let ignore = false;

    fetchReport(reportId)
      .then(({ report: loaded, extraction: status }) => {
        if (!ignore) {
          applyReport(loaded);
          setExtraction(status);
          setLoadState("ready");
        }
      })
      .catch((error) => {
        if (!ignore) {
          setLoadError(error.message);
          setLoadState("error");
        }
      });

    fetchFieldCategories()
      .then((cats) => {
        if (!ignore) setCategories(cats);
      })
      .catch(() => {
        if (!ignore) setCategories([]);
      });

    return () => {
      ignore = true;
    };
  }, [signedIn, reportId, applyReport]);

  function updateDraft(index, changes) {
    setSavedNote(null);

    setDrafts((current) =>
      current.map((draft, position) =>
        position === index ? { ...draft, ...changes } : draft
      )
    );
  }

  function addField() {
    setSavedNote(null);

    setDrafts((current) => [
      ...current,
      {
        key: slugify("value", new Set(current.map((draft) => draft.key))),
        label: "",
        category: categories[0]?.value ?? "lab_result",
        value: "",
        unit: "",
        printedReferenceRange: "",
        include: true,
        isNew: true,
      },
    ]);
  }

  function removeDraft(index) {
    setDrafts((current) => current.filter((_, position) => position !== index));
  }

  async function runAction(name, work) {
    setBusy(name);
    setActionError(null);
    setSavedNote(null);

    try {
      return await work();
    } catch (error) {
      setActionError(error.message);

      return null;
    } finally {
      setBusy(null);
    }
  }

  async function handleExtract() {
    const updated = await runAction("extract", () => extractReport(reportId));

    if (updated) applyReport(updated);
  }

  function readyToSave() {
    // A row the user added but never named cannot be stored, and the server
    // would reject the whole submission for it, so it is caught here where the
    // message can point at the actual problem.
    const unnamed = drafts.find((draft) => draft.isNew && !draft.label.trim());

    if (unnamed) {
      setActionError("Give every value you added a name, or remove the row.");

      return false;
    }

    return true;
  }

  async function handleSave() {
    if (!readyToSave()) return null;

    const updated = await runAction("save", () =>
      saveReportFields(reportId, drafts.map(toPayload))
    );

    if (updated) {
      applyReport(updated);
      setSavedNote("Your changes were saved. They are not confirmed yet.");
    }

    return updated;
  }

  async function handleSaveAndConfirm() {
    if (!readyToSave()) return;

    const saved = await runAction("confirm", async () => {
      await saveReportFields(reportId, drafts.map(toPayload));

      return confirmReport(reportId);
    });

    if (saved) {
      applyReport(saved);
      setSavedNote("Confirmed. These values can now be used for your guidance.");
    }
  }

  async function handleReopen() {
    const updated = await runAction("reopen", () => reopenReport(reportId));

    if (updated) {
      applyReport(updated);
      setSavedNote("This report is open for editing again.");
    }
  }

  if (loadState === "signed-out") {
    return (
      <div className="reports-page">
        <main className="reports-main">
          <p className="reports-empty">Sign in to see this report.</p>
        </main>
      </div>
    );
  }

  if (loadState === "loading") {
    return (
      <div className="reports-page">
        <main className="reports-main">
          <p className="reports-empty">Loading this report…</p>
        </main>
      </div>
    );
  }

  if (loadState === "error") {
    return (
      <div className="reports-page">
        <main className="reports-main">
          <div className="reports-empty">
            <p>This report could not be loaded. {loadError}</p>
            <button
              type="button"
              className="assess-btn assess-btn--ghost"
              onClick={() => navigate("/reports")}
            >
              Back to reports
            </button>
          </div>
        </main>
      </div>
    );
  }

  const fieldsByKey = new Map((report.fields ?? []).map((field) => [field.key, field]));

  const confirmed = report.isConfirmed;
  const hasFields = drafts.length > 0;
  const canExtract =
    report.source === "upload" && !confirmed && extraction?.available === true;

  return (
    <div className="reports-page">
      <header className="assess-header">
        <button
          type="button"
          className="assess-header__logo"
          onClick={() => navigate("/dashboard")}
        >
          <span className="assess-header__mark">M</span>
          <span>
            MoveWell<small>AI</small>
          </span>
        </button>

        <span className="assess-header__title">{report.title}</span>

        <button
          type="button"
          className="assess-btn assess-btn--quiet"
          onClick={() => navigate("/reports")}
        >
          All reports
        </button>
        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <button
            type="button"
            className="assess-btn assess-btn--quiet"
            onClick={() => navigate("/reports")}
          >
            ← Back to reports
          </button>
          <button
            type="button"
            className="assess-btn assess-btn--quiet"
            onClick={() => navigate("/dashboard")}
            aria-label="Back to Dashboard"
          >
            ← Dashboard
          </button>
        </div>
      </header>

      <main className="reports-main">
        <div
          className={`review-banner${confirmed ? " review-banner--confirmed" : ""}`}
        >
          {confirmed ? (
            <>
              <strong>You confirmed these values.</strong> They can be used for
              your guidance. If anything is wrong, reopen the report and change
              it — the guidance will stop using it straight away.
            </>
          ) : (
            <>
              <strong>Nothing here is being used yet.</strong> These values were
              read from your document and may be wrong. Check each one against
              your own copy, correct anything that does not match, then confirm.
            </>
          )}
        </div>

        {report.extraction?.error && !hasFields && (
          <p className="reports-notice">{report.extraction.error}</p>
        )}

        {report.extraction?.documentNote && hasFields && (
          <p className="reports-notice">
            About the document: {report.extraction.documentNote}
          </p>
        )}

        {report.extraction?.droppedFieldCount > 0 && (
          <p className="reports-notice">
            {report.extraction.droppedFieldCount}{" "}
            {report.extraction.droppedFieldCount === 1 ? "value was" : "values were"}{" "}
            discarded because they came back in a form that could not be stored.
            They are not shown, and nothing was guessed in their place. Add them
            by hand if you need them.
          </p>
        )}

        {!hasFields && (
          <section className="reports-panel">
            <h2>No values yet</h2>

            {report.source === "upload" ? (
              <p>
                {canExtract
                  ? "Your document has been uploaded but not read yet."
                  : "Automatic reading is not available, so this document has not been read."}{" "}
                You can add the values from it yourself, which works exactly the
                same way from here on.
              </p>
            ) : (
              <p>
                Add each value from your report. Everything you enter here comes
                from you, so it starts as your own entry rather than something
                that needs checking.
              </p>
            )}

            <div className="reports-actions">
              {canExtract && (
                <button
                  type="button"
                  className="assess-btn assess-btn--primary"
                  disabled={busy === "extract"}
                  onClick={handleExtract}
                >
                  {busy === "extract" ? "Reading your report…" : "Read my report"}
                </button>
              )}

              <button
                type="button"
                className="assess-btn assess-btn--ghost"
                onClick={addField}
              >
                Add a value by hand
              </button>
            </div>
          </section>
        )}

        {hasFields && (
          <>
            <div className="review-progress-line">
              {confirmed ? (
                <span>
                  {report.progress.included} confirmed
                  {report.progress.rejected > 0 &&
                    `, ${report.progress.rejected} removed`}
                </span>
              ) : (
                <span>
                  {report.progress.total - report.progress.pending} of{" "}
                  {report.progress.total} checked
                  {report.progress.pending > 0 &&
                    ` · ${report.progress.pending} still to check`}
                </span>
              )}
            </div>

            <ol className="field-list">
              {drafts.map((draft, index) => (
                <FieldRow
                  key={draft.key}
                  draft={draft}
                  field={fieldsByKey.get(draft.key)}
                  categories={categories}
                  onChange={(changes) => updateDraft(index, changes)}
                  onRemoveNew={() => removeDraft(index)}
                />
              ))}
            </ol>

            <div className="review-footer">
              <button
                type="button"
                className="assess-btn assess-btn--ghost"
                onClick={addField}
              >
                Add a value that is missing
              </button>

              {canExtract && (
                <button
                  type="button"
                  className="assess-btn assess-btn--ghost"
                  disabled={busy === "extract"}
                  onClick={handleExtract}
                >
                  {busy === "extract" ? "Reading…" : "Read the document again"}
                </button>
              )}
            </div>

            {actionError && <p className="reports-error">{actionError}</p>}
            {savedNote && <p className="reports-saved">{savedNote}</p>}

            {report.confirmBlockedReason && !confirmed && (
              <p className="reports-notice">{report.confirmBlockedReason}</p>
            )}

            <div className="review-actions">
              {confirmed ? (
                <button
                  type="button"
                  className="assess-btn assess-btn--ghost"
                  disabled={busy === "reopen"}
                  onClick={handleReopen}
                >
                  {busy === "reopen" ? "Reopening…" : "Reopen and edit"}
                </button>
              ) : (
                <>
                  <button
                    type="button"
                    className="assess-btn assess-btn--ghost"
                    disabled={busy !== null}
                    onClick={handleSave}
                  >
                    {busy === "save" ? "Saving…" : "Save and finish later"}
                  </button>

                  <button
                    type="button"
                    className="assess-btn assess-btn--primary"
                    disabled={busy !== null}
                    onClick={handleSaveAndConfirm}
                  >
                    {busy === "confirm"
                      ? "Confirming…"
                      : "These match my report — confirm"}
                  </button>
                </>
              )}
            </div>

            {!confirmed && (
              <p className="review-caveat">
                Confirming means the values above match your document. It does not
                mean this application has interpreted them: nothing here decides
                whether a value is normal, and nothing here is a diagnosis.
              </p>
            )}
          </>
        )}
      </main>
    </div>
  );
}

export default ReportReviewPage;
