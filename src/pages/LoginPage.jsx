import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import PasswordInput from "../components/PasswordInput";
import { signin } from "../services/auth";

import "./LoginPage.css";


function LoginPage() {

  const navigate = useNavigate();
  const location = useLocation();

  // Where RequireAuth turned this visitor away from, if it did. Signing
  // in should continue to the page they asked for rather than dropping
  // them on the dashboard. Only in-app paths are accepted, so a crafted
  // link cannot use this to bounce anyone to another site.
  const from = location.state?.from;

  const destination =
    typeof from === "string" && from.startsWith("/") && !from.startsWith("//")
      ? from
      : "/dashboard";

  const [form, setForm] = useState({
    email: "",
    password: "",
  });

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Set by ResetPasswordPage when it sends the user here after a reset.
  const passwordWasReset = location.state?.passwordReset === true;


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

      const data = await signin(form);

      localStorage.setItem(
        "movewell_user",
        JSON.stringify(data.user)
      );

      navigate(destination, { replace: true });

    } catch (err) {

      setError(err.message);

    } finally {

      setLoading(false);

    }
  }


  return (
    <div className="auth-page login-auth-page">

      <section className="login-visual">
        <Link to="/" className="auth-brand">
          <div className="brand-icon">M</div>
          <span>Move<span>Well</span></span>
        </Link>

        <div className="login-visual-content">
          <span className="section-tag">WELCOME BACK</span>
          <h1>Keep building <span>your routine.</span></h1>
          <p>
            Come back to your MoveWell Score, the areas behind it, and the
            actions in your plan.
          </p>

          <div className="login-trust-list">
            <span><b>✓</b> Your MoveWell Score, and the areas behind it</span>
            <span><b>✓</b> The plan you are working through</span>
            <span><b>✓</b> A safety review before any plan is shown</span>
          </div>
        </div>

        <div className="auth-decoration decoration-one"></div>
        <div className="auth-decoration decoration-two"></div>
      </section>

      <section className="auth-form-area login-form-area">
        <div className="login-container">

        <div className="login-heading">

          <span className="section-tag">
            SIGN IN
          </span>

          <h1>
            Sign in to
            <span> MoveWell.</span>
          </h1>

          <p>
            Your score, your plan and your progress are waiting. When it is
            time for the next assessment, MoveWell will take you through the
            three movement checks again.
          </p>

        </div>


        <form
          className="login-form"
          onSubmit={handleSubmit}
        >

          {passwordWasReset && !error && (
            <div className="form-success" role="status">
              Your password has been reset. Sign in with your new password.
            </div>
          )}


          <div className="input-group">

            <label htmlFor="login-email">Email</label>

            <input
              id="login-email"
              type="email"
              name="email"
              autoComplete="email"
              placeholder="you@example.com"
              value={form.email}
              onChange={handleChange}
              required
            />

          </div>


          <div className="input-group">

            <div className="login-password-label">

              <label htmlFor="login-password">Password</label>

              <Link to="/forgot-password" className="forgot-password-link">
                Forgot password?
              </Link>

            </div>

            <PasswordInput
              id="login-password"
              name="password"
              placeholder="Your password"
              autoComplete="current-password"
              value={form.password}
              onChange={handleChange}
              required
            />

          </div>


          {error && (
            <div className="form-error">
              {error}
            </div>
          )}


          <button
            type="submit"
            className="login-button"
            disabled={loading}
          >
            {loading
              ? "Signing in..."
              : "Sign in"}
          </button>

        </form>


        <p className="signup-link">
          Don't have an account?{" "}
          <Link to="/signup">
            Create one
          </Link>
        </p>

        </div>
      </section>

    </div>
  );
}


export default LoginPage;