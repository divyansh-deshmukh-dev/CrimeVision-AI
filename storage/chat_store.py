"""
storage/chat_store.py — CRUD helpers for the ``chat_messages`` table.

Stores user queries and assistant responses associated with specific cases,
including structured citations, confidence metrics, and limitations metadata.
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from .database import get_db


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    d = dict(row)
    if d.get("metadata_json") and isinstance(d["metadata_json"], str):
        try:
            d["metadata"] = json.loads(d["metadata_json"])
        except (json.JSONDecodeError, TypeError):
            d["metadata"] = None
    else:
        d["metadata"] = None
    return d


def save_message(
    case_id: str,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
    message_id: str | None = None,
) -> dict[str, Any]:
    """Persist a chat message for a given case."""
    msg_id = message_id or f"msg_{uuid.uuid4().hex[:12]}"
    created_at = _now_iso()
    meta_json = json.dumps(metadata) if metadata is not None else None

    db = get_db()
    db.execute(
        """
        INSERT INTO chat_messages (message_id, case_id, role, content, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?);
        """,
        (msg_id, case_id, role, content, meta_json, created_at),
    )
    db.commit()

    return {
        "message_id": msg_id,
        "case_id": case_id,
        "role": role,
        "content": content,
        "metadata": metadata,
        "created_at": created_at,
    }


def list_messages(case_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Retrieve chronologically ordered chat messages for a case."""
    db = get_db()
    # Fetch in descending order by created_at, then reverse to return chronological order
    rows = db.execute(
        """
        SELECT message_id, case_id, role, content, metadata_json, created_at
        FROM chat_messages
        WHERE case_id = ?
        ORDER BY created_at ASC
        LIMIT ?;
        """,
        (case_id, max(1, limit)),
    ).fetchall()
    return [_row_to_dict(r) for r in rows if r is not None]


def clear_messages(case_id: str) -> int:
    """Delete all chat messages for a given case. Returns count of deleted messages."""
    db = get_db()
    cursor = db.execute(
        "DELETE FROM chat_messages WHERE case_id = ?;",
        (case_id,),
    )
    db.commit()
    return cursor.rowcount
