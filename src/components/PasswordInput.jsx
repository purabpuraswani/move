import { useState } from "react";

import "./PasswordInput.css";

/**
 * A password field with a show/hide toggle inside it, on the right.
 *
 * Hidden by default. Each instance keeps its own visibility, so a new password
 * and its confirmation toggle independently. The toggle is a real <button>, so
 * it is reachable with Tab and operated with Enter or Space, and it announces
 * its state through aria-pressed and a label naming the field it controls.
 *
 * Every other prop (name, value, onChange, placeholder, autoComplete, required,
 * aria-describedby...) is passed straight to the <input>.
 */
function PasswordInput({ id, label = "password", className = "", inputClassName = "", ...inputProps }) {
  const [visible, setVisible] = useState(false);

  return (
    <div className={`password-input ${className}`.trim()}>
      <input
        {...inputProps}
        id={id}
        className={`password-input__field ${inputClassName}`.trim()}
        type={visible ? "text" : "password"}
        autoCapitalize="off"
        autoCorrect="off"
        spellCheck={false}
      />

      <button
        type="button"
        className="password-input__toggle"
        onClick={() => setVisible((current) => !current)}
        aria-label={`${visible ? "Hide" : "Show"} ${label}`}
        aria-pressed={visible}
        aria-controls={id}
        title={`${visible ? "Hide" : "Show"} ${label}`}
      >
        {visible ? <EyeOffIcon /> : <EyeIcon />}
      </button>
    </div>
  );
}

function EyeIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d="M10.6 5.1A10.8 10.8 0 0 1 12 5c6.4 0 10 7 10 7a17.6 17.6 0 0 1-3.1 4" />
      <path d="M6.6 6.6C3.7 8.4 2 12 2 12s3.6 7 10 7a9.7 9.7 0 0 0 5.4-1.6" />
      <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
      <path d="m3 3 18 18" />
    </svg>
  );
}

export default PasswordInput;
