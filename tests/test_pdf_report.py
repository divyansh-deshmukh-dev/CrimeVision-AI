"""
tests/test_pdf_report.py — Phase 3 PDF Forensic Report Generation Test Suite.

Covers:
  - POST /api/cases/<case_id>/report: generate report for full case
  - POST /api/cases/<case_id>/report: generate report for specific evidence item
  - GET /api/reports/<report_id>: download generated PDF
  - GET /api/cases/<case_id>/reports: list generated reports
  - Nonexistent cases & evidence handling
  - Case-isolation checks on report generation & downloads
  - Verifying generated PDF content using pypdf:
      - Correct Case ID
      - Correct Evidence ID
      - Cryptographic SHA-256 hash match
      - RT-DETR detection classes and confidence scores
      - BLIP captions
      - CLIP similarity scores
      - Legal & Forensic Disclaimers
"""

import io
from pathlib import Path
import pytest
from pypdf import PdfReader


def _upload_img(client, case_id: str, file_bytes: bytes, filename: str = "crime_scene.png"):
    data = {
        "file": (io.BytesIO(file_bytes), filename, "image/png"),
    }
    return client.post(
        f"/api/cases/{case_id}/evidence",
        data=data,
        content_type="multipart/form-data",
    )


class TestPDFReportGeneration:
    """POST /api/cases/<case_id>/report and GET /api/reports/<report_id>"""

    def test_generate_report_nonexistent_case_404(self, client):
        resp = client.post("/api/cases/case_nonexistent_999/report")
        assert resp.status_code == 404
        assert "not found" in resp.get_json()["error"]

    def test_generate_report_nonexistent_evidence_404(self, client, case_id):
        resp = client.post(
            f"/api/cases/{case_id}/report",
            json={"evidence_id": "ev_nonexistent"},
        )
        assert resp.status_code == 404

    def test_generate_report_cross_case_isolation_404(self, client, tiny_png):
        res_a = client.post("/api/cases", json={"name": "Case A"}).get_json()
        cid_a = res_a["case"]["case_id"]

        res_b = client.post("/api/cases", json={"name": "Case B"}).get_json()
        cid_b = res_b["case"]["case_id"]

        ev_a = _upload_img(client, cid_a, tiny_png, "ev_a.png").get_json()["evidence"]["evidence_id"]

        # Request report in Case B specifying Case A's evidence
        resp = client.post(f"/api/cases/{cid_b}/report", json={"evidence_id": ev_a})
        assert resp.status_code == 404
        assert "not found in case" in resp.get_json()["error"]

    def test_generate_empty_case_report_success(self, client, case_id):
        """Report generation on a newly created case with no evidence records yet."""
        resp = client.post(f"/api/cases/{case_id}/report")
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["status"] == "generated"
        rep = data["report"]
        assert rep["case_id"] == case_id
        assert rep["file_size"] > 0
        assert rep["download_url"].startswith("/api/reports/rep_")

        # Download PDF and verify basic structure
        dl_resp = client.get(rep["download_url"])
        assert dl_resp.status_code == 200
        assert dl_resp.mimetype == "application/pdf"

        reader = PdfReader(io.BytesIO(dl_resp.data))
        text = "\n".join(page.extract_text() for page in reader.pages)
        assert case_id in text
        assert "CRIMEVISION AI" in text
        assert "LEGAL & FORENSIC DISCLAIMER" in text

    def test_generate_report_with_complete_image_analysis(self, client, case_id, tiny_png):
        """Generate report with full RT-DETR, CLIP, and BLIP analysis records."""
        up_res = _upload_img(client, case_id, tiny_png, "forensic_scene.png").get_json()
        ev_id = up_res["evidence"]["evidence_id"]
        sha256 = up_res["evidence"]["sha256"]

        # Simulate completed Phase 2 analysis
        from storage.evidence_store import update_analysis
        analysis_payload = {
            "status": "completed",
            "image_metadata": {"filename": "forensic_scene.png", "width": 640, "height": 480},
            "detection": {
                "status": "success",
                "model": "PekingU/rtdetr_r50vd",
                "objects": [
                    {
                        "label": "person",
                        "confidence": 0.9421,
                        "box_pixels": [50.0, 60.0, 180.0, 320.0],
                        "box_normalized": [0.0781, 0.125, 0.2812, 0.6667],
                    },
                    {
                        "label": "car",
                        "confidence": 0.8845,
                        "box_pixels": [220.0, 150.0, 580.0, 420.0],
                        "box_normalized": [0.3438, 0.3125, 0.9062, 0.875],
                    },
                ],
                "class_counts": {"person": 1, "car": 1},
                "total_detections": 2,
            },
            "clip": {
                "status": "success",
                "model": "openai/clip-vit-base-patch32",
                "matches": [
                    {"label": "parking lot or vehicle garage", "similarity_score": 0.8124},
                    {"label": "commercial office or store", "similarity_score": 0.1245},
                ],
                "top_match": {"label": "parking lot or vehicle garage", "similarity_score": 0.8124},
                "forensic_notice": "CLIP zero-shot similarity scores represent text-image semantic correlation.",
            },
            "caption": {
                "status": "success",
                "model": "Salesforce/blip-image-captioning-base",
                "caption": "a person standing beside a dark vehicle in an underground parking lot",
            },
        }
        update_analysis(ev_id, status="completed", analysis_data=analysis_payload)

        # Trigger PDF generation
        resp = client.post(f"/api/cases/{case_id}/report", json={"evidence_id": ev_id})
        assert resp.status_code == 201
        rep = resp.get_json()["report"]
        assert rep["file_size"] > 1000

        # Download and verify PDF text content
        dl_resp = client.get(rep["download_url"])
        assert dl_resp.status_code == 200

        reader = PdfReader(io.BytesIO(dl_resp.data))
        pdf_text = "\n".join(page.extract_text() for page in reader.pages)

        # Verify key case & evidence metadata
        assert case_id in pdf_text
        assert ev_id in pdf_text
        assert sha256 in pdf_text
        assert "forensic_scene.png" in pdf_text

        # Verify RT-DETR detection details
        assert "person" in pdf_text
        assert "car" in pdf_text
        assert "94.21%" in pdf_text
        assert "88.45%" in pdf_text

        # Verify BLIP caption
        assert "a person standing beside a dark vehicle in an underground parking lot" in pdf_text

        # Verify CLIP scene classification
        assert "parking lot or vehicle garage" in pdf_text
        assert "81.24%" in pdf_text

        # Verify forensic disclaimer
        assert "LEGAL & FORENSIC DISCLAIMER" in pdf_text
        assert "scientific" in pdf_text.lower()

    def test_generate_report_with_failed_analysis_state(self, client, case_id, tiny_png):
        """Generate report when analysis experienced an error; verifies transparent error reporting."""
        up_res = _upload_img(client, case_id, tiny_png, "broken_model.png").get_json()
        ev_id = up_res["evidence"]["evidence_id"]

        from storage.evidence_store import update_analysis
        error_payload = {
            "status": "failed",
            "detection": {"status": "failed", "error": "CUDA device unavailable on CPU-only container", "objects": []},
            "caption": {"status": "failed", "error": "Model weight download interrupted", "caption": None},
            "clip": {"status": "failed", "error": "Out of memory", "matches": []},
        }
        update_analysis(ev_id, status="failed", analysis_data=error_payload)

        resp = client.post(f"/api/cases/{case_id}/report")
        assert resp.status_code == 201

        rep = resp.get_json()["report"]
        dl_resp = client.get(rep["download_url"])
        assert dl_resp.status_code == 200

        reader = PdfReader(io.BytesIO(dl_resp.data))
        pdf_text = "\n".join(page.extract_text() for page in reader.pages)

        # Verify error notes appear honestly and without fabrications
        assert "RT-DETR Inference Failed" in pdf_text
        assert "CUDA device unavailable" in pdf_text
        assert "BLIP Captioning Failed" in pdf_text

    def test_download_nonexistent_report_404(self, client):
        resp = client.get("/api/reports/rep_nonexistent_999")
        assert resp.status_code == 404

    def test_list_case_reports(self, client, case_id):
        # Generate two reports
        client.post(f"/api/cases/{case_id}/report")
        client.post(f"/api/cases/{case_id}/report")

        resp = client.get(f"/api/cases/{case_id}/reports")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] >= 2
        for r in data["reports"]:
            assert r["case_id"] == case_id
            assert "report_id" in r

    def test_generate_report_pdf_endpoint_alias(self, client, case_id):
        resp = client.post(f"/api/cases/{case_id}/reports/pdf")
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["status"] == "generated"
        assert "download_url" in data["report"]
        assert data["report"]["filename"].endswith(".pdf")
        dl_resp = client.get(data["report"]["download_url"])
        assert dl_resp.status_code == 200
        assert dl_resp.mimetype == "application/pdf"
