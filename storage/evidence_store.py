"""
storage/evidence_store.py — CRUD helpers for the ``evidence`` table.

Evidence files are written to ``<UPLOADS_DIR>/<case_id>/<evidence_id>/``
with their original filename preserved (sanitised).  The directory is made
read-only after the file is written so evidence cannot be silently modified.
"""

import hashlib
import json
import os
import shutil
import sqlite3
import stat
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import current_app
from werkzeug.utils import secure_filename

from .database import get_db


# ── Internal helpers ──────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    d = dict(row)
    # Deserialise analysis_json back to dict/list when present
    if d.get("analysis_json") and isinstance(d["analysis_json"], str):
        try:
            d["analysis_json"] = json.loads(d["analysis_json"])
        except (json.JSONDecodeError, TypeError):
            pass
    return d


def _sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sanitise_filename(name: str, max_stem_length: int = 80) -> str:
    """Safely sanitize uploaded filename using Werkzeug's secure_filename.

    Strips directory traversal, replaces invalid characters, and truncates
    overly long stems to prevent Windows MAX_PATH (260 chars) filesystem errors,
    while preserving the file extension and keeping the original filename
    intact in the database metadata.
    """
    path_obj = Path(name)
    raw_name = path_obj.name  # drop any directory traversal component
    ext = Path(raw_name).suffix.lower()
    stem = Path(raw_name).stem

    safe_stem = secure_filename(stem)
    if not safe_stem:
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
        safe_stem = "".join(c if c in allowed else "_" for c in stem).strip("._- ")
        if not safe_stem:
            safe_stem = "evidence"

    # Truncate stem to max_stem_length to prevent Windows MAX_PATH overflows
    safe_stem = safe_stem[:max_stem_length].rstrip("._- ")
    if not safe_stem:
        safe_stem = "evidence"

    safe_ext = secure_filename(ext.lstrip("."))
    if safe_ext:
        return f"{safe_stem}.{safe_ext}"
    elif ext:
        clean_ext = "".join(c for c in ext if c.isalnum() or c == ".")
        return f"{safe_stem}{clean_ext}"
    return safe_stem


def _make_readonly(path: Path) -> None:
    """Remove write permissions from *path* (best-effort)."""
    try:
        current_mode = path.stat().st_mode
        readonly_mode = current_mode & ~(stat.S_IWRITE | stat.S_IWGRP | stat.S_IWOTH)
        path.chmod(readonly_mode)
    except OSError:
        pass  # non-fatal on platforms where chmod is restricted


# ── Public API ────────────────────────────────────────────────────────────────

def save_evidence(
    case_id: str,
    file_data: bytes,
    original_name: str,
    mime_type: str,
    modality: str,
) -> dict[str, Any]:
    """Persist an evidence file and insert its metadata row.

    Parameters
    ----------
    case_id:       The parent case's ID.
    file_data:     Raw bytes of the uploaded file.
    original_name: The original filename as supplied by the client.
    mime_type:     Validated MIME type string.
    modality:      One of ``'image'``, ``'audio'``, or ``'video'``.

    Returns
    -------
    dict representing the inserted evidence row.
    """
    evidence_id = f"ev_{uuid.uuid4().hex[:12]}"
    sha256 = _sha256_of_bytes(file_data)
    now = _now_iso()

    safe_name = _sanitise_filename(original_name)
    from services.storage_service import get_storage_provider
    storage = get_storage_provider()
    storage_key = storage.upload_evidence(
        case_id=case_id,
        evidence_id=evidence_id,
        filename=safe_name,
        file_data=file_data,
        mime_type=mime_type,
    )

    db = get_db()
    db.execute(
        """
        INSERT INTO evidence
          (evidence_id, case_id, filename, original_name, modality,
           mime_type, sha256, file_size, uploaded_at, analysis_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        """,
        (
            evidence_id,
            case_id,
            storage_key,
            original_name,
            modality,
            mime_type,
            sha256,
            len(file_data),
            now,
        ),
    )
    # Touch the parent case's updated_at timestamp
    db.execute(
        "UPDATE cases SET updated_at = ? WHERE case_id = ?",
        (now, case_id),
    )
    db.commit()

    return get_evidence(evidence_id)  # type: ignore[return-value]


def get_evidence(evidence_id: str) -> dict[str, Any] | None:
    """Return a single evidence row as a dict or *None*."""
    db = get_db()
    row = db.execute(
        "SELECT * FROM evidence WHERE evidence_id = ?", (evidence_id,)
    ).fetchone()
    return _row_to_dict(row)


def list_evidence(case_id: str) -> list[dict[str, Any]]:
    """Return all evidence rows for *case_id* ordered by upload time."""
    db = get_db()
    rows = db.execute(
        "SELECT * FROM evidence WHERE case_id = ? ORDER BY uploaded_at ASC",
        (case_id,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]  # type: ignore[misc]


def update_analysis(
    evidence_id: str,
    status: str,
    analysis_data: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Update the analysis_status and optional analysis_json for an evidence item."""
    db = get_db()
    analysis_json = json.dumps(analysis_data) if analysis_data is not None else None
    db.execute(
        """
        UPDATE evidence
        SET analysis_status = ?, analysis_json = ?
        WHERE evidence_id = ?
        """,
        (status, analysis_json, evidence_id),
    )
    db.commit()
    return get_evidence(evidence_id)


def delete_evidence(evidence_id: str) -> bool:
    """Delete an evidence item from SQLite and clean up its files from disk.

    Returns True if the evidence existed and was removed, False otherwise.
    """
    db = get_db()
    row = db.execute("SELECT * FROM evidence WHERE evidence_id = ?", (evidence_id,)).fetchone()
    if row is None:
        return False

    case_id = row["case_id"]

    # Delete database record
    db.execute("DELETE FROM evidence WHERE evidence_id = ?", (evidence_id,))
    now = _now_iso()
    db.execute("UPDATE cases SET updated_at = ? WHERE case_id = ?", (now, case_id))
    db.commit()

    # Best-effort file and directory removal on storage provider
    try:
        from services.storage_service import get_storage_provider
        get_storage_provider().delete_evidence(case_id, evidence_id, storage_key=row.get("filename"))
    except Exception as exc:
        try:
            current_app.logger.warning(
                f"Failed to delete storage for evidence {evidence_id}: {exc}"
            )
        except Exception:
            pass

    return True

