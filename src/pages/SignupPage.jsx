import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { signup } from "../services/auth";

import "./SignupPage.css";


function SignupPage() {
  const navigate = useNavigate();

  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
  });

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);


  function handleChange(e) {
    setForm({
      ...form,
      [e.target.name]: e.target.value,
    });
  }


  async function handleSubmit(e) {
    e.preventDefault();

    setError("");
    setLoading(true);

    try {
      const data = await signup(form);

      localStorage.setItem(
        "movewell_user",
        JSON.stringify(data.user)
      );

      navigate("/dashboard");

    } catch (err) {
      setError(err.message);

    } finally {
      setLoading(false);
    }
  }


  return (
    <div className="auth-page">

      {/* =================================
          LEFT SIDE
      ================================= */}

      <section className="auth-visual">

        <Link to="/" className="auth-brand">

          <div className="brand-icon">
            M
          </div>

          <span>
            Move<span>Well</span> AI
          </span>

        </Link>


        <div className="auth-visual-content">

          <span className="section-tag">
            PERSONALIZED WELLNESS
          </span>

          <h1>
            Move better.
            <br />
            <span>Live better.</span>
          </h1>

          <p>
            MoveWell AI combines movement analysis,
            lifestyle information and intelligent
            wellness guidance to help you understand
            your body better.
          </p>


          <div className="auth-points">

            <div>
              <span>✓</span>
              <p>AI-powered movement assessment</p>
            </div>

            <div>
              <span>✓</span>
              <p>Personalized wellness insights</p>
            </div>

            <div>
              <span>✓</span>
              <p>Guidance from specialized AI assistants</p>
            </div>

          </div>

        </div>


        {/* Decorative circles */}

        <div className="auth-decoration decoration-one"></div>

        <div className="auth-decoration decoration-two"></div>

      </section>


      {/* =================================
          RIGHT SIDE
      ================================= */}

      <section className="auth-form-area">

        <div className="auth-form-container">

          {/* Mobile brand */}

          <Link to="/" className="mobile-brand">

            <div className="brand-icon">
              M
            </div>

            Move<span>Well</span> AI

          </Link>


          {/* Heading */}

          <div className="form-heading">

            <span className="section-tag">
              GET STARTED
            </span>

            <h2>
              Create your
              <br />
              MoveWell account.
            </h2>

            <p>
              Start your personalized wellness journey.
            </p>

          </div>


          {/* Form */}

          <form
            className="signup-form"
            onSubmit={handleSubmit}
          >

            {/* Name */}

            <div className="input-group">

              <label htmlFor="name">
                Full name
              </label>

              <input
                id="name"
                type="text"
                name="name"
                placeholder="Enter your name"
                value={form.name}
                onChange={handleChange}
                required
              />

            </div>


            {/* Email */}

            <div className="input-group">

              <label htmlFor="email">
                Email
              </label>

              <input
                id="email"
                type="email"
                name="email"
                placeholder="you@example.com"
                value={form.email}
                onChange={handleChange}
                required
              />

            </div>


            {/* Password */}

            <div className="input-group">

              <label htmlFor="password">
                Password
              </label>

              <input
                id="password"
                type="password"
                name="password"
                placeholder="Create a password"
                value={form.password}
                onChange={handleChange}
                required
              />

            </div>


            {/* Error */}

            {error && (
              <div className="form-error">
                {error}
              </div>
            )}


            {/* Terms */}

            <label className="terms">

              <input
                type="checkbox"
                required
              />

              <span>
                I agree to the MoveWell AI terms and
                understand that this platform provides
                wellness information and is not a
                replacement for professional medical advice.
              </span>

            </label>


            {/* Submit */}

            <button
              type="submit"
              className="signup-button"
              disabled={loading}
            >

              <span>
                {loading
                  ? "Creating account..."
                  : "Create account"}
              </span>

              {!loading && (
                <span>→</span>
              )}

            </button>

          </form>


          {/* Divider */}

          <div className="auth-divider">
            OR
          </div>


          {/* Google */}

          <button
            type="button"
            className="google-button"
          >

            <span className="google-icon">
              G
            </span>

            Continue with Google

          </button>


          {/* Login */}

          <p className="login-text">

            Already have an account?{" "}

            <Link to="/login">
              Sign in
            </Link>

          </p>


          {/* Disclaimer */}

          <p className="health-disclaimer">
            MoveWell AI provides general wellness insights
            and does not diagnose or treat medical conditions.
          </p>

        </div>

      </section>

    </div>
  );
}


export default SignupPage;