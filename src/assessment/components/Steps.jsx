/**
 * The steps of the assessment flow that do not involve measurement:
 * the introduction, the safety and scope notice, and the chair setup question.
 */

import { useState } from "react";

import { BALANCE, FTSST, SHOULDER } from "../config/protocol.js";

export function IntroStep({ onContinue, onExit }) {
  return (
    <div className="assess-card">
      <span className="assess-card__eyebrow">Movement check</span>
      <h1>Three short movement checks</h1>

      <p className="assess-card__lead">
        Your camera watches how you move and records a small number of
        measurements. It takes about five minutes.
      </p>

      <div className="assess-card__grid">
        <section>
          <h3>What this does</h3>
          <ul>
            <li>Estimates the position of your body from the camera image.</li>
            <li>
              Measures three things: how far your arms move out to the side, how
              long five sit-to-stands take, and how long you can stand on one leg.
            </li>
            <li>Records those numbers, and how good the recording conditions were.</li>
          </ul>
        </section>

        <section>
          <h3>What this does not do</h3>
          <ul>
            <li>It is not a clinical measurement and not a medical test.</li>
            <li>
              It cannot measure clinical range of motion, muscle strength, bone or
              joint health, or anything happening inside your body.
            </li>
            <li>It does not diagnose any condition and does not produce a score.</li>
          </ul>
        </section>

        <section>
          <h3>Your privacy</h3>
          <ul>
            <li>Everything the camera sees is processed on your own device.</li>
            <li>No video, image, or single frame is ever uploaded or saved.</li>
            <li>Only the final numbers from each check are kept.</li>
          </ul>
        </section>

        <section>
          <h3>What you will need</h3>
          <ul>
            <li>Space to stand with your whole body in the frame.</li>
            <li>A stable chair without wheels for the second check.</li>
            <li>Somewhere steady to hold on to for the third check.</li>
          </ul>
        </section>
      </div>

      <div className="assess-card__actions">
        <button type="button" className="assess-btn assess-btn--ghost" onClick={onExit}>
          Not now
        </button>
        <button type="button" className="assess-btn assess-btn--primary" onClick={onContinue}>
          Continue
        </button>
      </div>
    </div>
  );
}

export function SafetyStep({ onAccept, onExit }) {
  const [acknowledged, setAcknowledged] = useState(false);

  return (
    <div className="assess-card">
      <span className="assess-card__eyebrow">Before you start</span>
      <h1>Safety and scope</h1>

      <div className="assess-card__notice">
        <p>
          Move only as far as is comfortable. Stop immediately if you feel pain,
          dizziness, or that you might lose your balance. You can skip any check,
          and skipping one does not affect the others.
        </p>
        <p>
          Do not attempt these movements if you have been advised not to exercise,
          if you are recovering from an injury or surgery affecting the movements,
          or if you feel unwell today.
        </p>
      </div>

      <h3>What these checks are for</h3>
      <p>
        They give you a record of how you moved on a particular day, under
        conditions that were not controlled: your camera, your lighting, your
        clothing, your floor, and where you stood all affect the numbers. That
        makes them useful for noticing change over time in the same setup, and not
        useful as a measurement of your health.
      </p>

      <h3>What happens next</h3>
      <ol>
        <li>
          Arm movement, facing the camera: {SHOULDER.requiredRepetitions} repetitions
          on each side.
        </li>
        <li>
          Sit to stand, side-on to the camera: {FTSST.requiredRepetitions} stands,
          timed automatically.
        </li>
        <li>
          Standing on one leg, facing the camera: up to{" "}
          {BALANCE.maxDurationMs / 1000} seconds per leg, eyes open.
        </li>
      </ol>

      <p className="assess-card__caveat">
        If anything the checks record concerns you, that is a reason to talk to a
        qualified health professional — not a finding in itself.
      </p>

      <label className="assess-check">
        <input
          type="checkbox"
          checked={acknowledged}
          onChange={(event) => setAcknowledged(event.target.checked)}
        />
        <span>
          I have read this, I will stop if I feel unsafe, and I understand these
          checks are not a medical assessment.
        </span>
      </label>

      <div className="assess-card__actions">
        <button type="button" className="assess-btn assess-btn--ghost" onClick={onExit}>
          Go back
        </button>
        <button
          type="button"
          className="assess-btn assess-btn--primary"
          disabled={!acknowledged}
          onClick={onAccept}
        >
          Turn on my camera
        </button>
      </div>
    </div>
  );
}

export function ChairSetupStep({ onContinue, onSkip }) {
  const [value, setValue] = useState("");

  const parsed = value.trim() === "" ? null : Number(value);
  const isNumber = typeof parsed === "number" && Number.isFinite(parsed);
  const outOfRange =
    isNumber && (parsed < FTSST.chairHeightMinCm || parsed > FTSST.chairHeightMaxCm);

  return (
    <div className="assess-panel">
      <span className="assess-panel__step">Check 2 of 3 · setup</span>
      <h2>How high is the chair seat?</h2>

      <p>
        Measure from the floor to the top of the seat. Seat height changes how hard
        standing up is, so this is recorded alongside the result. Two sessions can
        only be compared if the chair was the same.
      </p>

      <label className="assess-field">
        <span>Seat height in centimetres (optional)</span>
        <input
          type="number"
          inputMode="decimal"
          min="10"
          max="120"
          step="0.5"
          value={value}
          placeholder="e.g. 45"
          onChange={(event) => setValue(event.target.value)}
        />
      </label>

      {outOfRange && (
        <p className="assess-panel__warning">
          That is outside the usual range of {FTSST.chairHeightMinCm}–
          {FTSST.chairHeightMaxCm} cm. You can continue, and it will be recorded
          exactly as entered with a note that it looks unusual.
        </p>
      )}

      {!isNumber && value.trim() !== "" && (
        <p className="assess-panel__warning">Enter a number, or leave this blank.</p>
      )}

      <p className="assess-panel__caveat">
        If you leave this blank it is stored as not provided. It is never guessed.
      </p>

      <div className="assess-panel__actions">
        <button type="button" className="assess-btn assess-btn--ghost" onClick={onSkip}>
          Skip this check
        </button>
        <button
          type="button"
          className="assess-btn assess-btn--primary"
          onClick={() => onContinue(isNumber ? parsed : null)}
        >
          Continue to Sit-to-Stand →
        </button>
      </div>
    </div>
  );
}
