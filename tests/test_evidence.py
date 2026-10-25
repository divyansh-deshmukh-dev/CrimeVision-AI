"""
tests/test_evidence.py — Tests for evidence upload and retrieval endpoints.

Covers:
  POST /api/cases/<id>/evidence  — upload image / audio / video
  GET  /api/cases/<id>/evidence  — list evidence
  GET  /api/cases/<id>/evidence/<ev_id>  — get single evidence
  Failure paths: missing file, bad extension, unknown case, empty file.
"""

import io
import pytest


def _upload(client, case_id: str, file_bytes: bytes, filename: str, content_type: str):
    """Helper: POST a multipart upload to /api/cases/<id>/evidence."""
    data = {
        "file": (io.BytesIO(file_bytes), filename, content_type),
    }
    return client.post(
        f"/api/cases/{case_id}/evidence",
        data=data,
        content_type="multipart/form-data",
    )


class TestUploadEvidence:
    """POST /api/cases/<case_id>/evidence"""

    # ── Happy path ────────────────────────────────────────────────────────────

    def test_upload_image_returns_201(self, client, case_id, tiny_png):
        resp = _upload(client, case_id, tiny_png, "scene.png", "image/png")
        assert resp.status_code == 201, resp.get_json()

    def test_upload_audio_returns_201(self, client, case_id, tiny_wav):
        resp = _upload(client, case_id, tiny_wav, "witness.wav", "audio/wav")
        assert resp.status_code == 201, resp.get_json()

    def test_upload_video_returns_201(self, client, case_id, tiny_mp4):
        resp = _upload(client, case_id, tiny_mp4, "cctv.mp4", "video/mp4")
        assert resp.status_code == 201, resp.get_json()

    def test_upload_response_structure(self, client, case_id, tiny_png):
        data = _upload(client, case_id, tiny_png, "test.png", "image/png").get_json()
        assert data["status"] == "uploaded"
        ev = data["evidence"]
        for field in (
            "evidence_id", "case_id", "original_name", "modality",
            "mime_type", "sha256", "file_size", "uploaded_at", "analysis_status",
        ):
            assert field in ev, f"'{field}' missing from evidence response"

    def test_upload_sha256_is_64_hex_chars(self, client, case_id, tiny_png):
        ev = _upload(client, case_id, tiny_png, "hash_test.png", "image/png").get_json()["evidence"]
        sha = ev["sha256"]
        assert len(sha) == 64, f"SHA-256 should be 64 hex chars, got {len(sha)}"
        assert all(c in "0123456789abcdef" for c in sha)

    def test_upload_analysis_status_pending(self, client, case_id, tiny_png):
        ev = _upload(client, case_id, tiny_png, "pending.png", "image/png").get_json()["evidence"]
        assert ev["analysis_status"] == "pending"

    def test_upload_modality_image(self, client, case_id, tiny_png):
        ev = _upload(client, case_id, tiny_png, "img.png", "image/png").get_json()["evidence"]
        assert ev["modality"] == "image"

    def test_upload_modality_audio(self, client, case_id, tiny_wav):
        ev = _upload(client, case_id, tiny_wav, "audio.wav", "audio/wav").get_json()["evidence"]
        assert ev["modality"] == "audio"

    def test_upload_modality_video(self, client, case_id, tiny_mp4):
        ev = _upload(client, case_id, tiny_mp4, "vid.mp4", "video/mp4").get_json()["evidence"]
        assert ev["modality"] == "video"

    def test_upload_file_size_recorded(self, client, case_id, tiny_png):
        ev = _upload(client, case_id, tiny_png, "size.png", "image/png").get_json()["evidence"]
        assert ev["file_size"] == len(tiny_png)

    def test_upload_case_id_matches(self, client, case_id, tiny_png):
        ev = _upload(client, case_id, tiny_png, "cid.png", "image/png").get_json()["evidence"]
        assert ev["case_id"] == case_id

    def test_upload_original_name_preserved(self, client, case_id, tiny_png):
        ev = _upload(client, case_id, tiny_png, "my_evidence.png", "image/png").get_json()["evidence"]
        assert ev["original_name"] == "my_evidence.png"

    def test_upload_evidence_id_format(self, client, case_id, tiny_png):
        ev = _upload(client, case_id, tiny_png, "id_format.png", "image/png").get_json()["evidence"]
        assert ev["evidence_id"].startswith("ev_")

    def test_sha256_deterministic(self, client, case_id, tiny_png):
        """Same bytes → same SHA-256 regardless of filename."""
        ev1 = _upload(client, case_id, tiny_png, "a.png", "image/png").get_json()["evidence"]
        ev2 = _upload(client, case_id, tiny_png, "b.png", "image/png").get_json()["evidence"]
        assert ev1["sha256"] == ev2["sha256"]

    # ── Failure paths ─────────────────────────────────────────────────────────

    def test_upload_to_nonexistent_case_returns_404(self, client, tiny_png):
        resp = _upload(client, "case_does_not_exist", tiny_png, "f.png", "image/png")
        assert resp.status_code == 404

    def test_upload_no_file_field_returns_400(self, client, case_id):
        resp = client.post(
            f"/api/cases/{case_id}/evidence",
            data={"other": "value"},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_upload_disallowed_extension_returns_400(self, client, case_id):
        resp = _upload(client, case_id, b"data", "malware.exe", "application/octet-stream")
        assert resp.status_code == 400

    def test_upload_empty_file_returns_400(self, client, case_id):
        resp = _upload(client, case_id, b"", "empty.png", "image/png")
        assert resp.status_code == 400

    def test_upload_python_script_returns_400(self, client, case_id):
        resp = _upload(client, case_id, b"print('hi')", "evil.py", "text/plain")
        assert resp.status_code == 400

    def test_upload_pdf_returns_400(self, client, case_id):
        resp = _upload(client, case_id, b"%PDF-1.4", "document.pdf", "application/pdf")
        assert resp.status_code == 400

    def test_upload_zip_returns_400(self, client, case_id):
        resp = _upload(client, case_id, b"PK\x03\x04", "archive.zip", "application/zip")
        assert resp.status_code == 400


class TestListEvidence:
    """GET /api/cases/<case_id>/evidence"""

    def test_list_empty_when_no_evidence(self, client, case_id):
        data = client.get(f"/api/cases/{case_id}/evidence").get_json()
        assert data["count"] == 0
        assert data["evidence"] == []

    def test_list_count_increases_after_upload(self, client, case_id, tiny_png):
        _upload(client, case_id, tiny_png, "a.png", "image/png")
        _upload(client, case_id, tiny_png, "b.png", "image/png")
        data = client.get(f"/api/cases/{case_id}/evidence").get_json()
        assert data["count"] == 2

    def test_list_for_nonexistent_case_returns_404(self, client):
        resp = client.get("/api/cases/no_such_case/evidence")
        assert resp.status_code == 404


class TestGetSingleEvidence:
    """GET /api/cases/<case_id>/evidence/<evidence_id>"""

    def test_get_existing_evidence(self, client, case_id, tiny_png):
        ev_id = _upload(client, case_id, tiny_png, "get_test.png", "image/png").get_json()["evidence"]["evidence_id"]
        resp = client.get(f"/api/cases/{case_id}/evidence/{ev_id}")
        assert resp.status_code == 200
        assert resp.get_json()["evidence"]["evidence_id"] == ev_id

    def test_get_nonexistent_evidence_returns_404(self, client, case_id):
        resp = client.get(f"/api/cases/{case_id}/evidence/ev_doesnotexist")
        assert resp.status_code == 404

    def test_get_evidence_wrong_case_returns_404(self, client, tiny_png):
        """Evidence ID belonging to one case must not be accessible via another case's URL."""
        res_a = client.post("/api/cases", json={"name": "Case A"})
        cid_a = res_a.get_json()["case"]["case_id"]

        res_b = client.post("/api/cases", json={"name": "Case B"})
        cid_b = res_b.get_json()["case"]["case_id"]

        ev_id = _upload(client, cid_a, tiny_png, "case_a_evidence.png", "image/png").get_json()["evidence"]["evidence_id"]

        # Attempt to access Case A's evidence under Case B's endpoint
        resp = client.get(f"/api/cases/{cid_b}/evidence/{ev_id}")
        assert resp.status_code == 404
        assert f"Evidence '{ev_id}' not found in case '{cid_b}'" in resp.get_json().get("error", "")


class TestDeleteEvidence:
    """DELETE /api/cases/<case_id>/evidence/<evidence_id>"""

    def test_delete_existing_evidence_returns_200(self, client, case_id, tiny_png):
        ev_id = _upload(client, case_id, tiny_png, "del_test.png", "image/png").get_json()["evidence"]["evidence_id"]

        resp = client.delete(f"/api/cases/{case_id}/evidence/{ev_id}")
        assert resp.status_code == 200, resp.get_json()
        assert resp.get_json()["status"] == "deleted"

        # Verify it no longer exists
        get_resp = client.get(f"/api/cases/{case_id}/evidence/{ev_id}")
        assert get_resp.status_code == 404

        # Verify evidence list count drops
        list_resp = client.get(f"/api/cases/{case_id}/evidence")
        assert list_resp.get_json()["count"] == 0

    def test_delete_nonexistent_evidence_returns_404(self, client, case_id):
        resp = client.delete(f"/api/cases/{case_id}/evidence/ev_nonexistent123")
        assert resp.status_code == 404

    def test_delete_evidence_nonexistent_case_returns_404(self, client):
        resp = client.delete("/api/cases/nonexistent_case/evidence/ev_test123")
        assert resp.status_code == 404

    def test_delete_evidence_wrong_case_isolation_returns_404(self, client, tiny_png):
        res_a = client.post("/api/cases", json={"name": "Case Alpha"})
        cid_a = res_a.get_json()["case"]["case_id"]

        res_b = client.post("/api/cases", json={"name": "Case Beta"})
        cid_b = res_b.get_json()["case"]["case_id"]

        ev_id = _upload(client, cid_a, tiny_png, "iso_test.png", "image/png").get_json()["evidence"]["evidence_id"]

        # Attempt to delete Case Alpha's evidence from Case Beta
        resp = client.delete(f"/api/cases/{cid_b}/evidence/{ev_id}")
        assert resp.status_code == 404

        # Verify Case Alpha still has the evidence intact
        still_exists = client.get(f"/api/cases/{cid_a}/evidence/{ev_id}")
        assert still_exists.status_code == 200


class TestEvidenceStorageRobustness:
    """Robustness tests for directory creation, sanitization, long filenames, and write cleanup."""

    def test_upload_mp4_creates_case_and_evidence_directories(self, client, tiny_mp4, app):
        """Uploading an MP4 creates the parent case and evidence directories on disk."""
        c_res = client.post("/api/cases", json={"name": "New Video Case"}).get_json()
        cid = c_res["case"]["case_id"]

        resp = _upload(client, cid, tiny_mp4, "cctv_surveillance.mp4", "video/mp4")
        assert resp.status_code == 201
        ev = resp.get_json()["evidence"]

        uploads_dir = app.config["UPLOADS_DIR"]
        stored_path = uploads_dir / ev["filename"]
        assert stored_path.is_file()
        assert stored_path.parent.is_dir()
        assert stored_path.parent.parent.is_dir()
        assert stored_path.stat().st_size == len(tiny_mp4)

    def test_upload_mp3_and_image(self, client, case_id, tiny_png):
        """Upload MP3 audio and PNG image evidence, verifying metadata and status."""
        tiny_mp3 = b"\xFF\xFB\x90\x00" + (b"\x00" * 256)
        resp_audio = _upload(client, case_id, tiny_mp3, "wiretap_sample.mp3", "audio/mpeg")
        assert resp_audio.status_code == 201
        ev_audio = resp_audio.get_json()["evidence"]
        assert ev_audio["modality"] == "audio"
        assert ev_audio["file_size"] == len(tiny_mp3)

        resp_img = _upload(client, case_id, tiny_png, "forensic_scene.png", "image/png")
        assert resp_img.status_code == 201
        ev_img = resp_img.get_json()["evidence"]
        assert ev_img["modality"] == "image"
        assert ev_img["file_size"] == len(tiny_png)

    def test_upload_creates_missing_destination_directory(self, client, case_id, tiny_mp4, app):
        """If the uploads root or case directory does not pre-exist, mkdir creates it."""
        import shutil
        uploads_dir = app.config["UPLOADS_DIR"]
        case_dir = uploads_dir / case_id
        if case_dir.exists():
            shutil.rmtree(case_dir, ignore_errors=True)

        resp = _upload(client, case_id, tiny_mp4, "resilient_camera.mp4", "video/mp4")
        assert resp.status_code == 201
        ev = resp.get_json()["evidence"]
        assert (uploads_dir / ev["filename"]).is_file()

    def test_upload_long_and_unusual_filenames(self, client, case_id, tiny_mp4, app):
        """Very long filenames (>200 chars) are safely truncated on disk while preserving original_name in DB."""
        long_filename = (
            "Realistic_15-second_continuous_CCTV_surveillance_footage_of_a_small_urban_street_"
            "during_daytime._Fixed_security_camera_mounted_high_on_a_building__overlooking_the_"
            "full_street_and_sidewalk_in_a_wide-angle_view._A_wh.mp4"
        )
        resp = _upload(client, case_id, tiny_mp4, long_filename, "video/mp4")
        assert resp.status_code == 201
        ev = resp.get_json()["evidence"]

        # Original name preserved in metadata
        assert ev["original_name"] == long_filename

        # On-disk filename is sanitized and truncated to prevent Windows MAX_PATH failures
        uploads_dir = app.config["UPLOADS_DIR"]
        stored_file = (uploads_dir / ev["filename"]).resolve()
        assert stored_file.is_file()
        assert stored_file.suffix.lower() == ".mp4"
        assert len(stored_file.name) < 120
        assert stored_file.read_bytes() == tiny_mp4

    def test_failed_write_cleans_up_partial_files(self, client, case_id, tiny_mp4, app, monkeypatch):
        """If a disk write fails, partial files and the empty evidence directory are purged."""
        from pathlib import Path

        def _mock_write_bytes(self, data):
            raise OSError("Simulated disk write failure")

        monkeypatch.setattr(Path, "write_bytes", _mock_write_bytes)

        resp = _upload(client, case_id, tiny_mp4, "failing_write.mp4", "video/mp4")
        assert resp.status_code == 500
        assert "Internal error while saving evidence" in resp.get_json()["error"]

        # Verify no orphan evidence record exists in DB
        list_resp = client.get(f"/api/cases/{case_id}/evidence").get_json()
        matching = [e for e in list_resp["evidence"] if e["original_name"] == "failing_write.mp4"]
        assert len(matching) == 0

    def test_saved_file_exists_at_recorded_storage_path_and_integrity_matches(self, client, case_id, tiny_mp4, app):
        """The saved file exists at the recorded relative path and passes sha256 checksum verification."""
        import hashlib
        resp = _upload(client, case_id, tiny_mp4, "checksum_verified.mp4", "video/mp4")
        assert resp.status_code == 201
        ev = resp.get_json()["evidence"]

        uploads_dir = app.config["UPLOADS_DIR"]
        stored_file = uploads_dir / ev["filename"]
        assert stored_file.is_file()

        disk_bytes = stored_file.read_bytes()
        assert disk_bytes == tiny_mp4
        expected_sha = hashlib.sha256(tiny_mp4).hexdigest()
        assert ev["sha256"] == expected_sha


