"""Fetches an account-gated ForeFlight link server-side using either a saved
ForeFlight session (foreflight_auth.json) or dynamic credentials defined in .env
(FOREFLIGHT_EMAIL and FOREFLIGHT_PASSWORD).

Automatically handles logging in, OneTrust cookie consent, saving/refreshing session
cookies, and retrying if a session expires.
"""

import os
import time

from playwright.sync_api import sync_playwright

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

AUTH_FILE = os.path.join(os.path.dirname(__file__), "foreflight_auth.json")
ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")


class PlaywrightFetchError(Exception):
    pass


def get_credentials():
    if load_dotenv and os.path.exists(ENV_FILE):
        load_dotenv(ENV_FILE, override=True)
    email = (os.getenv("FOREFLIGHT_EMAIL") or os.getenv("FOREFLIGHT_USERNAME") or "").strip()
    password = (os.getenv("FOREFLIGHT_PASSWORD") or "").strip()
    return email, password


def is_configured():
    email, password = get_credentials()
    return os.path.exists(AUTH_FILE) or (bool(email) and bool(password))


def _login_with_credentials(context, email, password, timeout_ms=30000):
    """Logs into ForeFlight with multi-step login and saves storage state."""
    page = context.new_page()
    try:
        print(f"[AUTH] Logging into ForeFlight as {email}...")
        page.goto(
            "https://login.foreflight.com/login?next=https%3A%2F%2Fplan.foreflight.com",
            wait_until="networkidle",
            timeout=timeout_ms,
        )

        # Dismiss OneTrust cookie banner if present
        try:
            accept_cookie = page.query_selector(
                "#onetrust-accept-btn-handler, button:has-text('Accept Cookies'), #onetrust-reject-all-handler"
            )
            if accept_cookie:
                accept_cookie.click(force=True)
                page.wait_for_timeout(1000)
        except Exception:
            pass

        # Step 1: Fill Email
        email_input = page.wait_for_selector(
            "input[type='text'], input[type='email'], input[name='username']",
            timeout=10000,
        )
        email_input.fill(email)

        next_btn = page.query_selector("button[type='submit']")
        if next_btn:
            next_btn.click(force=True)
        else:
            page.keyboard.press("Enter")
        page.wait_for_timeout(2000)

        # Step 2: Fill Password
        pwd_input = page.wait_for_selector("input[type='password']", timeout=10000)
        pwd_input.fill(password)

        sign_in_btn = page.query_selector("button[type='submit']")
        if sign_in_btn:
            sign_in_btn.click(force=True)
        else:
            page.keyboard.press("Enter")

        page.wait_for_timeout(5000)

        # Check for login errors
        body_text = page.inner_text("body").lower()
        if "invalid username or password" in body_text:
            raise PlaywrightFetchError(
                "ForeFlight auto-login failed: Invalid email or password in .env."
            )

        # Wait for navigation away from login
        try:
            page.wait_for_url(lambda u: "login.foreflight.com" not in u, timeout=15000)
        except Exception:
            pass

        # Save session
        context.storage_state(path=AUTH_FILE)
        print(f"[AUTH] ForeFlight session saved successfully to {AUTH_FILE}")
    finally:
        page.close()


def fetch_via_playwright(url, timeout_ms=30000):
    """Navigates to url in a headless browser carrying ForeFlight authentication
    and returns the resulting page HTML."""
    if not is_configured():
        raise PlaywrightFetchError(
            "ForeFlight link fetching is not configured. Either add FOREFLIGHT_EMAIL "
            "and FOREFLIGHT_PASSWORD to backend/backend/.env, or run foreflight_login.py once."
        )

    email, password = get_credentials()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context_kwargs = {
                "viewport": {"width": 1280, "height": 800}
            }
            if os.path.exists(AUTH_FILE):
                context_kwargs["storage_state"] = AUTH_FILE

            context = browser.new_context(**context_kwargs)

            # If no auth file exists yet but credentials are provided, log in first
            if not os.path.exists(AUTH_FILE) and email and password:
                _login_with_credentials(context, email, password, timeout_ms=timeout_ms)

            page = context.new_page()

            try:
                page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            except Exception as error:
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    page.wait_for_timeout(3000)
                except Exception:
                    raise PlaywrightFetchError(f"Navigation to ForeFlight link failed: {error}") from error

            current_url = page.url
            # If session was expired and redirected to login, re-authenticate and retry
            if "login.foreflight.com" in current_url and email and password:
                print("[AUTH] Session expired (redirected to login). Re-authenticating...")
                _login_with_credentials(context, email, password, timeout_ms=timeout_ms)
                page.goto(url, wait_until="networkidle", timeout=timeout_ms)

            html = page.content()
        finally:
            browser.close()

    return html
