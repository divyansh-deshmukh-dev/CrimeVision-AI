"""
tests/test_audio_analysis.py — Phase 4 Audio Analysis Test Suite.

Covers:
  - Audio evidence ingestion & storage
  - Audio analysis endpoint: POST /api/cases/<cid>/evidence/<eid>/analyze/audio
  - Analysis retrieval endpoint: GET /api/cases/<cid>/evidence/<eid>/analysis
  - Modality validation (rejection of non-audio files like images or videos)
  - Nonexistent case and evidence ID handling (404)
  - Case isolation enforcement (evidence from Case A cannot be analyzed under Case B)
  - Handling of corrupted / empty audio files
  - Mocked pipeline tests for Whisper speech-to-text:
      - Transcript text extraction
      - Timestamped segment interval extraction [start, end, text]
      - Detected language preservation
      - Forensic notice requirement: speech transcription does not prove speaker identity or veracity
  - Audio Analyzer unit tests (audio loading, resample to 16kHz mono)
  - Forensic PDF report integration:
      - Including audio metadata, transcript, timestamps, and forensic disclaimer in PDF
"""

import io
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from pypdf import PdfReader


def _upload_audio(client, case_id: str, file_bytes: bytes, filename: str = "recording.wav"):
    data = {
        "file": (io.BytesIO(file_bytes), filename, "audio/wav"),
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


class TestAudioAnalysisEndpoint:
    """POST /api/cases/<case_id>/evidence/<evidence_id>/analyze/audio"""

    def test_analyze_audio_nonexistent_case_404(self, client):
        resp = client.post("/api/cases/case_nonexistent_999/evidence/ev_123/analyze/audio")
        assert resp.status_code == 404
        assert "not found" in resp.get_json()["error"]

    def test_analyze_audio_nonexistent_evidence_404(self, client, case_id):
        resp = client.post(f"/api/cases/{case_id}/evidence/ev_nonexistent_999/analyze/audio")
        assert resp.status_code == 404
        assert "not found" in resp.get_json()["error"]

    def test_analyze_audio_wrong_modality_400(self, client, case_id, tiny_png):
        upload_res = _upload_img(client, case_id, tiny_png, "photo.png").get_json()
        ev_id = upload_res["evidence"]["evidence_id"]

        resp = client.post(f"/api/cases/{case_id}/evidence/{ev_id}/analyze/audio")
        assert resp.status_code == 400
        assert "Only 'audio' modality can be transcribed" in resp.get_json()["error"]

    def test_analyze_audio_cross_case_isolation_404(self, client, tiny_wav):
        res_a = client.post("/api/cases", json={"name": "Case Alpha"}).get_json()
        cid_a = res_a["case"]["case_id"]

        res_b = client.post("/api/cases", json={"name": "Case Beta"}).get_json()
        cid_b = res_b["case"]["case_id"]

        ev_a = _upload_audio(client, cid_a, tiny_wav, "wiretap.wav").get_json()["evidence"]["evidence_id"]

        # Attempt to analyze Case A's audio evidence from Case B's path
        resp = client.post(f"/api/cases/{cid_b}/evidence/{ev_a}/analyze/audio")
        assert resp.status_code == 404

    @patch("services.audio_analyzer.AudioAnalyzer.transcribe_audio_pipeline")
    def test_analyze_audio_success(self, mock_pipeline, client, case_id, tiny_wav):
        mock_pipeline.return_value = {
            "status": "completed",
            "model": "openai/whisper-base",
            "transcript": "Drop the weapon and step away.",
            "language": "en",
            "segments": [
                {
                    "id": 0,
                    "start_seconds": 0.0,
                    "end_seconds": 2.5,
                    "text": "Drop the weapon and step away.",
                }
            ],
            "forensic_notice": (
                "Automated machine transcription generated via OpenAI Whisper Base. "
                "Speech recognition does NOT establish speaker identity or prove statement truth."
            ),
        }

        upload_res = _upload_audio(client, case_id, tiny_wav, "dispatch.wav").get_json()
        ev_id = upload_res["evidence"]["evidence_id"]

        resp = client.post(f"/api/cases/{case_id}/evidence/{ev_id}/analyze/audio")
        assert resp.status_code == 200
        data = resp.get_json()

        assert data["evidence_id"] == ev_id
        assert data["case_id"] == case_id
        assert data["status"] == "completed"

        analysis = data["analysis"]
        assert "audio" in analysis
        audio = analysis["audio"]
        assert audio["status"] == "completed"
        assert audio["transcript"] == "Drop the weapon and step away."
        assert audio["language"] == "en"
        assert len(audio["segments"]) == 1
        assert audio["segments"][0]["start_seconds"] == 0.0
        assert "does NOT establish speaker identity" in audio["forensic_notice"]

        # Also verify persisted analysis via GET /analysis
        get_resp = client.get(f"/api/cases/{case_id}/evidence/{ev_id}/analysis")
        assert get_resp.status_code == 200
        assert get_resp.get_json()["analysis"]["audio"]["transcript"] == "Drop the weapon and step away."

    @patch("services.audio_analyzer.AudioAnalyzer.transcribe_audio_pipeline")
    def test_analyze_audio_pipeline_failure_recorded(self, mock_pipeline, client, case_id, tiny_wav):
        mock_pipeline.return_value = {
            "status": "failed",
            "error": "Audio decoding error or corrupted stream",
            "transcript": "",
            "segments": [],
        }

        upload_res = _upload_audio(client, case_id, tiny_wav, "corrupted.wav").get_json()
        ev_id = upload_res["evidence"]["evidence_id"]

        resp = client.post(f"/api/cases/{case_id}/evidence/{ev_id}/analyze/audio")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "failed"
        assert data["analysis"]["audio"]["status"] == "failed"
        assert "Audio decoding error" in data["analysis"]["audio"]["error"]


class TestAudioAnalyzerUnit:
    """Unit tests for services.audio_analyzer.AudioAnalyzer helper methods"""

    def test_load_and_resample_audio(self, tmp_path, tiny_wav):
        from services.audio_analyzer import AudioAnalyzer

        audio_path = tmp_path / "test.wav"
        audio_path.write_bytes(tiny_wav)

        waveform, sr, metadata = AudioAnalyzer.load_and_resample_audio(audio_path, target_sr=16000)
        assert sr == 16000
        assert metadata["target_sample_rate"] == 16000
        assert metadata["channels"] == 1
        assert "duration_seconds" in metadata

    def test_load_nonexistent_audio_raises(self, tmp_path):
        from services.audio_analyzer import AudioAnalyzer

        with pytest.raises(FileNotFoundError):
            AudioAnalyzer.load_and_resample_audio(tmp_path / "missing.wav")


class TestAudioPDFReportIntegration:
    """Verify that audio transcripts and disclaimers are correctly rendered in forensic PDF reports"""

    @patch("services.audio_analyzer.AudioAnalyzer.transcribe_audio_pipeline")
    def test_pdf_report_with_audio_evidence(self, mock_pipeline, client, case_id, tiny_wav):
        mock_pipeline.return_value = {
            "status": "success",
            "model": "openai/whisper-base",
            "transcript": "Suspect observed fleeing westbound on Main Street.",
            "language": "en",
            "segments": [
                {
                    "id": 0,
                    "start_seconds": 1.25,
                    "end_seconds": 4.50,
                    "text": "Suspect observed fleeing westbound on Main Street.",
                }
            ],
            "forensic_notice": (
                "Automated machine transcription generated via OpenAI Whisper Base. "
                "Speech recognition does NOT establish speaker identity or prove statement truth."
            ),
        }

        # 1. Ingest audio evidence
        upload_res = _upload_audio(client, case_id, tiny_wav, "radio_comm.wav").get_json()
        ev_id = upload_res["evidence"]["evidence_id"]
        sha256 = upload_res["evidence"]["sha256"]

        # 2. Run analysis
        client.post(f"/api/cases/{case_id}/evidence/{ev_id}/analyze/audio")

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

        # Confirm header & identifiers
        assert case_id in text
        assert ev_id in text
        assert sha256 in text

        # Confirm audio findings & transcript
        assert "Acoustic Stream Ingest Metadata" in text
        assert "OpenAI Whisper Base Speech-to-Text Findings" in text
        assert "Suspect observed fleeing westbound on Main Street." in text
        assert "1.25s - 4.50s" in text

        # Confirm forensic disclaimer
        assert "Transcribing speech does NOT establish speaker identity" in text


class TestAudioIntelligenceReport:
    """Tests for AI Intelligence Report generation, multilingual translations, and audio Q&A"""

    def test_synthesize_audio_intelligence_unit(self):
        from services.audio_analyzer import AudioAnalyzer

        transcript = (
            "At around 4.15 pm, I was standing near a bus stop on a busy street. "
            "I noticed a white car parked beside a black motorcycle."
        )
        segments = [
            {"start_seconds": 0.0, "end_seconds": 3.5, "text": "At around 4.15 pm, I was standing near a bus stop on a busy street."},
            {"start_seconds": 3.5, "end_seconds": 7.0, "text": "I noticed a white car parked beside a black motorcycle."}
        ]

        report = AudioAnalyzer._deterministic_audio_intelligence(transcript, segments, detected_language="en")
        assert "ai_summary" in report
        assert "event_type" in report
        assert "location" in report
        assert "translations" in report
        assert "timeline" in report

        # Verify translations have EN, HI, TE, FR
        translations = report["translations"]
        assert "original" in translations
        assert "en" in translations
        assert "hi" in translations
        assert "te" in translations
        assert "fr" in translations

        # Verify timeline structure
        timeline = report["timeline"]
        assert len(timeline) == 2
        assert timeline[0]["timestamp_display"] == "00:00"
        assert timeline[1]["timestamp_display"] == "00:03"
        assert "white car" in timeline[1]["event_description"]

    def test_audio_intelligence_endpoint_success(self, client, case_id, tiny_wav):
        # 1. Ingest audio evidence
        upload_res = _upload_audio(client, case_id, tiny_wav, "witness_statement.wav").get_json()
        ev_id = upload_res["evidence"]["evidence_id"]

        # Pre-seed analysis with transcript & segments using storage.evidence_store
        from storage.evidence_store import update_analysis
        update_analysis(
            ev_id,
            "completed",
            {
                "audio": {
                    "status": "completed",
                    "transcript": "I noticed a white car parked beside a black motorcycle near a bus stop.",
                    "segments": [{"start_seconds": 1.0, "end_seconds": 4.0, "text": "I noticed a white car parked beside a black motorcycle near a bus stop."}]
                }
            }
        )

        # 2. Call audio intelligence endpoint
        resp = client.post(f"/api/cases/{case_id}/evidence/{ev_id}/analyze/audio/intelligence")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "completed"
        assert "intelligence_report" in data
        rep = data["intelligence_report"]
        assert "ai_summary" in rep
        assert "translations" in rep
        assert "hi" in rep["translations"]
        assert "te" in rep["translations"]
        assert "fr" in rep["translations"]
        assert "timeline" in rep
        assert len(rep["timeline"]) > 0


class TestAudioDeterministicFallbackReliability:
    """Regression tests ensuring deterministic audio fallback is strictly grounded in evidence."""

    def test_sample_specific_hardcoded_override_completely_removed(self):
        from services.audio_analyzer import AudioAnalyzer

        # Previously, this exact phrase triggered a fabricated 4:15 PM blue-shirt narrative and static translations
        transcript = "I noticed a white car parked beside a black motorcycle."
        segments = [{"start_seconds": 0.0, "end_seconds": 3.0, "text": transcript}]

        report = AudioAnalyzer._deterministic_audio_intelligence(transcript, segments, detected_language="en")

        # 1. Summary must NOT contain invented details
        summary = report["ai_summary"]
        assert "blue shirt" not in summary.lower(), "Must not invent a person in a blue shirt"
        assert "main road" not in summary.lower(), "Must not invent departing towards main road"
        assert "unusual conduct" not in summary.lower(), "Must not include hardcoded disclaimer phrasing"
        assert "4:15" not in summary and "4.15" not in summary, "Must not inject 4:15 PM when not in text"
        assert "yesterday" not in summary.lower(), "Must not invent 'yesterday' timeframe"

        # 2. Entities must NOT contain fabricated contexts
        for ent in report.get("entities", []):
            ctx = ent.get("context", "")
            assert "departed towards main road" not in ctx, "Entity context must not contain hardcoded narrative"
            if ent.get("category") == "Timeframe":
                pytest.fail("Timeframe entity must not be generated when no time is mentioned in transcript")

        # 3. Non-English translations must be explicitly marked as unavailable, NOT static strings
        translations = report["translations"]
        assert translations["status"] == "translation_unavailable"
        assert isinstance(translations["hi"], dict)
        assert translations["hi"]["status"] == "translation_unavailable"
        assert "offline" in translations["hi"]["explanation"].lower() or "not generated" in translations["hi"]["explanation"].lower()
        assert isinstance(translations["fr"], dict)
        assert translations["fr"]["status"] == "translation_unavailable"
        assert isinstance(translations["te"], dict)
        assert translations["te"]["status"] == "translation_unavailable"

    def test_no_hallucinated_locations_times_or_persons(self):
        from services.audio_analyzer import AudioAnalyzer

        # Statement with NO location, NO time, and NO persons
        transcript = "There was loud glass breaking and banging sounds from downstairs."
        segments = [{"start_seconds": 0.0, "end_seconds": 2.5, "text": transcript}]

        report = AudioAnalyzer._deterministic_audio_intelligence(transcript, segments, detected_language="en")

        assert report["location"] == "Not specified"
        # No location, timeframe, or person entities should be invented
        for ent in report.get("entities", []):
            assert ent.get("category") != "Location / Setting"
            assert ent.get("category") != "Timeframe"
            assert ent.get("category") != "Persons & Clothing"

    def test_grounded_entity_and_time_extraction(self):
        from services.audio_analyzer import AudioAnalyzer

        transcript = (
            "At 11:45 am, a black motorcycle was spotted on Elm Street. "
            "A person in a red jacket walked into the building."
        )
        segments = [
            {"start_seconds": 0.0, "end_seconds": 3.0, "text": "At 11:45 am, a black motorcycle was spotted on Elm Street."},
            {"start_seconds": 3.0, "end_seconds": 6.0, "text": "A person in a red jacket walked into the building."}
        ]

        report = AudioAnalyzer._deterministic_audio_intelligence(transcript, segments, detected_language="en")

        assert "Elm Street" in report["location"]

        entities = report.get("entities", [])
        categories = {ent["category"] for ent in entities}
        assert "Vehicles" in categories
        assert "Timeframe" in categories
        assert "Location / Setting" in categories
        assert "Persons & Clothing" in categories

        # Timeframe must match actual time mentioned, not fabricated "Yesterday afternoon ~4:15 PM"
        time_ent = next(e for e in entities if e["category"] == "Timeframe")
        assert "11:45 am" in time_ent["value"]
        assert "4:15" not in time_ent["value"]

        # Entity contexts must be grounded in actual transcript sentences
        for ent in entities:
            assert ent["context"] in transcript or any(part in transcript for part in ent["context"].split()), \
                f"Context '{ent['context']}' must be grounded in transcript"

    def test_empty_transcript_handling(self):
        from services.audio_analyzer import AudioAnalyzer

        report = AudioAnalyzer.synthesize_audio_intelligence("", [])
        assert report["event_type"] == "Undetermined (No Speech Detected)"
        assert report["entities"] == []
        assert report["timeline"] == []
        assert report["translations"]["status"] == "translation_unavailable"
        assert report["provenance"]["result_source"] == "deterministic_fallback"

