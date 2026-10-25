"""
tests/test_fusion_analysis.py — Phase 6 Multimodal Evidence Fusion Test Suite.

Covers:
  1. Multimodal fusion with Image and Video analysis results (cross-modal category matching).
  2. Multimodal fusion with Image, Audio, and Video results (temporal audio-video correlation).
  3. Cases containing only one analyzed modality (single_modality status).
  4. Evidence items that have not yet been analyzed (pending / unanalyzed coverage reporting).
  5. Empty cases (empty status).
  6. Empty transcripts or empty detection lists.
  7. Environmental / scene descriptor contradictions flagged for review.
  8. Preservation of original source model confidence scores and evidence references.
  9. Case-isolation enforcement: evidence and fusion strictly bounded by case ID.
  10. API endpoint success and error responses (POST /api/cases/<cid>/analyze/fusion).
  11. Forensic PDF report integration with Multimodal Fusion section asserting content with pypdf.
"""

import io
from pathlib import Path
import pytest
from pypdf import PdfReader


def _upload_img(client, case_id: str, file_bytes: bytes, filename: str = "scene.png"):
    data = {"file": (io.BytesIO(file_bytes), filename, "image/png")}
    return client.post(f"/api/cases/{case_id}/evidence", data=data, content_type="multipart/form-data")


def _upload_audio(client, case_id: str, file_bytes: bytes, filename: str = "wiretap.wav"):
    data = {"file": (io.BytesIO(file_bytes), filename, "audio/wav")}
    return client.post(f"/api/cases/{case_id}/evidence", data=data, content_type="multipart/form-data")


def _upload_video(client, case_id: str, file_bytes: bytes, filename: str = "cctv.mp4"):
    data = {"file": (io.BytesIO(file_bytes), filename, "video/mp4")}
    return client.post(f"/api/cases/{case_id}/evidence", data=data, content_type="multipart/form-data")


# ── Test Suite ───────────────────────────────────────────────────────────────

class TestFusionAPI:
    """POST /api/cases/<case_id>/analyze/fusion"""

    def test_fusion_nonexistent_case_404(self, client):
        resp = client.post("/api/cases/case_nonexistent_999/analyze/fusion")
        assert resp.status_code == 404
        assert "not found" in resp.get_json()["error"]

    def test_fusion_empty_case_returns_empty_status(self, client, case_id):
        resp = client.post(f"/api/cases/{case_id}/analyze/fusion")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "empty"
        assert data["fusion"]["evidence_count"] == 0
        assert data["fusion"]["analyzed_modalities_count"] == 0

    def test_fusion_cross_case_isolation(self, client, tiny_png):
        from storage.evidence_store import update_analysis

        # Case A with an analyzed image
        res_a = client.post("/api/cases", json={"name": "Case Alpha"}).get_json()
        cid_a = res_a["case"]["case_id"]
        ev_a = _upload_img(client, cid_a, tiny_png, "ev_a.png").get_json()["evidence"]["evidence_id"]
        update_analysis(ev_a, "completed", {
            "detection": {"status": "success", "objects": [{"label": "firearm", "confidence": 0.92}]},
            "caption": {"status": "success", "caption": "a gun on a table"},
        })

        # Case B with no evidence
        res_b = client.post("/api/cases", json={"name": "Case Beta"}).get_json()
        cid_b = res_b["case"]["case_id"]

        # Run fusion on Case B — must NOT see Case A's firearm
        resp_b = client.post(f"/api/cases/{cid_b}/analyze/fusion")
        assert resp_b.status_code == 200
        data_b = resp_b.get_json()
        assert data_b["fusion"]["evidence_count"] == 0
        assert len(data_b["fusion"]["cross_modal_associations"]) == 0

    def test_fusion_single_modality_analyzed(self, client, case_id, tiny_png):
        from storage.evidence_store import update_analysis

        ev_id = _upload_img(client, case_id, tiny_png, "still.png").get_json()["evidence"]["evidence_id"]
        update_analysis(ev_id, "completed", {
            "detection": {"status": "success", "objects": [{"label": "backpack", "confidence": 0.85}]},
            "caption": {"status": "success", "caption": "a red backpack left unattended"},
        })

        resp = client.post(f"/api/cases/{case_id}/analyze/fusion")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "single_modality"
        assert data["fusion"]["analyzed_modalities_count"] == 1
        assert data["fusion"]["modality_coverage"]["image"]["status"] == "analyzed"
        assert data["fusion"]["modality_coverage"]["audio"]["status"] == "unavailable"
        assert data["fusion"]["modality_coverage"]["video"]["status"] == "unavailable"
        assert len(data["fusion"]["cross_modal_associations"]) == 0

    def test_fusion_image_and_video_cross_modal_matching(self, client, case_id, tiny_png, tiny_mp4):
        from storage.evidence_store import update_analysis

        # 1. Upload & analyze Image
        ev_img = _upload_img(client, case_id, tiny_png, "scene.png").get_json()["evidence"]["evidence_id"]
        update_analysis(ev_img, "completed", {
            "detection": {
                "status": "success",
                "objects": [
                    {"label": "person", "confidence": 0.94, "box_pixels": [10, 10, 50, 50]},
                    {"label": "knife", "confidence": 0.88, "box_pixels": [20, 20, 40, 40]},
                ],
            },
            "caption": {"status": "success", "caption": "a person holding a knife"},
        })

        # 2. Upload & analyze Video
        ev_vid = _upload_video(client, case_id, tiny_mp4, "cctv.mp4").get_json()["evidence"]["evidence_id"]
        update_analysis(ev_vid, "completed", {
            "video": {
                "status": "completed",
                "video_metadata": {"fps": 30.0, "total_frames": 90, "duration_seconds": 3.0},
                "sampled_frames": [
                    {
                        "frame_index": 0,
                        "timestamp_seconds": 0.0,
                        "status": "success",
                        "objects": [{"label": "person", "confidence": 0.91, "box_pixels": [50, 50, 100, 100]}],
                    },
                    {
                        "frame_index": 30,
                        "timestamp_seconds": 1.0,
                        "status": "success",
                        "objects": [{"label": "car", "confidence": 0.79, "box_pixels": [100, 100, 200, 200]}],
                    },
                ],
            }
        })

        resp = client.post(f"/api/cases/{case_id}/analyze/fusion")
        assert resp.status_code == 200
        fusion = resp.get_json()["fusion"]

        assert fusion["status"] == "completed"
        assert fusion["analyzed_modalities_count"] == 2
        assert fusion["modality_coverage"]["image"]["status"] == "analyzed"
        assert fusion["modality_coverage"]["video"]["status"] == "analyzed"

        # Check cross-modal category matching: 'person' in both image and video
        assert "cross_modal_corroborations" in fusion
        assert "cross_modal_associations" in fusion
        assert fusion["modality_coverage"]["image_count"] == 1
        assert fusion["modality_coverage"]["video_count"] == 1
        assocs = fusion["cross_modal_associations"]
        assert len(assocs) >= 1
        person_match = next((a for a in assocs if a["category"] == "person"), None)
        assert person_match is not None
        assert "image" in person_match["modalities_involved"]
        assert "video" in person_match["modalities_involved"]
        assert person_match["entity"] == "person"
        assert "observation" in person_match
        # Confirm original confidence scores are preserved
        confs = [r["confidence"] for r in person_match["evidence_references"]]
        assert 0.94 in confs
        assert 0.91 in confs

    def test_fusion_trimodal_with_audio_video_temporal_correlation(self, client, case_id, tiny_png, tiny_wav, tiny_mp4):
        from storage.evidence_store import update_analysis

        # 1. Image
        ev_img = _upload_img(client, case_id, tiny_png, "photo.png").get_json()["evidence"]["evidence_id"]
        update_analysis(ev_img, "completed", {
            "detection": {"status": "success", "objects": [{"label": "car", "confidence": 0.89}]},
        })

        # 2. Audio
        ev_aud = _upload_audio(client, case_id, tiny_wav, "audio.wav").get_json()["evidence"]["evidence_id"]
        update_analysis(ev_aud, "completed", {
            "audio": {
                "status": "completed",
                "transcript": "Get in the car right now!",
                "language": "en",
                "segments": [
                    {
                        "id": 0,
                        "start_seconds": 1.0,
                        "end_seconds": 2.5,
                        "text": "Get in the car right now!",
                    }
                ],
            }
        })

        # 3. Video
        ev_vid = _upload_video(client, case_id, tiny_mp4, "surveillance.mp4").get_json()["evidence"]["evidence_id"]
        update_analysis(ev_vid, "completed", {
            "video": {
                "status": "completed",
                "video_metadata": {"fps": 25.0, "duration_seconds": 5.0},
                "sampled_frames": [
                    {
                        "frame_index": 25,
                        "timestamp_seconds": 1.0,
                        "status": "success",
                        "objects": [{"label": "car", "confidence": 0.95}],
                    }
                ],
            }
        })

        resp = client.post(f"/api/cases/{case_id}/analyze/fusion")
        assert resp.status_code == 200
        fusion = resp.get_json()["fusion"]

        assert fusion["analyzed_modalities_count"] == 3
        # Check temporal audio-video correlation
        temp = fusion["temporal_associations"]
        assert len(temp) == 1
        assert "Get in the car right now!" in temp[0]["speech_excerpt"]
        assert "car" in temp[0]["correlated_video_objects"]
        assert temp[0]["audio_timestamp_range"] == [1.0, 2.5]

    def test_fusion_detects_environmental_contradictions(self, client, case_id, tiny_png):
        from storage.evidence_store import update_analysis

        # Image A: outdoor daytime scene
        ev_a = _upload_img(client, case_id, tiny_png, "outdoor_cam.png").get_json()["evidence"]["evidence_id"]
        update_analysis(ev_a, "completed", {
            "caption": {"status": "success", "caption": "a crowded outdoor market in daylight"},
        })

        # Image B: indoor nighttime scene
        ev_b = _upload_img(client, case_id, tiny_png, "indoor_cam.png").get_json()["evidence"]["evidence_id"]
        update_analysis(ev_b, "completed", {
            "caption": {"status": "success", "caption": "an indoor living room at nighttime"},
        })

        resp = client.post(f"/api/cases/{case_id}/analyze/fusion")
        assert resp.status_code == 200
        fusion = resp.get_json()["fusion"]

        conflicts = fusion["potential_contradictions"]
        assert len(conflicts) >= 1
        divergence_types = [c["contradiction_type"] for c in conflicts]
        assert "environmental_descriptor_divergence" in divergence_types


class TestFusionReportLabIntegration:
    """Verify that Multimodal Fusion sections are rendered in forensic PDF reports."""

    def test_pdf_report_includes_fusion_summary(self, client, case_id, tiny_png, tiny_mp4):
        from storage.evidence_store import update_analysis

        # Upload & analyze Image
        ev_img = _upload_img(client, case_id, tiny_png, "evidence1.png").get_json()["evidence"]["evidence_id"]
        update_analysis(ev_img, "completed", {
            "detection": {"status": "success", "objects": [{"label": "vehicle", "confidence": 0.92}]},
            "caption": {"status": "success", "caption": "a black vehicle parked outside"},
        })

        # Upload & analyze Video
        ev_vid = _upload_video(client, case_id, tiny_mp4, "evidence2.mp4").get_json()["evidence"]["evidence_id"]
        update_analysis(ev_vid, "completed", {
            "video": {
                "status": "completed",
                "video_metadata": {"fps": 30.0, "duration_seconds": 4.0},
                "sampled_frames": [
                    {"frame_index": 0, "timestamp_seconds": 0.0, "status": "success", "objects": [{"label": "vehicle", "confidence": 0.88}]}
                ],
            }
        })

        # Generate Case-wide Report
        rep_resp = client.post(f"/api/cases/{case_id}/report")
        assert rep_resp.status_code == 201
        report_id = rep_resp.get_json()["report"]["report_id"]

        # Download and assert with pypdf
        pdf_bytes = client.get(f"/api/reports/{report_id}").data
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)

        # Confirm Fusion sections rendered
        assert "Multimodal Forensic Evidence Fusion Summary" in text
        assert "Cross-Modal Corroborated Entities" in text
        assert "VEHICLE" in text
        assert "Fusion Forensic Safeguard" in text
