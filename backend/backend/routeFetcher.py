"""Resolves one navlog route (Main Route, Alternate 1, Alternate 2) from
whichever source the operator actually gave /convert - an uploaded
ForeFlight .html export, or a pasted ForeFlight link. Kept separate from
server.py so the two very different concerns - "what does a route look
like once parsed" (routing/HTTP glue) vs. "where does its HTML come
from" (file save + read, or a remote fetch with ForeFlight's own
sign-in-wall quirks worked around) - don't end up tangled in one file.
"""

import os

from urllib.parse import unquote

import requests
from flask import request
from werkzeug.utils import secure_filename

from htmlParser import parse_html
from playwrightFetcher import fetch_via_playwright, is_configured as playwright_configured

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def empty_route():

    return {

        "header": "",

        "performance": {},

        "fuel": {},

        "weight": {},

        "route": "",

        "waypoints": [],

        "airportInfo": {}

    }


class RouteFetchError(Exception):
    """A pasted link couldn't be turned into a usable navlog. Always
    carries a message telling the operator to fall back to uploading the
    .html file instead - the one path that's certain to work, since a
    server-side request has no access to the operator's own ForeFlight
    session and can't get past a sign-in wall a link may sit behind."""
    pass


def _resolve_doc_link(url):
    """The link ForeFlight's own share/print UI hands out points at
    plan.foreflight.com/flightdata/api/trips/view-trip-document/ - a page
    that needs the visitor signed in to render, since it's a ForeFlight
    account page. But the navlog HTML it displays isn't hosted there: the
    page itself just reads a `doc_link` query parameter pointing at a
    CloudFront URL and fetches THAT. Serving the shared document from
    CloudFront rather than from the account page is exactly what makes it
    reachable without a session - so fetching doc_link directly, instead
    of the wrapper page, is what lets this work without ForeFlight ever
    being logged in server-side.

    doc_link's own value is a signed CloudFront URL with its own
    Expires/Signature/Key-Pair-Id query params, appended without
    percent-encoding their & separators - so a normal query-string parser
    (parse_qs) splits on those too and silently truncates the signature
    off the end, leaving a broken URL. Taking the raw substring after
    "doc_link=" through to the end keeps it intact instead."""
    marker = "doc_link="
    index = url.find(marker)
    if index == -1:
        return url

    raw = url[index + len(marker):]
    decoded = unquote(raw)
    return decoded if decoded.startswith(("http://", "https://")) else raw


def _plain_fetch(url):
    """Fast path: a bare GET, no browser. Works for links that don't
    need a ForeFlight session at all (public share links)."""
    response = requests.get(
        url,
        timeout=15,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        },
    )
    response.raise_for_status()
    return response.text


def fetch_route_html(label, url):
    """Server-side fetch of a pasted ForeFlight link. Tries a plain,
    fast, browser-less GET first - that's all a public share link
    needs. If that comes back without a real navlog (e.g. redirected to
    a sign-in page) and a ForeFlight session has been saved (see
    foreflight_login.py), falls back to fetching it through headless
    Chromium carrying that session - the one way to reach a link that's
    gated behind the operator's own ForeFlight account. Without a saved
    session, that fallback isn't available and the plain fetch's result
    is what's reported."""
    resolved = _resolve_doc_link(url)

    plain_error = None
    try:
        html = _plain_fetch(resolved)
        parsed = parse_html(html)
        if parsed.get("waypoints"):
            return parsed
    except requests.RequestException as error:
        plain_error = error

    if playwright_configured():
        try:
            html = fetch_via_playwright(url)
            parsed = parse_html(html)
            if parsed.get("waypoints"):
                return parsed
        except Exception:
            pass

    if plain_error is not None:
        reason = (
            f"HTTP {plain_error.response.status_code}"
            if isinstance(plain_error, requests.HTTPError) and plain_error.response is not None
            else type(plain_error).__name__
        )
        raise RouteFetchError(
            f"Could not fetch the {label} navlog from that link ({reason}). "
            "ForeFlight may require you to be signed in, which a server "
            "request can't provide - please upload the .html file instead."
        ) from plain_error

    raise RouteFetchError(
        f"That link didn't return a {label} navlog - it may have "
        "redirected to a ForeFlight sign-in page. Please upload the "
        ".html file instead."
    )


def resolve_route(label, file_key, url_key, required=False):
    """Either the uploaded file (existing path) or a pasted link (new
    path) supplies a route - the file always wins if both are given."""
    file = request.files.get(file_key)
    if file and file.filename:
        path = os.path.join(UPLOAD_FOLDER, secure_filename(file.filename))
        file.save(path)
        with open(path, "r", encoding="utf8") as f:
            html = f.read()
        return parse_html(html)

    url = (request.form.get(url_key) or "").strip()
    if url:
        return fetch_route_html(label, url)

    if required:
        raise RouteFetchError(
            f"{label} is missing - upload a file or paste a link."
        )

    return empty_route()
