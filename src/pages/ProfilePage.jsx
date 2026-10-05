/**
 * YOU — the person's own information.
 *
 * Four sections can be changed here (basic information, body, lifestyle, goals
 * and preferences), each on its own, each saving only the fields that actually
 * changed. The section list, the labels, the options and the allowed ranges all
 * come from the server (GET /api/profile), so this screen can only offer what
 * the server will accept and the server can only receive what this screen could
 * have produced. Nothing about the person is cached in the browser.
 *
 * Two things this page deliberately does not do.
 *
 * It does not regenerate the plan. A profile change is input for the *next*
 * plan review, and the confirmation says exactly that instead of implying the
 * plan moved underneath the person; the plan has its own explicit action.
 *
 * It does not show or edit the self-reported health answers. Those are given
 * during setup and the safety review reads them directly, and the server
 * deliberately does not send them here. Rather than a blank space, the card
 * that stands in their place says plainly where they live and what reads them.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import AppShell from "../components/ui/AppShell.jsx";
import {
  DetailDrawer,
  EmptyState,
  Field,
  PageHeader,
  PrimaryButton,
  SectionHeader,
  StatusBadge,
} from "../components/ui/primitives.jsx";
import { getToken } from "../services/auth";
import { fetchProfile, updateProfile } from "../services/profile";
import { safeDisplayValue } from "../services/specialistData.js";

import "./ProfilePage.css";

// The server's own wording for a successful save. Used only if a response ever
// arrives without its message; the phrase is also the promise this page makes
// about when a change takes effect.
const SAVED_MESSAGE =
  "Your profile was updated. Future plan reviews will use the new information.";

// The profile response reports *which* check-in questions are unanswered, not
// how many there are. The check-in is defined with six questions on the server,
// so the total is named once, here, for the sentence that says what is left.
const CHECK_IN_QUESTIONS = 6;

const NOT_ANSWERED = "Not answered";

function formatDisplayValue(field, value) {
  if (value === null || value === undefined || value === "") return NOT_ANSWERED;

  if (field.kind === "select") {
    const option = (field.options || []).find((entry) => entry.value === value);

    // A stored value this build no longer recognises is shown as unanswered
    // rather than as a stored token the person never chose.
    return option ? safeDisplayValue(option.label) : NOT_ANSWERED;
  }

  if (field.kind === "number") {
    return field.unit ? `${value} ${safeDisplayValue(field.unit)}` : String(value);
  }

  return String(value);
}

function formatUpdatedAt(value) {
  if (!value) return null;

  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) return null;

  return parsed.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function escapeForPattern(text) {
  return String(text).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * The server names the field it refused ("height_cm must be between 90 and
 * 250"). That is the right sentence to show, but the key is internal, so it is
 * swapped for the words the person actually sees on the input beside it.
 */
function readableError(message, section) {
  const text =
    safeDisplayValue(message) ||
    "Your changes could not be saved. Please check the values above and try again.";

  let readable = String(text);

  for (const field of section.fields || []) {
    if (!field.key) continue;

    const label = safeDisplayValue(field.label);

    if (!label) continue;

    readable = readable.replace(
      new RegExp(`\\b${escapeForPattern(field.key)}\\b`, "g"),
      label,
    );
  }

  return readable;
}

/** One editable field, rendered from the descriptor the server sent. */
function FieldEditor({ field, value, disabled, onChange }) {
  const id = `you-${field.key}`;
  const label = safeDisplayValue(field.label);

  function renderControl() {
    if (field.kind === "select") {
      return (
        <select
          id={id}
          className="mw-input"
          value={value ?? ""}
          disabled={disabled}
          onChange={(event) => onChange(field.key, event.target.value)}
        >
          <option value="">Not answered</option>
          {(field.options || []).map((option) => (
            <option key={String(option.value)} value={option.value}>
              {safeDisplayValue(option.label)}
            </option>
          ))}
        </select>
      );
    }

    if (field.kind === "number") {
      return (
        <div className="you-number">
          <input
            id={id}
            className="mw-input"
            type="number"
            inputMode="decimal"
            min={field.min}
            max={field.max}
            step={field.step ?? (field.integer ? 1 : "any")}
            value={value ?? ""}
            disabled={disabled}
            onChange={(event) => onChange(field.key, event.target.value)}
          />
          {field.unit ? (
            <span className="you-unit">{safeDisplayValue(field.unit)}</span>
          ) : null}
        </div>
      );
    }

    return (
      <input
        id={id}
        className="mw-input"
        type="text"
        maxLength={field.max_length}
        value={value ?? ""}
        disabled={disabled}
        onChange={(event) => onChange(field.key, event.target.value)}
      />
    );
  }

  return (
    <div className="mw-field you-field">
      <label className="mw-label" htmlFor={id}>
        {label}
      </label>
      {renderControl()}
      {field.help ? (
        <p className="mw-help">{safeDisplayValue(field.help)}</p>
      ) : null}
    </div>
  );
}

/** One server section: its fields, and the two states it can be in. */
function SectionCard({
  section,
  values,
  draft,
  editing,
  saving,
  dirty,
  error,
  savedMessage,
  derived = null,
  onStart,
  onCancel,
  onChange,
  onSave,
}) {
  return (
    <section
      className="mw-card mw-section"
      aria-label={safeDisplayValue(section.title) || undefined}
    >
      <SectionHeader
        title={section.title}
        hint={section.note}
        action={
          editing ? (
            <div className="mw-row">
              <PrimaryButton variant="ghost" onClick={onCancel} disabled={saving}>
                Cancel
              </PrimaryButton>
              <PrimaryButton onClick={onSave} disabled={saving || !dirty}>
                {saving ? "Saving…" : "Save changes"}
              </PrimaryButton>
            </div>
          ) : (
            <PrimaryButton variant="ghost" onClick={onStart}>
              Edit
            </PrimaryButton>
          )
        }
      />

      <div className="you-fields">
        {(section.fields || []).map((field) =>
          editing ? (
            <FieldEditor
              key={field.key}
              field={field}
              value={draft[field.key]}
              disabled={saving}
              onChange={onChange}
            />
          ) : (
            <Field
              key={field.key}
              label={field.label}
              value={formatDisplayValue(field, values[field.key])}
            />
          ),
        )}

        {derived}
      </div>

      {error ? (
        <p className="mw-error" role="alert">
          {error}
        </p>
      ) : null}

      {savedMessage ? (
        <div className="you-saved">
          <p className="mw-success" role="status">
            {savedMessage}
          </p>
          <p className="mw-meta">
            Nothing in your plan changes on its own — this is used the next time
            you ask for one.{" "}
            <Link className="mw-section-link" to="/plan">
              See your plan
            </Link>
          </p>
        </div>
      ) : null}
    </section>
  );
}

function ProfilePage() {
  const navigate = useNavigate();

  const [profile, setProfile] = useState(null);
  const [values, setValues] = useState({});
  const [editingKey, setEditingKey] = useState(null);
  const [draft, setDraft] = useState({});
  const [saving, setSaving] = useState(false);
  const [sectionError, setSectionError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [state, setState] = useState("loading");
  const [error, setError] = useState(null);

  const signedIn = Boolean(getToken());

  const load = useCallback(async () => {
    setState("loading");
    setError(null);

    try {
      const data = await fetchProfile();

      setProfile(data);
      setValues(flattenValues(data.sections));
      setEditingKey(null);
      setDraft({});
      setNotice(null);
      setSectionError(null);
      setState("ready");
    } catch (loadError) {
      setError(loadError.message);
      setState("error");
    }
  }, []);

  useEffect(() => {
    if (!signedIn) {
      navigate("/login", { replace: true });

      return;
    }

    load();
  }, [signedIn, navigate, load]);

  const sections = useMemo(() => profile?.sections || [], [profile]);

  const editingSection = sections.find((section) => section.key === editingKey) || null;

  const dirty = useMemo(() => {
    if (!editingSection) return false;

    return (editingSection.fields || []).some(
      (field) =>
        String(values[field.key] ?? "") !== String(draft[field.key] ?? ""),
    );
  }, [editingSection, values, draft]);

  function startEditing(section) {
    const start = {};

    for (const field of section.fields || []) {
      start[field.key] = values[field.key] ?? "";
    }

    setDraft(start);
    setEditingKey(section.key);
    setSectionError(null);
    setNotice(null);
  }

  function cancelEditing() {
    setEditingKey(null);
    setDraft({});
    setSectionError(null);
  }

  async function saveSection(section) {
    // Only what actually changed is sent, so a save from one section cannot
    // touch another — and the request carries no value the person did not edit.
    const changes = {};

    for (const field of section.fields || []) {
      const before = values[field.key] ?? "";
      const after = draft[field.key] ?? "";

      if (String(before) !== String(after)) {
        changes[field.key] = after === "" ? null : after;
      }
    }

    if (!Object.keys(changes).length) {
      cancelEditing();
      return;
    }

    setSaving(true);
    setSectionError(null);
    setNotice(null);

    try {
      const data = await updateProfile(changes);

      // The response carries the fresh sections, so the screen is re-rendered
      // from what was stored rather than from what was typed.
      setProfile(data);
      setValues(flattenValues(data.sections));
      setEditingKey(null);
      setDraft({});
      setNotice({
        key: section.key,
        message: safeDisplayValue(data.message) || SAVED_MESSAGE,
      });
    } catch (saveError) {
      setSectionError({
        key: section.key,
        message: readableError(saveError.message, section),
      });
    } finally {
      setSaving(false);
    }
  }

  const updatedAt = formatUpdatedAt(profile?.updatedAt);
  const complete = Boolean(profile?.complete);

  const checkIn = profile?.nutritionCheckIn || null;
  const checkInComplete = Boolean(checkIn?.complete);
  const unanswered = Array.isArray(checkIn?.unanswered) ? checkIn.unanswered.length : null;

  const bmiKnown = profile?.bmi !== null && profile?.bmi !== undefined;

  return (
    <AppShell>
      <div className="mw-main mw-main--narrow mw-stack">
        <PageHeader
          title="You"
          lead="Your information helps MoveWell personalize your experience."
        >
          {updatedAt ? (
            <p className="mw-meta">Last updated {updatedAt}</p>
          ) : null}
        </PageHeader>

        {state === "loading" ? (
          <p className="mw-loading">Loading your information…</p>
        ) : null}

        {state === "error" ? (
          <EmptyState
            title="We couldn’t load your information"
            why={safeDisplayValue(error)}
            action={<PrimaryButton onClick={load}>Try again</PrimaryButton>}
          />
        ) : null}

        {state === "ready" ? (
          <>
            {!complete ? (
              <EmptyState
                title="Finish your setup first"
                why="There is nothing to show or change yet, because MoveWell has no information about you. The setup questions take a couple of minutes."
                action={
                  <PrimaryButton onClick={() => navigate("/onboarding")}>
                    Complete setup
                  </PrimaryButton>
                }
              />
            ) : null}

            {complete
              ? sections.map((section) => (
                  <SectionCard
                    key={section.key}
                    section={section}
                    values={values}
                    draft={draft}
                    editing={editingKey === section.key}
                    saving={saving && editingKey === section.key}
                    dirty={dirty}
                    error={
                      sectionError?.key === section.key
                        ? sectionError.message
                        : null
                    }
                    savedMessage={
                      notice?.key === section.key ? notice.message : null
                    }
                    derived={
                      section.key === "body" ? (
                        <div className="you-derived">
                          <Field
                            label="BMI"
                            value={bmiKnown ? String(profile.bmi) : "Not worked out yet"}
                          />
                          <p className="mw-help">
                            Worked out from your height and weight, so it follows
                            both of them. It is not something you enter.
                          </p>
                        </div>
                      ) : null
                    }
                    onStart={() => startEditing(section)}
                    onCancel={cancelEditing}
                    onChange={(fieldKey, value) =>
                      setDraft((previous) => ({ ...previous, [fieldKey]: value }))
                    }
                    onSave={() => saveSection(section)}
                  />
                ))
              : null}

            {/* Health information is not editable here and is not sent to this
                page, so this card explains where it lives instead of showing a
                field the server would refuse. It never shows a health value. */}
            <section className="mw-card mw-section" aria-label="Health information">
              <SectionHeader title="Health information" />
              <p className="mw-lede">
                The health questions — conditions, previous injuries and pain —
                are answered during setup. The safety review reads them before
                anything is recommended to you, which is why they are handled
                there rather than here.
              </p>
              <DetailDrawer label="Why they are not changed here">
                <p className="mw-lede">
                  Your medical history is a decision about your care, not a
                  profile setting, so MoveWell keeps those answers where you gave
                  them and reads them from there. This page does not show them
                  back to you and cannot change them, and nothing on this page
                  repeats or replaces them.
                </p>
              </DetailDrawer>
              <div className="mw-row">
                <Link className="mw-btn" to="/onboarding">
                  Review or redo your setup answers
                </Link>
                <Link className="mw-btn mw-btn--ghost" to="/reports">
                  Medical reports
                </Link>
              </div>
            </section>

            <section className="mw-card mw-section" aria-label="Medical reports">
              <SectionHeader title="Medical reports" />
              <p className="mw-lede">
                Reports you add are read with your health answers, so the safety
                review works from what your own clinician recorded.
              </p>
              <div className="mw-row">
                <Link className="mw-btn" to="/reports">
                  Add or review a medical report
                </Link>
              </div>
            </section>

            <section className="mw-card mw-section" aria-label="Past sessions">
              <SectionHeader title="Past sessions" />
              <p className="mw-lede">
                Your recorded sessions, with what was measured each time and how
                it compares.
              </p>
              <div className="mw-row">
                <Link className="mw-btn" to="/history">
                  View past sessions
                </Link>
              </div>
            </section>

            <section
              className="mw-card mw-section"
              aria-label="Nutrition and lifestyle check-in"
            >
              <SectionHeader
                title="Nutrition & lifestyle check-in"
                action={
                  <StatusBadge
                    label={checkInComplete ? "Complete" : "Not complete"}
                    tone={checkInComplete ? "active" : "warn"}
                  />
                }
              />

              {checkInComplete ? (
                <p className="mw-lede">
                  All {CHECK_IN_QUESTIONS} questions are answered. Your answers
                  are what the nutrition part of your plan is built from, and
                  they are used the next time your plan is prepared.
                </p>
              ) : (
                <p className="mw-lede">
                  {unanswered == null
                    ? "Some questions are still unanswered."
                    : unanswered === 1
                      ? `1 of ${CHECK_IN_QUESTIONS} questions is still unanswered.`
                      : `${unanswered} of ${CHECK_IN_QUESTIONS} questions are still unanswered.`}{" "}
                  Until they are answered, the nutrition part of your plan stays
                  “not assessed”, because there is nothing yet for it to be built
                  from.
                </p>
              )}

              <div className="mw-row">
                <Link className="mw-btn mw-btn--primary" to="/nutrition-check-in">
                  {checkInComplete ? "Review your answers" : "Complete check-in"}
                </Link>
                <Link className="mw-btn mw-btn--ghost" to="/plan">
                  See your plan
                </Link>
              </div>
            </section>
          </>
        ) : null}
      </div>
    </AppShell>
  );
}

function flattenValues(sections) {
  const flat = {};

  for (const section of sections || []) {
    for (const field of section.fields || []) {
      flat[field.key] = field.value ?? "";
    }
  }

  return flat;
}

export default ProfilePage;
