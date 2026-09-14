import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import MovementSnapshot from "../components/MovementSnapshot";
import {
  buildMovementSnapshot,
  previousCompletedSessions,
} from "../assessment/utils/movementSnapshot";
import {
  fetchAssessment,
  fetchAssessmentHistory,
  fetchLatestAssessment,
} from "../services/assessments";
import { clearSession, fetchMe, getToken } from "../services/auth";
import { fetchProfileSummary } from "../services/profile";
import { fetchReports } from "../services/reports";

import "./Dashboard.css";


function Dashboard() {

  const navigate = useNavigate();

  const [user, setUser] = useState(() => {
    const storedUser = localStorage.getItem("movewell_user");
    if (storedUser) {
      try {
        return JSON.parse(storedUser);
      } catch {
        return null;
      }
    }
    return null;
  });

  const [timeOfDay] = useState(() => {
    const hour = new Date().getHours();
    if (hour < 12) return "morning";
    if (hour < 18) return "afternoon";
    return "evening";
  });

  // The latest real assessment, or null when the user has never done one.
  // Never a placeholder: a user with no assessment has no numbers, and the
  // interface has to say that rather than show zeros.
  const [latest, setLatest] = useState(null);

  const [assessmentCount, setAssessmentCount] = useState(0);

  const [assessmentState, setAssessmentState] = useState("loading");

  const [assessmentError, setAssessmentError] = useState(null);

  // The most recent earlier completed result of each check, for the neutral
  // "Previous result" line. Empty when there is no earlier session.
  // Stored with the id of the latest session they were loaded for, so a
  // result from an older load is never shown against a newer session.
  const [previousResults, setPreviousResults] = useState({
    forSessionId: null,
    byTest: {}
  });

  // The lifestyle answers from onboarding. Self-reported, not measured.
  const [profile, setProfile] = useState(null);

  const [profileComplete, setProfileComplete] = useState(false);

  const [profileState, setProfileState] = useState("loading");


  const [reports, setReports] = useState([]);

  const [reportState, setReportState] = useState("loading");


  // Confirm with the backend who this token belongs to.
  //
  // The name on the screen should come from the account the server recognises,
  // not from a value in localStorage that can go stale or be edited. This also
  // catches an expired token on arrival: rather than letting each card fail its
  // own request, the session is cleared once and the user is asked to sign in.
  useEffect(() => {

    let cancelled = false;


    async function confirmAccount() {

      try {

        const account = await fetchMe();

        if (cancelled) return;

        setUser(account);

        localStorage.setItem(
          "movewell_user",
          JSON.stringify(account)
        );

      } catch {

        if (cancelled) return;

        // Only a rejected token clears the session, and fetchMe has already
        // done that. A network failure leaves the stored copy in place.
        if (!getToken()) {
          navigate("/login", { replace: true });
        }

      }

    }


    confirmAccount();


    return () => {
      cancelled = true;
    };

  }, [navigate]);


  useEffect(() => {

    let cancelled = false;


    async function loadAssessment() {

      try {

        const { assessment, total } =
          await fetchLatestAssessment();

        if (cancelled) return;

        setLatest(assessment);
        setAssessmentCount(total);
        setAssessmentState("ready");

      } catch (error) {

        if (cancelled) return;

        // A failure is shown as a failure. Falling back to zeros here would be
        // indistinguishable from "you scored nothing".
        setAssessmentError(error.message);
        setAssessmentState("error");

      }

    }


    async function loadProfile() {

      try {

        const summary = await fetchProfileSummary();

        if (cancelled) return;

        setProfile(summary.profile);
        setProfileComplete(summary.complete);
        setProfileState("ready");

      } catch {

        if (cancelled) return;

        setProfileState("error");

      }

    }


    async function loadReports() {

      try {

        const page = await fetchReports({ limit: 50 });

        if (cancelled) return;

        setReports(page.reports);
        setReportState("ready");

      } catch {

        if (cancelled) return;

        // The dashboard works without reports, so a failure here is recorded
        // and the panel says so rather than the whole page failing.
        setReportState("error");

      }

    }


    loadAssessment();
    loadProfile();
    loadReports();


    return () => {
      cancelled = true;
    };

  }, []);


  const firstName =
    user?.full_name?.split(" ")[0] ||
    user?.name?.split(" ")[0] ||
    "there";


  const greeting = {

    morning: "Good morning",

    afternoon: "Good afternoon",

    evening: "Good evening"

  }[timeOfDay];


  useEffect(() => {

    if (!latest?.id || assessmentCount < 2) {
      return undefined;
    }

    let ignore = false;

    async function loadPreviousResults() {

      try {

        const { assessments } = await fetchAssessmentHistory({ limit: 20 });

        const picked = previousCompletedSessions(assessments, latest.id);

        const ids = [
          ...new Set(
            Object.values(picked).filter(Boolean).map((entry) => entry.id)
          )
        ];

        const sessions = Object.fromEntries(
          await Promise.all(
            ids.map(async (id) => [id, await fetchAssessment(id)])
          )
        );

        if (ignore) return;

        setPreviousResults({
          forSessionId: latest.id,
          byTest: Object.fromEntries(
            Object.entries(picked)
              .filter(([, entry]) => entry && sessions[entry.id])
              .map(([testId, entry]) => [
                testId,
                {
                  startedAt: sessions[entry.id].startedAt,
                  test: sessions[entry.id].tests?.[testId]
                }
              ])
          )
        });

      } catch {

        // Earlier results are supplementary. If they cannot be loaded the
        // latest results still show, just without a previous value.
        if (!ignore) {
          setPreviousResults({ forSessionId: latest.id, byTest: {} });
        }

      }
    }

    loadPreviousResults();

    return () => {
      ignore = true;
    };

  }, [latest?.id, assessmentCount]);


  const movementSnapshot = useMemo(
    () =>
      buildMovementSnapshot(
        latest,
        latest && previousResults.forSessionId === latest.id
          ? previousResults.byTest
          : {}
      ),
    [latest, previousResults]
  );


  // How many of the three checks recorded a usable measurement. This is a
  // count of completed checks, not a rating of how well anything was done.
  const checksRecorded =
    latest?.summary?.testsCompleted ?? 0;

  const checksRecordedPercent =
    Math.round((checksRecorded / 3) * 100);


  // Confirmed means the user checked the values against their own document and
  // said they match. It is the only status that counts as usable, so it is the
  // only one counted here.
  const confirmedReportCount = reports.filter(
    (report) => report.isConfirmed
  ).length;

  const reportsNeedingReview = reports.filter(
    (report) =>
      report.status === "needs_review" ||
      report.status === "extracted" ||
      report.status === "uploaded"
  ).length;


  function startAssessment() {

    navigate("/assessment");

  }


  function openHistory() {

    navigate("/history");

  }


  function openSession(assessmentId) {

    navigate(
      assessmentId
        ? `/history?session=${encodeURIComponent(assessmentId)}`
        : "/history"
    );

  }


  function handleLogout() {

    // Clears the stored user and the auth token together.
    clearSession();

    navigate("/login");

  }


  return (

    <div className="dashboard">

    {/* Animated wellness background */}
    <div className="ambient-background">
      <div className="ambient-orb orb-one"></div>
      <div className="ambient-orb orb-two"></div>
      <div className="ambient-orb orb-three"></div>
      <div className="ambient-grid"></div>
    </div>

    <div className="dashboard-content">


      {/* ───────────────── NAVBAR ───────────────── */}

      <header className="dashboard-nav">

        <div
          className="dashboard-logo"
          onClick={() => navigate("/dashboard")}
        >

          <div className="logo-mark">
            M
          </div>

          <span>
            MoveWell
            <small>AI</small>
          </span>

        </div>


        <nav className="dashboard-links">

          <button className="nav-link active">
            Dashboard
          </button>

          <button
            className="nav-link"
            onClick={() =>
              navigate("/assessment")
            }
          >
            Assessment
          </button>

          <button
            className="nav-link"
            onClick={() =>
              navigate("/plan")
            }
          >
            My plan
          </button>

          <button
            className="nav-link"
            onClick={() =>
              navigate("/progress")
            }
          >
            My progress
          </button>

          {/* Past assessment sessions. Distinct from "My progress": this is
              the raw record of what was measured, that is what changed in the
              plan because of it. */}
          <button
            className="nav-link"
            onClick={openHistory}
          >
            Past sessions
          </button>

          <button
            className="nav-link"
            onClick={() =>
              navigate("/reports")
            }
          >
            Reports
          </button>

        </nav>


        <div className="nav-right">

          <button className="notification-button">
            <span>⌁</span>
            <i />
          </button>


          <div className="user-menu">

            <div className="avatar">
              {firstName.charAt(0).toUpperCase()}
            </div>

            <div className="user-name">
              <strong>{firstName}</strong>
              <span>My profile</span>
            </div>

          </div>


          <button
            className="logout-button"
            onClick={handleLogout}
          >
            Log out
          </button>

        </div>

      </header>


      {/* ───────────────── MAIN ───────────────── */}

      <main className="dashboard-main">


        {/* Hero */}

        <section className="welcome-section">

          <div>

            <span className="eyebrow">
              YOUR WELLNESS SPACE
            </span>

            <h1>
              {greeting},{" "}
              <span>{firstName}.</span>
            </h1>

            <p>
              Ready to move a little better today?
              Let's take it one step at a time.
            </p>

          </div>


          <div className="date-pill">

            <span className="calendar-icon">
              ◷
            </span>

            {new Date().toLocaleDateString(
              "en-US",
              {
                weekday: "long",
                month: "short",
                day: "numeric"
              }
            )}

          </div>

        </section>


        {/* ───────────────── HERO CARDS ───────────────── */}

        <section className="hero-grid">


          {/* Assessment CTA */}

          <div className="assessment-hero">

            <div className="hero-decoration decoration-one" />
            <div className="hero-decoration decoration-two" />

            <div className="assessment-content">

              <span className="hero-label">
                MOVEWELL ASSESSMENT
              </span>

              <h2>
                Understand how
                <br />
                your body moves.
              </h2>

              <p>
                A quick camera-based movement
                assessment can help you understand
                mobility, balance and movement
                consistency.
              </p>

              <button
                className="primary-button"
                onClick={startAssessment}
              >
                Start assessment

                <span>→</span>
              </button>

            </div>


            <div className="hero-figure">

              <div className="figure-circle">

                <div className="figure-person">

                  <div className="person-head" />

                  <div className="person-body" />

                  <div className="person-arm left" />

                  <div className="person-arm right" />

                  <div className="person-leg left" />

                  <div className="person-leg right" />

                </div>

              </div>

            </div>

          </div>


          {/* Latest movement check */}

          <div className="progress-card">

            <div className="card-top">

              <div>

                <span className="card-label">
                  LATEST MOVEMENT CHECK
                </span>

                <h3>
                  {assessmentState === "loading"
                    ? "Loading…"
                    : latest
                      ? "Checks recorded"
                      : "Nothing recorded yet"}
                </h3>

              </div>

              <div className="sparkle">
                ✦
              </div>

            </div>


            {assessmentState === "error" && (

              <p className="card-empty">
                Your last check could not be loaded.
                {" "}
                {assessmentError}
              </p>

            )}


            {assessmentState !== "error" && (

              <div className="progress-ring">

                <svg
                  viewBox="0 0 120 120"
                >

                  <circle
                    className="ring-background"
                    cx="60"
                    cy="60"
                    r="48"
                  />

                  {latest && (

                    <circle
                      className="ring-progress"
                      cx="60"
                      cy="60"
                      r="48"
                      style={{
                        strokeDashoffset:
                          301 -
                          (301 *
                            checksRecordedPercent) /
                            100
                      }}
                    />

                  )}

                </svg>


                <div className="ring-content">

                  <strong>
                    {latest
                      ? `${checksRecorded}/3`
                      : "—"}
                  </strong>

                  <span>
                    {latest
                      ? "checks recorded"
                      : "no check yet"}
                  </span>

                </div>

              </div>

            )}


            <div className="progress-bottom">

              <span>
                {latest
                  ? new Date(
                      latest.startedAt
                    ).toLocaleDateString(
                      "en-US",
                      {
                        month: "short",
                        day: "numeric"
                      }
                    )
                  : "Not started"}
              </span>

              <span>
                {assessmentCount > 0
                  ? `${assessmentCount} ${
                      assessmentCount === 1
                        ? "session"
                        : "sessions"
                    } saved`
                  : ""}
              </span>

            </div>

          </div>

        </section>


        {/* ───────────────── SNAPSHOT ───────────────── */}

        <section className="snapshot-section">

          <div className="section-heading">

            <div>

              <span className="section-eyebrow">
                YOUR SETUP ANSWERS
              </span>

              <h2>
                Wellness snapshot
              </h2>

            </div>

            <button
              className="text-button"
              onClick={() =>
                navigate("/onboarding")
              }
            >
              Update answers →
            </button>

          </div>


          <p className="section-note">
            These are the answers you gave when you
            set up your account. They are what you
            told us, not activity measured today.
          </p>


          {profileState === "loading" && (

            <p className="card-empty">
              Loading your answers…
            </p>

          )}


          {profileState === "error" && (

            <p className="card-empty">
              Your setup answers could not be loaded
              right now.
            </p>

          )}


          {profileState === "ready" &&
            !profileComplete && (

            <div className="empty-panel">

              <h3>
                You haven't filled this in yet.
              </h3>

              <p>
                Your sitting, sleep, steps and
                exercise answers come from setup.
                Nothing is shown here until you
                provide them.
              </p>

              <button
                className="outline-button"
                onClick={() =>
                  navigate("/onboarding")
                }
              >
                Complete setup
                <span>→</span>
              </button>

            </div>

          )}


          {profileState === "ready" &&
            profileComplete && (

            <div className="stats-grid">


              <StatCard
                icon="🪑"
                title="Sitting"
                value={formatHours(
                  profile?.daily_sitting_hours
                )}
                description="a day"
              />


              <StatCard
                icon="☁"
                title="Sleep"
                value={formatHours(
                  profile?.sleep_hours
                )}
                description="a night"
              />


              <StatCard
                icon="↗"
                title="Steps"
                value={formatCount(
                  profile?.daily_steps
                )}
                description="a day"
              />


              <StatCard
                icon="✦"
                title="Exercise"
                value={formatCount(
                  profile?.exercise_days
                )}
                description="days a week"
              />

            </div>

          )}

        </section>


        {/* ───────────────── LOWER GRID ───────────────── */}

        <section className="lower-grid">


          {/* Latest results: each baseline check shown separately. */}

          <MovementSnapshot
            loadState={assessmentState}
            error={assessmentError}
            snapshot={movementSnapshot}
            onStartAssessment={startAssessment}
            onOpenSession={openSession}
            onOpenHistory={openHistory}
          />


          {/* Medical reports.
              Counts only. A dashboard is a glanceable surface and a lab value
              on one would be both a privacy problem and an invitation to read
              meaning into a number nobody has interpreted. */}

          <div className="reports-summary">

            <div className="section-heading">

              <div>

                <span className="section-eyebrow">
                  MEDICAL REPORTS
                </span>

                <h2>
                  {confirmedReportCount > 0
                    ? `${confirmedReportCount} confirmed`
                    : "Nothing confirmed yet"}
                </h2>

              </div>

            </div>


            <p className="section-note">
              {reportState === "error"
                ? "Your reports could not be loaded just now."
                : confirmedReportCount > 0
                  ? "Values you have checked against your own document and confirmed. Only these are used for your guidance."
                  : "You can add a report and check what is read from it. Nothing from a report is used until you confirm it."}
            </p>


            {reportsNeedingReview > 0 && (

              <p className="reports-summary__pending">
                {reportsNeedingReview}{" "}
                {reportsNeedingReview === 1
                  ? "report is waiting"
                  : "reports are waiting"}{" "}
                for you to check the values.
              </p>

            )}


            <button
              className="text-button"
              onClick={() =>
                navigate("/reports")
              }
            >
              {reports.length > 0
                ? "Open my reports →"
                : "Add a report →"}
            </button>

          </div>


          {/* Specialists */}

          <div id="specialists" className="specialist-card">

            <div className="section-heading">

              <div>

                <span className="section-eyebrow">
                  YOUR AI TEAM
                </span>

                <h2>
                  Meet your specialists
                </h2>

              </div>

            </div>


            <div className="specialist-list">


              {/* What the user's plan can actually cover, described as
                  outcomes rather than as the components that produce them.
                  The specialists behind these are chosen by need, so a given
                  user may not receive all three -- which is why these are
                  worded as areas the plan may include, not as a team roster.

                  This panel previously advertised the legacy Wellness Guide
                  and Care Navigator and sent the user to /guidance. That path
                  is deprecated and is no longer part of the journey. */}

              <Specialist
                emoji="🏃"
                title="Exercise & Physical Activity"
                text="Daily walking volume, steps & sedentary pacing"
                onClick={() => navigate("/specialist/exercise")}
              />

              <Specialist
                emoji="🧑‍⚕️"
                title="Physiotherapy & Movement"
                text="Mobility, balance & corrective exercise matched to checks"
                onClick={() => navigate("/specialist/physio")}
              />

              <Specialist
                emoji="🍎"
                title="Nutrition & Lifestyle"
                text="Balanced dietary quality, hydration & authentic meal logging"
                onClick={() => navigate("/specialist/nutrition")}
              />

              <Specialist
                emoji="🌙"
                title="Recovery & Care"
                text="Rest days, sleep hygiene & fatigue management"
                onClick={() => navigate("/specialist/recovery")}
              />

              <Specialist
                emoji="🧠"
                title="Behaviour & Adherence"
                text="Micro-habits, routine pacing & consistency"
                onClick={() => navigate("/specialist/behaviour")}
              />

              <Specialist
                emoji="🛡️"
                title="Safety & Clinical Escalation"
                text="Clinical gatekeeping & contraindication checks"
                onClick={() => navigate("/specialist/safety")}
              />
            </div>


            <button
              type="button"
              className="specialist-button"
              onClick={() =>
                navigate("/plan")
              }
            >
              See your plan
              <span>→</span>
            </button>

          </div>

        </section>


        {/* ───────────────── DAILY TIP ───────────────── */}

        <section className="tip-card">

          <div className="tip-icon">
            ☀
          </div>

          <div className="tip-content">

            <span>
              TODAY'S LITTLE REMINDER
            </span>

            <h3>
              Your body doesn't need a perfect
              workout. It needs regular movement.
            </h3>

            <p>
              Try standing up and walking around
              for a couple of minutes after your
              next long sitting session.
            </p>

          </div>

          <div className="tip-decoration">
            ✦
          </div>

        </section>


      </main>

    </div>

    </div>
  );
}


/* ───────────────── COMPONENTS ───────────────── */


/** A self-reported number, or an em dash when it was not given. */
function formatHours(value) {

  if (typeof value !== "number") {
    return "—";
  }

  return `${Number.isInteger(value) ? value : value.toFixed(1)}h`;

}


function formatCount(value) {

  if (typeof value !== "number") {
    return "—";
  }

  return value.toLocaleString();

}


function StatCard({
  icon,
  title,
  value,
  description,
  status
}) {

  return (

    <div className="stat-card">

      <div className="stat-icon">
        {icon}
      </div>

      <div className="stat-title">
        {title}
      </div>

      <div className="stat-value">
        {value}
        <span>{description}</span>
      </div>

      {/* Only rendered when there is something factual to say. The previous
          version showed judgements such as "A little high", which this
          application is in no position to make. */}
      {status && (

        <div className="stat-status">
          {status}
        </div>

      )}

    </div>

  );

}


function Specialist({
  emoji,
  title,
  text,
  onClick,
}) {
  return (
    <button
      type="button"
      className="specialist"
      onClick={onClick}
      aria-label={`${title}: ${text}`}
    >
      <div className="specialist-avatar" aria-hidden="true">
        {emoji}
      </div>

      <div className="specialist-info">
        <strong>
          {title}
        </strong>
        <span>
          {text}
        </span>
      </div>

      <span className="specialist-arrow" aria-hidden="true">
        →
      </span>
    </button>
  );
}


export default Dashboard;