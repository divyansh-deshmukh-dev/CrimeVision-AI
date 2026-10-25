"""
tests/test_auth.py — Tests for public user registration, login, logout, and rate limiting.
"""

import time
import pytest
from services.rate_limiter import login_limiter
from storage.users_store import create_user, get_user_by_username


class TestSignup:
    """Tests for POST /api/auth/signup."""

    def test_signup_success(self, unauthenticated_client):
        resp = unauthenticated_client.post(
            "/api/auth/signup",
            json={
                "username": "agent_reyes",
                "email": "reyes@fbi.gov",
                "password": "SecurePassword123!",
                "display_name": "Special Agent Reyes",
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["status"] == "created"
        user = data["user"]
        assert user["username"] == "agent_reyes"
        assert user["email"] == "reyes@fbi.gov"
        assert user["role"] == "user"  # Normal role assigned
        assert "password_hash" not in user  # Hash never leaked
        assert user["user_id"].startswith("usr_")

    def test_duplicate_username_rejected(self, unauthenticated_client):
        unauthenticated_client.post(
            "/api/auth/signup",
            json={
                "username": "agent_dup",
                "email": "dup1@fbi.gov",
                "password": "SecurePassword123!",
            },
        )
        resp = unauthenticated_client.post(
            "/api/auth/signup",
            json={
                "username": "AGENT_DUP",  # Case insensitive duplicate check
                "email": "dup2@fbi.gov",
                "password": "SecurePassword123!",
            },
        )
        assert resp.status_code == 400
        assert "already taken" in resp.get_json()["error"].lower()

    def test_duplicate_email_rejected(self, unauthenticated_client):
        unauthenticated_client.post(
            "/api/auth/signup",
            json={
                "username": "agent_first",
                "email": "same_email@fbi.gov",
                "password": "SecurePassword123!",
            },
        )
        resp = unauthenticated_client.post(
            "/api/auth/signup",
            json={
                "username": "agent_second",
                "email": "SAME_EMAIL@fbi.gov",
                "password": "SecurePassword123!",
            },
        )
        assert resp.status_code == 400
        assert "already registered" in resp.get_json()["error"].lower()

    def test_short_password_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.post(
            "/api/auth/signup",
            json={
                "username": "agent_weak",
                "email": "weak@fbi.gov",
                "password": "short",
            },
        )
        assert resp.status_code == 400
        assert "at least 8 characters" in resp.get_json()["error"].lower()

    def test_password_complexity_rejected(self, unauthenticated_client):
        # Letters only, no numbers
        resp = unauthenticated_client.post(
            "/api/auth/signup",
            json={
                "username": "agent_letters",
                "email": "letters@fbi.gov",
                "password": "allletterspassword",
            },
        )
        assert resp.status_code == 400
        assert "at least one letter and at least one number" in resp.get_json()["error"].lower()


class TestLoginAndLogout:
    """Tests for POST /api/auth/login and /api/auth/logout."""

    def test_valid_login_success(self, unauthenticated_client, app):
        with app.app_context():
            create_user(
                username="login_user",
                email="login@fbi.gov",
                password="CorrectPassword123!",
                role="user",
            )

        resp = unauthenticated_client.post(
            "/api/auth/login",
            json={"username": "login_user", "password": "CorrectPassword123!"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "authenticated"
        assert data["user"]["username"] == "login_user"
        assert "password_hash" not in data["user"]

    def test_invalid_password_returns_401(self, unauthenticated_client, app):
        with app.app_context():
            create_user(
                username="login_wrong",
                email="wrong@fbi.gov",
                password="CorrectPassword123!",
            )

        resp = unauthenticated_client.post(
            "/api/auth/login",
            json={"username": "login_wrong", "password": "WrongPassword999!"},
        )
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "Invalid username or password."

    def test_nonexistent_user_returns_generic_401(self, unauthenticated_client):
        resp = unauthenticated_client.post(
            "/api/auth/login",
            json={"username": "ghost_agent_999", "password": "AnyPassword123!"},
        )
        assert resp.status_code == 401
        # Generic message prevents username enumeration
        assert resp.get_json()["error"] == "Invalid username or password."

    def test_inactive_account_rejected(self, unauthenticated_client, app):
        with app.app_context():
            user = create_user(
                username="disabled_agent",
                email="disabled@fbi.gov",
                password="ValidPassword123!",
                is_active=False,
            )

        resp = unauthenticated_client.post(
            "/api/auth/login",
            json={"username": "disabled_agent", "password": "ValidPassword123!"},
        )
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "Invalid username or password."

    def test_current_user_endpoint_authenticated(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        user = resp.get_json()["user"]
        assert user["username"] == "test_examiner"
        assert "password_hash" not in user

    def test_current_user_endpoint_unauthenticated(self, unauthenticated_client):
        resp = unauthenticated_client.get("/api/auth/me")
        assert resp.status_code == 401
        assert resp.get_json()["code"] == "UNAUTHENTICATED"

    def test_logout_invalidates_session(self, client):
        # Client starts authenticated
        me_resp = client.get("/api/auth/me")
        assert me_resp.status_code == 200

        # Logout
        logout_resp = client.post("/api/auth/logout")
        assert logout_resp.status_code == 200
        assert logout_resp.get_json()["status"] == "logged_out"

        # Subsequent authenticated calls must fail with 401
        after_resp = client.get("/api/auth/me")
        assert after_resp.status_code == 401

    def test_login_rate_limiting(self, unauthenticated_client, app):
        login_limiter.reset()
        with app.app_context():
            create_user(
                username="victim_user",
                email="victim@fbi.gov",
                password="TargetPassword123!",
            )

        # 5 failed attempts
        for _ in range(5):
            resp = unauthenticated_client.post(
                "/api/auth/login",
                json={"username": "victim_user", "password": "WrongPassword!"},
            )
            assert resp.status_code == 401

        # 6th attempt should be blocked by rate limiter
        blocked_resp = unauthenticated_client.post(
            "/api/auth/login",
            json={"username": "victim_user", "password": "TargetPassword123!"},
        )
        assert blocked_resp.status_code == 429
        data = blocked_resp.get_json()
        assert data["code"] == "RATE_LIMITED"
        assert "retry_after" in data
        assert "Retry-After" in blocked_resp.headers
        login_limiter.reset()


class TestAuthCSRF:
    """Tests for Login CSRF and Signup CSRF mitigation."""

    def test_login_missing_csrf_rejected_403(self, raw_client):
        resp = raw_client.post(
            "/api/auth/login",
            json={"username": "any_user", "password": "Password123!"},
        )
        assert resp.status_code == 403
        assert resp.get_json()["code"] == "CSRF_ERROR"

    def test_login_tampered_csrf_rejected_403(self, unauthenticated_client):
        resp = unauthenticated_client.post(
            "/api/auth/login",
            json={"username": "any_user", "password": "Password123!"},
            headers={"X-CSRF-Token": "tampered-csrf-token-1234567890"},
        )
        assert resp.status_code == 403
        assert resp.get_json()["code"] == "CSRF_ERROR"

    def test_signup_missing_csrf_rejected_403(self, raw_client):
        resp = raw_client.post(
            "/api/auth/signup",
            json={
                "username": "agent_new",
                "email": "agent_new@fbi.gov",
                "password": "Password123!",
            },
        )
        assert resp.status_code == 403
        assert resp.get_json()["code"] == "CSRF_ERROR"

    def test_signup_tampered_csrf_rejected_403(self, unauthenticated_client):
        resp = unauthenticated_client.post(
            "/api/auth/signup",
            json={
                "username": "agent_new",
                "email": "agent_new@fbi.gov",
                "password": "Password123!",
            },
            headers={"X-CSRF-Token": "tampered-csrf-token-1234567890"},
        )
        assert resp.status_code == 403
        assert resp.get_json()["code"] == "CSRF_ERROR"

    def test_login_with_fetched_csrf_token_succeeds(self, raw_client, app):
        with app.app_context():
            create_user(
                username="csrf_user",
                email="csrf_user@fbi.gov",
                password="CorrectPassword123!",
            )
        # Fetch token from GET /api/auth/csrf
        csrf_resp = raw_client.get("/api/auth/csrf")
        assert csrf_resp.status_code == 200
        token = csrf_resp.get_json()["csrf_token"]

        # Submit login using fetched token in header
        login_resp = raw_client.post(
            "/api/auth/login",
            json={"username": "csrf_user", "password": "CorrectPassword123!"},
            headers={"X-CSRF-Token": token},
        )
        assert login_resp.status_code == 200
        assert login_resp.get_json()["status"] == "authenticated"

    def test_signup_with_fetched_csrf_token_succeeds(self, raw_client):
        # Fetch token from GET /api/auth/csrf
        csrf_resp = raw_client.get("/api/auth/csrf")
        assert csrf_resp.status_code == 200
        token = csrf_resp.get_json()["csrf_token"]

        # Submit signup using fetched token in header
        signup_resp = raw_client.post(
            "/api/auth/signup",
            json={
                "username": "csrf_registered",
                "email": "registered@fbi.gov",
                "password": "Password123!",
                "display_name": "CSRF Registered",
            },
            headers={"X-CSRF-Token": token},
        )
        assert signup_resp.status_code == 201
        assert signup_resp.get_json()["status"] == "created"


class TestTrustedProxyAndRateLimiting:
    """Tests for trusted reverse proxy IP extraction and forged X-Forwarded-For handling."""

    def test_forged_forwarded_for_ignored_when_untrusted(self, unauthenticated_client, app):
        """Attacker sending rotating X-Forwarded-For cannot bypass IP rate limiting."""
        login_limiter.reset()
        with app.app_context():
            create_user(
                username="forged_ip_target",
                email="forged_ip@fbi.gov",
                password="TargetPassword123!",
            )

        # Send 5 failed attempts with different spoofed X-Forwarded-For headers
        for i in range(5):
            resp = unauthenticated_client.post(
                "/api/auth/login",
                json={"username": "forged_ip_target", "password": "WrongPassword!"},
                headers={"X-Forwarded-For": f"198.51.100.{i + 1}"},
                environ_overrides={"REMOTE_ADDR": "192.0.2.100"},
            )
            assert resp.status_code == 401

        # 6th attempt with yet another spoofed IP must still be blocked by real remote_addr rate limiter
        blocked_resp = unauthenticated_client.post(
            "/api/auth/login",
            json={"username": f"other_account_{i}", "password": "TargetPassword123!"},
            headers={"X-Forwarded-For": "203.0.113.99"},
            environ_overrides={"REMOTE_ADDR": "192.0.2.100"},
        )
        assert blocked_resp.status_code == 429
        assert blocked_resp.get_json()["code"] == "RATE_LIMITED"
        login_limiter.reset()

    def test_get_client_ip_unit(self):
        """Unit tests for get_client_ip function across various network configurations."""
        from services.rate_limiter import get_client_ip

        class MockRequest:
            def __init__(self, remote_addr, headers=None):
                self.remote_addr = remote_addr
                self.headers = headers or {}

        # 1. Untrusted peer: ignores X-Forwarded-For
        req1 = MockRequest("198.51.100.25", {"X-Forwarded-For": "203.0.113.10"})
        assert get_client_ip(req1, trusted_proxies=set()) == "198.51.100.25"
        assert get_client_ip(req1, trusted_proxies={"127.0.0.1"}) == "198.51.100.25"

        # 2. Trusted peer: accepts single forwarded IP
        req2 = MockRequest("127.0.0.1", {"X-Forwarded-For": "203.0.113.55"})
        assert get_client_ip(req2, trusted_proxies={"127.0.0.1"}) == "203.0.113.55"

        # 3. Trusted peer: multi-hop chain returns rightmost untrusted IP (ignoring spoofed prefix)
        req3 = MockRequest("127.0.0.1", {"X-Forwarded-For": "8.8.8.8, 10.0.0.1, 203.0.113.77"})
        assert get_client_ip(req3, trusted_proxies={"127.0.0.1", "10.0.0.1"}) == "203.0.113.77"

        # 4. Trusted peer with empty header falls back to remote_addr
        req4 = MockRequest("127.0.0.1", {})
        assert get_client_ip(req4, trusted_proxies={"127.0.0.1"}) == "127.0.0.1"


class TestProductionSecretKey:
    """Tests for production SECRET_KEY enforcement and fail-safe startup."""

    def test_production_mode_missing_secret_key_fails(self, monkeypatch, tmp_path):
        from app import create_app

        monkeypatch.setenv("FLASK_ENV", "production")
        monkeypatch.delenv("SECRET_KEY", raising=False)

        with pytest.raises(RuntimeError) as exc_info:
            create_app({
                "TESTING": False,
                "DEBUG": False,
                "SECRET_KEY": None,
                "STORAGE_DIR": tmp_path / "s",
                "CASES_DIR": tmp_path / "c",
                "UPLOADS_DIR": tmp_path / "u",
                "REPORTS_DIR": tmp_path / "r",
                "DB_PATH": tmp_path / "test.db",
            })

        err = str(exc_info.value)
        assert "SECRET_KEY environment variable is required in production mode" in err

    def test_production_mode_insecure_secret_fails(self, monkeypatch, tmp_path):
        from app import create_app

        monkeypatch.setenv("FLASK_ENV", "production")

        for bad_secret in ("changeme", "short-secret", "12345678", "my_weak_pwd"):
            with pytest.raises(RuntimeError) as exc_info:
                create_app({
                    "TESTING": False,
                    "DEBUG": False,
                    "SECRET_KEY": bad_secret,
                    "STORAGE_DIR": tmp_path / "s",
                    "CASES_DIR": tmp_path / "c",
                    "UPLOADS_DIR": tmp_path / "u",
                    "REPORTS_DIR": tmp_path / "r",
                    "DB_PATH": tmp_path / "test.db",
                })
            err = str(exc_info.value)
            assert "SECRET_KEY is insecure" in err
            # Verify secret itself is never leaked in the error message
            assert bad_secret not in err

    def test_production_mode_valid_secret_succeeds(self, monkeypatch, tmp_path):
        from app import create_app

        monkeypatch.setenv("FLASK_ENV", "production")
        strong_key = "a-very-strong-production-secret-key-32-chars-long!"
        monkeypatch.setenv("SECRET_KEY", strong_key)

        app = create_app({
            "TESTING": False,
            "DEBUG": False,
            "SECRET_KEY": strong_key,
            "STORAGE_DIR": tmp_path / "s",
            "CASES_DIR": tmp_path / "c",
            "UPLOADS_DIR": tmp_path / "u",
            "REPORTS_DIR": tmp_path / "r",
            "DB_PATH": tmp_path / "test.db",
        })
        assert app.config["SECRET_KEY"] == strong_key
