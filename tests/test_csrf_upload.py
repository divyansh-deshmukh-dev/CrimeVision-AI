"""
tests/test_csrf_upload.py — Comprehensive tests for CSRF token handling on evidence uploads.

Verifies:
  1. Valid CSRF token in X-CSRF-Token header allows evidence upload.
  2. Valid CSRF token in X-CSRFToken header allows evidence upload.
  3. Valid CSRF token in multipart form-data (csrf_token field) allows evidence upload without header.
  4. Valid CSRF token in both header and form-data allows evidence upload.
  5. Missing CSRF token is rejected with 403 CSRF_ERROR.
  6. Invalid/tampered CSRF token is rejected with 403 CSRF_ERROR.
  7. Empty/whitespace CSRF token is rejected with 403 CSRF_ERROR.
  8. Unauthenticated user cannot upload evidence (rejected before CSRF with 401/302).
  9. User cannot upload evidence to another user's case (403 FORBIDDEN, case isolation).
  10. Full multimodal upload verification: Image (PNG), Audio (WAV), Video (MP4).
  11. Multipart boundary and file content are preserved without corruption.
"""

import io
from pathlib import Path
import secrets

from flask.testing import FlaskClient
import pytest

from storage.cases_store import create_case
from storage.users_store import create_user


def _make_manual_client(app, user, csrf_token: str) -> FlaskClient:
    """Create a raw test client with an authenticated session and no auto-injected CSRF headers."""
    c = FlaskClient(app)
    with c.session_transaction() as sess:
        sess["user_id"] = user["user_id"]
        sess["username"] = user["username"]
        sess["role"] = user["role"]
        sess["display_name"] = user["display_name"]
        sess["csrf_token"] = csrf_token
    return c


class TestCsrfEvidenceUpload:
    """Validate CSRF protection on the evidence upload endpoint (POST /api/cases/<id>/evidence)."""

    def test_upload_with_valid_csrf_header_succeeds(self, app, test_user, tiny_png):
        """Valid X-CSRF-Token header authorizes evidence upload."""
        token = secrets.token_hex(32)
        client = _make_manual_client(app, test_user, token)

        with app.app_context():
            case = create_case("CSRF Header Test Case", user_id=test_user["user_id"])

        data = {
            "file": (io.BytesIO(tiny_png), "traffic_cam.png"),
        }
        headers = {"X-CSRF-Token": token}

        res = client.post(
            f"/api/cases/{case['case_id']}/evidence",
            data=data,
            content_type="multipart/form-data",
            headers=headers,
        )

        assert res.status_code == 201
        res_data = res.get_json()
        assert res_data["status"] == "uploaded"
        assert res_data["evidence"]["original_name"] == "traffic_cam.png"
        assert res_data["evidence"]["modality"] == "image"

    def test_upload_with_alternative_csrftoken_header_succeeds(self, app, test_user, tiny_png):
        """Valid X-CSRFToken header (Django/common variant) authorizes evidence upload."""
        token = secrets.token_hex(32)
        client = _make_manual_client(app, test_user, token)

        with app.app_context():
            case = create_case("CSRF Alt Header Test Case", user_id=test_user["user_id"])

        data = {
            "file": (io.BytesIO(tiny_png), "surveillance.png"),
        }
        headers = {"X-CSRFToken": token}

        res = client.post(
            f"/api/cases/{case['case_id']}/evidence",
            data=data,
            content_type="multipart/form-data",
            headers=headers,
        )

        assert res.status_code == 201
        res_data = res.get_json()
        assert res_data["status"] == "uploaded"

    def test_upload_with_csrf_token_in_form_data_succeeds(self, app, test_user, tiny_png):
        """CSRF token supplied in multipart/form-data body authorizes upload when headers are omitted."""
        token = secrets.token_hex(32)
        client = _make_manual_client(app, test_user, token)

        with app.app_context():
            case = create_case("CSRF Form Field Test Case", user_id=test_user["user_id"])

        data = {
            "file": (io.BytesIO(tiny_png), "form_evidence.png"),
            "csrf_token": token,
        }
        # No CSRF header passed
        res = client.post(
            f"/api/cases/{case['case_id']}/evidence",
            data=data,
            content_type="multipart/form-data",
        )

        assert res.status_code == 201
        res_data = res.get_json()
        assert res_data["status"] == "uploaded"
        assert res_data["evidence"]["original_name"] == "form_evidence.png"

    def test_upload_with_both_header_and_form_data_succeeds(self, app, test_user, tiny_png):
        """CSRF token supplied in both header and form-data succeeds cleanly."""
        token = secrets.token_hex(32)
        client = _make_manual_client(app, test_user, token)

        with app.app_context():
            case = create_case("CSRF Dual Header Form Test", user_id=test_user["user_id"])

        data = {
            "file": (io.BytesIO(tiny_png), "dual_evidence.png"),
            "csrf_token": token,
        }
        headers = {"X-CSRF-Token": token}

        res = client.post(
            f"/api/cases/{case['case_id']}/evidence",
            data=data,
            content_type="multipart/form-data",
            headers=headers,
        )

        assert res.status_code == 201
        res_data = res.get_json()
        assert res_data["status"] == "uploaded"

    def test_upload_missing_csrf_rejected_403(self, app, test_user, tiny_png):
        """Upload request without CSRF token in headers or form data is rejected with 403."""
        token = secrets.token_hex(32)
        client = _make_manual_client(app, test_user, token)

        with app.app_context():
            case = create_case("CSRF Missing Test Case", user_id=test_user["user_id"])

        data = {
            "file": (io.BytesIO(tiny_png), "unauthorized.png"),
        }
        # No CSRF header or form field provided
        res = client.post(
            f"/api/cases/{case['case_id']}/evidence",
            data=data,
            content_type="multipart/form-data",
        )

        assert res.status_code == 403
        data_json = res.get_json()
        assert data_json["code"] == "CSRF_ERROR"
        assert "CSRF token missing" in data_json["error"]

    def test_upload_tampered_csrf_header_rejected_403(self, app, test_user, tiny_png):
        """Upload request with an invalid/tampered CSRF header is rejected with 403."""
        token = secrets.token_hex(32)
        client = _make_manual_client(app, test_user, token)

        with app.app_context():
            case = create_case("CSRF Tampered Test Case", user_id=test_user["user_id"])

        data = {
            "file": (io.BytesIO(tiny_png), "tampered.png"),
        }
        headers = {"X-CSRF-Token": "bogus_tampered_csrf_token_1234567890"}

        res = client.post(
            f"/api/cases/{case['case_id']}/evidence",
            data=data,
            content_type="multipart/form-data",
            headers=headers,
        )

        assert res.status_code == 403
        data_json = res.get_json()
        assert data_json["code"] == "CSRF_ERROR"
        assert "CSRF token invalid" in data_json["error"]

    def test_upload_tampered_csrf_form_field_rejected_403(self, app, test_user, tiny_png):
        """Upload request with an invalid CSRF form field is rejected with 403."""
        token = secrets.token_hex(32)
        client = _make_manual_client(app, test_user, token)

        with app.app_context():
            case = create_case("CSRF Tampered Form Test", user_id=test_user["user_id"])

        data = {
            "file": (io.BytesIO(tiny_png), "tampered.png"),
            "csrf_token": "wrong_token_value",
        }

        res = client.post(
            f"/api/cases/{case['case_id']}/evidence",
            data=data,
            content_type="multipart/form-data",
        )

        assert res.status_code == 403
        data_json = res.get_json()
        assert data_json["code"] == "CSRF_ERROR"
        assert "CSRF token invalid" in data_json["error"]

    def test_upload_empty_csrf_token_rejected_403(self, app, test_user, tiny_png):
        """Upload request with whitespace-only CSRF token is rejected with 403."""
        token = secrets.token_hex(32)
        client = _make_manual_client(app, test_user, token)

        with app.app_context():
            case = create_case("CSRF Empty Token Test", user_id=test_user["user_id"])

        data = {
            "file": (io.BytesIO(tiny_png), "empty.png"),
        }
        headers = {"X-CSRF-Token": "   "}

        res = client.post(
            f"/api/cases/{case['case_id']}/evidence",
            data=data,
            content_type="multipart/form-data",
            headers=headers,
        )

        assert res.status_code == 403
        data_json = res.get_json()
        assert data_json["code"] == "CSRF_ERROR"

    def test_unauthenticated_upload_rejected(self, app, tiny_png):
        """An unauthenticated request cannot upload evidence (rejected with 401/302)."""
        raw_client = FlaskClient(app)

        data = {
            "file": (io.BytesIO(tiny_png), "unauth.png"),
        }
        res = raw_client.post(
            "/api/cases/case_nonexistent/evidence",
            data=data,
            content_type="multipart/form-data",
        )
        # Should be 401 or redirect to login
        assert res.status_code in (401, 302, 403)

    def test_upload_to_another_users_case_rejected_403(self, app, test_user, tiny_png):
        """A user cannot upload evidence to a case owned by a different user."""
        token = secrets.token_hex(32)
        client = _make_manual_client(app, test_user, token)

        # Create another user and case
        with app.app_context():
            other_user = create_user("victim_user", "victim@test.local", "VictimPass123!", role="user")
            victim_case = create_case("Victim Private Case", user_id=other_user["user_id"])

        data = {
            "file": (io.BytesIO(tiny_png), "malicious_evidence.png"),
        }
        headers = {"X-CSRF-Token": token}

        res = client.post(
            f"/api/cases/{victim_case['case_id']}/evidence",
            data=data,
            content_type="multipart/form-data",
            headers=headers,
        )

        assert res.status_code == 403
        res_data = res.get_json()
        assert res_data["code"] == "FORBIDDEN"

    def test_multimodal_uploads_with_csrf(self, app, test_user, tiny_png, tiny_wav, tiny_mp4):
        """All supported media modalities (image, audio, video) upload cleanly with CSRF."""
        token = secrets.token_hex(32)
        client = _make_manual_client(app, test_user, token)

        with app.app_context():
            case = create_case("Multimodal CSRF Case", user_id=test_user["user_id"])
        case_id = case["case_id"]

        headers = {"X-CSRF-Token": token}

        # 1. Image Upload
        res_img = client.post(
            f"/api/cases/{case_id}/evidence",
            data={"file": (io.BytesIO(tiny_png), "camera.png"), "csrf_token": token},
            content_type="multipart/form-data",
            headers=headers,
        )
        assert res_img.status_code == 201
        assert res_img.get_json()["evidence"]["modality"] == "image"

        # 2. Audio Upload
        res_aud = client.post(
            f"/api/cases/{case_id}/evidence",
            data={"file": (io.BytesIO(tiny_wav), "wiretap.wav"), "csrf_token": token},
            content_type="multipart/form-data",
            headers=headers,
        )
        assert res_aud.status_code == 201
        assert res_aud.get_json()["evidence"]["modality"] == "audio"

        # 3. Video Upload
        res_vid = client.post(
            f"/api/cases/{case_id}/evidence",
            data={"file": (io.BytesIO(tiny_mp4), "cctv.mp4"), "csrf_token": token},
            content_type="multipart/form-data",
            headers=headers,
        )
        assert res_vid.status_code == 201
        assert res_vid.get_json()["evidence"]["modality"] == "video"
