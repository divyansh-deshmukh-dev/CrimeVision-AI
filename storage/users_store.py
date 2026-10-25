"""
storage/users_store.py — User management, validation, and credentials persistence.

Handles user creation, secure password hashing via Werkzeug (scrypt),
normalization, and lookup queries against the ``users`` SQLite table.
"""

from datetime import datetime, timezone
import re
import sqlite3
from typing import Any
import uuid

from werkzeug.security import check_password_hash, generate_password_hash

from .database import get_db

# ── Validation Regexes ────────────────────────────────────────────────────────
_USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_-]{3,30}$")
_EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    d = dict(row)
    # Never return password_hash through standard dictionary conversions
    d.pop("password_hash", None)
    return d


def validate_username(username: str) -> tuple[bool, str]:
    """Validate username format and length."""
    u = (username or "").strip()
    if not u:
        return False, "Username is required."
    if len(u) < 3 or len(u) > 30:
        return False, "Username must be between 3 and 30 characters."
    if not _USERNAME_REGEX.match(u):
        return False, "Username can only contain letters, numbers, underscores, and hyphens."
    return True, ""


def validate_email(email: str) -> tuple[bool, str]:
    """Validate email format."""
    e = (email or "").strip().lower()
    if not e:
        return False, "Email address is required."
    if len(e) > 120 or not _EMAIL_REGEX.match(e):
        return False, "Invalid email address format."
    return True, ""


def validate_password(password: str) -> tuple[bool, str]:
    """Validate password complexity requirements."""
    p = password or ""
    if len(p) < 8:
        return False, "Password must be at least 8 characters long."
    if len(p) > 128:
        return False, "Password must not exceed 128 characters."
    has_letter = any(c.isalpha() for c in p)
    has_digit_or_symbol = any(not c.isalpha() for c in p)
    if not (has_letter and has_digit_or_symbol):
        return False, "Password must contain at least one letter and at least one number or symbol."
    return True, ""


# ── Public User API ───────────────────────────────────────────────────────────

def create_user(
    username: str,
    email: str,
    password: str,
    display_name: str = "",
    role: str = "user",
    user_id: str | None = None,
    is_active: bool = True,
    is_demo: bool = False,
) -> dict[str, Any]:
    """Create a new user with securely hashed password.

    Parameters
    ----------
    username:     Unique login handle (normalized to lowercase).
    email:        Unique email address (normalized to lowercase).
    password:     Plaintext password to be hashed via scrypt.
    display_name: Human-readable name.
    role:         'user', 'admin', or 'demo' (defaults to 'user').
    user_id:      Optional explicit ID (e.g. for testing/migration).
    is_active:    Active status flag.
    is_demo:      Whether this account is a read-only demo account.
    """
    valid_u, err_u = validate_username(username)
    if not valid_u:
        raise ValueError(err_u)

    valid_e, err_e = validate_email(email)
    if not valid_e:
        raise ValueError(err_e)

    valid_p, err_p = validate_password(password)
    if not valid_p:
        raise ValueError(err_p)

    norm_username = username.strip().lower()
    norm_email = email.strip().lower()
    norm_display = (display_name or username).strip()
    norm_role = role if role in ("admin", "demo") else "user"

    now = _now_iso()
    uid = user_id or f"usr_{uuid.uuid4().hex[:12]}"
    pwd_hash = generate_password_hash(password, method="scrypt")

    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO users (user_id, display_name, username, email, password_hash, role, created_at, is_active, is_demo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (uid, norm_display, norm_username, norm_email, pwd_hash, norm_role, now, int(is_active), int(is_demo)),
        )
        db.commit()
    except Exception as exc:
        err_msg = str(exc).lower()
        if "username" in err_msg:
            raise ValueError(f"Username '{norm_username}' is already taken.") from exc
        if "email" in err_msg:
            raise ValueError(f"Email '{norm_email}' is already registered.") from exc
        if "unique" in err_msg or "integrity" in err_msg or "duplicate key" in err_msg:
            raise ValueError("A user with these credentials already exists.") from exc
        raise exc

    user = get_user_by_id(uid)
    if user is None:
        raise RuntimeError("User was created but could not be retrieved.")
    return user


def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    """Retrieve user by user_id without exposing password_hash."""
    db = get_db()
    row = db.execute(
        "SELECT user_id, display_name, username, email, role, created_at, is_active, is_demo FROM users WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    return _row_to_dict(row)


def get_user_by_username(username: str) -> dict[str, Any] | None:
    """Retrieve user by username (case-insensitive) without password_hash."""
    db = get_db()
    row = db.execute(
        "SELECT user_id, display_name, username, email, role, created_at, is_active, is_demo FROM users WHERE username = ?",
        ((username or "").strip().lower(),),
    ).fetchone()
    return _row_to_dict(row)


def get_user_by_email(email: str) -> dict[str, Any] | None:
    """Retrieve user by email (case-insensitive) without password_hash."""
    db = get_db()
    row = db.execute(
        "SELECT user_id, display_name, username, email, role, created_at, is_active, is_demo FROM users WHERE email = ?",
        ((email or "").strip().lower(),),
    ).fetchone()
    return _row_to_dict(row)


def ensure_user(
    username: str,
    email: str,
    password: str,
    display_name: str = "",
    role: str = "user",
    user_id: str | None = None,
) -> tuple[dict[str, Any], bool]:
    """Ensure a user exists idempotently without modifying existing accounts or passwords.

    Parameters
    ----------
    username:     Login username.
    email:        Account email.
    password:     Password to use only if account must be created.
    display_name: Display name.
    role:         User role ('user' | 'admin' | 'demo').
    user_id:      Optional explicit ID.

    Returns
    -------
    tuple[dict, bool]: (user_dict, created_flag)
    """
    existing = get_user_by_username(username)
    if existing is not None:
        return existing, False

    new_user = create_user(
        username=username,
        email=email,
        password=password,
        display_name=display_name or username,
        role=role,
        user_id=user_id,
    )
    return new_user, True


def authenticate_user(username_or_email: str, password: str) -> dict[str, Any] | None:
    """Verify credentials and return user dict if valid and active, else None."""
    ident = (username_or_email or "").strip().lower()
    if not ident or not password:
        return None

    db = get_db()
    # Check by username or email
    row = db.execute(
        "SELECT user_id, display_name, username, email, password_hash, role, created_at, is_active, is_demo FROM users WHERE username = ? OR email = ?",
        (ident, ident),
    ).fetchone()

    if row is None:
        return None

    if not check_password_hash(row["password_hash"], password):
        return None

    if not row["is_active"]:
        return None

    return _row_to_dict(row)


def count_users() -> int:
    """Return total number of registered users."""
    db = get_db()
    row = db.execute("SELECT COUNT(*) FROM users").fetchone()
    return row[0] if row else 0


def list_users(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    """List users without password hashes (administrative query)."""
    db = get_db()
    rows = db.execute(
        """
        SELECT user_id, display_name, username, email, role, created_at, is_active, is_demo
        FROM users
        ORDER BY created_at ASC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ).fetchall()
    return [dict(r) for r in rows]


def set_user_role(user_id: str, role: str) -> bool:
    """Update role for a user ('user' or 'admin')."""
    if role not in ("user", "admin"):
        raise ValueError("Invalid role. Must be 'user' or 'admin'.")
    db = get_db()
    cur = db.execute("UPDATE users SET role = ? WHERE user_id = ?", (role, user_id))
    db.commit()
    return cur.rowcount > 0


def set_user_active(user_id: str, is_active: bool) -> bool:
    """Enable or disable user account."""
    db = get_db()
    cur = db.execute("UPDATE users SET is_active = ? WHERE user_id = ?", (int(is_active), user_id))
    db.commit()
    return cur.rowcount > 0


def assign_case_owner(case_id: str, user_id: str | None) -> bool:
    """Assign or reassign ownership of a case (e.g. legacy case migration)."""
    db = get_db()
    cur = db.execute("UPDATE cases SET user_id = ? WHERE case_id = ?", (user_id, case_id))
    db.commit()
    return cur.rowcount > 0
