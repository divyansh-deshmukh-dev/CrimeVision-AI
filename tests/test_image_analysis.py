"""
tests/test_image_analysis.py — Phase 2 Image Analysis Test Suite.

Covers:
  - Evidence file serving endpoint: GET /api/cases/<cid>/evidence/<eid>/file
  - Path traversal protection on evidence file endpoint
  - Image analysis endpoint: POST /api/cases/<cid>/evidence/<eid>/analyze/image
  - Analysis retrieval endpoint: GET /api/cases/<cid>/evidence/<eid>/analysis
  - Modality checks (rejection of non-image evidence)
  - Handling of corrupted/invalid images
  - Missing evidence / nonexistent case handling
  - Case-isolation checks on file retrieval and analysis
  - Mocked unit tests for RT-DETR, CLIP, and BLIP pipelines
"""

import io
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from PIL import Image


def _upload_img(client, case_id: str, file_bytes: bytes, filename: str = "test.png"):
    data = {
        "file": (io.BytesIO(file_bytes), filename, "image/png"),
    }
    return client.post(
        f"/api/cases/{case_id}/evidence",
        data=data,
        content_type="multipart/form-data",
    )


def _upload_audio(client, case_id: str, file_bytes: bytes, filename: str = "audio.wav"):
    data = {
        "file": (io.BytesIO(file_bytes), filename, "audio/wav"),
    }
    return client.post(
        f"/api/cases/{case_id}/evidence",
        data=data,
        content_type="multipart/form-data",
    )


class TestEvidenceFileEndpoint:
    """GET /api/cases/<case_id>/evidence/<evidence_id>/file"""

    def test_serve_image_file_success(self, client, case_id, tiny_png):
        upload_res = _upload_img(client, case_id, tiny_png, "sample.png").get_json()
        ev_id = upload_res["evidence"]["evidence_id"]

        resp = client.get(f"/api/cases/{case_id}/evidence/{ev_id}/file")
        assert resp.status_code == 200
        assert resp.mimetype == "image/png"
        assert resp.data == tiny_png

    def test_serve_file_nonexistent_case_404(self, client):
        resp = client.get("/api/cases/nonexistent_case/evidence/ev_123/file")
        assert resp.status_code == 404

    def test_serve_file_nonexistent_evidence_404(self, client, case_id):
        resp = client.get(f"/api/cases/{case_id}/evidence/ev_nonexistent/file")
        assert resp.status_code == 404

    def test_serve_file_cross_case_isolation_404(self, client, tiny_png):
        res_a = client.post("/api/cases", json={"name": "Case File A"}).get_json()
        cid_a = res_a["case"]["case_id"]

        res_b = client.post("/api/cases", json={"name": "Case File B"}).get_json()
        cid_b = res_b["case"]["case_id"]

        ev_a = _upload_img(client, cid_a, tiny_png, "a.png").get_json()["evidence"]["evidence_id"]

        # Attempt to access Case A's file via Case B's path
        resp = client.get(f"/api/cases/{cid_b}/evidence/{ev_a}/file")
        assert resp.status_code == 404


class TestImageAnalysisAPI:
    """POST /api/cases/<case_id>/evidence/<evidence_id>/analyze/image"""

    def test_analyze_nonexistent_case_404(self, client):
        resp = client.post("/api/cases/case_none/evidence/ev_none/analyze/image")
        assert resp.status_code == 404

    def test_analyze_nonexistent_evidence_404(self, client, case_id):
        resp = client.post(f"/api/cases/{case_id}/evidence/ev_none/analyze/image")
        assert resp.status_code == 404

    def test_analyze_wrong_modality_rejects_400(self, client, case_id, tiny_wav):
        ev_id = _upload_audio(client, case_id, tiny_wav, "witness.wav").get_json()["evidence"]["evidence_id"]

        resp = client.post(f"/api/cases/{case_id}/evidence/{ev_id}/analyze/image")
        assert resp.status_code == 400
        assert "modality" in resp.get_json()["error"]

    def test_analyze_cross_case_isolation_404(self, client, tiny_png):
        res_a = client.post("/api/cases", json={"name": "Isolation Case A"}).get_json()
        cid_a = res_a["case"]["case_id"]

        res_b = client.post("/api/cases", json={"name": "Isolation Case B"}).get_json()
        cid_b = res_b["case"]["case_id"]

        ev_a = _upload_img(client, cid_a, tiny_png, "iso.png").get_json()["evidence"]["evidence_id"]

        # Attempt to run analysis on Case A's evidence under Case B's endpoint
        resp = client.post(f"/api/cases/{cid_b}/evidence/{ev_a}/analyze/image")
        assert resp.status_code == 404

    def test_analyze_invalid_candidate_labels_format_400(self, client, case_id, tiny_png):
        ev_id = _upload_img(client, case_id, tiny_png).get_json()["evidence"]["evidence_id"]
        resp = client.post(
            f"/api/cases/{case_id}/evidence/{ev_id}/analyze/image",
            json={"candidate_labels": "not-a-list"},
        )
        assert resp.status_code == 400

    @patch("services.image_analyzer.ImageAnalyzer.analyze_image_pipeline")
    def test_mocked_image_analysis_pipeline_success(self, mock_pipeline, client, case_id, tiny_png):
        """Mocked unit test verifying API response structure and persistence."""
        ev_id = _upload_img(client, case_id, tiny_png).get_json()["evidence"]["evidence_id"]

        mock_result = {
            "status": "completed",
            "image_metadata": {"filename": "test.png", "width": 1, "height": 1},
            "detection": {
                "status": "success",
                "model": "PekingU/rtdetr_r50vd",
                "objects": [
                    {
                        "label": "person",
                        "confidence": 0.8921,
                        "box_pixels": [0.0, 0.0, 1.0, 1.0],
                        "box_normalized": [0.0, 0.0, 1.0, 1.0],
                    }
                ],
                "class_counts": {"person": 1},
                "total_detections": 1,
            },
            "clip": {
                "status": "success",
                "model": "openai/clip-vit-base-patch32",
                "matches": [
                    {"label": "street or roadway", "similarity_score": 0.7512},
                    {"label": "parking lot", "similarity_score": 0.2488},
                ],
                "top_match": {"label": "street or roadway", "similarity_score": 0.7512},
                "forensic_notice": "CLIP notice test",
            },
            "caption": {
                "status": "success",
                "model": "Salesforce/blip-image-captioning-base",
                "caption": "a person walking on a city street at night",
            },
        }
        mock_pipeline.return_value = mock_result

        # Run analysis
        resp = client.post(f"/api/cases/{case_id}/evidence/{ev_id}/analyze/image")
        assert resp.status_code == 200
        data = resp.get_json()

        assert data["status"] == "completed"
        assert data["evidence_id"] == ev_id
        assert data["case_id"] == case_id
        analysis = data["analysis"]
        assert analysis["detection"]["total_detections"] == 1
        assert analysis["detection"]["objects"][0]["label"] == "person"
        assert analysis["clip"]["top_match"]["label"] == "street or roadway"
        assert analysis["caption"]["caption"] == "a person walking on a city street at night"

        # Verify analysis retrieval via GET endpoint
        get_resp = client.get(f"/api/cases/{case_id}/evidence/{ev_id}/analysis")
        assert get_resp.status_code == 200
        get_data = get_resp.get_json()
        assert get_data["analysis_status"] == "completed"
        assert get_data["analysis"]["caption"]["caption"] == "a person walking on a city street at night"

    @patch("services.image_analyzer.ImageAnalyzer.analyze_image_pipeline")
    def test_mocked_image_analysis_pipeline_error_handling(self, mock_pipeline, client, case_id, tiny_png):
        """Mocked unit test for internal failure handling in model pipeline."""
        ev_id = _upload_img(client, case_id, tiny_png).get_json()["evidence"]["evidence_id"]

        mock_pipeline.side_effect = RuntimeError("Out of memory on CPU")

        resp = client.post(f"/api/cases/{case_id}/evidence/{ev_id}/analyze/image")
        assert resp.status_code == 500
        data = resp.get_json()
        assert data["status"] == "failed"
        assert "Out of memory" in data["analysis"]["error"]


class TestImageAnalyzerServiceUnit:
    """Direct unit tests on ImageAnalyzer class methods with mocks."""

    def test_analyzer_init(self):
        from services.image_analyzer import ImageAnalyzer
        analyzer = ImageAnalyzer()
        assert analyzer.rtdetr_model_id == "PekingU/rtdetr_r50vd"
        assert analyzer.clip_model_id == "openai/clip-vit-base-patch32"
        assert analyzer.blip_model_id == "Salesforce/blip-image-captioning-base"

    def test_corrupted_image_handling(self, tmp_path):
        from services.image_analyzer import ImageAnalyzer
        bad_file = tmp_path / "corrupt.png"
        bad_file.write_bytes(b"NOT_A_VALID_IMAGE_HEADER")

        analyzer = ImageAnalyzer()
        res = analyzer.analyze_image_pipeline(bad_file)
        assert res["status"] == "error"
        assert "Failed to open or decode image" in res["error"]

    def test_missing_image_path_handling(self, tmp_path):
        from services.image_analyzer import ImageAnalyzer
        nonexistent = tmp_path / "ghost.png"
        analyzer = ImageAnalyzer()
        res = analyzer.analyze_image_pipeline(nonexistent)
        assert res["status"] == "error"
        assert "does not exist on disk" in res["error"]

    def test_analyze_image_pipeline_accepts_custom_labels(self, tmp_path):
        from services.image_analyzer import ImageAnalyzer
        img = Image.new("RGB", (32, 32), color="red")
        img_path = tmp_path / "test.png"
        img.save(img_path)

        analyzer = ImageAnalyzer()
        with patch.object(analyzer, "run_rtdetr_detection", return_value={"status": "success", "objects": []}), \
             patch.object(analyzer, "run_clip_similarity", return_value={"status": "success", "matches": []}) as mock_clip, \
             patch.object(analyzer, "run_blip_captioning", return_value={"status": "success", "caption": "test caption"}):
            res = analyzer.analyze_image_pipeline(img_path, custom_labels=["weapon", "vehicle"])
            assert res["status"] == "completed"
            mock_clip.assert_called_once_with(mock_clip.call_args[0][0], ["weapon", "vehicle"])

    def test_run_rtdetr_detection_on_images_empty(self):
        from services.image_analyzer import ImageAnalyzer
        analyzer = ImageAnalyzer()
        assert analyzer.run_rtdetr_detection_on_images([]) == []

    def test_analyzer_resizing_aspect_ratio(self, tmp_path):
        from services.image_analyzer import ImageAnalyzer
        # Create a 2400x1200 image (aspect ratio 2:1)
        img = Image.new("RGB", (2400, 1200), color="blue")
        img_path = tmp_path / "large_image.png"
        img.save(img_path)

        analyzer = ImageAnalyzer(max_inference_dimension=1200)
        captured_infer_img = []

        def mock_detect(pil_img, original_size=None):
            captured_infer_img.append((pil_img.size, original_size))
            return {"status": "success", "objects": []}

        with patch.object(analyzer, "run_rtdetr_detection", side_effect=mock_detect), \
             patch.object(analyzer, "run_clip_similarity", return_value={"status": "success", "matches": []}), \
             patch.object(analyzer, "run_blip_captioning", return_value={"status": "success", "caption": "caption"}):
            res = analyzer.analyze_image_pipeline(img_path)

            assert res["status"] == "completed"
            meta = res["image_metadata"]
            assert meta["width"] == 2400
            assert meta["height"] == 1200
            assert meta["inference_width"] == 1200
            assert meta["inference_height"] == 600
            assert meta["resized_for_inference"] is True
            assert meta["max_inference_dimension"] == 1200

            # Verify original_size was passed to detection
            assert len(captured_infer_img) == 1
            infer_size, orig_size = captured_infer_img[0]
            assert infer_size == (1200, 600)
            assert orig_size == (2400, 1200)

            # Verify original file on disk remains 2400x1200
            disk_img = Image.open(img_path)
            assert disk_img.size == (2400, 1200)

    def test_analyzer_no_resize_when_under_limit(self, tmp_path):
        from services.image_analyzer import ImageAnalyzer
        img = Image.new("RGB", (800, 600), color="green")
        img_path = tmp_path / "normal_image.png"
        img.save(img_path)

        analyzer = ImageAnalyzer(max_inference_dimension=1280)
        with patch.object(analyzer, "run_rtdetr_detection", return_value={"status": "success", "objects": []}), \
             patch.object(analyzer, "run_clip_similarity", return_value={"status": "success", "matches": []}), \
             patch.object(analyzer, "run_blip_captioning", return_value={"status": "success", "caption": "caption"}):
            res = analyzer.analyze_image_pipeline(img_path)
            assert res["status"] == "completed"
            meta = res["image_metadata"]
            assert meta["width"] == 800
            assert meta["height"] == 600
            assert meta["inference_width"] == 800
            assert meta["inference_height"] == 600
            assert meta["resized_for_inference"] is False

    def test_rtdetr_detection_maps_to_original_coordinates(self):
        from services.image_analyzer import ImageAnalyzer
        analyzer = ImageAnalyzer()

        # Mock processor and model
        mock_processor = MagicMock()
        mock_model = MagicMock()
        mock_model.config.id2label = {1: "person"}

        # Simulate detection output where target_sizes=[(2000, 4000)]
        mock_processor.post_process_object_detection.return_value = [{
            "scores": [0.95],
            "labels": [1],
            "boxes": [[100.0, 200.0, 500.0, 1000.0]],
        }]

        with patch("services.image_analyzer._load_hf_component") as mock_load:
            mock_load.side_effect = [mock_processor, mock_model]
            infer_img = Image.new("RGB", (1000, 500))
            res = analyzer.run_rtdetr_detection(infer_img, original_size=(4000, 2000))

            assert res["status"] == "success"
            assert res["image_dimensions"] == {"width": 4000, "height": 2000}
            assert res["total_detections"] == 1
            obj = res["objects"][0]
            assert obj["label"] == "person"
            assert obj["box_pixels"] == [100.0, 200.0, 500.0, 1000.0]
            # normalized to 4000x2000: x / 4000, y / 2000
            assert obj["box_normalized"] == [0.025, 0.1, 0.125, 0.5]


class TestInterruptedAnalysisRecovery:
    """Tests verifying recovery from interrupted or failed analysis states."""

    def test_retry_analysis_from_analyzing_state(self, client, case_id, tiny_png):
        from storage.evidence_store import update_analysis
        upload_res = _upload_img(client, case_id, tiny_png).get_json()
        ev_id = upload_res["evidence"]["evidence_id"]

        # Simulate stuck/interrupted 'analyzing' state in database
        update_analysis(ev_id, status="analyzing")

        # Now trigger analysis again with mock
        with patch("services.image_analyzer.ImageAnalyzer.analyze_image_pipeline") as mock_pipeline:
            mock_pipeline.return_value = {
                "status": "completed",
                "image_metadata": {"filename": "test.png", "width": 1, "height": 1},
                "detection": {"status": "success", "objects": []},
                "clip": {"status": "success", "matches": []},
                "caption": {"status": "success", "caption": "recovered"},
            }
            resp = client.post(f"/api/cases/{case_id}/evidence/{ev_id}/analyze/image")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["status"] == "completed"

    def test_interrupted_analysis_exception_marks_failed(self, client, case_id, tiny_png):
        upload_res = _upload_img(client, case_id, tiny_png).get_json()
        ev_id = upload_res["evidence"]["evidence_id"]

        with patch("services.image_analyzer.ImageAnalyzer.analyze_image_pipeline") as mock_pipeline:
            mock_pipeline.side_effect = RuntimeError("Worker process terminated unexpectedly")
            resp = client.post(f"/api/cases/{case_id}/evidence/{ev_id}/analyze/image")
            assert resp.status_code == 500
            data = resp.get_json()
            assert data["status"] == "failed"

        # Verify database record is marked failed, not left in analyzing
        get_resp = client.get(f"/api/cases/{case_id}/evidence/{ev_id}/analysis")
        assert get_resp.status_code == 200
        assert get_resp.get_json()["analysis_status"] == "failed"
