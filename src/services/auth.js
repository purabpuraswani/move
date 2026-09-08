import { apiFetch, getApiUrl } from "./api";

const TOKEN_KEY = "movewell_token";
const USER_KEY = "movewell_user";


export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}


// Whether a token is being held. Deliberately not a claim that the token is
// valid: only the backend can say that, because only the backend has the
// signing secret. This gates the routing so a signed-out visitor is sent to the
// sign-in page instead of a screen whose every request is about to fail. A token
// that has expired still reaches the server, which rejects it, and the request
// helpers below clear the session on a 401.
export function isSignedIn() {
  return Boolean(getToken());
}


export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}


// Used by every request to a protected endpoint. The backend identifies the
// user from this token, so nothing needs to send a user id.
export function authHeader() {
  const token = getToken();

  if (!token) {
    throw new Error(
      "You are not signed in. Please sign in again."
    );
  }

  return { Authorization: `Bearer ${token}` };
}


async function postJson(path, userData, fallbackError) {
  const response = await apiFetch(
    `${getApiUrl()}${path}`,
    {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify(userData),
    }
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || fallbackError);
  }

  if (data.token) {
    localStorage.setItem(TOKEN_KEY, data.token);
  }

  return data;
}


export async function signup(userData) {
  return postJson(
    "/api/auth/signup",
    userData,
    "Signup failed"
  );
}


export async function signin(userData) {
  return postJson(
    "/api/auth/signin",
    userData,
    "Signin failed"
  );
}


/**
 * Who the backend says this token belongs to.
 *
 * The name shown on a screen should come from the server rather than from a
 * copy kept in the browser, where it can go stale or be edited. Nothing is
 * trusted because of this call — the backend identifies the user from the token
 * on every request regardless — it is here so the interface displays the account
 * that is actually signed in.
 *
 * Throws on an expired or rejected token, having cleared the stored session, so
 * a caller can send the user back to sign in.
 */
export async function fetchMe() {

  const response = await apiFetch(
    `${getApiUrl()}/api/auth/me`,
    { headers: authHeader() }
  );

  if (response.status === 401) {
    clearSession();

    throw new Error("Your session has expired. Please sign in again.");
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || "Could not load your account.");
  }

  return data.user || data;
}
