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
    return { ok: false, error: "Cannot reach the server. Check your connection." };
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
