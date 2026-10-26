"""
tests/test_cloud_audio_inference.py — Tests for Groq Cloud Whisper Audio Inference.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from services.audio_analyzer import AudioAnalyzer
from services.cloud_audio_service import transcribe_audio_with_groq
from services.provider_manager import get_inference_provider, get_provider_details
from services.provenance import ResultSource


@pytest.fixture
def dummy_audio_file(tmp_path: Path) -> Path:
    """Create a temporary dummy audio file for testing."""
    f = tmp_path / "test_sample.mp3"
    f.write_bytes(b"ID3" + b"\x00" * 1024)
    return f


def test_provider_manager_routing(monkeypatch):
    """Test provider resolution across modes and environments."""
    # Explicit 'cloud'
    monkeypatch.setenv("INFERENCE_PROVIDER", "cloud")
    assert get_inference_provider("audio") == "cloud"

    # Explicit 'local'
    monkeypatch.setenv("INFERENCE_PROVIDER", "local")
    assert get_inference_provider("audio") == "local"

    # 'auto' on Render environment
    monkeypatch.setenv("INFERENCE_PROVIDER", "auto")
    monkeypatch.setenv("RENDER", "true")
    assert get_inference_provider("audio") == "cloud"
    monkeypatch.delenv("RENDER", raising=False)

    # 'auto' without key on high RAM
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("RENDER_SERVICE_ID", raising=False)
    with patch("services.provider_manager.get_system_memory_mb", return_value=8192):
        assert get_inference_provider("audio") == "local"

    # 'auto' without key on low RAM (e.g. Render 512MB)
    with patch("services.provider_manager.get_system_memory_mb", return_value=512):
        assert get_inference_provider("audio") == "cloud"


def test_cloud_audio_missing_api_key(dummy_audio_file, monkeypatch):
    """Verify that cloud audio returns structured error without crashing when GROQ_API_KEY is unset."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    res = transcribe_audio_with_groq(dummy_audio_file, api_key="")

    assert res["status"] == "failed"
    assert res["error_category"] == "MISSING_API_KEY"
    assert "GROQ_API_KEY" in res["error"]
    assert res["provenance"]["provider"] == "groq"
    assert res["provenance"]["result_source"] == ResultSource.EXTERNAL_API_GENERATION.value


def test_cloud_audio_mocked_success(dummy_audio_file, monkeypatch):
    """Verify successful Groq Whisper transcription flow and schema mapping."""
    monkeypatch.setenv("GROQ_API_KEY", "gsk-mock-valid-key")

    mock_segment = MagicMock()
    mock_segment.start = 0.0
    mock_segment.end = 2.5
    mock_segment.text = "Suspect was spotted fleeing north."

    mock_resp = MagicMock()
    mock_resp.text = "Suspect was spotted fleeing north."
    mock_resp.language = "en"
    mock_resp.duration = 2.5
    mock_resp.segments = [mock_segment]

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = mock_resp

    with patch("groq.Groq", return_value=mock_client):
        res = transcribe_audio_with_groq(
            dummy_audio_file,
            evidence_id="ev_audio_test",
            case_id="case_test",
        )

    assert res["status"] == "completed"
    assert res["provider"] == "groq"
    assert res["transcript"] == "Suspect was spotted fleeing north."
    assert res["detected_language"] == "en"
    assert len(res["segments"]) == 1
    assert res["segments"][0]["text"] == "Suspect was spotted fleeing north."
    assert res["result_source"] == ResultSource.EXTERNAL_API_GENERATION.value
    assert "intelligence_report" in res
    assert res["forensic_notice"]


def test_cloud_audio_rate_limit_handling(dummy_audio_file, monkeypatch):
    """Verify rate limit errors from Groq return clear retry instructions."""
    monkeypatch.setenv("GROQ_API_KEY", "gsk-mock-key")

    from groq import RateLimitError

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.side_effect = RateLimitError(
        message="Rate limit exceeded",
        response=MagicMock(status_code=429),
        body={"error": "Rate limit reached"},
    )

    with patch("groq.Groq", return_value=mock_client):
        res = transcribe_audio_with_groq(dummy_audio_file)

    assert res["status"] == "failed"
    assert res["error_category"] == "RATE_LIMIT_EXCEEDED"
    assert "rate limit" in res["error"].lower()


def test_audio_analyzer_pipeline_routes_to_cloud(dummy_audio_file, monkeypatch):
    """Verify AudioAnalyzer pipeline transparently delegates to cloud service when configured."""
    monkeypatch.setenv("INFERENCE_PROVIDER", "cloud")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-mock-key")

    with patch("services.cloud_audio_service.transcribe_audio_with_groq") as mock_groq_func:
        mock_groq_func.return_value = {
            "status": "completed",
            "provider": "groq",
            "transcript": "Test from routed pipeline",
            "segments": [],
        }

        analyzer = AudioAnalyzer()
        res = analyzer.transcribe_audio_pipeline(dummy_audio_file)

        assert mock_groq_func.called
        assert res["provider"] == "groq"
        assert res["transcript"] == "Test from routed pipeline"
