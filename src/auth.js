// ---------------------------------------------------------------------
// SESSION HANDLING
// ---------------------------------------------------------------------
// Access is decided by the Flask backend, not here. This module only
// carries the token the server issued and attaches it to requests.
//
// Nothing in this file is a secret, and that is the point: a browser
// bundle cannot keep one. The previous version compared a password that
// Vite had inlined into the JavaScript, so it was readable by anyone who
// opened the deployed site. Now the password never reaches the browser
// at all — it is checked server-side against a scrypt hash.

import { API_URL } from "./api";

const TOKEN_KEY = "eflight.token";

export function getToken() {
  return sessionStorage.getItem(TOKEN_KEY) || "";
}

// sessionStorage rather than localStorage: closing the tab signs out.
export function setToken(token) {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function signOut() {
  sessionStorage.removeItem(TOKEN_KEY);
}

export function isSignedIn() {
  return getToken() !== "";
}

export function authHeader() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function describeUnreachable() {
  const onLocalhost = ["localhost", "127.0.0.1"].includes(location.hostname);
  const apiIsLocalhost = /^https?:\/\/(localhost|127\.0\.0\.1)\b/.test(API_URL);

  // A deployed site pointing at localhost means the build never received
  // VITE_API_URL. The browser would be calling the visitor's own machine.
  if (apiIsLocalhost && !onLocalhost) {
    return (
      `This site was built without VITE_API_URL, so it is trying to reach ` +
      `${API_URL} — your own computer, not the server. Set VITE_API_URL in ` +
      `the hosting settings and redeploy.`
    );
  }

  if (apiIsLocalhost) {
    return `Cannot reach the backend at ${API_URL}. Is the Flask server running?`;
  }

  return (
    `Cannot reach the backend at ${API_URL}. It may be asleep (free tier ` +
    `services take ~30s to wake — try again), or ALLOWED_ORIGINS on the ` +
    `server may not include ${location.origin}.`
  );
}

/**
 * Exchange credentials for a session token.
 * Returns { ok: true } or { ok: false, error } — never throws for an
 * expected outcome like a wrong password.
 */
export async function login(email, password) {
  let response;

  try {
    response = await fetch(`${API_URL}/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
  } catch {
    // fetch() rejects for a refused connection, DNS failure, mixed
    // content AND a blocked CORS preflight, and the browser deliberately
    // hides which. "Check your connection" sent the reader looking in
    // the wrong place, so name the URL actually being called and the
    // configuration mistakes that produce each case.
    return { ok: false, error: describeUnreachable() };
  }

  let body = {};
  try {
    body = await response.json();
  } catch {
    /* non-JSON error page — fall through to the status-based message */
  }

  if (!response.ok) {
    return {
      ok: false,
      error: body.error || `Sign-in failed (${response.status}).`,
    };
  }

  if (!body.token) {
    return { ok: false, error: "Server did not return a session token." };
  }

  setToken(body.token);
  return { ok: true };
}
