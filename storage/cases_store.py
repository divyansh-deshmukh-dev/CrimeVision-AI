"""
storage/cases_store.py — CRUD helpers for the ``cases`` table.
"""

from datetime import datetime, timezone
import sqlite3
from typing import Any
import uuid

from .database import get_db


# ── Internal helpers ──────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


# ── Public API ────────────────────────────────────────────────────────────────

def is_legacy_demo_case(case: dict[str, Any] | None) -> bool:
    """Return True if the case is the shared, read-only legacy demonstration case."""
    if not case:
        return False
    if case.get("case_id") == "case_demo_sentinel":
        return True
    if case.get("demo_type") == "legacy":
        return True
    return False


def is_live_demo_case(case: dict[str, Any] | None) -> bool:
    """Return True if the case is a writable live-demo investigation workspace."""
    if not case:
        return False
    return case.get("demo_type") == "live"


def create_case(
    name: str,
    description: str = "",
    is_demo: bool = False,
    case_id: str | None = None,
    user_id: str | None = None,
    demo_type: str | None = None,
) -> dict[str, Any]:
    """Insert a new case row with ownership and return it as a dict.

    Parameters
    ----------
    name:        Human-readable case name.
    description: Optional free-text description.
    is_demo:     If *True* the case is flagged as the demo sample case.
    case_id:     Optional explicit ID (used when seeding the demo case).
    user_id:     ID of the owning user (None for unowned/system cases).
    demo_type:   Classification: 'legacy', 'live', or None for normal user cases.
    """
    now = _now_iso()
    cid = case_id or f"case_{uuid.uuid4().hex[:12]}"

    db = get_db()
    db.execute(
        """
        INSERT INTO cases (case_id, user_id, name, description, created_at, updated_at, status, is_demo, demo_type)
        VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)
        """,
        (cid, user_id, name, description, now, now, int(is_demo), demo_type),
    )
    db.commit()

    return get_case(cid)  # type: ignore[return-value]


def get_case(case_id: str) -> dict[str, Any] | None:
    """Return a case dict or *None* if not found."""
    db = get_db()
    row = db.execute(
        "SELECT * FROM cases WHERE case_id = ?", (case_id,)
    ).fetchone()
    return _row_to_dict(row)


def list_cases(
    user_id: str | None = None,
    is_admin: bool = False,
    include_demo: bool = True,
) -> list[dict[str, Any]]:
    """Return cases accessible to the given user or administrator.

    Parameters
    ----------
    user_id:      Current authenticated user ID.
    is_admin:     If True, returns all cases.
    include_demo: Whether to include the public demo case.
    """
    db = get_db()
    if is_admin:
        # Administrators have visibility across all cases
        if include_demo:
            rows = db.execute("SELECT * FROM cases ORDER BY created_at DESC").fetchall()
        else:
            rows = db.execute("SELECT * FROM cases WHERE is_demo = 0 ORDER BY created_at DESC").fetchall()
    elif user_id is not None:
        # Ordinary authenticated user sees only cases they own + the public demo case
        if include_demo:
            rows = db.execute(
                "SELECT * FROM cases WHERE user_id = ? OR is_demo = 1 ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM cases WHERE user_id = ? AND is_demo = 0 ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
    else:
        # Unauthenticated / unscoped call: return ONLY demo cases (never private or unowned legacy cases)
        if include_demo:
            rows = db.execute("SELECT * FROM cases WHERE is_demo = 1 ORDER BY created_at DESC").fetchall()
        else:
            rows = []

    return [dict(r) for r in rows]


def update_case(
    case_id: str,
    name: str | None = None,
    description: str | None = None,
    status: str | None = None,
) -> dict[str, Any] | None:
    """Partial-update a case row.  Returns the updated case or *None*."""
    existing = get_case(case_id)
    if existing is None:
        return None

    name = name if name is not None else existing["name"]
    description = description if description is not None else existing["description"]
    status = status if status is not None else existing["status"]
    now = _now_iso()

    db = get_db()
    db.execute(
        """
        UPDATE cases
        SET name = ?, description = ?, status = ?, updated_at = ?
        WHERE case_id = ?
        """,
        (name, description, status, now, case_id),
    )
    db.commit()
    return get_case(case_id)


def delete_case(case_id: str) -> bool:
    """Delete a case and its cascade relations."""
    db = get_db()
    # Delete child records
    db.execute("DELETE FROM chat_messages WHERE case_id = ?", (case_id,))
    db.execute("DELETE FROM reports WHERE case_id = ?", (case_id,))
    db.execute("DELETE FROM evidence WHERE case_id = ?", (case_id,))
    cur = db.execute("DELETE FROM cases WHERE case_id = ?", (case_id,))
    db.commit()
    return cur.rowcount > 0
