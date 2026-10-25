"""
tests/test_cases.py — Tests for case management endpoints.

Covers:
  POST   /api/cases          — create
  GET    /api/cases          — list
  GET    /api/cases/<id>     — retrieve
  Failure paths: missing name, empty name, unknown case_id.
"""

import pytest


class TestCreateCase:
    """POST /api/cases"""

    def test_create_case_success(self, client):
        resp = client.post(
            "/api/cases",
            json={"name": "Burglary #2024-001", "description": "Warehouse incident"},
            content_type="application/json",
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["status"] == "created"
        assert "case" in data

    def test_created_case_fields(self, client):
        resp = client.post(
            "/api/cases",
            json={"name": "Field Check"},
        )
        case = resp.get_json()["case"]
        for field in ("case_id", "name", "description", "created_at", "updated_at", "status", "is_demo"):
            assert field in case, f"'{field}' missing from case response"

    def test_case_id_format(self, client):
        resp = client.post("/api/cases", json={"name": "ID Format Test"})
        case_id = resp.get_json()["case"]["case_id"]
        assert case_id.startswith("case_"), f"case_id should start with 'case_', got: {case_id}"

    def test_case_status_default_active(self, client):
        resp = client.post("/api/cases", json={"name": "Status Test"})
        assert resp.get_json()["case"]["status"] == "active"

    def test_case_is_demo_false_by_default(self, client):
        resp = client.post("/api/cases", json={"name": "Demo Flag Test"})
        assert resp.get_json()["case"]["is_demo"] == 0

    def test_missing_name_returns_400(self, client):
        resp = client.post("/api/cases", json={}, content_type="application/json")
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_empty_name_returns_400(self, client):
        resp = client.post("/api/cases", json={"name": "   "})
        assert resp.status_code == 400

    def test_no_json_body_returns_400(self, client):
        resp = client.post("/api/cases", data="not json", content_type="text/plain")
        assert resp.status_code == 400

    def test_description_optional(self, client):
        resp = client.post("/api/cases", json={"name": "No Desc"})
        assert resp.status_code == 201

    def test_multiple_cases_unique_ids(self, client):
        ids = set()
        for i in range(5):
            resp = client.post("/api/cases", json={"name": f"Case {i}"})
            ids.add(resp.get_json()["case"]["case_id"])
        assert len(ids) == 5, "Expected 5 unique case IDs"


class TestListCases:
    """GET /api/cases"""

    def test_list_returns_200(self, client):
        resp = client.get("/api/cases")
        assert resp.status_code == 200

    def test_list_structure(self, client):
        data = client.get("/api/cases").get_json()
        assert "cases" in data
        assert "count" in data

    def test_list_count_matches(self, client):
        data = client.get("/api/cases").get_json()
        assert data["count"] == len(data["cases"])

    def test_created_case_appears_in_list(self, client):
        client.post("/api/cases", json={"name": "Listed Case"})
        cases = client.get("/api/cases").get_json()["cases"]
        names = [c["name"] for c in cases]
        assert "Listed Case" in names


class TestGetCase:
    """GET /api/cases/<case_id>"""

    def test_get_existing_case(self, client, case_id):
        resp = client.get(f"/api/cases/{case_id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "case" in data
        assert data["case"]["case_id"] == case_id

    def test_get_nonexistent_case_returns_404(self, client):
        resp = client.get("/api/cases/does_not_exist_xyz")
        assert resp.status_code == 404
        assert "error" in resp.get_json()
