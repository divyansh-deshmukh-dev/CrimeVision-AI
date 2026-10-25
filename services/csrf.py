"""
services/csrf.py — Session-based CSRF protection for state-changing requests.

Generates cryptographic CSRF tokens stored in the server-side Flask session,
validates incoming POST/PUT/PATCH/DELETE requests against the X-CSRF-Token header
or csrf_token body parameter, and sets a client-accessible cookie for AJAX fetch.
"""

from functools import wraps
import hmac
import secrets
from typing import Any, Callable

from flask import Flask, Response, current_app, jsonify, request, session

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
_EXEMPT_ROUTES: set[str] = set()


def generate_csrf_token() -> str:
    """Return the current session's CSRF token, generating one if needed."""
    token = session.get("csrf_token")
    if not token or not isinstance(token, str):
        token = secrets.token_hex(32)
        session["csrf_token"] = token
    return token


def csrf_exempt(view_func: Callable) -> Callable:
    """Decorator to mark a route as exempt from CSRF validation."""
    endpoint = view_func.__name__
    _EXEMPT_ROUTES.add(endpoint)

    @wraps(view_func)
    def decorated_view(*args: Any, **kwargs: Any):
        return view_func(*args, **kwargs)

    return decorated_view


def validate_csrf() -> tuple[bool, str]:
    """Validate the incoming request's CSRF token against the session.

    Returns (True, '') on success, or (False, error_message) on failure.
    """
    if request.method in SAFE_METHODS:
        return True, ""

    # Check route-level exemption
    if request.endpoint in _EXEMPT_ROUTES:
        return True, ""

    # Extract token from header, form, or JSON body
    submitted = (
        request.headers.get("X-CSRF-Token")
        or request.headers.get("X-CSRFToken")
        or (request.form.get("csrf_token") if request.form else None)
    )

    if not submitted and request.is_json:
        json_data = request.get_json(silent=True)
        if isinstance(json_data, dict):
            submitted = json_data.get("csrf_token")

    expected = session.get("csrf_token")
    if not expected:
        return False, "CSRF token missing from session. Please reload the page."

    if not submitted or not str(submitted).strip():
        return False, "CSRF token missing from request headers or form data."

    if not hmac.compare_digest(str(submitted).strip(), str(expected).strip()):
        return False, "CSRF token invalid."

    return True, ""


def init_csrf(app: Flask) -> None:
    """Register CSRF validation hooks and template context processor on the app."""

    @app.before_request
    def check_csrf():
        # Ensure a CSRF token always exists in session
        generate_csrf_token()

        # If testing and CSRF check is explicitly bypassed in app config, skip
        if app.config.get("TESTING_CSRF_DISABLED", False):
            return None

        # Safe methods (GET, HEAD, OPTIONS, TRACE) do not mutate state
        if request.method in SAFE_METHODS:
            return None

        # For static files, skip
        if request.path.startswith("/static/"):
            return None

        # For health check, skip
        if request.path == "/api/health":
            return None

        # CSRF validation is enforced on:
        # 1. State-changing auth endpoints (/api/auth/login, /api/auth/signup) to prevent Login/Signup CSRF
        # 2. All state-changing requests for authenticated sessions (session["user_id"])
        is_auth_endpoint = request.path in ("/api/auth/login", "/api/auth/signup", "/api/auth/demo-login")
        is_authenticated = bool(session.get("user_id"))

        if not (is_auth_endpoint or is_authenticated):
            # For unauthenticated calls to protected endpoints, defer to @login_required (returns 401/302)
            return None

        # Validate CSRF for all targeted state-changing requests
        valid, err_msg = validate_csrf()
        if not valid:
            if request.path.startswith("/api/"):
                return jsonify({"error": err_msg, "code": "CSRF_ERROR"}), 403
            return (
                f"<!DOCTYPE html><html><head><title>403 Forbidden</title></head>"
                f"<body style='font-family:sans-serif;background:#05070D;color:#EF4444;padding:40px;'>"
                f"<h2>403 Forbidden: CSRF Validation Failed</h2><p>{err_msg}</p>"
                f"<p><a href='/login' style='color:#00F0FF;'>Return to Login</a></p></body></html>",
                403,
            )
        return None

    @app.after_request
    def set_csrf_cookie(response: Response) -> Response:
        """Expose CSRF token in a readable cookie for frontend JavaScript."""
        token = session.get("csrf_token")
        if token:
            response.set_cookie(
                "csrf_token",
                token,
                httponly=False,  # Accessible to frontend JS for X-CSRF-Token header
                samesite="Lax",
                secure=app.config.get("SESSION_COOKIE_SECURE", False),
            )
        return response

    @app.context_processor
    def inject_csrf_token() -> dict[str, Any]:
        """Inject csrf_token into Jinja templates."""
        return {"csrf_token": generate_csrf_token()}
