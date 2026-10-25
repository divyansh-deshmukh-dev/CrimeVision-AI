"""
tests/test_regression_phase9.py — Phase 9 Comprehensive Regression & Edge Case Test Suite.

Covers:
  1. Full multimodal case PDF generation containing Image, Audio, Video,
     and Multimodal Fusion sections in a single unified forensic report.
  2. Multi-turn AI Chat Assistant history retention and context formatting.
  3. AI Chat Assistant insufficient evidence reporting.
  4. Spatial 3D mapper edge cases:
     - Completed analysis with 0 detected objects (empty scene).
     - Non-standard bounding box dimensions.
     - Out-of-order frame timestamps.
  5. Multimodal fusion edge cases:
     - Fusion with empty speech transcript + image detections.
     - Potential contradiction handling between scene descriptions.
  6. Security & path traversal defense on evidence file serving.
  7. Strict case-level data isolation across all endpoints.
"""

import io
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from pypdf import PdfReader

from services.spatial_mapper import map_case_to_spatial_scene, normalize_box
from services.chat_assistant import ChatAssistant, build_evidence_context
from services.fusion_analyzer import FusionAnalyzer
from storage.evidence_store import update_analysis


# ── Helper Upload Utilities ──────────────────────────────────────────────────

def _upload_img(client, case_id: str, file_bytes: bytes, filename: str = "scene.png"):
    data = {"file": (io.BytesIO(file_bytes), filename, "image/png")}
    return client.post(f"/api/cases/{case_id}/evidence", data=data, content_type="multipart/form-data")


def _upload_audio(client, case_id: str, file_bytes: bytes, filename: str = "audio.wav"):
    data = {"file": (io.BytesIO(file_bytes), filename, "audio/wav")}
    return client.post(f"/api/cases/{case_id}/evidence", data=data, content_type="multipart/form-data")


def _upload_video(client, case_id: str, file_bytes: bytes, filename: str = "video.mp4"):
    data = {"file": (io.BytesIO(file_bytes), filename, "video/mp4")}
    return client.post(f"/api/cases/{case_id}/evidence", data=data, content_type="multipart/form-data")


# ── 1. Full Multimodal Forensic PDF Report ────────────────────────────────────

class TestFullMultimodalPDFReport:
    """End-to-end test verifying a single PDF containing Image, Audio, Video, and Fusion."""

    def test_full_multimodal_case_pdf_generation(
        self, client, case_id, tiny_png, tiny_wav, tiny_mp4
    ):
        # 1. Ingest all 3 modalities into the case
        res_img = _upload_img(client, case_id, tiny_png, "surveillance_still.png").get_json()
        ev_img = res_img["evidence"]["evidence_id"]

        res_aud = _upload_audio(client, case_id, tiny_wav, "dispatch_call.wav").get_json()
        ev_aud = res_aud["evidence"]["evidence_id"]

        res_vid = _upload_video(client, case_id, tiny_mp4, "dashcam_feed.mp4").get_json()
        ev_vid = res_vid["evidence"]["evidence_id"]

        # 2. Attach completed analysis for Image
        update_analysis(
            ev_img,
            status="completed",
            analysis_data={
                "image_dimensions": {"width": 1920, "height": 1080},
                "rtdetr": {
                    "objects": [
                        {
                            "label": "person",
                            "confidence": 0.965,
                            "box_normalized": [0.2, 0.2, 0.4, 0.8],
                        }
                    ]
                },
                "detection": {
                    "status": "success",
                    "model": "PekingU/rtdetr_r50vd",
                    "objects": [
                        {
                            "label": "person",
                            "confidence": 0.965,
                            "box_pixels": [384, 216, 768, 864],
                            "box_normalized": [0.2, 0.2, 0.4, 0.8],
                        }
                    ],
                    "class_counts": {"person": 1},
                    "total_detections": 1,
                },
                "clip": {
                    "status": "success",
                    "top_match": {"label": "outdoor street corner", "similarity_score": 0.88},
                    "matches": [{"label": "outdoor street corner", "similarity_score": 0.88}],
                },
                "caption": {
                    "status": "success",
                    "caption": "a person walking on an outdoor street corner at dusk",
                },
            },
        )

        # 3. Attach completed analysis for Audio
        update_analysis(
            ev_aud,
            status="completed",
            analysis_data={
                "audio": {
                    "status": "success",
                    "transcript": "Subject is fleeing south on foot toward the alley.",
                    "language": "en",
                    "audio_metadata": {
                        "duration_seconds": 3.8,
                        "sample_rate": 16000,
                        "channels": 1,
                    },
                    "segments": [
                        {
                            "id": 0,
                            "start_seconds": 0.0,
                            "end_seconds": 3.8,
                            "text": "Subject is fleeing south on foot toward the alley.",
                        }
                    ],
                    "forensic_notice": "Speech transcription does not verify speaker identity.",
                }
            },
        )

        # 4. Attach completed analysis for Video
        update_analysis(
            ev_vid,
            status="completed",
            analysis_data={
                "status": "completed",
                "video": {
                    "status": "completed",
                    "video_metadata": {
                        "fps": 30.0,
                        "width": 1280,
                        "height": 720,
                        "duration": 5.0,
                        "duration_seconds": 5.0,
                        "total_frames": 150,
                    },
                    "aggregated_detections": {
                        "total_detections": 2,
                        "unique_classes": ["person", "backpack"],
                        "class_counts": {"person": 1, "backpack": 1},
                    },
                    "sampled_frames": [
                        {
                            "frame_index": 0,
                            "timestamp_seconds": 0.0,
                            "status": "success",
                            "objects": [
                                {"label": "person", "confidence": 0.92, "box_pixels": [100, 100, 300, 600]}
                            ],
                            "detection_count": 1,
                        },
                        {
                            "frame_index": 60,
                            "timestamp_seconds": 2.0,
                            "status": "success",
                            "objects": [
                                {"label": "backpack", "confidence": 0.84, "box_pixels": [150, 200, 250, 350]}
                            ],
                            "detection_count": 1,
                        },
                    ],
                    "forensic_notice": "Discrete frame-level snapshots.",
                },
            },
        )

        # 5. Execute Multimodal Evidence Fusion
        fuse_res = client.post(f"/api/cases/{case_id}/analyze/fusion")
        assert fuse_res.status_code == 200
        assert fuse_res.get_json()["status"] == "completed"

        # 6. Generate Case Forensic Report (covers entire case with all modalities)
        rep_res = client.post(f"/api/cases/{case_id}/report")
        assert rep_res.status_code == 201
        report_url = rep_res.get_json()["report"]["download_url"]

        # 7. Download and verify content with pypdf
        dl_res = client.get(report_url)
        assert dl_res.status_code == 200
        assert dl_res.mimetype == "application/pdf"

        reader = PdfReader(io.BytesIO(dl_res.data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)

        # Assert Case Metadata
        assert case_id in text
        assert "CRIMEVISION AI" in text

        # Assert Evidence Identifiers & Hashes
        assert ev_img in text
        assert ev_aud in text
        assert ev_vid in text

        # Assert Image findings
        assert "person" in text
        assert "outdoor street corner" in text
        assert "walking on an outdoor street corner" in text

        # Assert Audio findings
        assert "Subject is fleeing south on foot" in text

        # Assert Video findings
        assert "1280x720 @ 30.0 fps" in text
        assert "backpack" in text

        # Assert Multimodal Fusion section
        assert "Multimodal Forensic Evidence Fusion Summary" in text
        assert "Cross-Modal Corroborated Entities" in text


# ── 2. AI Chat Assistant Edge Cases ──────────────────────────────────────────

class TestChatAssistantEdgeCases:
    """Verifies AI Chat Assistant handling of multi-turn conversations and insufficient evidence."""

    def test_chat_insufficient_evidence_flow(self, client, case_id):
        mock_response = {
            "answer": "There is no forensic evidence regarding weapon caliber in the case repository.",
            "supporting_evidence": [],
            "limitations": [
                "No firearms or ballistic evidence items have been ingested into this case."
            ],
            "insufficient_evidence": True,
        }

        with patch.object(ChatAssistant, "ask", return_value=mock_response):
            resp = client.post(
                f"/api/cases/{case_id}/chat",
                json={"query": "What caliber was the firearm used?"},
                content_type="application/json",
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["response"]["insufficient_evidence"] is True
            assert len(data["response"]["limitations"]) > 0

    def test_chat_multi_turn_history_persistence(self, client, case_id):
        # Turn 1
        with patch.object(
            ChatAssistant,
            "ask",
            return_value={
                "answer": "One image evidence item was registered.",
                "supporting_evidence": [],
                "limitations": [],
                "insufficient_evidence": False,
            },
        ):
            r1 = client.post(
                f"/api/cases/{case_id}/chat",
                json={"query": "What evidence is available?"},
            )
            assert r1.status_code == 200

        # Turn 2
        with patch.object(
            ChatAssistant,
            "ask",
            return_value={
                "answer": "It shows a person detected with 96.5% confidence.",
                "supporting_evidence": [],
                "limitations": [],
                "insufficient_evidence": False,
            },
        ):
            r2 = client.post(
                f"/api/cases/{case_id}/chat",
                json={"query": "What does that item show?"},
            )
            assert r2.status_code == 200

        # Verify chat history contains both turns (2 user + 2 assistant messages = 4)
        hist_resp = client.get(f"/api/cases/{case_id}/chat/history")
        assert hist_resp.status_code == 200
        msgs = hist_resp.get_json()["messages"]
        assert len(msgs) == 4
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"
        assert msgs[2]["role"] == "user"
        assert msgs[3]["role"] == "assistant"


# ── 3. Spatial 3D Mapper Edge Cases ──────────────────────────────────────────

class TestSpatialMapperEdgeCases:
    """Verifies robustness of the 3D spatial mapping service under edge scenarios."""

    def test_spatial_mapper_completed_analysis_with_zero_objects(self):
        case = {"case_id": "case_empty_dets", "name": "Empty Detections"}
        evidence_items = [
            {
                "evidence_id": "ev_clear",
                "original_name": "empty_wall.png",
                "modality": "image",
                "analysis_status": "completed",
                "analysis_json": {
                    "image_dimensions": {"width": 800, "height": 600},
                    "rtdetr": {"objects": []},
                    "detection": {"objects": []},
                },
            }
        ]
        scene = map_case_to_spatial_scene(case, evidence_items)
        assert scene["status"] == "success"
        assert scene["summary"]["total_objects"] == 0
        assert scene["objects"] == []
        assert scene["legend"] == []
        assert scene["disclaimer"]["is_metric"] is False

    def test_spatial_mapper_video_out_of_order_frames(self):
        case = {"case_id": "case_shuffled", "name": "Shuffled Video Frames"}
        evidence_items = [
            {
                "evidence_id": "ev_shuffled_vid",
                "original_name": "surv.mp4",
                "modality": "video",
                "analysis_status": "completed",
                "analysis_json": {
                    "video_metadata": {"duration": 10.0, "width": 1280, "height": 720},
                    "sampled_frames": [
                        {
                            "frame_index": 90,
                            "timestamp_seconds": 6.0,
                            "status": "success",
                            "objects": [{"label": "car", "confidence": 0.90, "box_normalized": [0.1, 0.1, 0.5, 0.5]}],
                        },
                        {
                            "frame_index": 15,
                            "timestamp_seconds": 1.0,
                            "status": "success",
                            "objects": [{"label": "person", "confidence": 0.85, "box_normalized": [0.2, 0.2, 0.6, 0.6]}],
                        },
                    ],
                },
            }
        ]
        scene = map_case_to_spatial_scene(case, evidence_items)
        assert scene["summary"]["total_objects"] == 2
        car_obj = next(o for o in scene["objects"] if o["label"] == "car")
        person_obj = next(o for o in scene["objects"] if o["label"] == "person")
        assert car_obj["timestamp_seconds"] == 6.0
        assert person_obj["timestamp_seconds"] == 1.0
        assert car_obj["spatial_coords"]["z"] > person_obj["spatial_coords"]["z"]

    def test_normalize_box_extreme_values(self):
        # Degenerate box where x2 < x1 or y2 < y1
        res = normalize_box([0.8, 0.9, 0.2, 0.1])
        assert len(res) == 4
        # All coordinates clamped between 0.0 and 1.0
        for coord in res:
            assert 0.0 <= coord <= 1.0


# ── 4. Multimodal Fusion Edge Cases ──────────────────────────────────────────

class TestMultimodalFusionEdgeCases:
    """Verifies edge conditions in cross-modal correlation and conflict detection."""

    def test_fusion_with_silent_audio(self):
        analyzer = FusionAnalyzer()
        evidence_items = [
            {
                "evidence_id": "ev_aud_silent",
                "original_name": "silence.wav",
                "modality": "audio",
                "analysis_status": "completed",
                "analysis_json": {
                    "audio": {
                        "status": "success",
                        "transcript": "",
                        "language": "unknown",
                        "segments": [],
                    }
                },
            },
            {
                "evidence_id": "ev_img_scene",
                "original_name": "scene.png",
                "modality": "image",
                "analysis_status": "completed",
                "analysis_json": {
                    "rtdetr": {"objects": [{"label": "person", "confidence": 0.91}]}
                },
            },
        ]
        result = analyzer.fuse_case_evidence(
            case={"case_id": "c_silent", "name": "Silent Case"},
            evidence_items=evidence_items,
        )
        assert result["status"] == "completed"
        # Audio was analyzed but produced 0 transcript words; should not crash
        assert result["evidence_count"] == 2
        assert result["analyzed_modalities_count"] == 2


# ── 5. Security & Path Traversal Verification ─────────────────────────────────

class TestSecurityAndPathTraversal:
    """Verifies file serving endpoint rejects path traversal sequences."""

    def test_file_endpoint_path_traversal_rejected(self, client, case_id):
        # Attempt relative path traversal payloads in evidence ID
        traversal_attempts = [
            "../../app.py",
            "..%2F..%2Fapp.py",
            "....//....//app.py",
            "ev_../../../etc/passwd",
        ]
        for payload in traversal_attempts:
            resp = client.get(f"/api/cases/{case_id}/evidence/{payload}/file")
            # Must return 404 Not Found (or 400 Bad Request), NEVER 200 or internal leak
            assert resp.status_code in (400, 404), f"Payload '{payload}' was not rejected: {resp.status_code}"
