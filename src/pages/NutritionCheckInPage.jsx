/**
 * The Nutrition & Lifestyle check-in.
 *
 * The questions, their prompts, their options and the values those options
 * store all come from the server (GET/PATCH /api/profile/nutrition-check-in),
 * so this screen cannot offer an answer that would be refused later, and a
 * question added on the server appears here without a change to this file. It
 * holds no copy of the questions, their labels or their answers.
 *
 * Saving does not silently rebuild the plan. The check-in says what happens
 * next — these answers are what the nutrition part of the plan is built from —
 * and offers the explicit action, because a plan that changes underneath
 * someone without them asking is exactly the churn this product avoids.
 *
 * Once it is saved, the answers are read back as what was learned: each chosen
 * answer in the person's own words, not as raw values.
 */

import { useCallback, useEffect, useState } from "react";
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
import { fetchNutritionCheckIn, saveNutritionCheckIn } from "../services/profile";
import { safeDisplayValue } from "../services/specialistData.js";
import { runWorkflow } from "../services/workflow";

import "./NutritionCheckInPage.css";

const SAVED_FALLBACK = "Your answers were saved.";

const PERSONAL_NOTE =
  "MoveWell will use this information to personalize your nutrition and lifestyle guidance.";

function hasAnswer(value) {
  return value !== undefined && value !== null && value !== "";
}

function sameAnswer(left, right) {
  return hasAnswer(left) && hasAnswer(right) && String(left) === String(right);
}

/** The words for a stored answer, or null when it matches no option offered. */
function answeredLabel(question, value) {
  const option = (question.options || []).find((entry) =>
    sameAnswer(entry.value, value),
  );

  return option ? safeDisplayValue(option.label) : null;
}

function NutritionCheckInPage() {
  const navigate = useNavigate();

  const [checkIn, setCheckIn] = useState(null);
  const [answers, setAnswers] = useState({});
  const [savedAnswers, setSavedAnswers] = useState({});
  const [state, setState] = useState("loading");
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [savedMessage, setSavedMessage] = useState(null);
  const [rebuilding, setRebuilding] = useState(false);
  const [rebuildNote, setRebuildNote] = useState(null);

  const signedIn = Boolean(getToken());

  const load = useCallback(async () => {
    setState("loading");
    setError(null);

    try {
      const data = await fetchNutritionCheckIn();

      setCheckIn(data);
      setAnswers(data.answers || {});
      setSavedAnswers(data.answers || {});
      setSavedMessage(null);
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

  const questions = checkIn?.questions || [];
  const total = checkIn?.questionCount ?? questions.length;

  const answeredCount = questions.filter((question) =>
    hasAnswer(answers[question.key]),
  ).length;

  // What was saved, read back in the words of the option that was chosen.
  const learned = questions
    .map((question) => ({
      question,
      label: answeredLabel(question, savedAnswers[question.key]),
    }))
    .filter((row) => row.label);

  async function save() {
    setSaving(true);
    setError(null);

    try {
      const data = await saveNutritionCheckIn(answers);

      setCheckIn(data);
      setAnswers(data.answers || {});
      setSavedAnswers(data.answers || {});
      setSavedMessage(safeDisplayValue(data.message) || SAVED_FALLBACK);
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setSaving(false);
    }
  }

  async function updatePlanNow() {
    setRebuilding(true);
    setRebuildNote(null);

    try {
      await runWorkflow();
      setRebuildNote({
        tone: "success",
        text: "Your plan was prepared with this check-in.",
      });
    } catch (rebuildError) {
      setRebuildNote({ tone: "error", text: rebuildError.message });
    } finally {
      setRebuilding(false);
    }
  }

  return (
    <AppShell>
      <div className="mw-main mw-main--narrow mw-stack">
        <PageHeader
          eyebrow="Nutrition check-in"
          title="Let's understand your nutrition"
          lead="These questions are what let the nutrition part of your plan be built from your own answers, instead of staying “not assessed”."
        />

        {state === "loading" ? (
          <p className="mw-loading">Loading your questions…</p>
        ) : null}

        {state === "error" ? (
          <EmptyState
            title="We couldn’t load your questions"
            why={safeDisplayValue(error)}
            action={<PrimaryButton onClick={load}>Try again</PrimaryButton>}
          />
        ) : null}

        {state === "ready" ? (
          questions.length === 0 ? (
            <EmptyState
              title="There is nothing to answer yet"
              why="The check-in has no questions to show right now, so there is nothing to fill in."
              action={<PrimaryButton onClick={load}>Try again</PrimaryButton>}
            />
          ) : (
            <>
              <p className="mw-chip" role="status">
                {`${answeredCount} of ${total} answered`}
              </p>

              <div className="mw-stack">
                {questions.map((question) => {
                  const current = answers[question.key];
                  const chosen = hasAnswer(current);

                  return (
                    <section
                      className="mw-card mw-section"
                      key={question.key}
                      aria-label={safeDisplayValue(question.label) || undefined}
                    >
                      <SectionHeader
                        title={question.label}
                        action={
                          <StatusBadge
                            label={chosen ? "Answered" : "Not answered"}
                            tone={chosen ? "active" : "muted"}
                          />
                        }
                      />

                      <p className="mw-lede">{safeDisplayValue(question.prompt)}</p>

                      {question.preference ? (
                        <p className="mw-help">
                          A goal is not a finding about your diet — MoveWell uses
                          this as the direction you have asked for, never as
                          evidence about what you eat.
                        </p>
                      ) : null}

                      <div
                        className="checkin-options"
                        role="group"
                        aria-label={safeDisplayValue(question.label) || undefined}
                      >
                        {(question.options || []).map((option) => {
                          const selected = sameAnswer(current, option.value);

                          return (
                            <button
                              key={String(option.value)}
                              type="button"
                              className={`mw-btn checkin-option${
                                selected ? " checkin-option--selected" : ""
                              }`}
                              aria-pressed={selected}
                              onClick={() =>
                                setAnswers((previous) => ({
                                  ...previous,
                                  [question.key]: option.value,
                                }))
                              }
                            >
                              {safeDisplayValue(option.label)}
                            </button>
                          );
                        })}
                      </div>
                    </section>
                  );
                })}
              </div>

              <div className="mw-row checkin-actions">
                <PrimaryButton
                  onClick={save}
                  disabled={saving || answeredCount === 0}
                >
                  {saving ? "Saving…" : "Save my answers"}
                </PrimaryButton>
                <Link className="mw-btn mw-btn--ghost" to="/plan">
                  Back to your plan
                </Link>
              </div>

              {error ? (
                <p className="mw-error" role="alert">
                  {safeDisplayValue(error)}
                </p>
              ) : null}

              {savedMessage ? (
                <p className="mw-success" role="status">
                  {savedMessage}
                </p>
              ) : null}

              {learned.length > 0 ? (
                <section
                  className="mw-card mw-card--tint mw-section"
                  aria-label="Your nutrition profile"
                >
                  <span className="mw-eyebrow">Your nutrition profile</span>

                  <div className="checkin-summary">
                    {learned.map((row) => (
                      <Field
                        key={row.question.key}
                        label={row.question.label}
                        value={row.label}
                      />
                    ))}
                  </div>

                  <p className="mw-lede">{PERSONAL_NOTE}</p>

                  <div className="mw-row checkin-actions">
                    <Link className="mw-btn mw-btn--primary" to="/plan">
                      Continue
                    </Link>
                    <PrimaryButton
                      variant="ghost"
                      onClick={updatePlanNow}
                      disabled={rebuilding}
                    >
                      {rebuilding ? "Preparing…" : "Update my plan now"}
                    </PrimaryButton>
                  </div>

                  <p className="mw-meta">
                    Your plan is only prepared when you ask for it. Nothing in it
                    changes on its own.
                  </p>

                  {rebuildNote ? (
                    <p
                      className={
                        rebuildNote.tone === "error" ? "mw-error" : "mw-success"
                      }
                      role="status"
                    >
                      {safeDisplayValue(rebuildNote.text)}
                    </p>
                  ) : null}

                  <DetailDrawer label="How these answers are used">
                    <p className="mw-lede">
                      Your answers are stored with your information and are read
                      when a plan is prepared, so the nutrition guidance
                      describes what you actually do. Answering a question in a
                      new way here changes what the next plan is built from
                      without changing anything you have already been given.
                    </p>
                  </DetailDrawer>
                </section>
              ) : null}
            </>
          )
        ) : null}
      </div>
    </AppShell>
  );
}

export default NutritionCheckInPage;
