"""
tests/test_hardware_and_inference_resilience.py — Verification of Hardware Constraints & Graceful Inference Degradation.

Verifies:
1. Hardware memory assessment across cgroups and OS counters.
2. Graceful pre-flight rejection with actionable diagnostics on memory-constrained hosts (e.g. Render Free 512MB RAM).
3. Reliable non-crashing HTTP 200 failure responses across Image, Audio, and Video modules.
4. One-click baseline restoration for all three modalities (Image, Audio, Video).
5. Health check transparency regarding host memory and inference capability.
"""

import json
import pytest
from app import create_app
from services.hardware_utils import get_system_memory_mb, is_inference_memory_sufficient


class TestHardwareUtilsUnit:
    """Unit tests for services/hardware_utils.py."""

    def test_get_system_memory_mb_returns_positive_or_none(self):
        mem = get_system_memory_mb()
        if mem is not None:
            assert isinstance(mem, int)
            assert mem > 0

    def test_is_inference_memory_sufficient_when_memory_low(self, monkeypatch):
        monkeypatch.setattr("services.hardware_utils.get_system_memory_mb", lambda: 512)
        monkeypatch.delenv("ALLOW_UNSAFE_INFERENCE", raising=False)
        ok, mem, msg = is_inference_memory_sufficient(min_mb=1500, model_name="RT-DETR")
        assert ok is False
        assert mem == 512
        assert "Host hardware limitation" in msg
        assert "512 MB" in msg
        assert "RT-DETR" in msg

    def test_is_inference_memory_sufficient_when_memory_high(self, monkeypatch):
        monkeypatch.setattr("services.hardware_utils.get_system_memory_mb", lambda: 4096)
        monkeypatch.delenv("ALLOW_UNSAFE_INFERENCE", raising=False)
        ok, mem, msg = is_inference_memory_sufficient(min_mb=1500, model_name="RT-DETR")
        assert ok is True
        assert mem == 4096
        assert "is sufficient" in msg

    def test_is_inference_memory_sufficient_when_bypassed_by_env(self, monkeypatch):
        monkeypatch.setattr("services.hardware_utils.get_system_memory_mb", lambda: 512)
        monkeypatch.setenv("ALLOW_UNSAFE_INFERENCE", "true")
        ok, mem, msg = is_inference_memory_sufficient(min_mb=1500, model_name="RT-DETR")
        assert ok is True
        assert "Unsafe memory allocation allowed" in msg


class TestInferenceResilienceUnderHostConstraints:
    """End-to-end API tests for Image, Audio, and Video modules under host resource constraints."""

    @pytest.fixture()
    def test_client(self, tmp_path):
        isolated = tmp_path / "resilience_workspace"
        cfg = {
            "TESTING": True,
            "STORAGE_DIR": isolated,
            "CASES_DIR": isolated / "cases",
            "UPLOADS_DIR": isolated / "uploads",
            "REPORTS_DIR": isolated / "reports",
            "DB_PATH": isolated / "resilience.db",
            "SECRET_KEY": "resilience-test-secret-key-32-bytes!",
        }
        app = create_app(config_override=cfg)
        client = app.test_client()

        # Login as user-12
        csrf_tok = client.get("/api/auth/csrf").get_json()["csrf_token"]
        login_res = client.post(
            "/api/auth/login",
            json={"username": "user-12", "password": "user1234"},
            headers={"X-CSRF-Token": csrf_tok},
        )
        assert login_res.status_code == 200
        return client, app

    def test_image_analysis_graceful_failure_on_low_memory(self, test_client, monkeypatch):
        """Image analysis returns 200 with actionable error when host RAM is constrained."""
        client, app = test_client
        monkeypatch.setenv("INFERENCE_PROVIDER", "local")
        monkeypatch.setattr("services.hardware_utils.get_system_memory_mb", lambda: 512)
        monkeypatch.delenv("ALLOW_UNSAFE_INFERENCE", raising=False)

        csrf_tok = client.get("/api/auth/csrf").get_json()["csrf_token"]
        resp = client.post(
            "/api/cases/case_bd736d27b0e9/evidence/ev_b31dacb7da6f/analyze/image",
            headers={"X-CSRF-Token": csrf_tok},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "failed"
        assert "Host hardware limitation" in data["error"]
        assert data["analysis"]["is_seeded_sample"] is False
        assert data["analysis"]["error_code"] == "HOST_MEMORY_LIMITATION"

        with app.app_context():
            from storage.database import get_db
            db = get_db()
            row = db.execute("SELECT analysis_status FROM evidence WHERE evidence_id = 'ev_b31dacb7da6f'").fetchone()
            assert row["analysis_status"] == "failed"

    def test_audio_analysis_graceful_failure_on_low_memory(self, test_client, monkeypatch):
        """Audio transcription returns 200 with actionable error when host RAM is constrained."""
        client, app = test_client
        monkeypatch.setenv("INFERENCE_PROVIDER", "local")
        monkeypatch.setattr("services.hardware_utils.get_system_memory_mb", lambda: 512)
        monkeypatch.delenv("ALLOW_UNSAFE_INFERENCE", raising=False)

        csrf_tok = client.get("/api/auth/csrf").get_json()["csrf_token"]
        resp = client.post(
            "/api/cases/case_bd736d27b0e9/evidence/ev_b49348be7de2/analyze/audio",
            headers={"X-CSRF-Token": csrf_tok},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "failed"
        assert data["error_category"] == "HOST_MEMORY_LIMITATION"
        assert "Host hardware limitation" in data["error"]
        assert data["analysis"]["is_seeded_sample"] is False

        with app.app_context():
            from storage.database import get_db
            db = get_db()
            row = db.execute("SELECT analysis_status FROM evidence WHERE evidence_id = 'ev_b49348be7de2'").fetchone()
            assert row["analysis_status"] == "failed"

    def test_video_analysis_graceful_failure_on_low_memory(self, test_client, monkeypatch):
        """Video analysis returns 200 with actionable error when host RAM is constrained."""
        client, app = test_client
        monkeypatch.setenv("INFERENCE_PROVIDER", "local")
        monkeypatch.setattr("services.hardware_utils.get_system_memory_mb", lambda: 512)
        monkeypatch.delenv("ALLOW_UNSAFE_INFERENCE", raising=False)

        csrf_tok = client.get("/api/auth/csrf").get_json()["csrf_token"]
        resp = client.post(
            "/api/cases/case_bd736d27b0e9/evidence/ev_9d23b6a675ce/analyze/video",
            headers={"X-CSRF-Token": csrf_tok},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "failed"
        assert data["analysis"]["error_code"] == "HOST_MEMORY_LIMITATION"
        assert "Host hardware limitation" in data["error"]

        with app.app_context():
            from storage.database import get_db
            db = get_db()
            row = db.execute("SELECT analysis_status FROM evidence WHERE evidence_id = 'ev_9d23b6a675ce'").fetchone()
            assert row["analysis_status"] == "failed"

    def test_restore_seeded_sample_endpoint_works_for_all_three_modalities(self, test_client):
        """Verify restore endpoint restores precomputed baselines for image, audio, and video items."""
        client, app = test_client

        with app.app_context():
            from storage.database import get_db
            db = get_db()
            for eid in ("ev_b31dacb7da6f", "ev_b49348be7de2", "ev_9d23b6a675ce"):
                db.execute("UPDATE evidence SET analysis_status = 'failed' WHERE evidence_id = ?", (eid,))
            db.commit()

        # 1. Restore Image
        csrf_tok = client.get("/api/auth/csrf").get_json()["csrf_token"]
        res_img = client.post(
            "/api/cases/case_bd736d27b0e9/evidence/ev_b31dacb7da6f/restore_seeded_sample",
            headers={"X-CSRF-Token": csrf_tok},
        )
        assert res_img.status_code == 200
        data_img = res_img.get_json()
        assert data_img["status"] == "success"
        aj_img = json.loads(data_img["analysis"]) if isinstance(data_img["analysis"], str) else data_img["analysis"]
        assert aj_img["is_seeded_sample"] is True
        assert len(aj_img["detection"]["objects"]) == 8

        # 2. Restore Audio
        csrf_tok2 = client.get("/api/auth/csrf").get_json()["csrf_token"]
        res_aud = client.post(
            "/api/cases/case_bd736d27b0e9/evidence/ev_b49348be7de2/restore_seeded_sample",
            headers={"X-CSRF-Token": csrf_tok2},
        )
        assert res_aud.status_code == 200
        data_aud = res_aud.get_json()
        assert data_aud["status"] == "success"
        aj_aud = json.loads(data_aud["analysis"]) if isinstance(data_aud["analysis"], str) else data_aud["analysis"]
        assert aj_aud["is_seeded_sample"] is True
        assert "Target vehicle confirmed" in aj_aud["transcript"]

        # 3. Restore Video
        csrf_tok3 = client.get("/api/auth/csrf").get_json()["csrf_token"]
        res_vid = client.post(
            "/api/cases/case_bd736d27b0e9/evidence/ev_9d23b6a675ce/restore_seeded_sample",
            headers={"X-CSRF-Token": csrf_tok3},
        )
        assert res_vid.status_code == 200
        data_vid = res_vid.get_json()
        assert data_vid["status"] == "success"
        aj_vid = json.loads(data_vid["analysis"]) if isinstance(data_vid["analysis"], str) else data_vid["analysis"]
        assert aj_vid["is_seeded_sample"] is True
        assert aj_vid["sampled_frame_count"] == 15

    def test_health_endpoint_reports_memory_and_inference_status(self, test_client):
        """Verify /api/health exposes host memory and live inference readiness accurately."""
        client, _ = test_client
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "checks" in data
        assert "host_memory_mb" in data["checks"]
        assert "live_inference_status" in data["checks"]
