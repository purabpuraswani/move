import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import PasswordInput from "../components/PasswordInput";
import { resetPassword } from "../services/auth";
import {
  MIN_PASSWORD_LENGTH,
  validateNewPassword,
} from "../services/passwordRules";

import "./LoginPage.css";


// How long the success message stays up before moving on to sign in.
const REDIRECT_DELAY_MS = 3000;


function ResetPasswordPage() {

  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const token = searchParams.get("token") || "";

  const [form, setForm] = useState({
    password: "",
    confirmPassword: "",
  });

  const [error, setError] = useState("");
  const [tokenRejected, setTokenRejected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);


  useEffect(() => {

    if (!done) return undefined;

    const timer = setTimeout(() => {
      navigate("/login", { replace: true, state: { passwordReset: true } });
    }, REDIRECT_DELAY_MS);

    return () => clearTimeout(timer);

  }, [done, navigate]);


  function handleChange(e) {
    setForm({
      ...form,
      [e.target.name]: e.target.value,
    });
  }


  async function handleSubmit(e) {

    e.preventDefault();

    const validationError = validateNewPassword(
      form.password,
      form.confirmPassword
    );

    if (validationError) {
      setError(validationError);
      setTokenRejected(false);
      return;
    }

    setError("");
    setTokenRejected(false);
    setLoading(true);

    try {

      await resetPassword(token, form.password);

      setDone(true);

    } catch (err) {

      setError(err.message);
      setTokenRejected(/invalid or has expired/i.test(err.message));

    } finally {

      setLoading(false);

    }
  }


  let content;

  if (!token) {

    content = (
      <div className="login-form">

        <div className="form-error" role="alert">
          This password reset link is incomplete. Please use the full link
          from your email, or request a new one.
        </div>

        <Link to="/forgot-password" className="login-button auth-link-button">
          Request a new link
        </Link>

      </div>
    );

  } else if (done) {

    content = (
      <div className="login-form">

        <div className="form-success" role="status">
          Your password has been reset. Taking you to sign in...
        </div>

        <Link
          to="/login"
          replace
          state={{ passwordReset: true }}
          className="login-button auth-link-button"
        >
          Sign in now
        </Link>

      </div>
    );

  } else {

    content = (
      <form
        className="login-form"
        onSubmit={handleSubmit}
        noValidate
      >

        <div className="input-group">

          <label htmlFor="reset-password">New password</label>

          <PasswordInput
            id="reset-password"
            name="password"
            label="new password"
            placeholder={`At least ${MIN_PASSWORD_LENGTH} characters`}
            autoComplete="new-password"
            value={form.password}
            onChange={handleChange}
            aria-describedby="reset-password-hint"
            required
          />

          <p className="auth-helper-text" id="reset-password-hint">
            Use at least {MIN_PASSWORD_LENGTH} characters.
          </p>

        </div>


        <div className="input-group">

          <label htmlFor="reset-confirm-password">Confirm new password</label>

          <PasswordInput
            id="reset-confirm-password"
            name="confirmPassword"
            label="confirm new password"
            placeholder="Type it again"
            autoComplete="new-password"
            value={form.confirmPassword}
            onChange={handleChange}
            required
          />

        </div>


        {error && (
          <div className="form-error" role="alert">
            {error}
            {tokenRejected && (
              <>
                {" "}
                <Link to="/forgot-password">Request a new link</Link>
              </>
            )}
          </div>
        )}


        <button
          type="submit"
          className="login-button"
          disabled={loading}
        >
          {loading
            ? "Resetting..."
            : "Reset password"}
        </button>

      </form>
    );
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
            Choose a new
            <span> password.</span>
          </h1>

          <p>
            Set a new password for your MoveWell account.
          </p>

        </div>


        {content}


        <p className="signup-link">
          <Link to="/login">
            Back to sign in
          </Link>
        </p>

      </div>

    </div>
  );
}


export default ResetPasswordPage;
