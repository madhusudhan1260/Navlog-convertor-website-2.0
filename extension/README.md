# EFLIGHT AI - ForeFlight Bridge

Lets the Navlog Converter website fetch a pasted ForeFlight link that
needs your ForeFlight login to load - the website's own server can't do
that (no access to your session), so this extension fetches it inside
your browser instead, using whatever ForeFlight session is already
logged in there. See `background.js` for exactly what it does; it never
reads, stores, or transmits your cookies anywhere - it only calls
`fetch(url, { credentials: "include" })` and lets the browser attach
whatever's already there.

One-time setup:

1. Open `chrome://extensions`
2. Turn on **Developer mode** (top right)
3. Click **Load unpacked**
4. Select this `extension/` folder (not its parent)

That's it - the website talks to it automatically from then on whenever
you paste a ForeFlight link. No further setup, and no interaction with
the extension itself is needed day to day.

If you ever edit `background.js` or `manifest.json`, click the reload
icon (↻) on the extension's card at `chrome://extensions` for the change
to take effect.
