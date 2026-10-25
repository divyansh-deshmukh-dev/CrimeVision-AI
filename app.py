"""
app.py — CrimeVision AI Flask application entry point.

Creates and configures the Flask app, wires blueprints, initialises the
database, and provides a ``create_app()`` factory used by both the
development server and pytest.
"""

import os
from pathlib import Path
import sys

from flask import Flask, jsonify, render_template

from config import get_config, load_environment, validate_production_secret
from services.auth_service import get_current_user, login_required
from services.csrf import init_csrf
from storage.database import close_db, init_db


def create_app(config_override: dict | None = None) -> Flask:
    """Application factory.

    Parameters
    ----------
    config_override:
        Optional dict of config values that will overwrite the loaded
        configuration.  Primarily used by tests.
    """
    # Ensure .env is freshly loaded before reading configuration
    load_environment()

    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    # ── Configuration ─────────────────────────────────────────────────────────
    cfg_class = get_config()
    app.config.from_object(cfg_class)

    # Sync live environment variables into app.config so runtime updates take effect
    for env_key in ("GEMINI_API_KEY", "GEMINI_MODEL", "AI_PROVIDER", "GROQ_API_KEY"):
        val = os.getenv(env_key)
        if val is not None:
            app.config[env_key] = val

    if config_override:
        app.config.update(config_override)

    # Convert Path objects to Path (from_object may not preserve type)
    for key in ("STORAGE_DIR", "CASES_DIR", "UPLOADS_DIR", "REPORTS_DIR", "DB_PATH"):
        value = app.config.get(key)
        if value is not None and not isinstance(value, Path):
            app.config[key] = Path(value)

    # ── Storage directories ───────────────────────────────────────────────────
    for key in ("STORAGE_DIR", "CASES_DIR", "UPLOADS_DIR", "REPORTS_DIR"):
        try:
            app.config[key].mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

    # ── Session & Security Configuration ──────────────────────────────────────
    is_prod = (
        not (app.config.get("DEBUG") or app.config.get("TESTING"))
        or os.getenv("FLASK_ENV", "").lower() == "production"
    )
    if is_prod:
        validate_production_secret(app.config.get("SECRET_KEY"))

    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    is_secure = app.config.get("SESSION_COOKIE_SECURE", False)
    if not (app.config.get("DEBUG") or app.config.get("TESTING")):
        # In production, default to secure cookies unless explicitly overridden
        app.config["SESSION_COOKIE_SECURE"] = is_secure
    app.config.setdefault("PERMANENT_SESSION_LIFETIME", 86400)

    # ── CSRF Protection ───────────────────────────────────────────────────────
    init_csrf(app)

    # ── Database & Seed Provisioning ──────────────────────────────────────────
    with app.app_context():
        init_db(app.config["DB_PATH"])
        try:
            from storage.provision_demo import ensure_demo_evaluator
            ensure_demo_evaluator()
        except Exception as exc:  # noqa: BLE001
            app.logger.warning("Could not auto-provision demo evaluator on startup: %s", exc)

    app.teardown_appcontext(close_db)

    # ── Context Processors ────────────────────────────────────────────────────
    @app.context_processor
    def inject_auth_context():
        """Expose current_user and authentication state to all templates."""
        return {"current_user": get_current_user()}

    # ── Blueprints ────────────────────────────────────────────────────────────
    from routes.health import health_bp
    from routes.cases import cases_bp
    from routes.auth import auth_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(cases_bp)
    app.register_blueprint(auth_bp)

    # ── Frontend routes ───────────────────────────────────────────────────────
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/workspace")
    @login_required
    def workspace():
        return render_template("workspace.html")

    # ── Global error handlers ─────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(exc):  # noqa: ARG001
        return jsonify({"error": "Resource not found."}), 404

    @app.errorhandler(405)
    def method_not_allowed(exc):  # noqa: ARG001
        return jsonify({"error": "Method not allowed."}), 405

    @app.errorhandler(413)
    def request_entity_too_large(exc):  # noqa: ARG001
        return jsonify({"error": "File too large."}), 413

    @app.errorhandler(500)
    def internal_error(exc):
        app.logger.exception("Unhandled exception: %s", exc)
        return jsonify({"error": "Internal server error."}), 500

    return app


# ── Development server entry point ────────────────────────────────────────────
if __name__ == "__main__":
    flask_app = create_app()
    port = flask_app.config.get("PORT", 5000)
    host = flask_app.config.get("HOST", "0.0.0.0")
    debug = flask_app.config.get("DEBUG", False)

    print(f"[CrimeVision AI] Starting on http://{host}:{port}  debug={debug}")
    flask_app.run(host=host, port=port, debug=debug)
