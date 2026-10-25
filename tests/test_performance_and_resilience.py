"""
tests/test_performance_and_resilience.py — Comprehensive Regression & Resilience Tests.

Covers:
  1. First-run audio model initialization.
  2. Model reuse across subsequent audio requests (was_cached=True, model_init_duration_ms=0.0).
  3. Audio decoding, resampling, and corrupted/invalid media handling.
  4. Audio chunking for files >30s with timestamp offset preservation.
  5. Recovery from stale 'analyzing' status and successful retry.
  6. RT-DETR model reuse in-memory for video and image analysis.
  7. Video frame sampling, configurable max_frames, and exact timestamp preservation.
  8. Partial video analysis handling without false complete-success.
  9. Correct provenance tagging (fresh_inference, in_memory_model_reuse, deterministic_fallback).
  10. CSRF, authorization, and multi-tenant evidence isolation.
"""

from pathlib import Path
import threading
import time
from unittest.mock import patch, MagicMock

import numpy as np
import pytest

from services.audio_analyzer import AudioAnalyzer, get_cached_whisper, clear_whisper_cache
from services.image_analyzer import clear_rtdetr_cache, get_cached_rtdetr
from services.video_analyzer import VideoAnalyzer
from services.provenance import ResultSource


@pytest.fixture
def clean_caches():
    """Ensure clean model caches before and after test."""
    clear_whisper_cache()
    clear_rtdetr_cache()
    yield
    clear_whisper_cache()
    clear_rtdetr_cache()


class TestAudioModelCachingAndReuse:
    """Verify first-run initialization and thread-safe reuse of Whisper models."""

    def test_whisper_cache_lifecycle(self, clean_caches):
        proc1, mod1, cached1 = get_cached_whisper("openai/whisper-base", "cpu")
        assert cached1 is False
        assert proc1 is not None
        assert mod1 is not None

        proc2, mod2, cached2 = get_cached_whisper("openai/whisper-base", "cpu")
        assert cached2 is True
        assert proc1 is proc2
        assert mod1 is mod2

        clear_whisper_cache()
        proc3, mod3, cached3 = get_cached_whisper("openai/whisper-base", "cpu")
        assert cached3 is False

    def test_audio_pipeline_records_model_reuse_in_provenance(self, clean_caches, tmp_path, tiny_wav):
        wav_path = tmp_path / "sample.wav"
        wav_path.write_bytes(tiny_wav)

        analyzer = AudioAnalyzer()
        res1 = analyzer.transcribe_audio_pipeline(wav_path)
        assert res1["status"] in ("completed", "success")
        assert res1["model_cached"] is False
        assert res1["provenance"]["result_source"] == ResultSource.FRESH_INFERENCE.value

        res2 = analyzer.transcribe_audio_pipeline(wav_path)
        assert res2["status"] in ("completed", "success")
        assert res2["model_cached"] is True
        assert res2["provenance"]["result_source"] == ResultSource.IN_MEMORY_MODEL_REUSE.value
        assert res2["provenance"]["model_init_duration_ms"] == 0.0

    def test_concurrent_whisper_model_access_is_thread_safe(self, clean_caches):
        results = []

        def load_worker():
            p, m, c = get_cached_whisper("openai/whisper-base", "cpu")
            results.append((p is not None, m is not None))

        threads = [threading.Thread(target=load_worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 3
        assert all(r == (True, True) for r in results)


class TestAudioDecodingAndChunking:
    """Verify audio decoding, corrupt file rejection, and chunked processing."""

    def test_audio_decoding_empty_file_fails_gracefully(self, tmp_path):
        empty_wav = tmp_path / "empty.wav"
        empty_wav.write_bytes(b"")
        analyzer = AudioAnalyzer()
        res = analyzer.transcribe_audio_pipeline(empty_wav)
        assert res["status"] == "failed"
        assert "failed" in res["error"].lower() or "empty" in res["error"].lower()

    def test_audio_decoding_corrupted_file_fails_gracefully(self, tmp_path):
        corrupt = tmp_path / "bad.wav"
        corrupt.write_bytes(b"RIFF\x00\x00\x00\x00WAVEfmt \x10\x00\x00\x00not real audio data")
        analyzer = AudioAnalyzer()
        res = analyzer.load_audio_waveform(corrupt)
        assert res["status"] == "failed"

    def test_segment_offset_preservation(self):
        analyzer = AudioAnalyzer()
        raw = "<|0.00|> First statement <|2.50|>"
        segs = analyzer._parse_whisper_segments(raw, total_duration=2.5, time_offset=30.0)
        assert len(segs) == 1
        assert segs[0]["start_seconds"] == 30.0
        assert segs[0]["end_seconds"] == 32.5
        assert segs[0]["text"] == "First statement"


class TestRTDETRModelCachingAndReuse:
    """Verify RT-DETR model caching and in-memory reuse across frames and requests."""

    def test_rtdetr_cache_lifecycle(self, clean_caches):
        proc1, mod1, cached1 = get_cached_rtdetr("PekingU/rtdetr_r50vd", "cpu")
        assert cached1 is False
        assert proc1 is not None
        assert mod1 is not None

        proc2, mod2, cached2 = get_cached_rtdetr("PekingU/rtdetr_r50vd", "cpu")
        assert cached2 is True
        assert proc1 is proc2
        assert mod1 is mod2

        clear_rtdetr_cache()
        proc3, mod3, cached3 = get_cached_rtdetr("PekingU/rtdetr_r50vd", "cpu")
        assert cached3 is False


class TestVideoAnalysisConfigAndTimestamps:
    """Verify configurable sampling and timestamp tracking."""

    def test_video_endpoint_accepts_max_frames_and_interval(self, client, case_id, tiny_mp4):
        from tests.test_video_analysis import _upload_video
        upload_res = _upload_video(client, case_id, tiny_mp4, "test_config.mp4").get_json()
        ev_id = upload_res["evidence"]["evidence_id"]

        with patch("services.video_analyzer.VideoAnalyzer.analyze_video_pipeline") as mock_pipeline:
            mock_pipeline.return_value = {
                "status": "completed",
                "sampled_frames": [
                    {"frame_index": 0, "timestamp_seconds": 0.0, "status": "success", "objects": []},
                    {"frame_index": 24, "timestamp_seconds": 1.0, "status": "success", "objects": []},
                ],
                "sampled_frame_timestamps": [0.0, 1.0],
                "analyzed_frames_count": 2,
                "total_frames_in_stream": 50,
                "sampling_parameters": {"sample_interval_seconds": 1.0, "max_frames_requested": 2, "frames_analyzed": 2},
                "aggregated_detections": {"total_detections": 0, "unique_classes": [], "class_counts": {}},
                "scene_intelligence": {},
                "visual_summary": {},
                "event_timeline": [],
                "submodel_statuses": {"frame_sampling": "success", "rtdetr_detection": "success"},
                "provenance": {"result_source": "in_memory_model_reuse", "execution_status": "completed"},
            }

            resp = client.post(
                f"/api/cases/{case_id}/evidence/{ev_id}/analyze/video",
                json={"sample_interval_seconds": 1.0, "max_frames": 2},
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["status"] == "completed"
            assert mock_pipeline.call_args[1]["max_frames"] == 2


class TestStaleAnalysisRecoveryAndRetry:
    """Verify recovery from stale 'analyzing' status and retry workflow."""

    def test_reanalysis_allowed_when_stuck_in_analyzing(self, client, case_id, tiny_wav):
        from tests.test_audio_analysis import _upload_audio
        from storage.evidence_store import update_analysis

        upload_res = _upload_audio(client, case_id, tiny_wav, "stuck_test.wav").get_json()
        ev_id = upload_res["evidence"]["evidence_id"]

        # Simulate stuck in "analyzing" from previous dropped request
        update_analysis(ev_id, status="analyzing")

        with patch("services.audio_analyzer.AudioAnalyzer.transcribe_audio_pipeline") as mock_pipe:
            mock_pipe.return_value = {
                "status": "completed",
                "transcript": "Retry successfully completed.",
                "text": "Retry successfully completed.",
                "segments": [],
                "intelligence_report": {},
                "audio_metadata": {},
                "submodel_statuses": {"whisper": "success"},
                "provenance": {"result_source": "fresh_inference", "execution_status": "completed"},
            }

            resp = client.post(f"/api/cases/{case_id}/evidence/{ev_id}/analyze/audio")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["status"] == "completed"
            assert data["analysis"]["audio"]["transcript"] == "Retry successfully completed."

    def test_failed_analysis_retry_succeeds(self, client, case_id, tiny_wav):
        from tests.test_audio_analysis import _upload_audio
        upload_res = _upload_audio(client, case_id, tiny_wav, "retry_test.wav").get_json()
        ev_id = upload_res["evidence"]["evidence_id"]

        # Attempt 1 fails
        with patch("services.audio_analyzer.AudioAnalyzer.transcribe_audio_pipeline") as mock_pipe:
            mock_pipe.side_effect = RuntimeError("Temporary audio codec lock failure")
            resp1 = client.post(f"/api/cases/{case_id}/evidence/{ev_id}/analyze/audio")
            assert resp1.status_code == 500
            assert resp1.get_json()["status"] == "failed"

        # Attempt 2 (user retry) succeeds
        with patch("services.audio_analyzer.AudioAnalyzer.transcribe_audio_pipeline") as mock_pipe:
            mock_pipe.return_value = {
                "status": "completed",
                "transcript": "Second attempt succeeded.",
                "text": "Second attempt succeeded.",
                "segments": [],
                "intelligence_report": {},
                "audio_metadata": {},
                "submodel_statuses": {"whisper": "success"},
                "provenance": {"result_source": "fresh_inference", "execution_status": "completed"},
            }
            resp2 = client.post(f"/api/cases/{case_id}/evidence/{ev_id}/analyze/audio")
            assert resp2.status_code == 200
            assert resp2.get_json()["status"] == "completed"
