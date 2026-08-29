"""Fetches an account-gated ForeFlight link server-side using a saved
ForeFlight session (see foreflight_login.py), for teams who've decided
that tradeoff is worth it: no per-visitor browser extension or manual
upload, at the cost of a real, standing credential living on this
server. Only used as a fallback after routeFetcher.py's plain requests
attempt fails, since that plain attempt is faster and needs no browser
at all - this only spins up headless Chromium when the link actually
turns out to need a session.
"""

import os

from playwright.sync_api import sync_playwright

AUTH_FILE = os.path.join(os.path.dirname(__file__), "foreflight_auth.json")


class PlaywrightFetchError(Exception):
    pass


def is_configured():
    return os.path.exists(AUTH_FILE)


def fetch_via_playwright(url, timeout_ms=30000):
    """Navigates to url in a headless browser carrying the saved
    ForeFlight session and returns the resulting page HTML.

    Deliberately navigates to the URL exactly as given, doc_link wrapper
    included - plan.foreflight.com/.../view-trip-document/ isn't a
    client-side fetch of its own doc_link parameter, it's a server
    endpoint that proxies and returns the real document itself given a
    valid session (confirmed by watching the network panel: exactly one
    request happens, to the wrapper URL, nothing separate to
    CloudFront). So there's nothing to resolve here - just load the page
    and read back what the authenticated session actually got served."""
    if not is_configured():
        raise PlaywrightFetchError(
            "No saved ForeFlight session (foreflight_auth.json). Run "
            "foreflight_login.py once to create it."
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                storage_state=AUTH_FILE,
                viewport={"width": 1280, "height": 800},
            )
            page = context.new_page()

            try:
                page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            except Exception as error:
                raise PlaywrightFetchError(f"Navigation failed: {error}") from error

            html = page.content()
        finally:
            browser.close()

    return html
