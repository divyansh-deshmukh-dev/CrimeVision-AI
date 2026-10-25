"""
tests/test_provenance_and_reliability.py — Verification of Analysis Reliability,
Provenance Tracking, Submodel Status Preservation, and Result Differentiation.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from services.provenance import ResultSource, build_provenance_record
from services.image_analyzer import ImageAnalyzer
from services.audio_analyzer import AudioAnalyzer
from services.video_analyzer import VideoAnalyzer
from services.chat_assistant import ChatAssistant


class TestProvenanceModelUnits:
    """Unit tests for the provenance record constructor."""

    def test_build_provenance_record_defaults(self):
        rec = build_provenance_record(
            modality="image",
            result_source=ResultSource.FRESH_INFERENCE,
            execution_status="completed",
            evidence_id="ev_123",
            case_id="case_abc",
            input_sha256="abcdef123456",
            duration_ms=120.456,
            model_init_duration_ms=45.2,
            inference_duration_ms=75.25,
        )
        assert rec["modality"] == "image"
        assert rec["result_source"] == "fresh_inference"
        assert rec["execution_status"] == "completed"
        assert rec["evidence_id"] == "ev_123"
        assert rec["case_id"] == "case_abc"
        assert rec["input_sha256"] == "abcdef123456"
        assert rec["duration_ms"] == 120.46
        assert rec["model_init_duration_ms"] == 45.2
        assert rec["inference_duration_ms"] == 75.25
        assert rec["analysis_run_id"].startswith("run_")
        assert "requested_at" in rec
        assert "completed_at" in rec

    def test_build_provenance_record_demo_source(self):
        rec = build_provenance_record(
            modality="video",
            result_source=ResultSource.PRECOMPUTED_DEMO_RESULT,
            execution_status="completed",
            evidence_id="ev_demo",
            case_id="demo-case-001",
            duration_ms=0.0,
            is_demo=True,
        )
        assert rec["result_source"] == "precomputed_demo_result"
        assert rec["duration_ms"] == 0.0
        assert rec["is_demo"] is True


class TestImageReliabilityAndProvenance:
    """Tests for image analysis status preservation and provenance."""

    def test_partial_image_analysis_preserves_submodel_statuses(self, tmp_path):
        from PIL import Image
        img_path = tmp_path / "test_partial.jpg"
        Image.new("RGB", (64, 64), color="blue").save(img_path)

        analyzer = ImageAnalyzer()

        # Mock RT-DETR success, CLIP failure, BLIP success
        mock_rtdetr = {
            "status": "success",
            "model": "PekingU/rtdetr_r50vd",
            "objects": [{"label": "person", "confidence": 0.88, "box_pixels": [0, 0, 10, 10]}],
            "class_counts": {"person": 1},
            "total_detections": 1,
            "init_duration_ms": 10.0,
            "inference_duration_ms": 20.0,
        }
        mock_clip = {
            "status": "failed",
            "error": "CLIP weights connection timeout",
            "matches": [],
            "init_duration_ms": 5.0,
            "inference_duration_ms": 0.0,
        }
        mock_blip = {
            "status": "success",
            "model": "Salesforce/blip-image-captioning-base",
            "caption": "a person walking on a street",
            "init_duration_ms": 12.0,
            "inference_duration_ms": 25.0,
        }

        with patch.object(analyzer, "run_rtdetr_detection", return_value=mock_rtdetr), \
             patch.object(analyzer, "run_clip_similarity", return_value=mock_clip), \
             patch.object(analyzer, "run_blip_captioning", return_value=mock_blip):

            res = analyzer.analyze_image_pipeline(
                image_path=img_path,
                evidence_id="ev_part_img",
                case_id="case_part",
                input_sha256="dummy_sha256",
            )

            assert res["status"] == "partial", "Overall status must be 'partial' when one submodel fails"
            assert res["submodel_statuses"]["rtdetr"] == "success"
            assert res["submodel_statuses"]["clip"] == "failed"
            assert res["submodel_statuses"]["blip"] == "success"

            prov = res["provenance"]
            assert prov["result_source"] == "fresh_inference"
            assert prov["execution_status"] == "partial"
            assert prov["evidence_id"] == "ev_part_img"
            assert prov["submodel_statuses"]["clip"] == "failed"
            assert prov["model_init_duration_ms"] > 0
            assert prov["inference_duration_ms"] > 0

    def test_image_endpoint_returns_partial_status(self, client):
        # 1. Create case
        c_resp = client.post("/api/cases", json={"name": "Partial Image Case"})
        assert c_resp.status_code == 201
        case_id = c_resp.get_json()["case"]["case_id"]

        # 2. Upload dummy image evidence
        import io
        img_bytes = io.BytesIO()
        from PIL import Image
        Image.new("RGB", (32, 32), color="red").save(img_bytes, format="JPEG")
        img_bytes.seek(0)

        up_resp = client.post(
            f"/api/cases/{case_id}/evidence",
            data={"file": (img_bytes, "red_sample.jpg")},
            content_type="multipart/form-data",
        )
        assert up_resp.status_code == 201
        ev_id = up_resp.get_json()["evidence"]["evidence_id"]

        # Mock ImageAnalyzer.analyze_image_pipeline to return partial result
        partial_pipeline_result = {
            "status": "partial",
            "image_metadata": {"filename": "red_sample.jpg", "width": 32, "height": 32},
            "detection": {"status": "success", "objects": []},
            "clip": {"status": "failed", "error": "Simulated CLIP failure"},
            "caption": {"status": "success", "caption": "a red square"},
            "submodel_statuses": {"rtdetr": "success", "clip": "failed", "blip": "success"},
            "provenance": {
                "analysis_run_id": "run_test_partial",
                "result_source": "fresh_inference",
                "execution_status": "partial",
                "evidence_id": ev_id,
                "case_id": case_id,
            },
        }

        with patch("routes.cases.ImageAnalyzer.analyze_image_pipeline", return_value=partial_pipeline_result):
            res = client.post(
                f"/api/cases/{case_id}/evidence/{ev_id}/analyze/image",
                json={},
            )
            assert res.status_code == 200
            data = res.get_json()
            assert data["status"] == "partial", "Endpoint must never overwrite 'partial' with 'completed'"
            assert data["analysis"]["provenance"]["result_source"] == "fresh_inference"


class TestVideoReliabilityAndProvenance:
    """Tests for video analysis partial frame failure preservation and provenance."""

    def test_video_partial_status_preservation(self, tmp_path):
        vid_path = tmp_path / "test_partial_vid.mp4"
        vid_path.write_bytes(b"dummy_video_bytes")

        analyzer = VideoAnalyzer()

        mock_meta = {"width": 640, "height": 480, "fps": 24.0, "total_frames": 48, "duration_seconds": 2.0}
        mock_frames = [
            {"frame_index": 0, "timestamp_seconds": 0.0, "image": MagicMock(width=640, height=480)},
            {"frame_index": 24, "timestamp_seconds": 1.0, "image": MagicMock(width=640, height=480)},
        ]
        mock_batch_results = [
            {"status": "success", "objects": [{"label": "car", "confidence": 0.92}], "init_duration_ms": 15.0, "inference_duration_ms": 30.0},
            {"status": "failed", "error": "Frame decoding corrupted", "objects": [], "init_duration_ms": 0.0, "inference_duration_ms": 0.0},
        ]

        with patch.object(analyzer, "extract_video_metadata", return_value=mock_meta), \
             patch.object(analyzer, "sample_frames", return_value=mock_frames), \
             patch("services.video_analyzer.ImageAnalyzer.run_rtdetr_detection_on_images", return_value=mock_batch_results):

            res = analyzer.analyze_video_pipeline(vid_path, sample_interval_seconds=1.0)
            assert res["status"] == "partial", "Video analysis with 1 success and 1 failed frame must be 'partial'"
            assert res["submodel_statuses"]["rtdetr_detection"] == "partial"
            prov = res["provenance"]
            assert prov["result_source"] == "in_memory_model_reuse"
            assert prov["execution_status"] == "partial"


class TestAudioIntelligenceProvenance:
    """Tests for Audio Intelligence provenance: persisted reuse vs fresh LLM vs deterministic fallback."""

    def test_cached_audio_intelligence_returns_persisted_result_reuse(self, client):
        c_resp = client.post("/api/cases", json={"name": "Audio Cached Case"})
        case_id = c_resp.get_json()["case"]["case_id"]

        import io
        fake_wav = io.BytesIO(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
        up_resp = client.post(
            f"/api/cases/{case_id}/evidence",
            data={"file": (fake_wav, "sample.wav")},
            content_type="multipart/form-data",
        )
        ev_id = up_resp.get_json()["evidence"]["evidence_id"]

        # Preload analysis_json with existing intelligence_report
        from storage.evidence_store import update_analysis
        existing_report = {
            "ai_summary": "Stored witness statement from prior execution.",
            "event_type": "Theft / Burglary (Alleged)",
            "location": "Main Street",
            "translations": {"en": "Stored witness statement."},
            "timeline": [],
        }
        update_analysis(ev_id, status="completed", analysis_data={
            "audio": {"transcript": "I saw someone near Main Street."},
            "intelligence_report": existing_report,
        })

        # Request intelligence without refresh flag
        res = client.post(
            f"/api/cases/{case_id}/evidence/{ev_id}/analyze/audio/intelligence",
            json={},
        )
        assert res.status_code == 200
        data = res.get_json()
        report = data["intelligence_report"]
        assert report["ai_summary"] == "Stored witness statement from prior execution."
        assert report["provenance"]["result_source"] == "persisted_result_reuse"

    def test_fresh_audio_intelligence_records_gemini_or_deterministic_fallback(self):
        # 1. When Gemini succeeds
        mock_gemini_report = {
            "ai_summary": "Witness reports suspicious vehicle.",
            "event_type": "Suspicious Activity",
            "translations": {"en": "Witness reports suspicious vehicle.", "hi": "...", "te": "...", "fr": "..."},
            "timeline": [],
        }
        with patch("services.chat_assistant.ChatAssistant._query_gemini", return_value=mock_gemini_report):
            res_gemini = AudioAnalyzer.synthesize_audio_intelligence("I saw a suspicious car.", [])
            assert res_gemini["provenance"]["result_source"] == "external_api_generation"
            assert res_gemini["provenance"]["provider"] == "gemini"

        # 2. When Gemini fails (offline / network error) -> deterministic fallback
        with patch("services.chat_assistant.ChatAssistant._query_gemini", side_effect=Exception("11001 getaddrinfo failed")):
            res_fallback = AudioAnalyzer.synthesize_audio_intelligence("I saw a thief steal a wallet near Market Street.", [])
            assert res_fallback["provenance"]["result_source"] == "deterministic_fallback"
            assert res_fallback["provenance"]["provider"] == "deterministic_rule_engine"
            assert res_fallback["location"] == "near Market Street"


class TestChatAssistantProvenance:
    """Tests for ChatAssistant provenance identifying providers and fallbacks."""

    def test_gemini_chat_query_provenance(self):
        assistant = ChatAssistant(api_key="mock-key-for-test")
        mock_resp = {
            "answer": "A person in dark clothing was observed near the entryway.",
            "supporting_evidence": [],
            "limitations": [],
            "insufficient_evidence": False,
        }
        with patch.object(assistant, "_query_gemini", return_value=mock_resp):
            ans = assistant.ask("What was observed?", {"case_id": "c1", "name": "Case 1"}, [])
            assert ans["provenance"]["provider"] == "gemini"
            assert ans["provenance"]["result_source"] == "external_api_generation"
            assert "mock-key-for-test" not in str(ans["provenance"])

    def test_offline_chat_query_provenance(self):
        assistant = ChatAssistant(api_key="mock-key")
        with patch.object(assistant, "_query_gemini", side_effect=ConnectionError("11001 getaddrinfo failed")):
            ans = assistant.ask(
                "Who was seen?",
                {"case_id": "c1", "name": "Case 1"},
                [{
                    "evidence_id": "ev1",
                    "filename": "camera1.jpg",
                    "modality": "image",
                    "analysis_status": "completed",
                    "analysis_json": {
                        "detection": {"objects": [{"label": "person", "confidence": 0.95}]},
                        "caption": {"caption": "a person walking"},
                    },
                }],
            )
            assert ans["provenance"]["provider"] == "local_evidence_synthesizer"
            assert ans["provenance"]["result_source"] == "deterministic_fallback"
            assert "person" in ans["answer"].lower()


class TestDemoPrecomputedProvenance:
    """Tests that demo precomputed results return precomputed_demo_result provenance with duration 0.0."""

    def test_demo_image_endpoint_precomputed_provenance(self, client):
        # Demo user credentials from test fixtures
        login_res = client.post("/api/auth/demo-login", json={})
        assert login_res.status_code == 200

        # Demo case endpoint
        res = client.post(
            "/api/cases/case_demo_sentinel/evidence/ev_demo_img_01/analyze/image",
            json={},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] in ("completed", "partial")
        prov = data["analysis"].get("provenance")
        assert prov is not None
        assert prov["result_source"] == "precomputed_demo_result"
        assert prov["duration_ms"] == 0.0
        assert prov["is_demo"] is True
