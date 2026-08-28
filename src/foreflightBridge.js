// Talks to the "EFLIGHT AI - ForeFlight Bridge" browser extension
// (extension/ in this repo) when it's installed, so a pasted ForeFlight
// link that needs the operator to be signed in can still be fetched -
// the website itself can't do that fetch (no access to the operator's
// ForeFlight cookies, and the browser wouldn't send them cross-site even
// if it tried), but an extension with host_permissions for foreflight.com
// isn't bound by that restriction. Optional enhancement only: if the
// extension isn't installed, callers fall back to the existing
// server-side fetch, which already covers public/unauthenticated links.

// Fixed extension ID, derived from extension/manifest.json's "key" - see
// extension/extension_id.txt. Stays constant regardless of where the
// unpacked extension is loaded from.
const EXTENSION_ID = "mkljldpcgplpolehjoohkloapclfaaoi";

function sendToExtension(message) {
  return new Promise((resolve, reject) => {
    if (!window.chrome?.runtime?.sendMessage) {
      reject(new Error("extension-unavailable"));
      return;
    }

    try {
      chrome.runtime.sendMessage(EXTENSION_ID, message, (response) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
          return;
        }
        if (!response) {
          reject(new Error("no response from extension"));
          return;
        }
        resolve(response);
      });
    } catch (error) {
      reject(error);
    }
  });
}

// Resolves quickly (a couple hundred ms) whether the extension is
// installed and reachable, without throwing - callers use this to decide
// whether the extension path is even worth attempting.
export async function isBridgeAvailable() {
  try {
    const response = await Promise.race([
      sendToExtension({ action: "ping" }),
      new Promise((_, reject) => setTimeout(() => reject(new Error("timeout")), 800)),
    ]);
    return !!response?.ok;
  } catch {
    return false;
  }
}

// Fetches a pasted ForeFlight link's navlog HTML through the extension,
// using the operator's own logged-in ForeFlight session. Throws with a
// readable message on failure - callers should catch and fall back to
// the server-side URL path.
export async function fetchNavlogViaBridge(url) {
  const response = await sendToExtension({ action: "fetchNavlog", url });
  if (!response.ok) {
    throw new Error(response.error || "Extension fetch failed");
  }
  return response.html;
}
