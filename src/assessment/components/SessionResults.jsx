/**
 * Read-only rendering of one assessment session.
 *
 * Used twice: at the end of a session, and when opening a saved session from
 * the history. Both places must describe a result identically, so the
 * description lives here rather than being written twice.
 *
 * There is no overall score, no rating, and no comparison to any population,
 * because none of those things could be produced honestly from three webcam
 * observations. What is shown is what was measured, what was skipped, what was
 * not usable, and why.
 *
 * The shape accepted here is the same whether the session came from the local
 * assessment run or from the API, because the stored payload and the API
 * response use the same field names on purpose.
 */

import {
  PROTOCOL_VERSION,
  TEST_ORDER,
  TEST_STATUS,
  TEST_TITLES,
} from "../config/protocol.js";
import {
  describeEndReason,
  describeReason,
  getActionableSuggestion,
  formatDegrees,
  formatSeconds,
} from "../utils/labels.js";
import { Measurement, ReasonList, StatusPill } from "./Feedback.jsx";

/**
 * How the recording went, in words a person can act on.
 *
 * This used to print the raw quality figures straight at the user: "72% of
 * frames usable, average tracking confidence 0.42, longest gap 1.2s", and
 * on a failed attempt a list of frames discarded per reason code. Those are
 * real, useful numbers — for a developer. To someone who just tried to
 * stand up out of a chair five times they are an accusation in a language
 * they do not speak, and they are exactly the vocabulary this project has
 * committed to keeping out of the user's way.
 *
 * So the numbers have not been deleted, they have been moved behind
 * `technical`, which is off by default and is what the internal
 * developer/clinician view can switch on. What the user gets instead is the
 * one thing that helps: what to change before trying again, taken from
 * labels.js's own suggestion for the reason that actually dominated.
 */
function QualityNote({ quality, invalid = false, testType = "shoulder", technical = false }) {
  if (!quality) return null;

  // Which check rejected the most frames. This is what decides the advice,
  // and it is never shown as a code or a count.
  const counts = Object.entries(quality.reasonCounts || {})
    .filter(([, count]) => count > 0)
    .sort((a, b) => b[1] - a[1]);

  const dominantReason = counts.length ? counts[0][0] : null;

  if (technical) {
    const parts = [];

    if (typeof quality.fps === "number") {
      parts.push(`${Math.round(quality.fps)} frames per second`);
    }

    if (typeof quality.usableFrameRatio === "number") {
      parts.push(`${Math.round(quality.usableFrameRatio * 100)}% of frames usable`);
    }

    if (typeof quality.meanKeypointScore === "number") {
      parts.push(`mean keypoint score ${quality.meanKeypointScore.toFixed(2)}`);
    }

    if (typeof quality.longestPoseLossMs === "number" && quality.longestPoseLossMs > 0) {
      parts.push(`longest gap ${(quality.longestPoseLossMs / 1000).toFixed(1)}s`);
    }

    return (
      <>
        {parts.length ? (
          <p className="assess-result__quality">Diagnostics: {parts.join(", ")}.</p>
        ) : null}
        {counts.length ? (
          <ul className="assess-result__quality">
            {counts.map(([code, count]) => (
              <li key={code}>
                {describeReason(code)} — {count} frame{count === 1 ? "" : "s"}
              </li>
            ))}
          </ul>
        ) : null}
      </>
    );
  }

  // A usable attempt needs no commentary on the recording at all. Saying
  // "72% of frames were usable" about a result we are about to report as
  // valid only invites doubt about a measurement that is fine.
  if (!invalid) return null;

  return (
    <p className="assess-result__quality">
      {getActionableSuggestion(dominantReason, testType)}
    </p>
  );
}


function ShoulderResult({ result }) {
  if (!result.measurements) return null;

  const { left, right, observableDifferenceDeg } = result.measurements;

  return (
    <>
      <div className="assess-panel__measures">
        <Measurement
          label="Left arm"
          value={formatDegrees(left.finalElevationDeg)}
          note={`${left.repetitionCount} repetitions used`}
        />
        <Measurement
          label="Right arm"
          value={formatDegrees(right.finalElevationDeg)}
          note={`${right.repetitionCount} repetitions used`}
        />
        <Measurement
          label="Difference between sides"
          value={formatDegrees(observableDifferenceDeg)}
        />
      </div>
      <p className="assess-result__definition">
        Angle of the upper arm from vertical as it appeared in the camera image,
        taken as the middle value across repetitions.
      </p>
      <QualityNote
        quality={result.quality}
        invalid={!result.valid}
        testType={result.testType || result.test || "shoulder"}
      />
    </>
  );
}

function FtsstResult({ result }) {
  if (!result.measurements) return null;

  const { completionTimeMs, repetitionsDetected, requiredRepetitions } = result.measurements;
  const setup = result.setup ?? null;

  return (
    <>
      <div className="assess-panel__measures">
        <Measurement label="Time for five stands" value={formatSeconds(completionTimeMs)} />
        <Measurement
          label="Stands detected"
          value={`${repetitionsDetected} of ${requiredRepetitions}`}
        />
        <Measurement
          label="Chair seat height"
          value={
            setup && typeof setup.chairSeatHeightCm === "number"
              ? `${setup.chairSeatHeightCm} cm`
              : "Not provided"
          }
        />
      </div>
      <p className="assess-result__definition">
        Time from leaving the seated position to reaching the fifth stand, detected
        automatically from the knee angle. Not equivalent to a clinician timing the
        movement.
      </p>
      {setup && <ReasonList codes={setup.warnings} title="Setup notes" />}
      <QualityNote
        quality={result.quality}
        invalid={!result.valid}
        testType={result.testType || result.test || "shoulder"}
      />
    </>
  );
}

function BalanceResult({ result }) {
  if (!result.measurements) return null;

  const { left, right, observableDifferenceMs } = result.measurements;

  return (
    <>
      <div className="assess-panel__measures">
        <Measurement
          label="Standing on left leg"
          value={left.attempted ? formatSeconds(left.holdDurationMs) : "Skipped"}
          note={
            left.attempted && left.endReason
              ? `Ended because ${describeEndReason(left.endReason)}`
              : null
          }
        />
        <Measurement
          label="Standing on right leg"
          value={right.attempted ? formatSeconds(right.holdDurationMs) : "Skipped"}
          note={
            right.attempted && right.endReason
              ? `Ended because ${describeEndReason(right.endReason)}`
              : null
          }
        />
        <Measurement
          label="Difference between legs"
          value={
            typeof observableDifferenceMs === "number"
              ? formatSeconds(observableDifferenceMs)
              : "—"
          }
        />
      </div>
      <p className="assess-result__definition">
        Time each position was visibly held, eyes open, up to the maximum for this
        check. A hold that ended because the position was lost is a complete
        measurement.
      </p>
    </>
  );
}

const RESULT_BODIES = {
  shoulder: ShoulderResult,
  ftsst: FtsstResult,
  balance: BalanceResult,
};

function TestResultCard({ testId, result }) {
  const Body = RESULT_BODIES[testId];
  const skipped = result.status === TEST_STATUS.SKIPPED;
  const notStarted = result.status === TEST_STATUS.NOT_STARTED;

  return (
    <section className="assess-result">
      <header className="assess-result__head">
        <h3>{TEST_TITLES[testId]}</h3>
        <StatusPill status={result.status} />
      </header>

      {skipped && (
        <p className="assess-result__empty">
          You skipped this check. Nothing was measured, and this is stored as
          skipped rather than as a result of zero.
        </p>
      )}

      {notStarted && (
        <p className="assess-result__empty">
          This check was not reached. Nothing was measured.
        </p>
      )}

      {!skipped && !notStarted && <Body result={result} />}

      {!skipped && !notStarted && <ReasonList codes={result.invalidReasons} />}
    </section>
  );
}

/** A one-line summary of how many checks recorded something. */
export function SessionSummaryLine({ summary }) {
  return (
    <p className="assess-card__lead">
      {summary.testsCompleted} of 3 checks recorded a usable measurement
      {summary.testsSkipped > 0 && `, ${summary.testsSkipped} skipped`}
      {summary.testsInvalid > 0 && `, ${summary.testsInvalid} not usable`}.
    </p>
  );
}

/** The interpretation boundary, stated wherever results are shown. */
export function HowToReadNotice() {
  return (
    <section className="assess-card__notice">
      <h3>How to read this</h3>
      <p>
        These are observations of how you moved in front of a normal webcam. They
        are not clinical measurements, they are not compared to any reference
        population, and they are not combined into a score, because none of those
        would be honest from this kind of recording.
      </p>
      <p>
        Nothing here identifies or rules out any medical condition. If something
        you see here concerns you, or if you have symptoms, that is a reason to
        speak to a qualified health professional.
      </p>
    </section>
  );
}

export default function SessionResults({ session }) {
  const { tests } = session;

  return (
    <>
      <div className="assess-results">
        {TEST_ORDER.map((testId) => (
          <TestResultCard key={testId} testId={testId} result={tests[testId]} />
        ))}
      </div>

      <HowToReadNotice />

      <p className="assess-card__meta">
        Recorded {new Date(session.startedAt).toLocaleString()} · protocol version{" "}
        {session.protocolVersion ?? PROTOCOL_VERSION}
      </p>
    </>
  );
}
