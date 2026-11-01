/**
 * The steps of the assessment flow that do not involve measurement:
 * the introduction, the safety and scope notice, and the chair setup question.
 */

import { useState } from "react";

import { BALANCE, SHOULDER } from "../config/protocol.js";

export function IntroStep({ onContinue, onExit }) {
  return (
    <div className="assess-card">
      <span className="assess-card__eyebrow">Movement check</span>
      <h1>Two short movement checks</h1>

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
              Measures two things: how far your arms move out to the side and how
              long you can stand on one leg.
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
            <li>Somewhere steady to hold on to during the one-leg stand.</li>
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

