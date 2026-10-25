"""
storage/reports_store.py — CRUD helpers for the ``reports`` table.
"""

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .database import get_db


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: sqlite3.Row | None) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    return dict(row)


def create_report(
    case_id: str,
    filename: str,
    file_size: int = 0,
    report_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Insert a report record and return it."""
    rid = report_id or f"rep_{uuid.uuid4().hex[:12]}"
    now = _now_iso()

    db = get_db()
    db.execute(
        """
        INSERT INTO reports (report_id, case_id, filename, created_at, file_size)
        VALUES (?, ?, ?, ?, ?)
        """,
        (rid, case_id, filename, now, file_size),
    )
    db.commit()

    return get_report(rid)  # type: ignore[return-value]


def get_report(report_id: str) -> Optional[Dict[str, Any]]:
    """Return a single report row or None."""
    db = get_db()
    row = db.execute(
        "SELECT * FROM reports WHERE report_id = ?", (report_id,)
    ).fetchone()
    return _row_to_dict(row)


def list_reports(case_id: str) -> List[Dict[str, Any]]:
    """Return all reports generated for a given case."""
    db = get_db()
    rows = db.execute(
        "SELECT * FROM reports WHERE case_id = ? ORDER BY created_at DESC",
        (case_id,),
    ).fetchall()
    return [dict(r) for r in rows]
