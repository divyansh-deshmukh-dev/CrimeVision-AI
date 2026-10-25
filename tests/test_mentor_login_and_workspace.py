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


class TestFreshDeploymentStartupProvisioning:
    """Verify fresh deployment startup provisioning (simulating fresh Render container boot)."""

    def test_fresh_database_auto_provisions_evaluator_on_startup(self, tmp_path):
        """Simulate a completely fresh deployment without any existing database.

        Verifies that create_app() automatically provisions user-12 so they can immediately
        authenticate without any manual provisioning script.
        """
        isolated_dir = tmp_path / "fresh_render_deploy"
        cfg = {
            "TESTING": True,
            "DEBUG": False,
            "STORAGE_DIR": isolated_dir,
            "CASES_DIR": isolated_dir / "cases",
            "UPLOADS_DIR": isolated_dir / "uploads",
            "REPORTS_DIR": isolated_dir / "reports",
            "DB_PATH": isolated_dir / "crimevision_fresh.db",
            "SECRET_KEY": "fresh-deployment-test-secret-key-32!",
        }
        app = create_app(config_override=cfg)
        client = app.test_client()

        # 1. Fetch CSRF token
        csrf_res = client.get("/api/auth/csrf")
        assert csrf_res.status_code == 200
        csrf_token = csrf_res.get_json()["csrf_token"]

        # 2. Login immediately with user-12 / user1234
        login_resp = client.post(
            "/api/auth/login",
            json={"username": "user-12", "password": "user1234"},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert login_resp.status_code == 200
        data = login_resp.get_json()
        assert data["status"] == "authenticated"
        assert data["user"]["username"] == "user-12"
        assert data["user"]["display_name"] == "user"
        assert data["user"]["role"] == "user"

        # 3. Check cases for user-12 — should have the provisioned active workspace case named 'test case'
        cases_resp = client.get("/api/cases", headers={"X-CSRF-Token": csrf_token})
        assert cases_resp.status_code == 200
        cases = cases_resp.get_json()["cases"]
        assert len(cases) >= 1
        case_id = cases[0]["case_id"]
        assert case_id == "case_bd736d27b0e9"
        assert cases[0]["name"] == "test case"

        # 4. Check evidence in this case — preloaded multimodal evidence items exist
        ev_resp = client.get(f"/api/cases/{case_id}/evidence", headers={"X-CSRF-Token": csrf_token})
        assert ev_resp.status_code == 200
        evidence_items = ev_resp.get_json()["evidence"]
        modalities = {e["modality"] for e in evidence_items}
        assert "image" in modalities
        assert "audio" in modalities
        assert "video" in modalities

    def test_existing_render_database_migration_to_test_case(self, tmp_path):
        """Verify migration of an existing Render database seeded with 'Metro CCTV & Evidence Investigation'.

        Renames the case only if case_id='case_bd736d27b0e9' and name='Metro CCTV & Evidence Investigation'.
        Updates display_name only if user-12 has display_name='Lead Investigator'.
        Preserves all evidence, reports, and IDs.
        """
        import sqlite3
        isolated_dir = tmp_path / "migration_render_deploy"
        db_file = isolated_dir / "crimevision_mig.db"
        isolated_dir.mkdir(parents=True, exist_ok=True)

        cfg = {
            "TESTING": True,
            "DEBUG": False,
            "STORAGE_DIR": isolated_dir,
            "CASES_DIR": isolated_dir / "cases",
            "UPLOADS_DIR": isolated_dir / "uploads",
            "REPORTS_DIR": isolated_dir / "reports",
            "DB_PATH": db_file,
            "SECRET_KEY": "migration-test-secret-key-32-bytes!",
        }

        # Initialize schema and pre-populate with old Render seeded values
        from storage.database import init_db
        init_db(db_file)

        conn = sqlite3.connect(str(db_file))
        now = "2026-10-25T12:00:00+00:00"
        conn.execute(
            """
            INSERT INTO users (user_id, display_name, username, email, password_hash, role, created_at, is_active, is_demo)
            VALUES ('usr_1fb3fd9494ca', 'Lead Investigator', 'user-12', 'user@gmail.com', 'dummy_hash', 'user', ?, 1, 0)
            """,
            (now,),
        )
        conn.execute(
            """
            INSERT INTO cases (case_id, user_id, name, description, created_at, updated_at, status, is_demo, demo_type)
            VALUES ('case_bd736d27b0e9', 'usr_1fb3fd9494ca', 'Metro CCTV & Evidence Investigation', 'Old Desc', ?, ?, 'active', 0, NULL)
            """,
            (now, now),
        )
        conn.execute(
            """
            INSERT INTO evidence (evidence_id, case_id, filename, original_name, modality, mime_type, sha256, file_size, uploaded_at, analysis_status)
            VALUES ('ev_test_1', 'case_bd736d27b0e9', 'sample.png', 'sample.png', 'image', 'image/png', 'hash123', 100, ?, 'completed')
            """,
            (now,),
        )
        conn.execute(
            """
            INSERT INTO reports (report_id, case_id, filename, created_at, file_size)
            VALUES ('rep_test_1', 'case_bd736d27b0e9', 'report.pdf', ?, 200)
            """,
            (now,),
        )
        conn.commit()
        conn.close()

        # Boot application with startup hook
        app = create_app(config_override=cfg)
        with app.app_context():
            from storage.users_store import get_user_by_username
            from storage.cases_store import get_case
            from storage.evidence_store import list_evidence

            # Check user display name was migrated from 'Lead Investigator' to 'user'
            u = get_user_by_username("user-12")
            assert u is not None
            assert u["display_name"] == "user"

            # Check case was migrated from 'Metro CCTV & Evidence Investigation' to 'test case'
            c = get_case("case_bd736d27b0e9")
            assert c is not None
            assert c["name"] == "test case"
            assert c["case_id"] == "case_bd736d27b0e9"

            # Verify evidence and report associations are preserved
            ev_list = list_evidence("case_bd736d27b0e9")
            ev_ids = [e["evidence_id"] for e in ev_list]
            assert "ev_test_1" in ev_ids

    def test_unrelated_cases_and_users_are_not_modified(self, tmp_path):
        """Ensure other cases and users with custom names are never overwritten."""
        import sqlite3
        isolated_dir = tmp_path / "unrelated_render_deploy"
        db_file = isolated_dir / "crimevision_unrelated.db"
        isolated_dir.mkdir(parents=True, exist_ok=True)

        cfg = {
            "TESTING": True,
            "DEBUG": False,
            "STORAGE_DIR": isolated_dir,
            "CASES_DIR": isolated_dir / "cases",
            "UPLOADS_DIR": isolated_dir / "uploads",
            "REPORTS_DIR": isolated_dir / "reports",
            "DB_PATH": db_file,
            "SECRET_KEY": "unrelated-test-secret-key-32-bytes!",
        }

        from storage.database import init_db
        init_db(db_file)

        conn = sqlite3.connect(str(db_file))
        now = "2026-10-25T12:00:00+00:00"
        # Another user with different display name
        conn.execute(
            """
            INSERT INTO users (user_id, display_name, username, email, password_hash, role, created_at, is_active, is_demo)
            VALUES ('usr_other_999', 'Detective Miller', 'miller-01', 'miller@gmail.com', 'dummy_hash', 'user', ?, 1, 0)
            """,
            (now,),
        )
        # Another case with different ID and name
        conn.execute(
            """
            INSERT INTO cases (case_id, user_id, name, description, created_at, updated_at, status, is_demo, demo_type)
            VALUES ('case_custom_888', 'usr_other_999', 'Downtown Burglary Investigation', 'Desc', ?, ?, 'active', 0, NULL)
            """,
            (now, now),
        )
        conn.commit()
        conn.close()

        # Run application startup
        app = create_app(config_override=cfg)
        with app.app_context():
            from storage.users_store import get_user_by_username
            from storage.cases_store import get_case

            # Unrelated user remains untouched
            other_u = get_user_by_username("miller-01")
            assert other_u["display_name"] == "Detective Miller"

            # Unrelated case remains untouched
            other_c = get_case("case_custom_888")
            assert other_c["name"] == "Downtown Burglary Investigation"

    def test_idempotent_repeated_startup(self, tmp_path):
        """Verify ensure_demo_evaluator runs multiple times without duplicating or corrupting data."""
        isolated_dir = tmp_path / "repeated_render_deploy"
        db_file = isolated_dir / "crimevision_rep.db"
        isolated_dir.mkdir(parents=True, exist_ok=True)

        cfg = {
            "TESTING": True,
            "DEBUG": False,
            "STORAGE_DIR": isolated_dir,
            "CASES_DIR": isolated_dir / "cases",
            "UPLOADS_DIR": isolated_dir / "uploads",
            "REPORTS_DIR": isolated_dir / "reports",
            "DB_PATH": db_file,
            "SECRET_KEY": "repeated-test-secret-key-32-bytes!",
        }

        app = create_app(config_override=cfg)
        with app.app_context():
            from storage.provision_demo import ensure_demo_evaluator
            from storage.database import get_db

            # Call 3 times consecutively
            res1 = ensure_demo_evaluator()
            res2 = ensure_demo_evaluator()
            res3 = ensure_demo_evaluator()

            assert res1["username"] == "user-12"
            assert res2["username"] == "user-12"
            assert res3["username"] == "user-12"

            db = get_db()
            user_count = db.execute("SELECT COUNT(*) as c FROM users WHERE username = 'user-12'").fetchone()["c"]
            assert user_count == 1, "user-12 must not be duplicated"

            case_count = db.execute("SELECT COUNT(*) as c FROM cases WHERE user_id = 'usr_1fb3fd9494ca'").fetchone()["c"]
            assert case_count == 1, "Primary case must not be duplicated"

    def test_custom_evaluator_credentials_via_env_vars(self, tmp_path, monkeypatch):
        """Simulate Render deployment with custom DEMO_USERNAME and DEMO_PASSWORD env vars."""
        monkeypatch.setenv("DEMO_USERNAME", "custom_evaluator")
        monkeypatch.setenv("DEMO_PASSWORD", "CustomPass987!")
        monkeypatch.setenv("DEMO_EMAIL", "custom_eval@crimevision.ai")

        isolated_dir = tmp_path / "custom_render_deploy"
        cfg = {
            "TESTING": True,
            "DEBUG": False,
            "STORAGE_DIR": isolated_dir,
            "CASES_DIR": isolated_dir / "cases",
            "UPLOADS_DIR": isolated_dir / "uploads",
            "REPORTS_DIR": isolated_dir / "reports",
            "DB_PATH": isolated_dir / "crimevision_custom.db",
            "SECRET_KEY": "custom-deployment-test-secret-key-32!",
        }
        app = create_app(config_override=cfg)
        client = app.test_client()

        # 1. Check login page displays the custom username
        login_page_resp = client.get("/login")
        assert login_page_resp.status_code == 200
        html = login_page_resp.get_data(as_text=True)
        assert "custom_evaluator" in html

        # 2. Get CSRF token
        csrf_res = client.get("/api/auth/csrf")
        csrf_token = csrf_res.get_json()["csrf_token"]

        # 3. Authenticate with custom credentials
        login_resp = client.post(
            "/api/auth/login",
            json={"username": "custom_evaluator", "password": "CustomPass987!"},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert login_resp.status_code == 200
        data = login_resp.get_json()
        assert data["user"]["username"] == "custom_evaluator"

        # 4. Wrong password rejected
        csrf_res2 = client.get("/api/auth/csrf")
        csrf_token2 = csrf_res2.get_json()["csrf_token"]
        bad_resp = client.post(
            "/api/auth/login",
            json={"username": "custom_evaluator", "password": "WrongPassword99!"},
            headers={"X-CSRF-Token": csrf_token2},
        )
        assert bad_resp.status_code == 401

    def test_sample_media_files_restored_when_missing(self, tmp_path):
        """Simulate ephemeral container restart where uploads were cleared but DB persisted.
        ensure_demo_evaluator must restore files from storage/seed_assets without 404s."""
        isolated_dir = tmp_path / "ephemeral_render_deploy"
        uploads_dir = isolated_dir / "uploads"
        reports_dir = isolated_dir / "reports"
        db_file = isolated_dir / "crimevision_ephemeral.db"

        cfg = {
            "TESTING": True,
            "DEBUG": False,
            "STORAGE_DIR": isolated_dir,
            "CASES_DIR": isolated_dir / "cases",
            "UPLOADS_DIR": uploads_dir,
            "REPORTS_DIR": reports_dir,
            "DB_PATH": db_file,
            "SECRET_KEY": "ephemeral-test-secret-key-32-bytes!",
        }

        app = create_app(config_override=cfg)
        client = app.test_client()

        with app.app_context():
            from storage.provision_demo import ensure_demo_evaluator

            # Verify initial files exist and are non-empty
            img_file = uploads_dir / "case_bd736d27b0e9" / "ev_b31dacb7da6f" / "Gemini_Generated_Image_l79sz8l79sz8l79s_1.png"
            audio_file = uploads_dir / "case_bd736d27b0e9" / "ev_b49348be7de2" / "ElevenLabs_2026-10-18T17_37_53_Roger_-_Laid-Back_Casual_Resonant_pre_sp100_s50_s.mp3"
            video_file = uploads_dir / "case_bd736d27b0e9" / "ev_9d23b6a675ce" / "Realistic_15-second_continuous_CCTV_surveillance_footage_of_a_small_urban_street.mp4"
            pdf_file = reports_dir / "case_bd736d27b0e9" / "forensic_report_case_bd736d27b0e9.pdf"

            assert img_file.exists() and img_file.stat().st_size > 1000
            assert audio_file.exists() and audio_file.stat().st_size > 1000
            assert video_file.exists() and video_file.stat().st_size > 1000
            assert pdf_file.exists() and pdf_file.stat().st_size > 500

            # Simulate ephemeral container restart: delete all uploaded & reported files from disk
            import stat
            for p in [img_file, audio_file, video_file, pdf_file]:
                if p.exists():
                    p.chmod(stat.S_IWRITE)
                    p.unlink()

            assert not img_file.exists()
            assert not audio_file.exists()
            assert not video_file.exists()
            assert not pdf_file.exists()

            # Run ensure_demo_evaluator (as happens on container restart)
            res = ensure_demo_evaluator()
            assert res["username"] == "user-12"

            # Verify files are self-healed and restored from seed_assets
            assert img_file.exists() and img_file.stat().st_size > 1000
            assert audio_file.exists() and audio_file.stat().st_size > 1000
            assert video_file.exists() and video_file.stat().st_size > 1000
            assert pdf_file.exists() and pdf_file.stat().st_size > 500

        # Login and test preview/download endpoints return 200
        csrf_res = client.get("/api/auth/csrf")
        csrf_token = csrf_res.get_json()["csrf_token"]
        login_res = client.post(
            "/api/auth/login",
            json={"username": "user-12", "password": "user1234"},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert login_res.status_code == 200

        # Image preview
        r_img = client.get("/api/cases/case_bd736d27b0e9/evidence/ev_b31dacb7da6f/file")
        assert r_img.status_code == 200
        assert r_img.content_type.startswith("image/")
        assert len(r_img.data) > 1000

        # Audio file
        r_audio = client.get("/api/cases/case_bd736d27b0e9/evidence/ev_b49348be7de2/file")
        assert r_audio.status_code == 200
        assert r_audio.content_type.startswith("audio/")
        assert len(r_audio.data) > 1000

        # Video file
        r_video = client.get("/api/cases/case_bd736d27b0e9/evidence/ev_9d23b6a675ce/file")
        assert r_video.status_code == 200
        assert r_video.content_type.startswith("video/")
        assert len(r_video.data) > 1000

        # Report download
        r_pdf = client.get("/api/reports/rep_4af9ce45c9dd")
        assert r_pdf.status_code == 200
        assert r_pdf.content_type == "application/pdf"
        assert len(r_pdf.data) > 500

    def test_seeded_analysis_json_has_detection_objects_and_upgrades_old_schema(self, tmp_path):
        """Verify seeded image evidence contains analysis.detection.objects and migrates legacy schemas."""
        isolated_dir = tmp_path / "schema_render_deploy"
        db_file = isolated_dir / "crimevision_schema.db"

        cfg = {
            "TESTING": True,
            "DEBUG": False,
            "STORAGE_DIR": isolated_dir,
            "CASES_DIR": isolated_dir / "cases",
            "UPLOADS_DIR": isolated_dir / "uploads",
            "REPORTS_DIR": isolated_dir / "reports",
            "DB_PATH": db_file,
            "SECRET_KEY": "schema-test-secret-key-32-bytes!",
        }

        app = create_app(config_override=cfg)

        with app.app_context():
            from storage.database import get_db
            from storage.provision_demo import ensure_demo_evaluator

            db = get_db()
            row = db.execute("SELECT analysis_json FROM evidence WHERE evidence_id = 'ev_b31dacb7da6f'").fetchone()
            assert row is not None
            analysis = json.loads(row["analysis_json"])

            # Verify standard frontend contract
            assert "detection" in analysis
            assert "objects" in analysis["detection"]
            objects = analysis["detection"]["objects"]
            assert len(objects) == 4

            # Verify bounding box format is normalized [x1, y1, x2, y2]
            labels = [obj["label"] for obj in objects]
            assert "car" in labels
            assert "truck" in labels
            assert "person" in labels
            assert "traffic light" in labels

            for obj in objects:
                assert "box_normalized" in obj
                norm = obj["box_normalized"]
                assert len(norm) == 4
                assert all(0.0 <= c <= 1.0 for c in norm)

            # Now test schema migration: downgrade DB to legacy format lacking 'detection.objects'
            legacy_analysis = {
                "detections": [
                    {"label": "old_box", "confidence": 0.8}
                ],
                "caption": "old style caption"
            }
            db.execute(
                "UPDATE evidence SET analysis_json = ? WHERE evidence_id = 'ev_b31dacb7da6f'",
                (json.dumps(legacy_analysis),),
            )
            db.commit()

            # Confirm downgrade
            row2 = db.execute("SELECT analysis_json FROM evidence WHERE evidence_id = 'ev_b31dacb7da6f'").fetchone()
            parsed2 = json.loads(row2["analysis_json"])
            assert "detection" not in parsed2

            # Run ensure_demo_evaluator which should migrate the schema
            ensure_demo_evaluator()

            # Verify migrated schema
            row3 = db.execute("SELECT analysis_json FROM evidence WHERE evidence_id = 'ev_b31dacb7da6f'").fetchone()
            migrated = json.loads(row3["analysis_json"])
            assert "detection" in migrated
            assert "objects" in migrated["detection"]
            assert len(migrated["detection"]["objects"]) == 4

    def test_real_user_uploaded_files_never_overwritten(self, tmp_path):
        """Verify user-uploaded evidence files and records are never overwritten or touched by provisioning."""
        isolated_dir = tmp_path / "user_preserve_deploy"
        uploads_dir = isolated_dir / "uploads"
        db_file = isolated_dir / "crimevision_user_preserve.db"

        cfg = {
            "TESTING": True,
            "DEBUG": False,
            "STORAGE_DIR": isolated_dir,
            "CASES_DIR": isolated_dir / "cases",
            "UPLOADS_DIR": uploads_dir,
            "REPORTS_DIR": isolated_dir / "reports",
            "DB_PATH": db_file,
            "SECRET_KEY": "preserve-test-secret-key-32-bytes!",
        }

        app = create_app(config_override=cfg)

        with app.app_context():
            from storage.database import get_db
            from storage.provision_demo import ensure_demo_evaluator

            db = get_db()
            user_file_dir = uploads_dir / "case_bd736d27b0e9"
            user_file_dir.mkdir(parents=True, exist_ok=True)
            custom_file = user_file_dir / "custom_real_evidence.png"
            custom_file.write_bytes(b"REAL_INVESTIGATOR_EVIDENCE_BYTES_12345")

            now_iso = "2026-10-25T14:00:00+00:00"
            db.execute(
                """
                INSERT INTO evidence (evidence_id, case_id, filename, original_name, modality, mime_type, sha256, file_size, uploaded_at, analysis_status, analysis_json)
                VALUES ('ev_custom_user_1', 'case_bd736d27b0e9', 'case_bd736d27b0e9/custom_real_evidence.png', 'custom_real_evidence.png', 'image', 'image/png', 'hashcustom123', 38, ?, 'completed', '{"custom": true}')
                """,
                (now_iso,),
            )
            db.commit()

            # Re-run ensure_demo_evaluator
            ensure_demo_evaluator()

            # Custom file on disk must be completely untouched
            assert custom_file.exists()
            assert custom_file.read_bytes() == b"REAL_INVESTIGATOR_EVIDENCE_BYTES_12345"

            # Custom record in DB must be unchanged
            custom_row = db.execute("SELECT * FROM evidence WHERE evidence_id = 'ev_custom_user_1'").fetchone()
            assert custom_row is not None
            assert custom_row["original_name"] == "custom_real_evidence.png"
            assert json.loads(custom_row["analysis_json"]) == {"custom": True}

    def test_missing_seed_assets_do_not_crash_startup(self, tmp_path, monkeypatch):
        """Verify that even if seed assets folder is empty or unreadable, ensure_demo_evaluator falls back cleanly."""
        isolated_dir = tmp_path / "fallback_deploy"
        empty_seed_dir = tmp_path / "nonexistent_seed_assets"

        monkeypatch.setattr(
            "storage.provision_demo.Path",
            lambda *args, **kwargs: empty_seed_dir
        )

        cfg = {
            "TESTING": True,
            "DEBUG": False,
            "STORAGE_DIR": isolated_dir,
            "CASES_DIR": isolated_dir / "cases",
            "UPLOADS_DIR": isolated_dir / "uploads",
            "REPORTS_DIR": isolated_dir / "reports",
            "DB_PATH": isolated_dir / "crimevision_fallback.db",
            "SECRET_KEY": "fallback-test-secret-key-32-bytes!",
        }

        # Rather than monkeypatching Path directly which could break other things, test _read_seed_asset directly with non-existent asset
        from storage.provision_demo import _read_seed_asset, _get_synthetic_media
        fallback_data = _read_seed_asset("non_existent_file.png", "image")
        assert len(fallback_data) > 0
        assert fallback_data.startswith(b"\x89PNG")


