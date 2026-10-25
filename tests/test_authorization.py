"""
tests/test_authorization.py — Comprehensive multi-tenant authorization, IDOR, CSRF, and legacy case security tests.
"""

import io
import pytest
import secrets
from storage.users_store import create_user
from storage.cases_store import create_case, get_case
from storage.database import init_db


@pytest.fixture()
def client_b(app):
    """Return an authenticated client for a distinct second investigator (User B)."""
    with app.app_context():
        user_b = create_user(
            username="investigator_b",
            email="user_b@fbi.gov",
            password="UserBPassword123!",
            display_name="Investigator B",
            role="user",
            user_id="usr_user_b_id",
        )

    csrf_token = secrets.token_hex(32)
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["user_id"] = user_b["user_id"]
        sess["username"] = user_b["username"]
        sess["role"] = user_b["role"]
        sess["display_name"] = user_b["display_name"]
        sess["csrf_token"] = csrf_token

    c.environ_base["HTTP_X_CSRF_TOKEN"] = csrf_token
    return c


@pytest.fixture()
def admin_client(app):
    """Return an authenticated client for a system administrator."""
    with app.app_context():
        admin = create_user(
            username="sys_admin",
            email="admin@fbi.gov",
            password="AdminPassword123!",
            display_name="System Admin",
            role="admin",
            user_id="usr_admin_id",
        )

    csrf_token = secrets.token_hex(32)
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["user_id"] = admin["user_id"]
        sess["username"] = admin["username"]
        sess["role"] = admin["role"]
        sess["display_name"] = admin["display_name"]
        sess["csrf_token"] = csrf_token

    c.environ_base["HTTP_X_CSRF_TOKEN"] = csrf_token
    return c


class TestAnonymousAccessDenied:
    """Ensure all protected endpoints return 401 when accessed anonymously."""

    def test_anonymous_get_cases_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get("/api/cases")
        assert resp.status_code == 401
        assert resp.get_json()["code"] == "UNAUTHENTICATED"

    def test_anonymous_create_case_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.post("/api/cases", json={"name": "Hacked Case"})
        assert resp.status_code == 401

    def test_anonymous_workspace_html_redirects(self, unauthenticated_client):
        resp = unauthenticated_client.get("/workspace")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


class TestMultiTenantIDORProtection:
    """Ensure User B cannot view, edit, delete, or analyze User A's private case artifacts."""

    def test_user_a_can_access_own_case(self, client, case_id):
        resp = client.get(f"/api/cases/{case_id}")
        assert resp.status_code == 200
        assert resp.get_json()["case"]["case_id"] == case_id

    def test_user_b_cannot_read_user_a_case(self, client_b, case_id):
        resp = client_b.get(f"/api/cases/{case_id}")
        assert resp.status_code == 403
        assert resp.get_json()["code"] == "FORBIDDEN"

    def test_user_b_cannot_see_user_a_case_in_case_list(self, client_b, case_id):
        resp = client_b.get("/api/cases")
        assert resp.status_code == 200
        cases = resp.get_json()["cases"]
        case_ids = [c["case_id"] for c in cases]
        assert case_id not in case_ids

    def test_user_b_cannot_delete_user_a_case(self, client_b, case_id):
        resp = client_b.delete(f"/api/cases/{case_id}")
        assert resp.status_code == 403

    def test_user_b_cannot_upload_evidence_to_user_a_case(self, client_b, case_id, tiny_png):
        data = {"file": (io.BytesIO(tiny_png), "intruder.png")}
        resp = client_b.post(
            f"/api/cases/{case_id}/evidence",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 403

    def test_user_b_cannot_delete_user_a_evidence(self, client, client_b, case_id, tiny_png):
        # User A uploads evidence
        up = client.post(
            f"/api/cases/{case_id}/evidence",
            data={"file": (io.BytesIO(tiny_png), "evidence.png")},
            content_type="multipart/form-data",
        )
        assert up.status_code == 201
        ev_id = up.get_json()["evidence"]["evidence_id"]

        # User B attempts to delete User A's evidence
        resp = client_b.delete(f"/api/cases/{case_id}/evidence/{ev_id}")
        assert resp.status_code == 403

    def test_user_b_cannot_download_user_a_evidence_file(self, client, client_b, case_id, tiny_png):
        # User A uploads evidence
        up = client.post(
            f"/api/cases/{case_id}/evidence",
            data={"file": (io.BytesIO(tiny_png), "confidential.png")},
            content_type="multipart/form-data",
        )
        ev_id = up.get_json()["evidence"]["evidence_id"]

        # User B attempts to stream file
        resp = client_b.get(f"/api/cases/{case_id}/evidence/{ev_id}/file")
        assert resp.status_code == 403

    def test_user_b_cannot_trigger_analysis_on_user_a_evidence(self, client, client_b, case_id, tiny_png):
        up = client.post(
            f"/api/cases/{case_id}/evidence",
            data={"file": (io.BytesIO(tiny_png), "scene.png")},
            content_type="multipart/form-data",
        )
        ev_id = up.get_json()["evidence"]["evidence_id"]

        resp = client_b.post(f"/api/cases/{case_id}/evidence/{ev_id}/analyze/image")
        assert resp.status_code == 403

    def test_user_b_cannot_access_user_a_chat(self, client, client_b, case_id):
        # User A sends chat message
        client.post(
            f"/api/cases/{case_id}/chat",
            json={"query": "Who is the prime suspect?"},
        )

        # User B attempts to read chat history
        resp = client_b.get(f"/api/cases/{case_id}/chat/history")
        assert resp.status_code == 403

        # User B attempts to clear chat history
        del_resp = client_b.delete(f"/api/cases/{case_id}/chat/history")
        assert del_resp.status_code == 403

    def test_user_b_cannot_download_user_a_report(self, client, client_b, case_id):
        # User A generates report
        rep_resp = client.post(f"/api/cases/{case_id}/report", json={})
        assert rep_resp.status_code == 201
        report_id = rep_resp.get_json()["report"]["report_id"]

        # User B attempts to download report directly via /api/reports/<report_id>
        resp = client_b.get(f"/api/reports/{report_id}")
        assert resp.status_code == 403
        assert resp.get_json()["code"] == "FORBIDDEN"

    def test_admin_can_access_any_case(self, admin_client, case_id):
        # Administrator can access User A's case
        resp = admin_client.get(f"/api/cases/{case_id}")
        assert resp.status_code == 200
        assert resp.get_json()["case"]["case_id"] == case_id


class TestCSRFProtection:
    """Ensure state-changing requests without valid CSRF tokens are rejected."""

    def test_post_without_csrf_token_rejected_403(self, client):
        # Remove CSRF token header
        resp = client.post(
            "/api/cases",
            json={"name": "No CSRF Case"},
            headers={"X-CSRF-Token": ""},
        )
        assert resp.status_code == 403
        assert resp.get_json()["code"] == "CSRF_ERROR"

    def test_post_with_tampered_csrf_token_rejected_403(self, client):
        resp = client.post(
            "/api/cases",
            json={"name": "Bad CSRF Case"},
            headers={"X-CSRF-Token": "tampered-token-value-00000000"},
        )
        assert resp.status_code == 403
        assert resp.get_json()["code"] == "CSRF_ERROR"

    def test_delete_without_csrf_token_rejected_403(self, client, case_id):
        resp = client.delete(
            f"/api/cases/{case_id}",
            headers={"X-CSRF-Token": ""},
        )
        assert resp.status_code == 403


class TestLegacyCaseProtection:
    """Ensure unowned legacy cases (user_id IS NULL) are protected from standard users."""

    def test_legacy_case_not_accessible_by_normal_user(self, client, app):
        with app.app_context():
            legacy_case = create_case(name="Legacy Unowned Case", user_id=None, is_demo=False)
            legacy_id = legacy_case["case_id"]

        # Normal authenticated user attempts to access legacy case
        resp = client.get(f"/api/cases/{legacy_id}")
        assert resp.status_code == 403
        assert resp.get_json()["code"] == "FORBIDDEN"

    def test_legacy_case_accessible_by_admin(self, admin_client, app):
        with app.app_context():
            legacy_case = create_case(name="Legacy Unowned Case 2", user_id=None, is_demo=False)
            legacy_id = legacy_case["case_id"]

        # Administrator can access legacy case to resolve or claim it
        resp = admin_client.get(f"/api/cases/{legacy_id}")
        assert resp.status_code == 200
        assert resp.get_json()["case"]["case_id"] == legacy_id
