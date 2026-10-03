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
              AI-powered movement & lifestyle intelligence
            </div>

            <h1>
              Move smarter.
              <br />
              <span>Live stronger.</span>
            </h1>

            <p className="hero-description">
              MoveWell AI combines computer vision, machine learning and
              personalized AI agents to understand your movement patterns
              and help you build a healthier, more active lifestyle.
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
                <strong>MoveNet</strong>
                <span>Pose analysis</span>
              </div>

              <div className="trust-divider"></div>

              <div className="trust-item">
                <strong>ML</strong>
                <span>Risk assessment</span>
              </div>

              <div className="trust-divider"></div>

              <div className="trust-item">
                <strong>AI Agents</strong>
                <span>Personal guidance</span>
              </div>
            </div>

          </div>

          {/* HERO VISUAL */}
          <div className="hero-visual">

            <div className="visual-glow"></div>

            <div className="analysis-card">

              <div className="analysis-header">
                <div>
                  <span className="small-label">LIVE ANALYSIS</span>
                  <h3>Movement Assessment</h3>
                </div>

                <div className="live-indicator">
                  <span></span>
                  Live
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
                  <span>ROM</span>
                  <strong>82</strong>
                </div>

                <div className="measurement measurement-two">
                  <span>SYMMETRY</span>
                  <strong>91</strong>
                </div>

              </div>

              <div className="analysis-stats">

                <div className="stat">
                  <span>Mobility</span>
                  <div className="progress">
                    <div style={{ width: "82%" }}></div>
                  </div>
                  <strong>82%</strong>
                </div>

                <div className="stat">
                  <span>Stability</span>
                  <div className="progress">
                    <div style={{ width: "76%" }}></div>
                  </div>
                  <strong>76%</strong>
                </div>

                <div className="stat">
                  <span>Consistency</span>
                  <div className="progress">
                    <div style={{ width: "88%" }}></div>
                  </div>
                  <strong>88%</strong>
                </div>

              </div>

            </div>

            <div className="floating-card floating-score">
              <span>Movement Score</span>
              <strong>84</strong>
              <small>Good movement profile</small>
            </div>

            <div className="floating-card floating-ai">
              <div className="ai-icon">✦</div>
              <div>
                <span>MoveWell AI</span>
                <small>Personalized guidance ready</small>
              </div>
            </div>

          </div>

        </div>
      </section>


      {/* FEATURES */}
      <section id="features" className="section features-section">

        <div className="section-heading">

          <span className="section-tag">
            INTELLIGENT WELLNESS
          </span>

          <h2>
            Understand your movement.
            <br />
            <span>Improve your lifestyle.</span>
          </h2>

          <p>
            MoveWell AI brings together movement analysis, lifestyle
            information and evidence-grounded AI to create a personalized
            wellness experience.
          </p>

        </div>

        <div className="feature-grid">

          <div className="feature-card">
            <div className="feature-number">01</div>
            <div className="feature-icon">⌁</div>
            <h3>Movement Analysis</h3>
            <p>
              Analyze movement through webcam-based pose estimation
              using MoveNet and extract meaningful movement characteristics.
            </p>
            <div className="feature-tags">
              <span>ROM</span>
              <span>Symmetry</span>
              <span>Stability</span>
            </div>
          </div>

          <div className="feature-card featured-card">
            <div className="feature-number">02</div>
            <div className="feature-icon">◈</div>
            <h3>AI Risk Assessment</h3>
            <p>
              Combine movement and lifestyle parameters with machine
              learning to build a personalized sedentary-lifestyle profile.
            </p>
            <div className="feature-tags">
              <span>ML</span>
              <span>Personalized</span>
              <span>Data-driven</span>
            </div>
          </div>

          <div className="feature-card">
            <div className="feature-number">03</div>
            <div className="feature-icon">✦</div>
            <h3>Specialist AI Agents</h3>
            <p>
              Get personalized guidance from dedicated AI assistants
              focused on movement, fitness, yoga and ergonomics.
            </p>
            <div className="feature-tags">
              <span>Physio</span>
              <span>Yoga</span>
              <span>Fitness</span>
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
            From movement to
            <br />
            <span>meaningful action.</span>
          </h2>

        </div>

        <div className="process">

          <div className="process-line"></div>

          <div className="process-step">
            <div className="process-icon">01</div>
            <h3>Assess</h3>
            <p>
              Complete a short lifestyle questionnaire and perform
              simple movement assessments through your webcam.
            </p>
          </div>

          <div className="process-step">
            <div className="process-icon">02</div>
            <h3>Understand</h3>
            <p>
              MoveNet extracts movement features while ML models
              analyze your lifestyle and movement profile.
            </p>
          </div>

          <div className="process-step">
            <div className="process-icon">03</div>
            <h3>Personalize</h3>
            <p>
              AI agents use your profile and trusted health knowledge
              to create relevant recommendations.
            </p>
          </div>

          <div className="process-step">
            <div className="process-icon">04</div>
            <h3>Improve</h3>
            <p>
              Follow personalized movement and lifestyle suggestions
              and track your progress over time.
            </p>
          </div>

        </div>

      </section>


      {/* AGENTS */}
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
              MoveWell is a wellness platform that brings movement
              assessment, lifestyle signals and specialist guidance
              together in one place. It helps you understand where to
              start, choose achievable actions and learn from your
              progress over time.
            </p>

            <Link to="/signup" className="primary-button">
              Explore MoveWell
              <span>→</span>
            </Link>

            <div className="project-pillars">
              <div className="project-pillar">
                <div className="pillar-icon">01</div>
                <div>
                  <strong>Understand first</strong>
                  <span>Use movement and lifestyle context before suggesting change.</span>
                </div>
              </div>

              <div className="project-pillar">
                <div className="pillar-icon">02</div>
                <div>
                  <strong>Make it personal</strong>
                  <span>Receive guidance shaped around your needs, pace and routine.</span>
                </div>
              </div>

              <div className="project-pillar">
                <div className="pillar-icon">03</div>
                <div>
                  <strong>Improve safely</strong>
                  <span>Track what you do and adapt recommendations over time.</span>
                </div>
              </div>
            </div>

          </div>

          <div className="agent-cards">

            <div className="agent-card">
              <div className="agent-avatar physio">P</div>
              <div>
                <strong>Physiotherapy</strong>
                <span>Movement & mobility</span>
              </div>
              <span className="agent-arrow">↗</span>
            </div>

            <div className="agent-card">
              <div className="agent-avatar yoga">Y</div>
              <div>
                <strong>Yoga & Mobility</strong>
                <span>Flexibility & recovery</span>
              </div>
              <span className="agent-arrow">↗</span>
            </div>

            <div className="agent-card">
              <div className="agent-avatar fitness">F</div>
              <div>
                <strong>Fitness</strong>
                <span>Activity & movement</span>
              </div>
              <span className="agent-arrow">↗</span>
            </div>

            <div className="agent-card">
              <div className="agent-avatar ergo">E</div>
              <div>
                <strong>Ergonomics</strong>
                <span>Workplace wellness</span>
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
          Let MoveWell AI help you understand it.
        </p>

        <Link to="/signup" className="cta-button">
          Get started for free
          <span>→</span>
        </Link>

      </section>


      {/* FOOTER */}
      <footer className="footer">

        <div className="footer-brand">
          <div className="brand-icon">M</div>
          <span>
            Move<span>Well</span> AI
          </span>
        </div>

        <p>
          Intelligent movement. Personalized wellness.
        </p>

        <span className="copyright">
          © 2026 MoveWell AI
        </span>

      </footer>

    </div>
  );
}

export default LandingPage;