"""
routes/auth.py — Authentication and user session endpoints.

Provides public registration (/signup), login (/login), session termination (/logout),
current-user inspection (/api/auth/me), and CSRF token retrieval (/api/auth/csrf).
"""

import secrets
from typing import Any

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for

from services.auth_service import get_current_user
from services.csrf import generate_csrf_token
from services.rate_limiter import get_client_ip, login_limiter
from storage.users_store import authenticate_user, create_user

auth_bp = Blueprint("auth", __name__)


# ── UI Auth Pages ─────────────────────────────────────────────────────────────

@auth_bp.route("/signup", methods=["GET"])
def signup_page():
    """Render user registration page or redirect if already authenticated."""
    if get_current_user() is not None:
        return redirect(url_for("workspace"))
    return render_template("signup.html", csrf_token=generate_csrf_token())


@auth_bp.route("/login", methods=["GET"])
def login_page():
    """Render user login page or redirect if already authenticated."""
    if get_current_user() is not None:
        next_url = request.args.get("next") or url_for("workspace")
        return redirect(next_url)
    return render_template("login.html", csrf_token=generate_csrf_token())


# ── API Auth Endpoints ────────────────────────────────────────────────────────

@auth_bp.route("/api/auth/csrf", methods=["GET"])
def get_csrf_token_endpoint():
    """Return the session CSRF token for AJAX clients."""
    return jsonify({"csrf_token": generate_csrf_token()}), 200


@auth_bp.route("/api/auth/signup", methods=["POST"])
def signup_endpoint():
    """Register a new user account."""
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    display_name = (data.get("display_name") or username).strip()

    try:
        user = create_user(
            username=username,
            email=email,
            password=password,
            display_name=display_name,
            role="user",  # Public registration always grants standard 'user' role
        )
    except ValueError as exc:
        return jsonify({"error": str(exc), "code": "VALIDATION_ERROR"}), 400
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Unexpected error during signup")
        return jsonify({"error": "Failed to create account. Please try again.", "code": "SERVER_ERROR"}), 500

    # Auto-login upon successful registration
    session.clear()
    session["user_id"] = user["user_id"]
    session["username"] = user["username"]
    session["role"] = user["role"]
    session["display_name"] = user.get("display_name") or user["username"]
    session["csrf_token"] = secrets.token_hex(32)
    session.permanent = True

    return jsonify({"status": "created", "user": user}), 201


@auth_bp.route("/api/auth/login", methods=["POST"])
def login_endpoint():
    """Authenticate user credentials and create a session."""
    data = request.get_json(silent=True) or {}
    ident = (data.get("username") or data.get("email") or "").strip()
    password = data.get("password") or ""

    if not ident or not password:
        return jsonify({"error": "Username/email and password are required.", "code": "MISSING_CREDENTIALS"}), 400

    ip = get_client_ip()
    ip_key = f"ip:{ip}"
    user_key = f"user:{ident.lower()}"

    # Rate limiting check
    if login_limiter.is_rate_limited(ip_key) or login_limiter.is_rate_limited(user_key):
        retry_after = max(login_limiter.get_retry_after(ip_key), login_limiter.get_retry_after(user_key))
        return (
            jsonify({
                "error": "Too many failed login attempts. Please try again later.",
                "code": "RATE_LIMITED",
                "retry_after": retry_after,
            }),
            429,
            {"Retry-After": str(retry_after)},
        )

    user = authenticate_user(ident, password)
    if user is None:
        login_limiter.record_failure(ip_key)
        login_limiter.record_failure(user_key)
        return jsonify({"error": "Invalid username or password.", "code": "INVALID_CREDENTIALS"}), 401

    # Successful authentication — reset rate limiters
    login_limiter.record_success(ip_key)
    login_limiter.record_success(user_key)

    # Regenerate session (prevents session fixation)
    session.clear()
    session["user_id"] = user["user_id"]
    session["username"] = user["username"]
    session["role"] = user["role"]
    session["display_name"] = user.get("display_name") or user["username"]
    session["csrf_token"] = secrets.token_hex(32)
    session.permanent = True

    return jsonify({"status": "authenticated", "user": user}), 200


@auth_bp.route("/api/auth/demo-login", methods=["POST"])
def demo_login_endpoint():
    """Authenticate into the read-only mentor demo account with zero password exposure."""
    demo_enabled = current_app.config.get("DEMO_LOGIN_ENABLED")
    if demo_enabled is None:
        import os
        demo_enabled = os.getenv("DEMO_LOGIN_ENABLED", "1").lower() in ("1", "true", "yes")

    if not demo_enabled:
        return jsonify({"error": "Mentor demo access is currently disabled.", "code": "DEMO_DISABLED"}), 403

    ip = get_client_ip()
    ip_key = f"ip:{ip}"
    if login_limiter.is_rate_limited(ip_key):
        retry_after = login_limiter.get_retry_after(ip_key)
        return (
            jsonify({
                "error": "Too many failed attempts. Please try again later.",
                "code": "RATE_LIMITED",
                "retry_after": retry_after,
            }),
            429,
            {"Retry-After": str(retry_after)},
        )

    import os
    demo_username = (os.getenv("DEMO_USERNAME") or "demo_mentor").strip().lower()
    from storage.users_store import get_user_by_username
    demo_user = get_user_by_username(demo_username)

    if not demo_user:
        # Fallback query by role or is_demo
        from storage.database import get_db
        db = get_db()
        row = db.execute(
            "SELECT user_id, display_name, username, email, role, created_at, is_active, is_demo FROM users WHERE role = 'demo' OR is_demo = 1 LIMIT 1"
        ).fetchone()
        if row:
            from storage.users_store import _row_to_dict
            demo_user = _row_to_dict(row)

    if not demo_user:
        # Auto-provision if in non-production or explicitly allowed
        try:
            from storage.provision_demo import provision_demo_account
            prov_res = provision_demo_account(username=demo_username)
            demo_user = get_user_by_username(prov_res["username"])
        except Exception as exc:
            current_app.logger.exception("Failed to auto-provision demo user: %s", exc)

    if not demo_user or not demo_user.get("is_active"):
        return jsonify({
            "error": "Demo account is currently unavailable. Please run 'python provision_demo.py' to provision it.",
            "code": "DEMO_UNAVAILABLE",
        }), 503

    # Successful demo authentication — regenerate session
    session.clear()
    session["user_id"] = demo_user["user_id"]
    session["username"] = demo_user["username"]
    session["role"] = "demo"
    session["is_demo"] = True
    session["display_name"] = demo_user.get("display_name") or "Mentor Demo Examiner"
    session["csrf_token"] = secrets.token_hex(32)
    session.permanent = True

    return jsonify({"status": "authenticated", "user": demo_user, "is_demo": True}), 200


@auth_bp.route("/api/auth/logout", methods=["POST"])
def logout_endpoint():
    """Terminate the authenticated session."""
    session.clear()
    session["csrf_token"] = secrets.token_hex(32)
    return jsonify({"status": "logged_out"}), 200


@auth_bp.route("/api/auth/me", methods=["GET"])
def current_user_endpoint():
    """Return profile information for the currently authenticated user."""
    user = get_current_user()
    if user is None:
        return jsonify({"error": "Authentication required.", "code": "UNAUTHENTICATED"}), 401

    return jsonify({"user": user}), 200
