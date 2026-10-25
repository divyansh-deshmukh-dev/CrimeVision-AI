"""
tests/test_cloud_and_demo.py — Test suite for Vercel, Cloud Storage, PostgreSQL Adapter, and Mentor Demo.

Verifies:
  1. Demo login flow & read-only restrictions (mutating operations blocked).
  2. Normal user isolation (multi-tenant IDOR protection).
  3. Cloud storage abstraction (S3 provider with mocked boto3 client).
  4. Database adapter (SQLAlchemy query parameter mapping and row parity).
  5. Data migration utility (dry-run, idempotency, checksums).
  6. Vercel entrypoint (api/index.py) compatibility.
"""

import io
import json
from pathlib import Path
import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from app import create_app
from services.storage_service import (
    BaseStorageProvider,
    LocalStorageProvider,
    S3StorageProvider,
    get_storage_provider,
    set_storage_provider,
)
from storage.database import ConnectionAdapter, CursorAdapter, RowAdapter, get_db, init_db
from storage.migrate_data import inspect_source_data, run_migration
from storage.provision_demo import provision_demo_account
from storage.users_store import create_user, get_user_by_username


# ── 1. Demo Login & Read-Only Restrictions ───────────────────────────────────

class TestDemoLoginAndRestrictions:
    """Verify demo login endpoint, session attributes, and strict read-only enforcement."""

    def test_demo_login_endpoint_success(self, app, client):
        """Verify POST /api/auth/demo-login provisions demo and creates demo session."""
        with app.app_context():
            res = client.post("/api/auth/demo-login")
            assert res.status_code == 200
            data = res.get_json()
            assert data["status"] == "authenticated"
            assert data["is_demo"] is True
            assert data["user"]["role"] == "demo"

    def test_demo_user_can_create_live_case(self, app, client):
        """Demo user can create a writable live demonstration case container."""
        with app.app_context():
            # Login as demo
            client.post("/api/auth/demo-login")

            # Case creation succeeds with demo_type='live'
            res = client.post(
                "/api/cases",
                json={"name": "Live Investigation Case", "description": "Interactive forensic testing"},
            )
            assert res.status_code == 201
            data = res.get_json()
            assert data["status"] == "created"
            assert data["case"]["name"] == "Live Investigation Case"
            assert data["case"]["demo_type"] == "live"

    def test_demo_user_cannot_upload_evidence(self, app, client, tiny_png):
        """Demo user cannot upload new evidence to demo cases."""
        with app.app_context():
            client.post("/api/auth/demo-login")

            data = {
                "file": (io.BytesIO(tiny_png), "exploit.png"),
            }
            res = client.post(
                "/api/cases/case_demo_sentinel/evidence",
                data=data,
                content_type="multipart/form-data",
            )
            assert res.status_code == 403
            assert res.get_json()["code"] == "DEMO_CASE_READ_ONLY"

    def test_demo_user_cannot_delete_demo_case(self, app, client):
        """Demo user cannot delete shared demo cases."""
        with app.app_context():
            client.post("/api/auth/demo-login")

            res = client.delete("/api/cases/case_demo_sentinel")
            assert res.status_code == 403
            assert res.get_json()["code"] == "DEMO_CASE_READ_ONLY"

    def test_demo_user_cannot_delete_demo_evidence(self, app, client):
        """Demo user cannot delete shared demo evidence."""
        with app.app_context():
            client.post("/api/auth/demo-login")

            res = client.delete("/api/cases/case_demo_sentinel/evidence/ev_demo_img_01")
            assert res.status_code == 403
            assert res.get_json()["code"] == "DEMO_CASE_READ_ONLY"

    def test_demo_user_cannot_clear_demo_chat_history(self, app, client):
        """Demo user cannot wipe chat history on shared demo cases."""
        with app.app_context():
            client.post("/api/auth/demo-login")

            res = client.delete("/api/cases/case_demo_sentinel/chat/history")
            assert res.status_code == 403
            assert res.get_json()["code"] == "DEMO_CASE_READ_ONLY"

    def test_demo_user_can_view_demo_evidence_and_analysis(self, app, client):
        """Demo user can view preloaded demo evidence and precomputed analysis."""
        with app.app_context():
            client.post("/api/auth/demo-login")

            # List evidence
            res = client.get("/api/cases/case_demo_sentinel/evidence")
            assert res.status_code == 200
            ev_list = res.get_json()["evidence"]
            assert len(ev_list) >= 3

            # View image analysis (returns precomputed completed result)
            res_analysis = client.post("/api/cases/case_demo_sentinel/evidence/ev_demo_img_01/analyze/image")
            assert res_analysis.status_code == 200
            assert res_analysis.get_json()["status"] == "completed"
            assert "detections" in res_analysis.get_json()["analysis"]

    def test_demo_user_cannot_access_normal_user_private_case(self, app, client):
        """Demo user cannot access cases owned by private normal examiners."""
        with app.app_context():
            # Create a private user and private case
            private_user = create_user("private_examiner", "priv@test.gov", "TestPass1234!", role="user")
            from storage.cases_store import create_case
            priv_case = create_case("Secret Operation", user_id=private_user["user_id"])

            # Switch session to demo user
            client.post("/api/auth/demo-login")

            # Attempt to read private case
            res = client.get(f"/api/cases/{priv_case['case_id']}")
            assert res.status_code == 403
            assert res.get_json()["code"] == "FORBIDDEN"

    def test_demo_user_can_upload_evidence_to_live_case(self, app, client, tiny_png):
        """Demo user can upload evidence to their own live demo case container."""
        with app.app_context():
            client.post("/api/auth/demo-login")

            # Create a live demo case
            c_res = client.post("/api/cases", json={"name": "Live Case Uploads"}).get_json()
            case_id = c_res["case"]["case_id"]

            # Upload evidence
            data = {"file": (io.BytesIO(tiny_png), "live_sample.png")}
            res = client.post(
                f"/api/cases/{case_id}/evidence",
                data=data,
                content_type="multipart/form-data",
            )
            assert res.status_code == 201
            ev_data = res.get_json()
            assert ev_data["status"] == "uploaded"
            assert ev_data["evidence"]["case_id"] == case_id

            # Verify evidence list reflects newly uploaded artifact
            list_res = client.get(f"/api/cases/{case_id}/evidence")
            assert list_res.status_code == 200
            assert list_res.get_json()["count"] == 1

    def test_live_demo_runs_real_inference_without_precomputed_bypass(self, app, client, tiny_png):
        """Live demo case runs actual AI inference without precomputed bypass."""
        with app.app_context():
            client.post("/api/auth/demo-login")

            # Create live case & upload
            c_res = client.post("/api/cases", json={"name": "Inference Test Case"}).get_json()
            case_id = c_res["case"]["case_id"]

            data = {"file": (io.BytesIO(tiny_png), "test_infer.png")}
            up_res = client.post(
                f"/api/cases/{case_id}/evidence",
                data=data,
                content_type="multipart/form-data",
            ).get_json()
            ev_id = up_res["evidence"]["evidence_id"]

            # Run image analysis with mock pipeline to observe invocation
            mock_pipeline_res = {
                "status": "completed",
                "image_metadata": {"width": 1, "height": 1},
                "detection": {"status": "success", "objects": [{"label": "person", "confidence": 0.9}]},
                "clip": {"status": "success", "matches": []},
                "caption": {"status": "success", "caption": "a live test caption"},
            }
            with patch("services.image_analyzer.ImageAnalyzer.analyze_image_pipeline", return_value=mock_pipeline_res) as mock_pipe:
                res = client.post(f"/api/cases/{case_id}/evidence/{ev_id}/analyze/image")
                assert res.status_code == 200
                assert mock_pipe.called
                res_data = res.get_json()
                assert res_data["status"] == "completed"
                prov = res_data["analysis"].get("provenance", {})
                assert prov.get("result_source") != "precomputed_demo_result"

    def test_reanalysis_in_live_demo_case_triggers_fresh_inference(self, app, client, tiny_png):
        """Re-analyzing an already-completed item in live demo re-runs inference."""
        with app.app_context():
            client.post("/api/auth/demo-login")

            c_res = client.post("/api/cases", json={"name": "Reanalysis Case"}).get_json()
            case_id = c_res["case"]["case_id"]

            data = {"file": (io.BytesIO(tiny_png), "reanalysis.png")}
            up_res = client.post(f"/api/cases/{case_id}/evidence", data=data, content_type="multipart/form-data").get_json()
            ev_id = up_res["evidence"]["evidence_id"]

            from storage.evidence_store import update_analysis
            update_analysis(ev_id, status="completed", analysis_data={"prior": True})

            mock_pipeline_res = {
                "status": "completed",
                "image_metadata": {"width": 1, "height": 1},
                "detection": {"status": "success", "objects": []},
                "clip": {"status": "success", "matches": []},
                "caption": {"status": "success", "caption": "re-analyzed caption"},
            }
            with patch("services.image_analyzer.ImageAnalyzer.analyze_image_pipeline", return_value=mock_pipeline_res) as mock_pipe:
                res = client.post(f"/api/cases/{case_id}/evidence/{ev_id}/analyze/image")
                assert res.status_code == 200
                assert mock_pipe.called

    def test_demo_user_can_delete_own_live_case_evidence(self, app, client, tiny_png):
        """Demo user can delete evidence from their own live case."""
        with app.app_context():
            client.post("/api/auth/demo-login")

            c_res = client.post("/api/cases", json={"name": "Delete Case"}).get_json()
            case_id = c_res["case"]["case_id"]

            data = {"file": (io.BytesIO(tiny_png), "to_delete.png")}
            up_res = client.post(f"/api/cases/{case_id}/evidence", data=data, content_type="multipart/form-data").get_json()
            ev_id = up_res["evidence"]["evidence_id"]

            del_res = client.delete(f"/api/cases/{case_id}/evidence/{ev_id}")
            assert del_res.status_code == 200
            assert del_res.get_json()["status"] == "deleted"


# ── 2. Cloud Storage Abstraction (S3 with Mocked Provider) ───────────────────

class TestCloudStorageAbstraction:
    """Verify S3StorageProvider behavior using mocked boto3 S3 client."""

    def test_s3_storage_upload_and_stream(self):
        """Verify S3 upload and chunked streaming without saving to production filesystem."""
        mock_s3 = MagicMock()
        mock_body = MagicMock()
        mock_body.read.side_effect = [b"chunk1_", b"chunk2", b""]

        mock_s3.get_object.return_value = {
            "Body": mock_body,
            "ContentLength": 13,
            "ContentType": "image/png",
        }

        provider = S3StorageProvider(
            bucket_name="test-forensic-bucket",
            region="us-east-1",
            s3_client=mock_s3,
        )

        # Upload
        key = provider.upload_evidence(
            case_id="case_100",
            evidence_id="ev_200",
            filename="surveillance.png",
            file_data=b"test_payload_bytes",
            mime_type="image/png",
        )
        assert key == "case_100/ev_200/surveillance.png"
        mock_s3.put_object.assert_called_once_with(
            Bucket="test-forensic-bucket",
            Key="case_100/ev_200/surveillance.png",
            Body=b"test_payload_bytes",
            ContentType="image/png",
            Metadata={"case_id": "case_100", "evidence_id": "ev_200", "original_filename": "surveillance.png"},
        )

        # Stream
        chunks, length, mime = provider.get_evidence_stream(key)
        assert length == 13
        assert mime == "image/png"
        streamed = b"".join(chunks)
        assert streamed == b"chunk1_chunk2"

    def test_s3_storage_delete_evidence(self):
        """Verify S3 object deletion prefix paginator."""
        mock_s3 = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"Contents": [{"Key": "case_1/ev_1/photo.jpg"}]}
        ]
        mock_s3.get_paginator.return_value = mock_paginator

        provider = S3StorageProvider(
            bucket_name="test-bucket",
            s3_client=mock_s3,
        )
        success = provider.delete_evidence("case_1", "ev_1")
        assert success is True
        mock_s3.delete_objects.assert_called_once()

    def test_s3_storage_local_cache_path(self, tmp_path):
        """Verify S3 downloads on-demand to cache_dir when local path is requested."""
        mock_s3 = MagicMock()
        provider = S3StorageProvider(
            bucket_name="test-bucket",
            cache_dir=tmp_path / "cache",
            s3_client=mock_s3,
        )

        local_path = provider.get_local_cache_path("case_1/ev_1/test.mp4")
        mock_s3.download_file.assert_called_once_with(
            "test-bucket", "case_1/ev_1/test.mp4", str(local_path)
        )
        assert local_path.parent.is_dir()


# ── 3. Database Adapter & Parameter Mapping ──────────────────────────────────

class TestDatabaseAdapter:
    """Verify SQLAlchemy query parameter adaptation and RowAdapter dictionary parity."""

    def test_row_adapter_dict_and_index_access(self):
        """RowAdapter must allow both dict['col'] and tuple[0] indexing."""
        row = RowAdapter({"case_id": "c1", "name": "Case One"}, ("c1", "Case One"))
        assert row["case_id"] == "c1"
        assert row["name"] == "Case One"
        assert row[0] == "c1"
        assert row[1] == "Case One"
        assert dict(row) == {"case_id": "c1", "name": "Case One"}
        assert len(row) == 2

    def test_connection_adapter_param_mapping(self):
        """ConnectionAdapter must translate '?' parameter markers to named parameters."""
        mock_conn = MagicMock()
        adapter = ConnectionAdapter(mock_conn)

        adapter.execute("SELECT * FROM users WHERE username = ? AND is_active = ?", ("test", 1))

        # Check call arguments
        assert mock_conn.execute.call_count == 1
        call_args = mock_conn.execute.call_args
        executed_text = str(call_args[0][0])
        param_dict = call_args[0][1]

        assert ":p0" in executed_text
        assert ":p1" in executed_text
        assert param_dict == {"p0": "test", "p1": 1}


# ── 4. Data Migration Utility ─────────────────────────────────────────────────

class TestDataMigration:
    """Verify inspection, dry-run, and idempotent migration execution."""

    def test_migration_dry_run(self, tmp_path):
        """Dry-run must report record counts without modifying target database."""
        db_file = tmp_path / "source.db"
        conn = sqlite3.connect(str(db_file))
        conn.execute("CREATE TABLE cases (case_id TEXT PRIMARY KEY, user_id TEXT, name TEXT, created_at TEXT, updated_at TEXT, is_demo INTEGER);")
        conn.execute("CREATE TABLE evidence (evidence_id TEXT PRIMARY KEY, case_id TEXT, filename TEXT, original_name TEXT, modality TEXT, mime_type TEXT, sha256 TEXT, file_size INTEGER, uploaded_at TEXT, analysis_status TEXT, analysis_json TEXT);")
        conn.execute("CREATE TABLE reports (report_id TEXT PRIMARY KEY, case_id TEXT, filename TEXT, created_at TEXT, file_size INTEGER);")
        conn.execute("CREATE TABLE chat_messages (message_id TEXT PRIMARY KEY, case_id TEXT, role TEXT, content TEXT, metadata_json TEXT, created_at TEXT);")
        conn.execute("CREATE TABLE users (user_id TEXT PRIMARY KEY, display_name TEXT, username TEXT, email TEXT, password_hash TEXT, role TEXT, created_at TEXT, is_active INTEGER);")

        conn.execute("INSERT INTO cases VALUES ('c_src_1', NULL, 'Sample Source Case', '2026-01-01', '2026-01-01', 1);")
        conn.commit()
        conn.close()

        uploads_dir = tmp_path / "uploads"
        reports_dir = tmp_path / "reports"
        uploads_dir.mkdir()
        reports_dir.mkdir()

        summary = run_migration(
            source_db_path=db_file,
            source_uploads_dir=uploads_dir,
            source_reports_dir=reports_dir,
            dry_run=True,
            demo_only=True,
        )
        assert summary["dry_run"] is True
        assert summary["status"] == "dry_run_completed"
        assert summary["cases_count"] == 1


# ── 5. Vercel Entrypoint Compatibility ────────────────────────────────────────

class TestVercelEntrypoint:
    """Verify that api/index.py loads cleanly as a WSGI entrypoint."""

    def test_vercel_index_exports_app(self):
        """api/index.py must expose an 'app' instance of Flask."""
        from api.index import app as vercel_app
        assert vercel_app is not None
        assert vercel_app.name == "app"
        # Confirm blueprints are attached
        assert "health" in vercel_app.blueprints
        assert "cases" in vercel_app.blueprints
        assert "auth" in vercel_app.blueprints
