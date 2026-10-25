"""
routes/health.py — Health-check endpoint.

GET /api/health
    Returns service status, version, Groq API key presence, and DB
    connectivity so that a single curl call can verify the whole stack.
"""

import os
import sqlite3
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify

from storage.database import get_db

health_bp = Blueprint("health", __name__)


@health_bp.route("/api/health", methods=["GET"])
def health_check():
    """Return a JSON health-status payload."""
    status = "ok"
    checks: dict = {}

    # ── Database connectivity ─────────────────────────────────────────────────
    try:
        db = get_db()
        db.execute("SELECT 1").fetchone()
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc}"
        status = "degraded"

    # ── Storage directories ───────────────────────────────────────────────────
    from pathlib import Path

    for key in ("STORAGE_DIR", "CASES_DIR", "UPLOADS_DIR", "REPORTS_DIR"):
        raw_path = current_app.config.get(key)
        if raw_path is None:
            checks[key.lower()] = "missing"
            status = "degraded"
            continue
        try:
            p = Path(raw_path)
            is_d = p.is_dir()
            checks[key.lower()] = "ok" if is_d else "missing"
            if not is_d:
                status = "degraded"
        except Exception as exc:  # noqa: BLE001
            checks[key.lower()] = f"error: {exc}"
            status = "degraded"

    # ── AI API keys ──────────────────────────────────────────────────────────
    groq_key = current_app.config.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
    checks["groq_api_key"] = "configured" if (groq_key and groq_key.strip()) else "not_configured"
    gemini_key = current_app.config.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
    checks["gemini_api_key"] = "configured" if (gemini_key and gemini_key.strip()) else "not_configured"

    # ── Core AI Engine (PyTorch / Vision Runtime) ─────────────────────────────
    try:
        import torch
        import transformers
        checks["torch"] = f"available ({torch.__version__})"
        checks["ai_engine"] = "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError as exc:  # noqa: BLE001
        checks["torch"] = "not_installed"
        checks["ai_engine"] = f"unavailable: {exc}"

    return (
        jsonify(
            {
                "status": status,
                "service": "CrimeVision AI",
                "version": "1.0.0-phase1",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "checks": checks,
            }
        ),
        200,
    )
