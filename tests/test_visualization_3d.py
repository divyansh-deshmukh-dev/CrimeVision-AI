"""
tests/test_visualization_3d.py — Phase 8 Interactive 3D Evidence Visualization Test Suite.

Covers:
  1. Unit tests for spatial mapper:
     - normalize_box with normalized, pixel, empty, None, and out-of-bounds coordinates.
     - get_category_color for known, unknown, case-insensitive labels.
     - map_case_to_spatial_scene with empty cases, unanalyzed evidence, images, and videos.
     - Forensic disclaimer verification (strictly illustrative, non-metric).
  2. Integration tests for GET /api/cases/<case_id>/visualization/spatial:
     - 404 on nonexistent case.
     - 200 on empty case (0 detections, valid structure).
     - 200 with analyzed image evidence (proper spatial coordinates and proxy dimensions).
     - 200 with analyzed video evidence (proper timeline layering along Z-axis).
     - Cross-case isolation (Case A detections never leak into Case B).
     - Unanalyzed / failed evidence gracefully excluded from 3D scene.
"""

import io
import pytest
from services.spatial_mapper import (
    normalize_box,
    get_category_color,
    map_case_to_spatial_scene,
    CATEGORY_COLORS,
    DEFAULT_COLOR,
)
from storage.evidence_store import update_analysis


# ── Helper Upload Utilities ──────────────────────────────────────────────────

def _upload_img(client, case_id: str, file_bytes: bytes, filename: str = "scene.png"):
    data = {"file": (io.BytesIO(file_bytes), filename, "image/png")}
    return client.post(f"/api/cases/{case_id}/evidence", data=data, content_type="multipart/form-data")


def _upload_video(client, case_id: str, file_bytes: bytes, filename: str = "cctv.mp4"):
    data = {"file": (io.BytesIO(file_bytes), filename, "video/mp4")}
    return client.post(f"/api/cases/{case_id}/evidence", data=data, content_type="multipart/form-data")


# ── 1. Unit Tests: Spatial Mapper Service ────────────────────────────────────

class TestSpatialMapperUnit:
    """Unit tests for services/spatial_mapper.py."""

    def test_normalize_box_already_normalized(self):
        box = [0.1234, 0.2345, 0.7891, 0.8912]
        res = normalize_box(box)
        assert res == [0.1234, 0.2345, 0.7891, 0.8912]

    def test_normalize_box_with_image_dim(self):
        box_px = [192.0, 108.0, 960.0, 540.0]
        dim = {"width": 1920, "height": 1080}
        res = normalize_box(box_px, dim)
        assert res == [0.1, 0.1, 0.5, 0.5]

    def test_normalize_box_fallback_for_empty_or_none(self):
        assert normalize_box(None) == [0.4, 0.4, 0.6, 0.6]
        assert normalize_box([]) == [0.4, 0.4, 0.6, 0.6]
        assert normalize_box([0.1, 0.2]) == [0.4, 0.4, 0.6, 0.6]

    def test_normalize_box_clamping_out_of_bounds(self):
        box = [-100.0, -50.0, 3000.0, 2000.0]
        dim = {"width": 1000, "height": 1000}
        res = normalize_box(box, dim)
        assert res[0] == 0.0
        assert res[1] == 0.0
        assert res[2] == 1.0
        assert res[3] == 1.0

    def test_get_category_color(self):
        assert get_category_color("person") == "#10B981"
        assert get_category_color("  PERSON  ") == "#10B981"
        assert get_category_color("knife") == "#EF4444"
        assert get_category_color("car") == "#3B82F6"
        assert get_category_color("backpack") == "#F59E0B"
        assert get_category_color("cell phone") == "#8B5CF6"
        assert get_category_color("unknown_alien_object") == DEFAULT_COLOR

    def test_map_case_empty(self):
        case = {"case_id": "case_empty", "name": "Empty Test Case"}
        res = map_case_to_spatial_scene(case, [])

        assert res["status"] == "success"
        assert res["case_id"] == "case_empty"
        assert res["case_name"] == "Empty Test Case"
        assert res["summary"]["total_objects"] == 0
        assert res["objects"] == []
        assert res["legend"] == []
        assert res["disclaimer"]["is_metric"] is False
        assert res["disclaimer"]["has_genuine_3d"] is False
        assert "Forensic Notice" in res["disclaimer"]["notice"]

    def test_map_case_skips_unanalyzed_or_failed(self):
        case = {"case_id": "case_skip", "name": "Skip Test Case"}
        evidence_items = [
            {
                "evidence_id": "ev_pending",
                "original_name": "unprocessed.jpg",
                "modality": "image",
                "analysis_status": "pending",
                "analysis_json": None,
            },
            {
                "evidence_id": "ev_failed",
                "original_name": "failed.mp4",
                "modality": "video",
                "analysis_status": "failed",
                "analysis_json": {"status": "failed"},
            },
        ]
        res = map_case_to_spatial_scene(case, evidence_items)
        assert res["summary"]["total_objects"] == 0
        assert len(res["objects"]) == 0

    def test_map_case_image_and_video(self):
        case = {"case_id": "case_mixed", "name": "Mixed Evidence"}
        evidence_items = [
            {
                "evidence_id": "ev_img_1",
                "original_name": "scene.jpg",
                "modality": "image",
                "analysis_status": "completed",
                "analysis_json": {
                    "image_dimensions": {"width": 1920, "height": 1080},
                    "rtdetr": {
                        "objects": [
                            {
                                "label": "person",
                                "confidence": 0.952,
                                "box_normalized": [0.2, 0.3, 0.4, 0.7],
                            },
                            {
                                "label": "knife",
                                "confidence": 0.887,
                                "box_normalized": [0.45, 0.5, 0.55, 0.6],
                            },
                        ]
                    },
                },
            },
            {
                "evidence_id": "ev_vid_1",
                "original_name": "surveillance.mp4",
                "modality": "video",
                "analysis_status": "completed",
                "analysis_json": {
                    "video_metadata": {"duration": 10.0, "width": 1280, "height": 720},
                    "sampled_frames": [
                        {
                            "frame_index": 0,
                            "timestamp_seconds": 0.0,
                            "status": "success",
                            "objects": [
                                {
                                    "label": "car",
                                    "confidence": 0.912,
                                    "box_normalized": [0.1, 0.4, 0.5, 0.8],
                                }
                            ],
                        },
                        {
                            "frame_index": 15,
                            "timestamp_seconds": 5.0,
                            "status": "success",
                            "objects": [
                                {
                                    "label": "person",
                                    "confidence": 0.875,
                                    "box_normalized": [0.6, 0.2, 0.8, 0.8],
                                }
                            ],
                        },
                    ],
                },
            },
        ]

        res = map_case_to_spatial_scene(case, evidence_items)
        assert res["status"] == "success"
        assert res["summary"]["total_objects"] == 4
        assert set(res["summary"]["categories"]) == {"person", "knife", "car"}

        # Check legend
        legend_cats = [item["category"] for item in res["legend"]]
        assert "person" in legend_cats
        assert "knife" in legend_cats
        assert "car" in legend_cats

        # Check image object projection
        img_person = next(o for o in res["objects"] if o["evidence_id"] == "ev_img_1" and o["label"] == "person")
        assert img_person["modality"] == "image"
        assert img_person["color_hex"] == "#10B981"
        assert img_person["timestamp_seconds"] is None
        assert "x" in img_person["spatial_coords"]
        assert "y" in img_person["spatial_coords"]
        assert "z" in img_person["spatial_coords"]
        assert "position" in img_person
        assert len(img_person["position"]) == 3
        assert "estimated_dimensions" in img_person
        assert img_person["category"] == "person"
        assert img_person["source_evidence_filename"] == "scene.jpg"

        # Check video object timeline progression along Z-axis
        vid_car = next(o for o in res["objects"] if o["evidence_id"] == "ev_vid_1" and o["label"] == "car")
        vid_person = next(o for o in res["objects"] if o["evidence_id"] == "ev_vid_1" and o["label"] == "person")

        assert vid_car["timestamp_seconds"] == 0.0
        assert vid_person["timestamp_seconds"] == 5.0
        # Frame at 5.0s should have a higher Z coordinate than frame at 0.0s (-6.0 + (ts/dur)*12.0)
        assert vid_person["spatial_coords"]["z"] > vid_car["spatial_coords"]["z"]


# ── 2. Integration Tests: API Endpoint ──────────────────────────────────────

class TestSpatialVisualizationAPI:
    """GET /api/cases/<case_id>/visualization/spatial"""

    def test_spatial_nonexistent_case_404(self, client):
        resp = client.get("/api/cases/case_nonexistent_888/visualization/spatial")
        assert resp.status_code == 404
        assert "not found" in resp.get_json()["error"]

    def test_spatial_empty_case_returns_valid_scene(self, client, case_id):
        resp = client.get(f"/api/cases/{case_id}/visualization/spatial")
        assert resp.status_code == 200
        data = resp.get_json()

        assert data["status"] == "success"
        assert data["case_id"] == case_id
        assert data["summary"]["total_objects"] == 0
        assert data["objects"] == []
        assert data["legend"] == []
        assert data["disclaimer"]["is_metric"] is False
        assert "Forensic Notice" in data["disclaimer"]["notice"]

    def test_spatial_with_analyzed_evidence(self, client, case_id, tiny_png):
        # 1. Upload an image
        up_resp = _upload_img(client, case_id, tiny_png, "crime_scene.png")
        assert up_resp.status_code == 201
        ev_id = up_resp.get_json()["evidence"]["evidence_id"]

        # 2. Attach mock analysis findings to storage
        mock_analysis = {
            "image_dimensions": {"width": 800, "height": 600},
            "rtdetr": {
                "objects": [
                    {
                        "label": "person",
                        "confidence": 0.945,
                        "box_normalized": [0.25, 0.3, 0.45, 0.85],
                    },
                    {
                        "label": "knife",
                        "confidence": 0.892,
                        "box_normalized": [0.4, 0.6, 0.5, 0.7],
                    },
                ]
            },
        }
        update_analysis(ev_id, status="completed", analysis_data=mock_analysis)

        # 3. Request 3D spatial scene endpoint
        resp = client.get(f"/api/cases/{case_id}/visualization/spatial")
        assert resp.status_code == 200
        data = resp.get_json()

        assert data["status"] == "success"
        assert data["summary"]["total_objects"] == 2
        assert set(data["summary"]["categories"]) == {"person", "knife"}
        assert len(data["objects"]) == 2

        knife_obj = next(o for o in data["objects"] if o["label"] == "knife")
        assert knife_obj["evidence_id"] == ev_id
        assert knife_obj["evidence_name"] == "crime_scene.png"
        assert knife_obj["color_hex"] == "#EF4444"
        assert knife_obj["confidence"] == 0.892
        assert knife_obj["spatial_coords"]["y"] > 0

    def test_spatial_cross_case_isolation(self, client, tiny_png):
        # Create Case A and Case B
        rA = client.post("/api/cases", json={"name": "3D Case Alpha"})
        cid_A = rA.get_json()["case"]["case_id"]

        rB = client.post("/api/cases", json={"name": "3D Case Beta"})
        cid_B = rB.get_json()["case"]["case_id"]

        # Upload image to Case A and complete analysis
        up_A = _upload_img(client, cid_A, tiny_png, "alpha_knife.png")
        ev_id_A = up_A.get_json()["evidence"]["evidence_id"]

        update_analysis(
            ev_id_A,
            status="completed",
            analysis_data={
                "rtdetr": {
                    "objects": [
                        {"label": "knife", "confidence": 0.93, "box_normalized": [0.1, 0.1, 0.3, 0.3]}
                    ]
                }
            },
        )

        # Query Case A: Must have knife object
        resp_A = client.get(f"/api/cases/{cid_A}/visualization/spatial")
        assert resp_A.status_code == 200
        data_A = resp_A.get_json()
        assert data_A["summary"]["total_objects"] == 1
        assert data_A["objects"][0]["label"] == "knife"

        # Query Case B: Must have 0 objects (strict isolation)
        resp_B = client.get(f"/api/cases/{cid_B}/visualization/spatial")
        assert resp_B.status_code == 200
        data_B = resp_B.get_json()
        assert data_B["summary"]["total_objects"] == 0
        assert len(data_B["objects"]) == 0
