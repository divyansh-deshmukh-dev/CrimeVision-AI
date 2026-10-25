"""
tests/test_mentor_login_and_workspace.py — Regression tests for mentor login, real workspace experience,
and elimination of legacy read-only demo pollution.

Covers:
  1. Demo Login button behavior: prefills user-12/user1234 without auto-submitting.
  2. Normal login authentication for user-12.
  3. Rejection of invalid credentials.
  4. Real workspace landing (not legacy demo).
  5. Case selector excludes legacy demo cases (case_demo_sentinel) from normal user-facing flow.
  6. Accessibility of user-12's existing writable cases and multimodal evidence.
  7. Creation of new cases and evidence uploading for user-12.
  8. IDOR isolation: other users cannot access user-12's cases or evidence.
  9. Strict CSRF protection remains enforced on auth and case endpoints.
"""

import io
import json
import re
import pytest
from app import create_app
from storage.cases_store import get_case
from storage.users_store import authenticate_user, get_user_by_username


class TestDemoLoginButtonConfiguration:
    """Requirement 1: Verify the Demo Login button prefills credentials without auto-submitting."""

    def test_login_page_renders_demo_login_button(self, unauthenticated_client):
        """The login page contains the Demo Login button with prefill instructions."""
        resp = unauthenticated_client.get("/login")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)

        assert 'id="btn-demo-login"' in html
        assert "Demo Login" in html
        assert "user-12" in html
        assert 'id="btn-submit"' in html

    def test_demo_login_button_script_does_not_auto_submit(self, unauthenticated_client):
        """The script attached to btn-demo-login populates fields and does NOT submit or fetch."""
        resp = unauthenticated_client.get("/login")
        html = resp.get_data(as_text=True)

        # Find the listener script block specifically for demoBtn
        demo_btn_idx = html.find("demoBtn.addEventListener")
        assert demo_btn_idx != -1, "demoBtn event listener must exist"
        demo_script = html[demo_btn_idx:html.find("});", demo_btn_idx)]

        assert "usernameInput.value = 'user-12'" in demo_script
        assert "passwordInput.value = 'user1234'" in demo_script

        # Verify it does NOT submit the form or perform a fetch call
        assert "submit" not in demo_script.lower()
        assert "fetch" not in demo_script.lower()


class TestMentorAccountAndAuthentication:
    """Requirement 2 & 5: Verify user-12 credentials and rejection of invalid attempts."""

    def test_user_12_exists_in_database(self, app):
        """Ensure user-12 exists in the database and password matches stored hash."""
        from storage.users_store import ensure_user
        with app.app_context():
            user, _ = ensure_user(
                username="user-12",
                email="user@gmail.com",
                password="user1234",
                role="user",
                user_id="usr_1fb3fd9494ca",
            )
            assert user["username"] == "user-12"
            auth = authenticate_user("user-12", "user1234")
            assert auth is not None, "user-12 password must match user1234"
            assert auth["role"] == "user"

    def test_authenticate_user_12_normal_login_endpoint(self, app, unauthenticated_client):
        """Valid credentials authenticate through POST /api/auth/login."""
        from storage.users_store import ensure_user
        with app.app_context():
            ensure_user(
                username="user-12",
                email="user@gmail.com",
                password="user1234",
                role="user",
                user_id="usr_1fb3fd9494ca",
            )

        # Fetch valid CSRF token
        csrf_res = unauthenticated_client.get("/api/auth/csrf")
        csrf_token = csrf_res.get_json()["csrf_token"]

        resp = unauthenticated_client.post(
            "/api/auth/login",
            json={"username": "user-12", "password": "user1234"},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "authenticated"
        assert data["user"]["username"] == "user-12"
        assert data["user"]["role"] == "user"

    def test_invalid_password_rejected(self, unauthenticated_client):
        """Invalid credentials return 401 unauthorized."""
        csrf_res = unauthenticated_client.get("/api/auth/csrf")
        csrf_token = csrf_res.get_json()["csrf_token"]

        resp = unauthenticated_client.post(
            "/api/auth/login",
            json={"username": "user-12", "password": "wrong_password_999"},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert resp.status_code == 401
        assert resp.get_json()["code"] == "INVALID_CREDENTIALS"

    def test_nonexistent_user_rejected(self, unauthenticated_client):
        """Nonexistent username returns 401 unauthorized."""
        csrf_res = unauthenticated_client.get("/api/auth/csrf")
        csrf_token = csrf_res.get_json()["csrf_token"]

        resp = unauthenticated_client.post(
            "/api/auth/login",
            json={"username": "phantom_examiner_xyz", "password": "SomePassword123!"},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert resp.status_code == 401


class TestRealWorkspaceFlow:
    """Requirement 3 & 4: Workspace behavior and exclusion of legacy demo cases."""

    @pytest.fixture()
    def user_12_client(self, app):
        """Authenticated client logged in as user-12."""
        from storage.users_store import create_user, get_user_by_username
        import secrets
        with app.app_context():
            user = get_user_by_username("user-12")
            if not user:
                user = create_user(
                    username="user-12",
                    email="user@gmail.com",
                    password="user1234",
                    role="user",
                    user_id="usr_1fb3fd9494ca",
                )
        client = app.test_client()
        csrf_token = secrets.token_hex(32)
        with client.session_transaction() as sess:
            sess["user_id"] = user["user_id"]
            sess["username"] = user["username"]
            sess["role"] = user["role"]
            sess["display_name"] = user.get("display_name") or user["username"]
            sess["csrf_token"] = csrf_token
        return client

    def test_mentor_lands_in_real_workspace(self, user_12_client):
        """Mentor lands in /workspace as a real authenticated user, not a demo session."""
        resp = user_12_client.get("/workspace")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "CrimeVision" in html
        assert "Investigation Workspace" in html

        # Verify current user endpoint confirms standard user role
        me_resp = user_12_client.get("/api/auth/me")
        assert me_resp.status_code == 200
        me = me_resp.get_json()["user"]
        assert me["username"] == "user-12"
        assert me["role"] == "user"
        assert me.get("is_demo", 0) == 0

    def test_case_selector_excludes_legacy_demo_cases(self, user_12_client):
        """GET /api/cases excludes case_demo_sentinel from normal user-facing case list."""
        resp = user_12_client.get("/api/cases")
        assert resp.status_code == 200
        data = resp.get_json()
        cases = data["cases"]

        case_ids = [c["case_id"] for c in cases]
        assert "case_demo_sentinel" not in case_ids, "Legacy demo case must not appear in normal case list"
        for c in cases:
            assert c.get("demo_type") != "legacy", "Legacy demo types must be excluded"
            assert not c.get("is_readonly", False), "Cases in normal selector must be writable"

    def test_mentor_can_create_new_case_and_upload_evidence(self, user_12_client, tiny_png):
        """Mentor can create a new writable case and upload evidence in the real workspace."""
        # Create new case
        csrf_res = user_12_client.get("/api/auth/csrf")
        csrf_token = csrf_res.get_json()["csrf_token"]

        c_resp = user_12_client.post(
            "/api/cases",
            json={"name": "Mentor Evaluated Case", "description": "Tested by mentor"},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert c_resp.status_code == 201
        new_case_id = c_resp.get_json()["case"]["case_id"]

        # Upload evidence to new case
        data = {
            "file": (io.BytesIO(tiny_png), "eval_sample.png"),
        }
        up_resp = user_12_client.post(
            f"/api/cases/{new_case_id}/evidence",
            data=data,
            content_type="multipart/form-data",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert up_resp.status_code == 201
        ev = up_resp.get_json()["evidence"]
        assert ev["case_id"] == new_case_id
        assert ev["modality"] == "image"


class TestMultiTenantIsolationAndCSRF:
    """Requirements 5 & 8: IDOR protection and CSRF integrity."""

    def test_unauthorized_user_cannot_access_mentor_cases(self, app, client):
        """A different user cannot access or tamper with user-12's cases."""
        from storage.cases_store import create_case
        from storage.users_store import ensure_user
        with app.app_context():
            u12, _ = ensure_user(
                username="user-12",
                email="user@gmail.com",
                password="user1234",
                role="user",
                user_id="usr_1fb3fd9494ca",
            )
            case = create_case(
                name="Private User-12 Case",
                user_id=u12["user_id"],
            )
            priv_case_id = case["case_id"]

        # Other authenticated user attempts to access
        resp = client.get(f"/api/cases/{priv_case_id}")
        assert resp.status_code == 403
        assert resp.get_json()["code"] == "FORBIDDEN"

        # Other user attempts to delete
        del_resp = client.delete(f"/api/cases/{priv_case_id}")
        assert del_resp.status_code == 403

    def test_login_endpoint_enforces_csrf(self, raw_client):
        """Login endpoint rejects requests missing CSRF protection."""
        resp = raw_client.post(
            "/api/auth/login",
            json={"username": "user-12", "password": "user1234"},
        )
        assert resp.status_code == 403
        assert resp.get_json()["code"] == "CSRF_ERROR"


class TestLiveStorageAndEvidenceIntegrity:
    """Requirement 4 & 6: Verify actual SQLite database preserves user-12, case, and evidence."""

    def test_live_database_user_12_and_evidence_files(self):
        """Directly verify storage/crimevision.db contains user-12 and real evidence files exist."""
        import os
        import sqlite3
        from werkzeug.security import check_password_hash
        from config import get_config

        db_file = "storage/crimevision.db"
        assert os.path.exists(db_file), f"{db_file} must exist"

        conn = sqlite3.connect(db_file)
        c = conn.cursor()

        # Check user-12
        c.execute("SELECT user_id, username, email, password_hash, role, is_active, is_demo FROM users WHERE username = ?", ("user-12",))
        u_row = c.fetchone()
        assert u_row is not None, "user-12 must be present in storage/crimevision.db"
        uid, uname, email, pwd_hash, role, is_active, is_demo = u_row
        assert uname == "user-12"
        assert role == "user"
        assert is_active == 1
        assert is_demo == 0
        assert check_password_hash(pwd_hash, "user1234"), "Stored password hash must match user1234"

        # Check cases owned by user-12
        c.execute("SELECT case_id, name, is_demo, demo_type FROM cases WHERE user_id = ?", (uid,))
        cases = c.fetchall()
        assert len(cases) >= 1, "user-12 must have at least one case"

        cfg = get_config()
        uploads_dir = str(cfg.UPLOADS_DIR)

        # Check evidence for user-12 cases
        for cid, name, c_is_demo, demo_type in cases:
            assert c_is_demo == 0, "Case must not be marked demo"
            assert demo_type != "legacy", "Case must not be marked legacy"

            c.execute("SELECT evidence_id, filename, modality, analysis_status, analysis_json FROM evidence WHERE case_id = ?", (cid,))
            ev_rows = c.fetchall()
            for eid, fn, mod, status, aj in ev_rows:
                full_path = os.path.join(uploads_dir, fn)
                assert os.path.exists(full_path), f"Evidence file on disk must exist: {full_path}"
                if aj:
                    data = json.loads(aj)
                    assert data.get("is_demo", False) is False, "Evidence analysis must not be fake demo data"
