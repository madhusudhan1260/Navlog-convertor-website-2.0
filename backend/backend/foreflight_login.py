"""One-time (and periodic) manual step: log into ForeFlight in a real,
visible browser window and save the resulting session (cookies +
localStorage) to foreflight_auth.json. playwrightFetcher.py loads that
file to fetch account-gated ForeFlight links on the team's behalf
without every visitor needing their own ForeFlight login or browser
extension.

foreflight_auth.json IS A LIVE CREDENTIAL - anyone holding it can act as
whichever ForeFlight account logs in here, for as long as the session
stays valid. It's gitignored; never commit it, never paste its contents
anywhere, and treat copying it to a server the same as handing over a
password.

Run this again whenever fetches start failing with an auth/403 error -
that means the saved session expired and needs refreshing.

Usage:
    ./venv/bin/python foreflight_login.py
"""

import os

from playwright.sync_api import sync_playwright

AUTH_FILE = os.path.join(os.path.dirname(__file__), "foreflight_auth.json")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://plan.foreflight.com/")
        print("Log in to ForeFlight in the window that just opened.")
        print("Complete 2FA if prompted, then wait for the dashboard to load.")
        input("Press Enter here once you're logged in and looking at the dashboard... ")

        context.storage_state(path=AUTH_FILE)
        print(f"Session saved to {AUTH_FILE}")
        print("Keep this file private - it's gitignored, keep it that way.")

        browser.close()


if __name__ == "__main__":
    main()
