"""
tests/test_video_analysis.py — Phase 5 Video Analysis Test Suite.

Covers:
  1. Video evidence ingestion & storage
  2. Video analysis endpoint: POST /api/cases/<cid>/evidence/<eid>/analyze/video
  3. Nonexistent case and evidence ID handling (404)
  4. Cross-case isolation enforcement
  5. Modality validation (rejection of non-video evidence)
  6. Server-side validation of sampling parameters (bounds clamping)
  7. Handling of corrupted, empty, and non-decodable video files
  8. VideoAnalyzer unit tests (metadata extraction, frame sampling, resource release)
  9. Mocked pipeline tests for RT-DETR video frame detection:
      - Timestamp and frame index tracking
      - Detection results per sampled frame
      - Partial completion reporting when some frames fail
      - Forensic notice requirement
  10. Forensic PDF report integration:
      - Video metadata, sampled frame detections table, and legal disclaimers in PDF
  11. Real inference test with small synthetic video through OpenCV and real RT-DETR.
"""

import io
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import cv2
import numpy as np
import pytest
from pypdf import PdfReader


def _create_synthetic_mp4_bytes(fps: float = 10.0, num_frames: int = 15, width: int = 64, height: int = 64) -> bytes:
    """Generate valid playable MP4 bytes in memory using OpenCV."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(tmp_path, fourcc, fps, (width, height))
        for i in range(num_frames):
            # Generate frame with distinct solid color
            frame = np.full((height, width, 3), (i * 15) % 255, dtype=np.uint8)
            writer.write(frame)
        writer.release()

        with open(tmp_path, "rb") as f:
            data = f.read()
        return data
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@pytest.fixture(scope="session")
def valid_mp4_bytes() -> bytes:
    return _create_synthetic_mp4_bytes()


def _upload_video(client, case_id: str, file_bytes: bytes, filename: str = "cctv.mp4"):
    data = {
        "file": (io.BytesIO(file_bytes), filename, "video/mp4"),
    }
    return client.post(
        f"/api/cases/{case_id}/evidence",
        data=data,
        content_type="multipart/form-data",
    )


def _upload_img(client, case_id: str, file_bytes: bytes, filename: str = "image.png"):
    data = {
        "file": (io.BytesIO(file_bytes), filename, "image/png"),
    }
    return client.post(
        f"/api/cases/{case_id}/evidence",
        data=data,
        content_type="multipart/form-data",
    )


# ── Test Suite ───────────────────────────────────────────────────────────────

class TestVideoAnalysisAPI:
    """POST /api/cases/<case_id>/evidence/<evidence_id>/analyze/video"""

    def test_analyze_video_nonexistent_case_404(self, client):
        resp = client.post("/api/cases/case_nonexistent_999/evidence/ev_123/analyze/video")
        assert resp.status_code == 404
        assert "not found" in resp.get_json()["error"]

    def test_analyze_video_nonexistent_evidence_404(self, client, case_id):
        resp = client.post(f"/api/cases/{case_id}/evidence/ev_nonexistent_999/analyze/video")
        assert resp.status_code == 404
        assert "not found" in resp.get_json()["error"]

    def test_analyze_video_wrong_modality_400(self, client, case_id, tiny_png):
        upload_res = _upload_img(client, case_id, tiny_png, "photo.png").get_json()
        ev_id = upload_res["evidence"]["evidence_id"]

        resp = client.post(f"/api/cases/{case_id}/evidence/{ev_id}/analyze/video")
        assert resp.status_code == 400
        assert "Only 'video' modality can be processed" in resp.get_json()["error"]

    def test_analyze_video_cross_case_isolation_404(self, client, valid_mp4_bytes):
        res_a = client.post("/api/cases", json={"name": "Case Alpha"}).get_json()
        cid_a = res_a["case"]["case_id"]

        res_b = client.post("/api/cases", json={"name": "Case Beta"}).get_json()
        cid_b = res_b["case"]["case_id"]

        ev_a = _upload_video(client, cid_a, valid_mp4_bytes, "dashcam.mp4").get_json()["evidence"]["evidence_id"]

        # Attempt to analyze Case A's video evidence using Case B's path
        resp = client.post(f"/api/cases/{cid_b}/evidence/{ev_a}/analyze/video")
        assert resp.status_code == 404

    @patch("services.video_analyzer.VideoAnalyzer.analyze_video_pipeline")
    def test_analyze_video_success(self, mock_pipeline, client, case_id, valid_mp4_bytes):
        mock_pipeline.return_value = {
            "status": "completed",
            "video_metadata": {
                "filename": "cctv.mp4",
                "fps": 10.0,
                "width": 64,
                "height": 64,
                "total_frames": 15,
                "duration_seconds": 1.5,
                "codec": "mp4v",
            },
            "sampling_parameters": {
                "sample_interval_seconds": 1.0,
                "max_frames_requested": 10,
                "frames_analyzed": 2,
            },
            "aggregated_detections": {
                "total_detections": 2,
                "unique_classes": ["person"],
                "class_counts": {"person": 2},
            },
            "sampled_frames": [
                {
                    "frame_index": 0,
                    "timestamp_seconds": 0.0,
                    "status": "success",
                    "objects": [{"label": "person", "confidence": 0.88, "box_pixels": [10, 10, 50, 50]}],
                    "detection_count": 1,
                },
                {
                    "frame_index": 10,
                    "timestamp_seconds": 1.0,
                    "status": "success",
                    "objects": [{"label": "person", "confidence": 0.91, "box_pixels": [12, 12, 52, 52]}],
                    "detection_count": 1,
                },
            ],
            "forensic_notice": "Discrete frame-level snapshots.",
        }

        upload_res = _upload_video(client, case_id, valid_mp4_bytes, "cctv.mp4").get_json()
        ev_id = upload_res["evidence"]["evidence_id"]

        resp = client.post(
            f"/api/cases/{case_id}/evidence/{ev_id}/analyze/video",
            json={"sample_interval_seconds": 1.0, "max_frames": 5},
        )
        assert resp.status_code == 200
        data = resp.get_json()

        assert data["evidence_id"] == ev_id
        assert data["case_id"] == case_id
        assert data["status"] == "completed"

        analysis = data["analysis"]
        assert "video" in analysis
        vid = analysis["video"]
        assert vid["status"] == "completed"
        assert vid["aggregated_detections"]["total_detections"] == 2
        assert len(vid["sampled_frames"]) == 2
        assert vid["sampled_frames"][0]["timestamp_seconds"] == 0.0
        assert vid["sampled_frames"][1]["timestamp_seconds"] == 1.0

        # Verify analysis retrieval via GET /analysis
        get_res = client.get(f"/api/cases/{case_id}/evidence/{ev_id}/analysis")
        assert get_res.status_code == 200
        assert get_res.get_json()["analysis"]["video"]["video_metadata"]["fps"] == 10.0

    @patch("services.video_analyzer.VideoAnalyzer.analyze_video_pipeline")
    def test_analyze_video_partial_status_recorded(self, mock_pipeline, client, case_id, valid_mp4_bytes):
        mock_pipeline.return_value = {
            "status": "partial",
            "video_metadata": {"fps": 10.0, "total_frames": 10, "duration_seconds": 1.0},
            "sampling_parameters": {"sample_interval_seconds": 1.0, "max_frames_requested": 2, "frames_analyzed": 2},
            "aggregated_detections": {"total_detections": 1, "unique_classes": ["car"], "class_counts": {"car": 1}},
            "sampled_frames": [
                {"frame_index": 0, "timestamp_seconds": 0.0, "status": "success", "objects": [{"label": "car", "confidence": 0.85}], "detection_count": 1},
                {"frame_index": 5, "timestamp_seconds": 0.5, "status": "failed", "error": "Decoder glitch", "objects": [], "detection_count": 0},
            ],
            "forensic_notice": "Discrete frame snapshots.",
        }

        upload_res = _upload_video(client, case_id, valid_mp4_bytes, "partial.mp4").get_json()
        ev_id = upload_res["evidence"]["evidence_id"]

        resp = client.post(f"/api/cases/{case_id}/evidence/{ev_id}/analyze/video")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "partial"
        assert data["analysis"]["video"]["status"] == "partial"


class TestVideoAnalyzerUnit:
    """Unit tests for services.video_analyzer.VideoAnalyzer"""

    def test_sampling_params_bounds_clamping(self):
        from services.video_analyzer import VideoAnalyzer

        # Underflow clamped to min
        interval, max_f = VideoAnalyzer.validate_sampling_params(-5.0, -10)
        assert interval == 0.25
        assert max_f == 1

        # Overflow clamped to max
        interval, max_f = VideoAnalyzer.validate_sampling_params(100.0, 500)
        assert interval == 60.0
        assert max_f == 30

        # None defaults
        interval, max_f = VideoAnalyzer.validate_sampling_params(None, None)
        assert interval == 1.0
        assert max_f == 10

    def test_metadata_extraction_on_valid_video(self, tmp_path, valid_mp4_bytes):
        from services.video_analyzer import VideoAnalyzer

        vid_path = tmp_path / "sample.mp4"
        vid_path.write_bytes(valid_mp4_bytes)

        meta = VideoAnalyzer.extract_video_metadata(vid_path)
        assert meta["fps"] == 10.0
        assert meta["width"] == 64
        assert meta["height"] == 64
        assert meta["total_frames"] == 15
        assert meta["duration_seconds"] == 1.5

    def test_metadata_extraction_nonexistent_raises(self, tmp_path):
        from services.video_analyzer import VideoAnalyzer

        with pytest.raises(FileNotFoundError):
            VideoAnalyzer.extract_video_metadata(tmp_path / "nonexistent.mp4")

    def test_metadata_extraction_empty_video_raises(self, tmp_path):
        from services.video_analyzer import VideoAnalyzer

        empty_file = tmp_path / "empty.mp4"
        empty_file.write_bytes(b"")

        with pytest.raises(ValueError, match="empty"):
            VideoAnalyzer.extract_video_metadata(empty_file)

    def test_frame_sampling_extracts_correct_frames(self, tmp_path, valid_mp4_bytes):
        from services.video_analyzer import VideoAnalyzer

        vid_path = tmp_path / "sample.mp4"
        vid_path.write_bytes(valid_mp4_bytes)

        analyzer = VideoAnalyzer()
        # Video is 15 frames @ 10fps (1.5s total). Sample interval 0.5s -> frame 0 (0.0s), frame 5 (0.5s), frame 10 (1.0s)
        frames = analyzer.sample_frames(vid_path, sample_interval_seconds=0.5, max_frames=5)
        assert len(frames) == 3
        assert frames[0]["frame_index"] == 0
        assert frames[0]["timestamp_seconds"] == 0.0
        assert frames[1]["frame_index"] == 5
        assert frames[1]["timestamp_seconds"] == 0.5
        assert frames[2]["frame_index"] == 10
        assert frames[2]["timestamp_seconds"] == 1.0


class TestVideoPDFReportIntegration:
    """Verify that video metadata and sampled frame detections are rendered in forensic PDF reports."""

    @patch("services.video_analyzer.VideoAnalyzer.analyze_video_pipeline")
    def test_pdf_report_with_video_evidence(self, mock_pipeline, client, case_id, valid_mp4_bytes):
        mock_pipeline.return_value = {
            "status": "completed",
            "video_metadata": {
                "filename": "security_cam.mp4",
                "fps": 30.0,
                "width": 1920,
                "height": 1080,
                "total_frames": 300,
                "duration_seconds": 10.0,
                "codec": "mp4v",
            },
            "sampling_parameters": {
                "sample_interval_seconds": 2.0,
                "max_frames_requested": 5,
                "frames_analyzed": 2,
            },
            "aggregated_detections": {
                "total_detections": 3,
                "unique_classes": ["person", "backpack"],
                "class_counts": {"person": 2, "backpack": 1},
            },
            "sampled_frames": [
                {
                    "frame_index": 0,
                    "timestamp_seconds": 0.0,
                    "status": "success",
                    "objects": [{"label": "person", "confidence": 0.94, "box_pixels": [50, 100, 200, 400]}],
                    "detection_count": 1,
                },
                {
                    "frame_index": 60,
                    "timestamp_seconds": 2.0,
                    "status": "success",
                    "objects": [
                        {"label": "person", "confidence": 0.89, "box_pixels": [60, 110, 210, 410]},
                        {"label": "backpack", "confidence": 0.77, "box_pixels": [120, 180, 180, 260]},
                    ],
                    "detection_count": 2,
                },
            ],
            "forensic_notice": "Discrete frame-level snapshots.",
        }

        # 1. Ingest video evidence
        upload_res = _upload_video(client, case_id, valid_mp4_bytes, "security_cam.mp4").get_json()
        ev_id = upload_res["evidence"]["evidence_id"]
        sha256 = upload_res["evidence"]["sha256"]

        # 2. Analyze video
        client.post(f"/api/cases/{case_id}/evidence/{ev_id}/analyze/video")

        # 3. Generate Case Forensic Report
        rep_resp = client.post(f"/api/cases/{case_id}/report", json={"evidence_id": ev_id})
        assert rep_resp.status_code == 201
        report_id = rep_resp.get_json()["report"]["report_id"]

        # 4. Download PDF
        pdf_resp = client.get(f"/api/reports/{report_id}")
        assert pdf_resp.status_code == 200
        assert pdf_resp.mimetype == "application/pdf"

        # 5. Inspect PDF content with pypdf
        reader = PdfReader(io.BytesIO(pdf_resp.data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)

        # Confirm IDs and hashes
        assert case_id in text
        assert ev_id in text
        assert sha256 in text

        # Confirm Video sections
        assert "Video Stream Ingest Metadata" in text
        assert "1920x1080 @ 30.0 fps" in text
        assert "Sampled Frame RT-DETR Detections Timeline" in text
        assert "0.00s (frame #0)" in text
        assert "2.00s (frame #60)" in text
        assert "person (94.0%)" in text
        assert "backpack (77.0%)" in text

        # Confirm Video Forensic Notice
        assert "Sampled frame analysis captures discrete snapshot intervals" in text


# ── Real Video & RT-DETR Inference Test (Distinguished from Mocked Tests) ───

class TestRealVideoRTDETRInference:
    """Verifies actual OpenCV frame extraction + real RT-DETR model pipeline."""

    def test_real_video_pipeline_inference(self, tmp_path, valid_mp4_bytes):
        from services.video_analyzer import VideoAnalyzer

        vid_path = tmp_path / "real_test.mp4"
        vid_path.write_bytes(valid_mp4_bytes)

        analyzer = VideoAnalyzer()
        # Analyze real video with max 2 frames
        result = analyzer.analyze_video_pipeline(vid_path, sample_interval_seconds=0.5, max_frames=2)

        assert result["status"] == "completed"
        assert result["video_metadata"]["fps"] == 10.0
        assert len(result["sampled_frames"]) == 2
        for sf in result["sampled_frames"]:
            assert sf["status"] == "success"
            assert "objects" in sf
            assert "detections" in sf
            assert isinstance(sf["objects"], list)
            assert sf["objects"] == sf["detections"]

    def test_corrupted_video_fails_gracefully(self, client, case_id):
        """Corrupted video bytes must be caught gracefully and return status=failed with error details."""
        corrupted_bytes = b"CORRUPTED_NOT_A_REAL_MP4_VIDEO_HEADER_12345"
        upload_res = _upload_video(client, case_id, corrupted_bytes, "corrupt.mp4").get_json()
        ev_id = upload_res["evidence"]["evidence_id"]

        resp = client.post(f"/api/cases/{case_id}/evidence/{ev_id}/analyze/video")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "failed"
        analysis = data["analysis"]
        assert analysis["status"] == "failed"
        assert "error" in analysis["video"] or "error" in analysis
        assert analysis["sampled_frames"] == []

    def test_analyze_video_dual_schema_aliases(self, client, case_id, valid_mp4_bytes):
        """Verify that the API response satisfies both nested 'video' and top-level schema contracts."""
        upload_res = _upload_video(client, case_id, valid_mp4_bytes, "dual_schema.mp4").get_json()
        ev_id = upload_res["evidence"]["evidence_id"]

        resp = client.post(
            f"/api/cases/{case_id}/evidence/{ev_id}/analyze/video",
            json={"sample_interval_seconds": 1.0, "max_frames": 2},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "completed"
        analysis = data["analysis"]

        # 1. Nested 'video' key (legacy & backend pipeline structure)
        assert "video" in analysis
        assert "sampled_frames" in analysis["video"]
        assert "video_metadata" in analysis["video"]

        # 2. Top-level aliases for frontend compatibility
        assert "sampled_frames" in analysis
        assert "video_metadata" in analysis
        assert "aggregated_detections" in analysis

        # 3. Each frame must have both 'objects' and 'detections'
        for frame in analysis["sampled_frames"]:
            assert "objects" in frame
            assert "detections" in frame
            assert frame["objects"] == frame["detections"]

    def test_real_cctv_file_pipeline_if_present(self):
        """Verify real CCTV surveillance footage analysis if present in storage."""
        real_cctv_path = Path("storage/uploads/case_d9baa2028b5b/ev_09814865021a/Realistic_15-second_continuous_CCTV_surveillance_footage_of_a_small_urban_street.mp4")
        if not real_cctv_path.is_file():
            pytest.skip("Real CCTV test file not present in workspace storage")

        from services.video_analyzer import VideoAnalyzer
        analyzer = VideoAnalyzer()
        meta = analyzer.extract_video_metadata(real_cctv_path)
        assert meta["fps"] == 24.0
        assert meta["width"] == 1366
        assert meta["height"] == 768
        assert meta["duration_seconds"] > 5.0

        # Sample and detect across 2 frames
        res = analyzer.analyze_video_pipeline(real_cctv_path, sample_interval_seconds=1.0, max_frames=2)
        assert res["status"] == "completed"
        assert len(res["sampled_frames"]) == 2
        for f in res["sampled_frames"]:
            assert f["status"] == "success"
            assert len(f["objects"]) > 0
            assert f["detection_count"] > 0
            assert "detections" in f
            assert "frame_dimensions" in f
            assert f["frame_dimensions"]["width"] == 1366
            assert f["frame_dimensions"]["height"] == 768

            # Verify bounding box coordinates for each object
            for obj in f["objects"]:
                assert "label" in obj
                assert isinstance(obj["confidence"], float)
                assert 0.0 <= obj["confidence"] <= 1.0
                assert "box_normalized" in obj
                norm = obj["box_normalized"]
                assert len(norm) == 4
                assert all(0.0 <= c <= 1.0 for c in norm)
                assert norm[0] <= norm[2]
                assert norm[1] <= norm[3]
                assert "box_pixels" in obj
                pix = obj["box_pixels"]
                assert len(pix) == 4
                assert pix[0] <= pix[2]
                assert pix[1] <= pix[3]

    def test_video_overlay_metadata_and_frame_sync_contract(self, tmp_path, valid_mp4_bytes):
        """Verify video analysis output guarantees all fields required for video overlay synchronization."""
        from services.video_analyzer import VideoAnalyzer

        vid_path = tmp_path / "sync_test.mp4"
        vid_path.write_bytes(valid_mp4_bytes)

        analyzer = VideoAnalyzer()
        res = analyzer.analyze_video_pipeline(vid_path, sample_interval_seconds=0.5, max_frames=3)
        assert res["status"] == "completed"
        assert "video_metadata" in res
        meta = res["video_metadata"]
        assert meta["width"] == 64
        assert meta["height"] == 64
        assert meta["fps"] == 10.0
        assert meta["duration_seconds"] == 1.5

        frames = res["sampled_frames"]
        assert len(frames) == 3
        timestamps = [f["timestamp_seconds"] for f in frames]
        assert timestamps == [0.0, 0.5, 1.0]

        for f in frames:
            assert "frame_dimensions" in f
            assert f["frame_dimensions"]["width"] == 64
            assert f["frame_dimensions"]["height"] == 64
            assert "objects" in f
            assert "detections" in f
            assert f["objects"] == f["detections"]


class TestVideoIntelligenceSynthesis:
    """Test Scene Intelligence, AI Visual Summary, and Event Timeline synthesis."""

    def test_deterministic_video_intelligence_empty(self):
        from services.video_analyzer import VideoAnalyzer

        res = VideoAnalyzer._deterministic_video_intelligence(
            video_metadata={"duration_seconds": 5.0, "fps": 24.0, "width": 1280, "height": 720},
            sampled_frames=[],
            aggregated_detections={},
        )
        assert "scene_intelligence" in res
        assert "visual_summary" in res
        assert "event_timeline" in res
        assert res["scene_intelligence"]["people_count"]["peak"] == 0
        assert "Undetermined" in res["scene_intelligence"]["scene_type"]
        assert len(res["event_timeline"]) == 0

    def test_deterministic_video_intelligence_with_street_detections(self):
        from services.video_analyzer import VideoAnalyzer

        metadata = {"duration_seconds": 15.0, "fps": 24.0, "width": 1366, "height": 768}
        sampled_frames = [
            {
                "frame_index": 0,
                "timestamp_seconds": 0.0,
                "status": "success",
                "objects": [
                    {"label": "person", "confidence": 0.88, "box_pixels": [10, 10, 50, 100]},
                    {"label": "bicycle", "confidence": 0.82, "box_pixels": [100, 200, 180, 280]},
                    {"label": "car", "confidence": 0.91, "box_pixels": [300, 300, 500, 450]},
                ],
            },
            {
                "frame_index": 24,
                "timestamp_seconds": 1.0,
                "status": "success",
                "objects": [
                    {"label": "person", "confidence": 0.90, "box_pixels": [15, 12, 52, 102]},
                    {"label": "person", "confidence": 0.75, "box_pixels": [200, 50, 240, 140]},
                    {"label": "bicycle", "confidence": 0.84, "box_pixels": [120, 210, 200, 290]},
                    {"label": "car", "confidence": 0.93, "box_pixels": [300, 300, 500, 450]},
                ],
            },
        ]

        res = VideoAnalyzer._deterministic_video_intelligence(
            video_metadata=metadata,
            sampled_frames=sampled_frames,
            aggregated_detections={},
        )

        sc = res["scene_intelligence"]
        assert "objects_detected" in sc
        labels = [o["label"] for o in sc["objects_detected"]]
        assert "person" in labels
        assert "bicycle" in labels
        assert "car" in labels

        # People count
        p_info = sc["people_count"]
        assert p_info["peak"] == 2
        assert p_info["total"] == 3
        assert p_info["average"] == 1.5

        # Scene Type
        assert "Outdoor Urban Street" in sc["scene_type"]
        assert sc["scene_type_confidence"] >= 0.80

        # Observable Actions
        actions = sc["observable_actions"]
        assert any("Bicycle transit" in a for a in actions)
        assert any("Pedestrian movement" in a for a in actions)

        # AI Visual Summary
        vs = res["visual_summary"]
        assert "summary" in vs
        assert len(vs["summary"]) > 20
        assert len(vs["direct_observations"]) >= 2
        assert len(vs["ai_interpretations"]) >= 1
        assert "uncertainty_details" in vs

        # Event Timeline
        tl = res["event_timeline"]
        assert len(tl) == 2
        assert tl[0]["timestamp_seconds"] == 0.0
        assert tl[0]["timestamp_display"] == "0.0s"
        assert tl[0]["detection_count"] == 3
        assert tl[1]["timestamp_seconds"] == 1.0
        assert tl[1]["detection_count"] == 4
        assert len(tl[0]["description"]) > 10

    def test_pipeline_includes_synthesized_intelligence(self, tmp_path, valid_mp4_bytes):
        from services.video_analyzer import VideoAnalyzer

        vid_path = tmp_path / "intel_test.mp4"
        vid_path.write_bytes(valid_mp4_bytes)

        analyzer = VideoAnalyzer()
        res = analyzer.analyze_video_pipeline(vid_path, sample_interval_seconds=0.5, max_frames=2)
        assert res["status"] == "completed"
        assert "scene_intelligence" in res
        assert "visual_summary" in res
        assert "event_timeline" in res
        assert isinstance(res["scene_intelligence"], dict)
        assert isinstance(res["visual_summary"], dict)
        assert isinstance(res["event_timeline"], list)

    def test_video_endpoint_persists_intelligence(self, client, case_id, valid_mp4_bytes):
        upload_res = _upload_video(client, case_id, valid_mp4_bytes, "cctv_intel.mp4").get_json()
        ev_id = upload_res["evidence"]["evidence_id"]

        resp = client.post(f"/api/cases/{case_id}/evidence/{ev_id}/analyze/video", json={"sample_interval_seconds": 1.0})
        assert resp.status_code == 200
        data = resp.get_json()
        analysis = data["analysis"]
        assert "scene_intelligence" in analysis
        assert "visual_summary" in analysis
        assert "event_timeline" in analysis
        assert "objects_detected" in analysis["scene_intelligence"]
        assert "summary" in analysis["visual_summary"]

    def test_chat_assistant_grounds_video_intelligence(self, case_id):
        from services.chat_assistant import build_evidence_context

        sample_ev = {
            "evidence_id": "ev_vid_test_1",
            "case_id": case_id,
            "modality": "video",
            "original_filename": "street_cam.mp4",
            "file_size_bytes": 1024,
            "analysis_status": "completed",
            "analysis_json": {
                "status": "completed",
                "video_metadata": {"duration_seconds": 15.0, "fps": 24.0, "width": 1366, "height": 768, "total_frames": 360},
                "sampled_frames": [
                    {
                        "frame_index": 0,
                        "timestamp_seconds": 0.0,
                        "status": "success",
                        "objects": [{"label": "bicycle", "confidence": 0.85}],
                    }
                ],
                "scene_intelligence": {
                    "scene_type": "Outdoor Urban Street / Public Sidewalk",
                    "scene_type_basis": "Vehicular and bicycle transit observed",
                    "people_count": {"peak": 2, "total": 5, "average": 1.2},
                    "observable_actions": ["Bicycle transit along roadway corridor"],
                },
                "visual_summary": {
                    "summary": "Routine daytime traffic flow along urban street with cyclist.",
                    "direct_observations": ["Cyclist detected in right lane."],
                    "ai_interpretations": ["Normal public activity."],
                },
            },
        }

        ctx = build_evidence_context(case={"case_id": case_id, "name": "Video Case"}, evidence_items=[sample_ev], fusion_result=None)
        assert "Outdoor Urban Street" in ctx
        assert "People Count: Peak 2" in ctx
        assert "Routine daytime traffic flow" in ctx



