"""
tests/test_cloud_vision_inference.py — Tests for Google Gemini Cloud Vision Image and Video Inference.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from PIL import Image

from services.cloud_vision_service import (
    analyze_image_with_gemini,
    analyze_video_frames_with_gemini,
    _normalize_box,
)
from services.image_analyzer import ImageAnalyzer
from services.provider_manager import get_inference_provider
from services.provenance import ResultSource
from services.video_analyzer import VideoAnalyzer


@pytest.fixture
def dummy_image_file(tmp_path: Path) -> Path:
    """Create a temporary test image file."""
    f = tmp_path / "test_street.jpg"
    img = Image.new("RGB", (640, 480), color=(128, 128, 128))
    img.save(f, format="JPEG")
    return f


def test_box_normalization_helper():
    """Verify Gemini 0-1000 integer boxes convert accurately to 0.0-1.0 and pixel coordinates."""
    # [ymin, xmin, ymax, xmax] -> 0-1000 scale
    box_2d = [200, 100, 800, 500]
    b_norm, b_px = _normalize_box(box_2d, img_w=1000, img_h=1000)

    # Expected [x1, y1, x2, y2]
    assert b_norm == [0.1, 0.2, 0.5, 0.8]
    assert b_px == [100.0, 200.0, 500.0, 800.0]


def test_cloud_vision_provider_routing(monkeypatch):
    """Test vision provider resolution across configurations."""
    monkeypatch.setenv("INFERENCE_PROVIDER", "cloud")
    assert get_inference_provider("image") == "cloud"
    assert get_inference_provider("video") == "cloud"

    monkeypatch.setenv("INFERENCE_PROVIDER", "local")
    assert get_inference_provider("image") == "local"
    assert get_inference_provider("video") == "local"

    monkeypatch.setenv("INFERENCE_PROVIDER", "auto")
    monkeypatch.setenv("RENDER", "true")
    assert get_inference_provider("image") == "cloud"
    assert get_inference_provider("video") == "cloud"
    monkeypatch.delenv("RENDER", raising=False)


def test_gemini_image_missing_api_key(dummy_image_file, monkeypatch):
    """Verify structured failure when GEMINI_API_KEY is not configured."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    res = analyze_image_with_gemini(dummy_image_file, api_key="")

    assert res["status"] == "failed"
    assert res["error_code"] == "MISSING_API_KEY"
    assert "GEMINI_API_KEY" in res["error"]
    assert res["provenance"]["provider"] == "gemini"


def test_gemini_image_mocked_success(dummy_image_file, monkeypatch):
    """Verify end-to-end Gemini image object detection and forensic analysis flow."""
    monkeypatch.setenv("GEMINI_API_KEY", "mock-gemini-key")

    mock_response = MagicMock()
    mock_response.text = """
    {
        "objects": [
            {
                "label": "person",
                "confidence": 0.94,
                "box_2d": [150, 100, 750, 300]
            },
            {
                "label": "car",
                "confidence": 0.89,
                "box_2d": [400, 500, 800, 950]
            }
        ],
        "caption": "A realistic urban street with a pedestrian walking near a parked car.",
        "scene_classifications": [
            {"label": "urban street", "similarity_score": 0.96},
            {"label": "daytime", "similarity_score": 0.91}
        ],
        "forensic_summary": "Visual observation: One pedestrian and one vehicle detected on paved roadway."
    }
    """

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("google.genai.Client", return_value=mock_client):
        res = analyze_image_with_gemini(
            dummy_image_file,
            evidence_id="ev_img_test",
            case_id="case_test",
        )

    assert res["status"] == "completed"
    assert res["provider"] == "gemini"
    assert res["result_source"] == ResultSource.EXTERNAL_API_GENERATION.value
    assert res["detection"]["total_detections"] == 2
    assert len(res["detection"]["objects"]) == 2

    # Check normalized coordinate order [x1, y1, x2, y2]
    person = res["detection"]["objects"][0]
    assert person["label"] == "person"
    assert person["box_normalized"][0] == 0.1   # x1
    assert person["box_normalized"][1] == 0.15  # y1
    assert person["box_normalized"][2] == 0.3   # x2
    assert person["box_normalized"][3] == 0.75  # y2

    # Check BLIP caption & CLIP matches
    assert "urban street" in res["caption"]["caption"]
    assert res["clip"]["top_match"]["label"] == "urban street"
    assert res["statistics"]["persons_detected"] == 1
    assert res["statistics"]["vehicles_detected"] == 1


def test_gemini_image_rate_limit(dummy_image_file, monkeypatch):
    """Verify graceful handling when Gemini API returns 429 quota exhaustion."""
    monkeypatch.setenv("GEMINI_API_KEY", "mock-gemini-key")

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("429 ResourceExhausted: Quota exceeded")

    with patch("google.genai.Client", return_value=mock_client):
        res = analyze_image_with_gemini(dummy_image_file)

    assert res["status"] == "failed"
    assert res["error_code"] == "RATE_LIMIT_EXCEEDED"
    assert "rate limit" in res["error"].lower()


def test_gemini_video_mocked_success(monkeypatch):
    """Verify batched Gemini video analysis across sampled frames."""
    monkeypatch.setenv("GEMINI_API_KEY", "mock-gemini-key")

    sampled_frames = [
        {"image": Image.new("RGB", (640, 360)), "frame_index": 0, "timestamp_seconds": 0.0},
        {"image": Image.new("RGB", (640, 360)), "frame_index": 30, "timestamp_seconds": 1.0},
    ]
    video_meta = {"duration_seconds": 2.0, "fps": 30.0, "width": 640, "height": 360}

    mock_response = MagicMock()
    mock_response.text = """
    {
        "frames": [
            {
                "frame_index": 0,
                "timestamp_seconds": 0.0,
                "objects": [{"label": "motorcycle", "confidence": 0.92, "box_2d": [300, 200, 700, 500]}]
            },
            {
                "frame_index": 30,
                "timestamp_seconds": 1.0,
                "objects": [{"label": "motorcycle", "confidence": 0.94, "box_2d": [300, 300, 700, 600]}]
            }
        ],
        "activity_summary": "Motorcycle transit observed across two sequential frames.",
        "timeline_events": [
            {"timestamp": "0.00s", "timestamp_seconds": 0.0, "observation": "Motorcycle enters field of view."},
            {"timestamp": "1.00s", "timestamp_seconds": 1.0, "observation": "Motorcycle advances eastward."}
        ]
    }
    """

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("google.genai.Client", return_value=mock_client):
        res = analyze_video_frames_with_gemini(
            sampled_frames=sampled_frames,
            video_metadata=video_meta,
            evidence_id="ev_vid_test",
            case_id="case_test",
        )

    assert res["status"] == "completed"
    assert res["provider"] == "gemini"
    assert len(res["sampled_frames"]) == 2
    assert res["aggregated_detections"]["total_detections"] == 2
    assert "motorcycle" in res["aggregated_detections"]["unique_classes"]
    assert len(res["timeline"]) == 2


def test_image_analyzer_pipeline_routes_to_cloud(dummy_image_file, monkeypatch):
    """Verify ImageAnalyzer transparently delegates to Gemini cloud vision when configured."""
    monkeypatch.setenv("INFERENCE_PROVIDER", "cloud")
    monkeypatch.setenv("GEMINI_API_KEY", "mock-gemini-key")

    with patch("services.cloud_vision_service.analyze_image_with_gemini") as mock_gemini_func:
        mock_gemini_func.return_value = {
            "status": "completed",
            "provider": "gemini",
            "detection": {"objects": []},
        }

        analyzer = ImageAnalyzer()
        res = analyzer.analyze_image_pipeline(dummy_image_file)

        assert mock_gemini_func.called
        assert res["provider"] == "gemini"
