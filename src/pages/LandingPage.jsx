import { Link } from "react-router-dom";
import Navbar from "../components/Navbar";
import "./LandingPage.css";

function LandingPage() {
  return (
    <div className="landing-page">

      <Navbar />

      {/* HERO */}
      <section className="hero">
        <div className="hero-container">

          <div className="hero-content">

            <div className="eyebrow">
              <span className="pulse-dot"></span>
              Movement and lifestyle coaching, in one place
            </div>

            <h1>
              Move smarter.
              <br />
              <span>Live stronger.</span>
            </h1>

            <p className="hero-description">
              Tell MoveWell about yourself, then do three movement checks on
              your own device — an arm and shoulder raise, five sit-to-stands
              and a single-leg stand. Your measurements become one MoveWell
              Score you can follow over time, and one plan of concrete actions
              built by five specialists.
            </p>

            <div className="hero-buttons">
              <Link to="/signup" className="primary-button">
                Start your assessment
                <span>→</span>
              </Link>

              <a href="#how-it-works" className="secondary-button">
                See how it works
              </a>
            </div>

            <div className="hero-trust">
              <div className="trust-item">
                <strong>Three checks</strong>
                <span>on your own device</span>
              </div>

              <div className="trust-divider"></div>

              <div className="trust-item">
                <strong>One score</strong>
                <span>progress over time</span>
              </div>

              <div className="trust-divider"></div>

              <div className="trust-item">
                <strong>Five specialists</strong>
                <span>one plan</span>
              </div>
            </div>

          </div>

          {/* HERO VISUAL */}
          <div className="hero-visual">

            <div className="visual-glow"></div>

            <div className="analysis-card">

              <div className="analysis-header">
                <div>
                  <span className="small-label">MOVEWELL ASSESSMENT</span>
                  <h3>Your movement checks</h3>
                </div>

                <div className="live-indicator">
                  <span></span>
                  Preview
                </div>
              </div>

              <div className="person-area">

                <div className="grid-lines"></div>

                {/* Abstract pose */}
                <div className="pose">

                  <div className="joint head"></div>

                  <div className="bone neck"></div>

                  <div className="bone torso"></div>

                  <div className="bone left-arm"></div>
                  <div className="bone right-arm"></div>

                  <div className="bone left-forearm"></div>
                  <div className="bone right-forearm"></div>

                  <div className="bone left-leg"></div>
                  <div className="bone right-leg"></div>

                  <div className="bone left-shin"></div>
                  <div className="bone right-shin"></div>

                  <div className="joint shoulder-left"></div>
                  <div className="joint shoulder-right"></div>

                  <div className="joint elbow-left"></div>
                  <div className="joint elbow-right"></div>

                  <div className="joint wrist-left"></div>
                  <div className="joint wrist-right"></div>

                  <div className="joint hip-left"></div>
                  <div className="joint hip-right"></div>

                  <div className="joint knee-left"></div>
                  <div className="joint knee-right"></div>

                  <div className="joint ankle-left"></div>
                  <div className="joint ankle-right"></div>

                </div>

                <div className="scan-line"></div>

                <div className="measurement measurement-one">
                  <span>MOVEMENT CHECKS</span>
                  <strong>3</strong>
                </div>

                <div className="measurement measurement-two">
                  <span>SPECIALISTS</span>
                  <strong>5</strong>
                </div>

              </div>

              <div className="analysis-stats">

                <div className="stat">
                  <span>Shoulder raise</span>
                  <div className="progress">
                    <div style={{ width: "100%" }}></div>
                  </div>
                  <strong>1</strong>
                </div>

                <div className="stat">
                  <span>Sit-to-stand</span>
                  <div className="progress">
                    <div style={{ width: "100%" }}></div>
                  </div>
                  <strong>2</strong>
                </div>

                <div className="stat">
                  <span>Single-leg stand</span>
                  <div className="progress">
                    <div style={{ width: "100%" }}></div>
                  </div>
                  <strong>3</strong>
                </div>

              </div>

            </div>

            <div className="floating-card floating-score">
              <span>MoveWell Score</span>
              <strong>One number</strong>
              <small>that follows your progress</small>
            </div>

            <div className="floating-card floating-ai">
              <div className="ai-icon">✦</div>
              <div>
                <span>Safety review</span>
                <small>Checks every plan first</small>
              </div>
            </div>

          </div>

        </div>
      </section>


      {/* FEATURES */}
      <section id="features" className="section features-section">

        <div className="section-heading">

          <span className="section-tag">
            WHAT YOU GET
          </span>

          <h2>
            Understand your movement.
            <br />
            <span>Improve your lifestyle.</span>
          </h2>

          <p>
            MoveWell measures three movement checks, turns them into a score
            with the areas behind it, and works out what matters most right
            now — then brings in the specialists for it.
          </p>

        </div>

        <div className="feature-grid">

          <div className="feature-card">
            <div className="feature-number">01</div>
            <div className="feature-icon">⌁</div>
            <h3>Three movement checks</h3>
            <p>
              Do an arm and shoulder raise, five sit-to-stands and a
              single-leg stand on your own device, with your camera. MoveWell
              measures how you move in each one.
            </p>
            <div className="feature-tags">
              <span>Shoulder raise</span>
              <span>Sit-to-stand ×5</span>
              <span>Single-leg stand</span>
            </div>
          </div>

          <div className="feature-card featured-card">
            <div className="feature-number">02</div>
            <div className="feature-icon">◈</div>
            <h3>Your MoveWell Score</h3>
            <p>
              Your measurements come together as one MoveWell Score, with the
              areas behind it. It is a way of following your progress over
              time — not a medical measurement and not a diagnosis.
            </p>
            <div className="feature-tags">
              <span>One number</span>
              <span>The areas behind it</span>
              <span>Over time</span>
            </div>
          </div>

          <div className="feature-card">
            <div className="feature-number">03</div>
            <div className="feature-icon">✦</div>
            <h3>Five specialists, one plan</h3>
            <p>
              MoveWell works out what matters most right now, then your five
              specialists — movement, nutrition, habits, recovery and safety —
              build one plan of concrete actions together.
            </p>
            <div className="feature-tags">
              <span>Movement</span>
              <span>Nutrition</span>
              <span>Habits</span>
              <span>Recovery</span>
              <span>Safety</span>
            </div>
          </div>

        </div>

      </section>


      {/* HOW IT WORKS */}
      <section id="how-it-works" className="section process-section">

        <div className="section-heading centered">

          <span className="section-tag">
            HOW IT WORKS
          </span>

          <h2>
            From three checks to
            <br />
            <span>one plan you can follow.</span>
          </h2>

        </div>

        <div className="process">

          <div className="process-line"></div>

          <div className="process-step">
            <div className="process-icon">01</div>
            <h3>Your profile</h3>
            <p>
              Answer a short set of questions about your movement, your daily
              habits and what you would like to change.
            </p>
          </div>

          <div className="process-step">
            <div className="process-icon">02</div>
            <h3>Three checks</h3>
            <p>
              Do an arm and shoulder raise, five sit-to-stands and a
              single-leg stand on your own device. MoveWell measures each one.
            </p>
          </div>

          <div className="process-step">
            <div className="process-icon">03</div>
            <h3>Your team</h3>
            <p>
              MoveWell works out what matters most right now — mobility,
              stability, functional movement, daily habits, nutrition or
              activity — and brings in the specialists for it.
            </p>
          </div>

          <div className="process-step">
            <div className="process-icon">04</div>
            <h3>Follow and adapt</h3>
            <p>
              Do the actions in your plan, record what you did, and the next
              assessment adapts the plan around it.
            </p>
          </div>

        </div>

      </section>


      {/* TEAM */}
      <section id="about" className="agent-section">

        <div className="agent-container">

          <div className="agent-content">

            <span className="section-tag">
              ABOUT MOVEWELL
            </span>

            <h2>
              A practical path to
              <br />
              <span>better everyday movement.</span>
            </h2>

            <p>
              MoveWell is one system for movement and lifestyle. It measures
              three movement checks with you, turns them into a score and the
              areas behind it, and works out what matters most right now. Then
              five specialists build one plan of concrete actions — and the
              safety review checks that plan before you see it.
            </p>

            <Link to="/signup" className="primary-button">
              Start with three checks
              <span>→</span>
            </Link>

            <div className="project-pillars">
              <div className="project-pillar">
                <div className="pillar-icon">01</div>
                <div>
                  <strong>Measure first</strong>
                  <span>Three checks on your own device, before anything is suggested.</span>
                </div>
              </div>

              <div className="project-pillar">
                <div className="pillar-icon">02</div>
                <div>
                  <strong>Make it personal</strong>
                  <span>One plan shaped around your needs, your pace and your routine.</span>
                </div>
              </div>

              <div className="project-pillar">
                <div className="pillar-icon">03</div>
                <div>
                  <strong>Improve safely</strong>
                  <span>A safety review checks every plan before it is shown to you.</span>
                </div>
              </div>
            </div>

          </div>

          <div className="agent-cards">

            {/* The five specialists the product actually has. Each card names
                the specialist and the coach role it plays, and there is no
                sixth: a role the product cannot field is never promised. */}

            <div className="agent-card">
              <div className="agent-avatar physio">E</div>
              <div>
                <strong>Exercise &amp; Movement</strong>
                <span>Your movement coach — mobility, stability and daily activity</span>
              </div>
              <span className="agent-arrow">↗</span>
            </div>

            <div className="agent-card">
              <div className="agent-avatar fitness">N</div>
              <div>
                <strong>Nutrition &amp; Lifestyle</strong>
                <span>Your nutrition coach — eating patterns and hydration</span>
              </div>
              <span className="agent-arrow">↗</span>
            </div>

            <div className="agent-card">
              <div className="agent-avatar ergo">B</div>
              <div>
                <strong>Behaviour &amp; Adherence</strong>
                <span>Your habit coach — routines that hold up in a normal week</span>
              </div>
              <span className="agent-arrow">↗</span>
            </div>

            <div className="agent-card">
              <div className="agent-avatar yoga">R</div>
              <div>
                <strong>Recovery &amp; Care</strong>
                <span>Your recovery coach — rest, sleep and pacing</span>
              </div>
              <span className="agent-arrow">↗</span>
            </div>

            <div className="agent-card">
              <div className="agent-avatar physio">S</div>
              <div>
                <strong>Safety &amp; Practitioner Recommendation</strong>
                <span>Safety review — checks your plan before you see it</span>
              </div>
              <span className="agent-arrow">↗</span>
            </div>

          </div>

        </div>

      </section>


      {/* CTA */}
      <section className="cta-section">

        <div className="cta-glow"></div>

        <span className="section-tag">
          START YOUR JOURNEY
        </span>

        <h2>
          Your body is telling
          <br />
          <span>a story.</span>
        </h2>

        <p>
          Three checks, one MoveWell Score, and one plan you can follow.
        </p>

        <Link to="/signup" className="cta-button">
          Start your assessment
          <span>→</span>
        </Link>

      </section>


      {/* FOOTER */}
      <footer className="footer">

        <div className="footer-brand">
          <div className="brand-icon">M</div>
          <span>
            Move<span>Well</span>
          </span>
        </div>

        <p>
          Movement, lifestyle and one plan that adapts.
        </p>

        <span className="copyright">
          © 2026 MoveWell
        </span>

      </footer>

    </div>
  );
}

export default LandingPage;
