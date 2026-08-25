import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import "./Dashboard.css";


function Dashboard() {

  const navigate = useNavigate();

  const [user, setUser] = useState(null);

  const [timeOfDay, setTimeOfDay] = useState("morning");

  const [stats, setStats] = useState({
    sitting: 8.2,
    sleep: 7.1,
    steps: 6240,
    exerciseDays: 3
  });


  useEffect(() => {

    // Get logged-in user
    const storedUser = localStorage.getItem(
      "movewell_user"
    );

    if (storedUser) {

      try {

        setUser(
          JSON.parse(storedUser)
        );

      } catch {

        console.log(
          "Could not read user data"
        );

      }

    }


    // Time-based greeting
    const hour = new Date().getHours();

    if (hour < 12) {

      setTimeOfDay("morning");

    } else if (hour < 18) {

      setTimeOfDay("afternoon");

    } else {

      setTimeOfDay("evening");

    }

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


  const movementProgress = 68;


  function startAssessment() {

    navigate("/assessment");

  }


  function handleLogout() {

    localStorage.removeItem(
      "movewell_user"
    );

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

          <button className="nav-link">
            My progress
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


          {/* Daily progress */}

          <div className="progress-card">

            <div className="card-top">

              <div>

                <span className="card-label">
                  TODAY'S MOVEMENT
                </span>

                <h3>
                  You're doing great.
                </h3>

              </div>

              <div className="sparkle">
                ✦
              </div>

            </div>


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

                <circle
                  className="ring-progress"
                  cx="60"
                  cy="60"
                  r="48"
                  style={{
                    strokeDashoffset:
                      301 -
                      (301 *
                        movementProgress) /
                        100
                  }}
                />

              </svg>


              <div className="ring-content">

                <strong>
                  {movementProgress}%
                </strong>

                <span>
                  complete
                </span>

              </div>

            </div>


            <div className="progress-bottom">

              <span>
                3 of 5 activities
              </span>

              <span>
                Keep going 🌱
              </span>

            </div>

          </div>

        </section>


        {/* ───────────────── SNAPSHOT ───────────────── */}

        <section className="snapshot-section">

          <div className="section-heading">

            <div>

              <span className="section-eyebrow">
                YOUR ROUTINE
              </span>

              <h2>
                Wellness snapshot
              </h2>

            </div>

            <button className="text-button">
              View details →
            </button>

          </div>


          <div className="stats-grid">


            <StatCard
              icon="🪑"
              title="Sitting"
              value={`${stats.sitting}h`}
              description="today"
              status="A little high"
            />


            <StatCard
              icon="☁"
              title="Sleep"
              value={`${stats.sleep}h`}
              description="last night"
              status="Looking good"
            />


            <StatCard
              icon="↗"
              title="Steps"
              value={stats.steps.toLocaleString()}
              description="today"
              status="1.8k to goal"
            />


            <StatCard
              icon="✦"
              title="Exercise"
              value={stats.exerciseDays}
              description="days this week"
              status="Nice streak!"
            />

          </div>

        </section>


        {/* ───────────────── LOWER GRID ───────────────── */}

        <section className="lower-grid">


          {/* Movement score */}

          <div className="score-card">

            <div className="section-heading">

              <div>

                <span className="section-eyebrow">
                  MOVEMENT INSIGHT
                </span>

                <h2>
                  Your MoveWell score
                </h2>

              </div>

              <span className="coming-pill">
                NOT YET
              </span>

            </div>


            <div className="score-content">

              <div className="score-number">
                —
              </div>

              <div className="score-info">

                <h3>
                  Your score is waiting.
                </h3>

                <p>
                  Complete your first movement
                  assessment to see your mobility,
                  stability and movement insights.
                </p>

                <button
                  className="outline-button"
                  onClick={startAssessment}
                >
                  Take assessment
                  <span>→</span>
                </button>

              </div>

            </div>


            <div className="score-bars">

              <ScoreBar
                label="Mobility"
                value={0}
              />

              <ScoreBar
                label="Stability"
                value={0}
              />

              <ScoreBar
                label="Symmetry"
                value={0}
              />

            </div>

          </div>


          {/* Specialists */}

          <div className="specialist-card">

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


              <Specialist
                emoji="🧘"
                title="Yoga guide"
                text="Mobility & mindful movement"
              />


              <Specialist
                emoji="🏃"
                title="Fitness coach"
                text="Strength & daily activity"
              />


              <Specialist
                emoji="🦴"
                title="Physio guide"
                text="Movement & recovery"
              />

            </div>


            <button
              className="specialist-button"
              onClick={() =>
                navigate("/specialists")
              }
            >
              Explore your AI team
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

      <div className="stat-status">
        {status}
      </div>

    </div>

  );

}


function ScoreBar({
  label,
  value
}) {

  return (

    <div className="score-bar">

      <div className="score-bar-header">

        <span>
          {label}
        </span>

        <span>
          {value || "—"}
        </span>

      </div>

      <div className="bar">

        <div
          style={{
            width: `${value}%`
          }}
        />

      </div>

    </div>

  );

}


function Specialist({
  emoji,
  title,
  text
}) {

  return (

    <div className="specialist">

      <div className="specialist-avatar">
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

      <span className="specialist-arrow">
        →
      </span>

    </div>

  );

}


export default Dashboard;