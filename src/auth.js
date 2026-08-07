// ---------------------------------------------------------------------
// SINGLE-OPERATOR ACCESS GATE
// ---------------------------------------------------------------------
// One account only. The address is not a secret so it lives here; the
// password is read from the build environment (VITE_AUTH_PASSWORD) so it
// never enters the git history of a public repository.
//
// READ THIS BEFORE RELYING ON IT: Vite inlines VITE_* values into the
// JavaScript bundle at build time. Anyone who opens the deployed site's
// bundle can read the password. This gate keeps casual visitors out of
// the dashboard — it is NOT protection against anyone who looks. Real
// enforcement has to happen in the Flask backend, which is the only
// place a secret can be held without shipping it to the browser.

export const AUTH_EMAIL = "madhusudhan@eflight.com";

const AUTH_PASSWORD = import.meta.env.VITE_AUTH_PASSWORD || "";

// Surfaced on the login screen so a missing env var reads as a setup
// problem rather than "my password stopped working".
export const AUTH_CONFIGURED = AUTH_PASSWORD !== "";

const SESSION_KEY = "eflight.session";

export function checkCredentials(email, password) {
  const normalised = String(email || "").trim().toLowerCase();
  return normalised === AUTH_EMAIL && password === AUTH_PASSWORD;
}

// Only ever a flag — the password itself is never written to storage.
// sessionStorage rather than localStorage so closing the tab signs out.
export function signIn() {
  sessionStorage.setItem(SESSION_KEY, "1");
}

export function signOut() {
  sessionStorage.removeItem(SESSION_KEY);
}

export function isSignedIn() {
  return sessionStorage.getItem(SESSION_KEY) === "1";
}
