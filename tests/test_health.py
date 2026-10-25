"""
tests/test_health.py — Tests for GET /api/health.
"""

import pytest


class TestHealthEndpoint:
    """Tests for the /api/health endpoint."""

    def test_health_returns_200(self, client):
        """Health check must return HTTP 200 when everything is healthy."""
        resp = client.get("/api/health")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_health_json_structure(self, client):
        """Health response must contain required top-level keys."""
        data = client.get("/api/health").get_json()
        assert "status" in data, "'status' key missing"
        assert "service" in data, "'service' key missing"
        assert "version" in data, "'version' key missing"
        assert "timestamp" in data, "'timestamp' key missing"
        assert "checks" in data, "'checks' key missing"

    def test_health_service_name(self, client):
        """Service name must identify CrimeVision AI."""
        data = client.get("/api/health").get_json()
        assert data["service"] == "CrimeVision AI"

    def test_health_checks_database(self, client):
        """Health checks dict must report database status."""
        data = client.get("/api/health").get_json()
        assert "database" in data["checks"], "'database' key missing from checks"
        assert data["checks"]["database"] == "ok"

    def test_health_checks_storage_dirs(self, client):
        """Health checks must report all four storage directory statuses."""
        data = client.get("/api/health").get_json()
        checks = data["checks"]
        for key in ("storage_dir", "cases_dir", "uploads_dir", "reports_dir"):
            assert key in checks, f"'{key}' key missing from health checks"
            assert checks[key] == "ok", f"'{key}' is not 'ok': {checks[key]}"

    def test_health_groq_key_absent(self, client):
        """Without GROQ_API_KEY, health must report 'not_configured' (not an error)."""
        with pytest.MonkeyPatch.context() as mp:
            mp.delenv("GROQ_API_KEY", raising=False)
            client.application.config["GROQ_API_KEY"] = None
            data = client.get("/api/health").get_json()
            assert data["checks"].get("groq_api_key") == "not_configured"

    def test_health_gemini_key_absent(self, client):
        """Without GEMINI_API_KEY, health must report 'not_configured'."""
        with pytest.MonkeyPatch.context() as mp:
            mp.delenv("GEMINI_API_KEY", raising=False)
            client.application.config["GEMINI_API_KEY"] = None
            data = client.get("/api/health").get_json()
            assert data["checks"].get("gemini_api_key") == "not_configured"

    def test_health_gemini_key_configured(self, client, monkeypatch):
        """When GEMINI_API_KEY is configured with dummy value, health must report 'configured'."""
        monkeypatch.setenv("GEMINI_API_KEY", "dummy-test-key")
        data = client.get("/api/health").get_json()
        assert data["checks"].get("gemini_api_key") == "configured"

    def test_health_status_ok(self, client):
        """Overall status must be 'ok' when all checks pass."""
        data = client.get("/api/health").get_json()
        assert data["status"] == "ok"

    def test_health_timestamp_iso8601(self, client):
        """Timestamp must be a valid ISO-8601 string."""
        from datetime import datetime
        data = client.get("/api/health").get_json()
        ts = data.get("timestamp", "")
        # Raises ValueError if not valid ISO-8601
        datetime.fromisoformat(ts.replace("Z", "+00:00"))
