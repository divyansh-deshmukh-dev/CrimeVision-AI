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
    for key in ("STORAGE_DIR", "CASES_DIR", "UPLOADS_DIR", "REPORTS_DIR"):
        path = current_app.config[key]
        checks[key.lower()] = "ok" if path.is_dir() else "missing"
        if not path.is_dir():
            status = "degraded"

    # ── AI API keys ──────────────────────────────────────────────────────────
    groq_key = current_app.config.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
    checks["groq_api_key"] = "configured" if (groq_key and groq_key.strip()) else "not_configured"
    gemini_key = current_app.config.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
    checks["gemini_api_key"] = "configured" if (gemini_key and gemini_key.strip()) else "not_configured"

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
        200 if status == "ok" else 207,
    )
