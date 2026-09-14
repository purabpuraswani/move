/**
 * Client-side checks for the password reset flow. They mirror the backend's
 * rules (routes/auth.py) so a mistake is reported before a request is sent,
 * but the backend remains the authority and re-checks everything.
 */

export const MIN_PASSWORD_LENGTH = 8;

// bcrypt reads at most 72 bytes; backend/auth/security.py rejects longer input.
export const MAX_PASSWORD_BYTES = 72;

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateEmail(email) {
  const value = (email || "").trim();

  if (!value) return "Please enter your email address.";
  if (!EMAIL_PATTERN.test(value)) return "Please enter a valid email address.";

  return "";
}

export function validateNewPassword(password, confirmPassword) {
  const value = password || "";

  if (!value) return "Please enter a new password.";

  if (value.length < MIN_PASSWORD_LENGTH) {
    return `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`;
  }

  if (new TextEncoder().encode(value).length > MAX_PASSWORD_BYTES) {
    return "Password is too long. Please use a shorter password.";
  }

  if (value !== (confirmPassword || "")) return "Passwords do not match.";

  return "";
}
