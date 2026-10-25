"""
services/auth_service.py — Centralized authentication and case authorization utilities.

Provides view decorators and helper functions to enforce authentication,
role-based access control, and strict case ownership checks (IDOR mitigation).
"""

from functools import wraps
from typing import Any, Callable

from flask import g, jsonify, redirect, request, session, url_for

from storage.cases_store import get_case
from storage.users_store import get_user_by_id


def get_current_user() -> dict[str, Any] | None:
    """Retrieve the authenticated user for the current request context."""
    uid = session.get("user_id")
    if not uid:
        g._current_user = None
        return None

    if hasattr(g, "_current_user") and g._current_user and g._current_user.get("user_id") == uid:
        return g._current_user

    user = get_user_by_id(uid)
    if not user or not user.get("is_active"):
        # Inactive or deleted user session — invalidate
        session.clear()
        g._current_user = None
        return None

    g._current_user = user
    return user


def login_required(view_func: Callable) -> Callable:
    """Ensure the user is authenticated before accessing the view.

    Returns 401 JSON error for API requests, or redirects to /login for HTML requests.
    """
    @wraps(view_func)
    def decorated_view(*args: Any, **kwargs: Any):
        user = get_current_user()
        if user is None:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required.", "code": "UNAUTHENTICATED"}), 401
            return redirect(url_for("auth.login_page", next=request.path))
        return view_func(*args, **kwargs)

    return decorated_view


def admin_required(view_func: Callable) -> Callable:
    """Ensure the authenticated user holds the administrator role."""
    @wraps(view_func)
    def decorated_view(*args: Any, **kwargs: Any):
        user = get_current_user()
        if user is None:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required.", "code": "UNAUTHENTICATED"}), 401
            return redirect(url_for("auth.login_page", next=request.path))

        if user.get("role") != "admin":
            if request.path.startswith("/api/"):
                return jsonify({"error": "Administrator privilege required.", "code": "FORBIDDEN"}), 403
            return (
                "<!DOCTYPE html><html><head><title>403 Forbidden</title></head>"
                "<body style='font-family:sans-serif;background:#05070D;color:#EF4444;padding:40px;'>"
                "<h2>403 Forbidden</h2><p>Administrator privilege required to access this resource.</p>"
                "<p><a href='/workspace' style='color:#00F0FF;'>Return to Workspace</a></p></body></html>",
                403,
            )

        return view_func(*args, **kwargs)

    return decorated_view


def verify_case_access(case_id: str, write: bool = False) -> tuple[dict[str, Any] | None, tuple[Any, int] | None]:
    """Verify that the current user is authorized to access the specified case.

    Parameters
    ----------
    case_id: The ID of the case to verify.
    write:   Whether the requested action modifies case data (write/delete/analyze).

    Returns
    -------
    (case_dict, None) if authorized.
    (None, (json_response, status_code)) if unauthorized or case not found.
    """
    case = get_case(case_id)
    if case is None:
        return None, (jsonify({"error": f"Case '{case_id}' not found.", "code": "CASE_NOT_FOUND"}), 404)

    user = get_current_user()
    if user is None:
        return None, (jsonify({"error": "Authentication required.", "code": "UNAUTHENTICATED"}), 401)

    is_admin = user.get("role") == "admin"
    is_legacy_case = case.get("case_id") == "case_demo_sentinel" or case.get("demo_type") == "legacy"
    is_owner = case.get("user_id") is not None and case.get("user_id") == user.get("user_id")

    # Administrator has full access to all cases
    if is_admin:
        return case, None

    # The legacy demo sample case is strictly read-only for all non-admins
    if is_legacy_case:
        if write:
            return None, (
                jsonify({
                    "error": "The legacy demo sample case is read-only. To upload evidence and run live inference, use your writable live-demo workspace or create a new case.",
                    "code": "DEMO_CASE_READ_ONLY",
                }),
                403,
            )
        # Allow read access to legacy demo for all authenticated users
        return case, None

    # Owner has full access to their own case (both normal users and demo users on live-demo cases)
    if is_owner:
        return case, None

    # Unowned legacy cases or private cases owned by another user: FORBIDDEN
    return None, (
        jsonify({"error": "Access denied. You do not have permission to access this case.", "code": "FORBIDDEN"}),
        403,
    )
