"""
Server-side access control.

Everything that matters happens here rather than in the React app,
because a browser bundle cannot hold a secret — anything shipped to the
client is readable by the client. The frontend gate is now only a
convenience; this module is the thing that actually says no.

Three secrets, all supplied by the environment and none of them in the
repository:

    AUTH_EMAIL           the single authorised address
    AUTH_PASSWORD_HASH   scrypt hash of the password (never the password)
    SECRET_KEY           signing key for session tokens

Generate the hash with:

    python -c "from werkzeug.security import generate_password_hash as g; \
print(g(input('password: ')))"
"""

import os
import time
import hmac
import threading
from functools import wraps

from flask import request, jsonify
from itsdangerous import (
    URLSafeTimedSerializer,
    BadSignature,
    SignatureExpired,
)
from werkzeug.security import check_password_hash

AUTH_EMAIL = (os.getenv("AUTH_EMAIL") or "").strip().lower()
AUTH_PASSWORD_HASH = (os.getenv("AUTH_PASSWORD_HASH") or "").strip()
SECRET_KEY = (os.getenv("SECRET_KEY") or "").strip()

# How long a sign-in lasts before the operator has to authenticate again.
SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE_SECONDS", 12 * 60 * 60))

# Brute-force damping. The password is short enough that an unthrottled
# endpoint could be exhausted offline-fast, so failures per client IP are
# capped over a rolling window.
MAX_ATTEMPTS = 8
ATTEMPT_WINDOW = 15 * 60

AUTH_CONFIGURED = bool(AUTH_EMAIL and AUTH_PASSWORD_HASH and SECRET_KEY)

_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="eflight-session") \
    if SECRET_KEY else None

_failures = {}
_failures_lock = threading.Lock()


def _client_ip():
    """Render sits behind a proxy, so remote_addr is the proxy. Trust the
    first hop in X-Forwarded-For, which the platform sets itself."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _record_failure(ip):
    now = time.time()
    with _failures_lock:
        recent = [t for t in _failures.get(ip, []) if now - t < ATTEMPT_WINDOW]
        recent.append(now)
        _failures[ip] = recent


def _is_locked_out(ip):
    now = time.time()
    with _failures_lock:
        recent = [t for t in _failures.get(ip, []) if now - t < ATTEMPT_WINDOW]
        _failures[ip] = recent
        return len(recent) >= MAX_ATTEMPTS


def _clear_failures(ip):
    with _failures_lock:
        _failures.pop(ip, None)


def verify_credentials(email, password):
    """True only for the one authorised operator.

    The address is compared with hmac.compare_digest rather than == so a
    wrong address cannot be distinguished from a right one by timing, and
    the password always goes through the hash check so that a request for
    an unknown address costs the same as a request for the real one.
    """
    if not AUTH_CONFIGURED:
        return False

    supplied = (email or "").strip().lower()
    email_ok = hmac.compare_digest(supplied, AUTH_EMAIL)
    password_ok = check_password_hash(AUTH_PASSWORD_HASH, password or "")

    return email_ok and password_ok


def issue_token():
    return _serializer.dumps({"sub": AUTH_EMAIL})


def token_is_valid(token):
    if not (_serializer and token):
        return False
    try:
        _serializer.loads(token, max_age=SESSION_MAX_AGE)
        return True
    except (BadSignature, SignatureExpired):
        return False


def _bearer_token():
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:].strip()
    return ""


def login_view():
    """POST /login -> {token} for the authorised operator, 401 otherwise."""
    if not AUTH_CONFIGURED:
        return jsonify({
            "error": "Sign-in is not configured on this server "
                     "(AUTH_EMAIL / AUTH_PASSWORD_HASH / SECRET_KEY)."
        }), 503

    ip = _client_ip()
    if _is_locked_out(ip):
        return jsonify({
            "error": "Too many failed attempts. Try again later."
        }), 429

    body = request.get_json(silent=True) or {}

    if verify_credentials(body.get("email"), body.get("password")):
        _clear_failures(ip)
        return jsonify({"token": issue_token()})

    _record_failure(ip)
    # One message for both halves: naming which was wrong hands an
    # attacker a confirmed username.
    return jsonify({"error": "Incorrect email or password."}), 401


def require_auth(view):
    """Gate a route behind a valid session token."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not AUTH_CONFIGURED:
            return jsonify({
                "error": "Sign-in is not configured on this server."
            }), 503
        if not token_is_valid(_bearer_token()):
            return jsonify({"error": "Not authorised."}), 401
        return view(*args, **kwargs)
    return wrapper
