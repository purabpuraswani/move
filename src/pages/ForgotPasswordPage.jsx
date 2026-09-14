import { useState } from "react";
import { Link } from "react-router-dom";

import { requestPasswordReset } from "../services/auth";
import { validateEmail } from "../services/passwordRules";

import "./LoginPage.css";


// Shown for every accepted request. The backend sends the same wording, but
// the page does not depend on it, so it can never hint at whether the address
// has an account.
const SENT_MESSAGE =
  "If an account exists with this email address, password reset instructions have been sent.";


function ForgotPasswordPage() {

  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);


  async function handleSubmit(e) {

    e.preventDefault();

    const validationError = validateEmail(email);

    if (validationError) {
      setError(validationError);
      return;
    }

    setError("");
    setLoading(true);

    try {

      await requestPasswordReset(email.trim());

      setSent(true);

    } catch (err) {

      setError(err.message);

    } finally {

      setLoading(false);

    }
  }


  return (
    <div className="login-page">

      <div className="login-container">

        <Link to="/" className="login-brand">
          <div className="brand-icon">
            M
          </div>

          Move<span>Well</span> AI
        </Link>


        <div className="login-heading">

          <span className="section-tag">
            ACCOUNT RECOVERY
          </span>

          <h1>
            Forgot your
            <span> password?</span>
          </h1>

          <p>
            Enter the email address you signed up with and we will send
            you a link to choose a new password.
          </p>

        </div>


        {sent ? (

          <div className="login-form">

            <div className="form-success" role="status">
              {SENT_MESSAGE}
            </div>

            <p className="auth-helper-text">
              The link works once and expires after a short time. If nothing
              arrives, check your spam folder or send another link.
            </p>

            <button
              type="button"
              className="login-button"
              onClick={() => setSent(false)}
            >
              Send another link
            </button>

          </div>

        ) : (

          <form
            className="login-form"
            onSubmit={handleSubmit}
            noValidate
          >

            <div className="input-group">

              <label htmlFor="forgot-email">Email</label>

              <input
                id="forgot-email"
                type="email"
                name="email"
                placeholder="you@example.com"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                aria-invalid={Boolean(error)}
                aria-describedby={error ? "forgot-error" : undefined}
                required
              />

            </div>


            {error && (
              <div className="form-error" id="forgot-error" role="alert">
                {error}
              </div>
            )}


            <button
              type="submit"
              className="login-button"
              disabled={loading}
            >
              {loading
                ? "Sending..."
                : "Send reset link"}
            </button>

          </form>

        )}


        <p className="signup-link">
          Remembered it?{" "}
          <Link to="/login">
            Back to sign in
          </Link>
        </p>

      </div>

    </div>
  );
}


export default ForgotPasswordPage;
