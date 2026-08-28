// Bridges the EFLIGHT AI Navlog Converter website to ForeFlight: the
// website itself can't fetch an account-gated ForeFlight link (a plain
// webpage fetch to a different origin doesn't carry that origin's
// cookies, and ForeFlight doesn't allow it even if it did - that's
// standard cross-site cookie protection). An extension with
// host_permissions for foreflight.com/cloudfront.foreflight.com isn't
// bound by that restriction, so it can fetch the link with the
// operator's real ForeFlight session attached and hand the resulting
// HTML back to the website, which then treats it exactly like an
// uploaded file.

// Mirrors routeFetcher.py's _resolve_doc_link() - kept as a fallback,
// see below.
function resolveDocLink(url) {
  const marker = "doc_link=";
  const index = url.indexOf(marker);
  if (index === -1) return url;

  const raw = url.slice(index + marker.length);
  try {
    const decoded = decodeURIComponent(raw);
    return decoded.startsWith("http://") || decoded.startsWith("https://")
      ? decoded
      : raw;
  } catch {
    return raw;
  }
}

// plan.foreflight.com/.../view-trip-document/?doc_link=... is NOT a
// client-side SPA that separately fetches doc_link with JS - it's a
// server endpoint that, given a valid plan.foreflight.com session
// (cookies), fetches doc_link itself server-side and returns the real
// navlog HTML directly as its own response body. Confirmed by watching
// the network panel while it loads authenticated: exactly one request
// happens, to the wrapper URL itself, nothing separate to CloudFront.
// So the fetch here has to target the wrapper URL (with credentials for
// plan.foreflight.com), not the doc_link URL underneath it - the
// CloudFront URL has no auth of its own to give it.
//
// When unauthenticated, that same endpoint instead returns a mostly-
// empty SPA shell (title + a cookie-consent script, no navlog data) -
// distinguishing that from a real result by size, since the real
// document is tens of KB and the shell is close to 1KB.
const MIN_REAL_RESPONSE_LENGTH = 5000;

async function tryFetch(url) {
  const response = await fetch(url, { credentials: "include" });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.text();
}

async function fetchNavlogHtml(url) {
  try {
    const html = await tryFetch(url);
    if (html.length >= MIN_REAL_RESPONSE_LENGTH) {
      return html;
    }
    // Response came back thin - likely the unauthenticated shell rather
    // than the real document. Fall through to the doc_link attempt
    // below instead of returning a near-empty PDF silently.
  } catch {
    // Wrapper fetch itself failed outright - also fall through.
  }

  const resolved = resolveDocLink(url);
  if (resolved === url) {
    throw new Error("No usable content at that link");
  }
  return tryFetch(resolved);
}

chrome.runtime.onMessageExternal.addListener((message, sender, sendResponse) => {
  console.log("[ForeFlight Bridge] message received:", message, "from", sender?.url);

  if (!message || typeof message !== "object") return;

  if (message.action === "ping") {
    sendResponse({ ok: true });
    return;
  }

  if (message.action === "fetchNavlog" && message.url) {
    fetchNavlogHtml(message.url)
      .then((html) => sendResponse({ ok: true, html }))
      .catch((error) => sendResponse({ ok: false, error: String(error && error.message || error) }));
    return true; // keep the message channel open for the async response
  }
});
