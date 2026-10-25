"""
tests/test_chat_assistant.py — Test suite for Phase 7 AI Chat Assistant.

Covers:
  - Evidence retrieval context builder (image, audio, video, fusion)
  - Forensic neutrality & prompt constraints
  - Structured response parsing (JSON, markdown code blocks, fallbacks)
  - Missing API key detection & graceful 503 handling
  - Mocked Gemini generation and exact confidence preservation
  - REST endpoints: POST /chat, GET /history, DELETE /history
  - Validation: 404 nonexistent cases, empty query, query > 1000 chars
  - Multi-case chat isolation & history integrity
"""

import json
from unittest.mock import MagicMock, patch
import pytest

from services.chat_assistant import (
    ChatAssistant,
    APIKeyMissingError,
    build_evidence_context,
    _extract_json_response,
    SYSTEM_INSTRUCTION,
)
from storage.chat_store import (
    save_message,
    list_messages,
    clear_messages,
)


# ── Fixtures & Mock Data ──────────────────────────────────────────────────────

@pytest.fixture
def sample_case():
    return {
        "case_id": "case_test_001",
        "name": "Warehouse Intrusion Investigation",
        "description": "Investigating unauthorized entry at sector 4.",
        "created_at": "2026-10-18T10:00:00Z",
    }


@pytest.fixture
def sample_multimodal_evidence():
    return [
        {
            "evidence_id": "ev_img_101",
            "original_name": "surveillance_frame_01.jpg",
            "modality": "image",
            "file_size": 204800,
            "sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "analysis_status": "completed",
            "analysis_json": {
                "rtdetr": {
                    "detections": [
                        {"label": "person", "confidence": 0.94, "bbox": [100, 150, 300, 450]},
                        {"label": "knife", "confidence": 0.81, "bbox": [210, 320, 260, 390]},
                    ]
                },
                "blip": {
                    "caption": "a person holding a sharp object near a doorway"
                },
                "clip": {
                    "similarities": [
                        {"query": "armed trespasser", "score": 0.88},
                        {"query": "warehouse interior", "score": 0.92},
                    ]
                },
            },
        },
        {
            "evidence_id": "ev_aud_102",
            "original_name": "radio_dispatch.wav",
            "modality": "audio",
            "file_size": 512000,
            "sha256": "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            "analysis_status": "completed",
            "analysis_json": {
                "duration": 18.5,
                "language": "en",
                "transcript": "Subject sighted at rear exit carrying a metallic object.",
                "segments": [
                    {"start": 0.0, "end": 4.2, "text": "Dispatch this is unit 4."},
                    {"start": 4.5, "end": 9.8, "text": "Subject sighted at rear exit carrying a metallic object."},
                ],
            },
        },
        {
            "evidence_id": "ev_vid_103",
            "original_name": "parking_cam.mp4",
            "modality": "video",
            "file_size": 5242880,
            "sha256": "fedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321",
            "analysis_status": "completed",
            "analysis_json": {
                "video_metadata": {
                    "duration": 30.0,
                    "fps": 25.0,
                    "width": 1920,
                    "height": 1080,
                    "total_frames": 750,
                    "sampled_frames_count": 3,
                },
                "sampled_frames": [
                    {
                        "timestamp_seconds": 2.0,
                        "frame_index": 50,
                        "status": "completed",
                        "detections": [{"label": "person", "confidence": 0.89, "bbox": [50, 50, 150, 250]}],
                    },
                    {
                        "timestamp_seconds": 6.0,
                        "frame_index": 150,
                        "status": "completed",
                        "detections": [
                            {"label": "person", "confidence": 0.91, "bbox": [60, 60, 160, 260]},
                            {"label": "knife", "confidence": 0.77, "bbox": [110, 140, 140, 190]},
                        ],
                    },
                ],
            },
        },
    ]


# ── Context Builder & Forensic Neutrality Tests ───────────────────────────────

def test_forensic_neutrality_instruction():
    """Verify system instructions enforce forensic neutrality and citation requirements."""
    assert "STRICT IMPARTIALITY" in SYSTEM_INSTRUCTION
    assert "guilt, innocence, motive, intent" in SYSTEM_INSTRUCTION
    assert "PRESERVE CONFIDENCE METRICS" in SYSTEM_INSTRUCTION
    assert "CITATION REQUIREMENT" in SYSTEM_INSTRUCTION
    assert "supporting_evidence" in SYSTEM_INSTRUCTION
    assert "limitations" in SYSTEM_INSTRUCTION
    assert "insufficient_evidence" in SYSTEM_INSTRUCTION


def test_build_evidence_context_empty(sample_case):
    """Context builder should gracefully handle an empty evidence repository."""
    ctx = build_evidence_context(sample_case, [])
    assert "Case ID: case_test_001" in ctx
    assert "Warehouse Intrusion Investigation" in ctx
    assert "No evidence items have been uploaded" in ctx


def test_build_evidence_context_multimodal(sample_case, sample_multimodal_evidence):
    """Context builder should serialize image, audio, video, and fusion details."""
    fusion_mock = {
        "synthesis": {
            "overall_consistency": "Consistent",
            "corroborated_entities": ["person", "knife"],
        },
        "corroborations": [
            {
                "entity": "knife",
                "evidence_ids": ["ev_img_101", "ev_vid_103"],
                "description": "Bladed weapon detected in image and video frame @ 6.0s.",
            }
        ],
        "contradictions": [],
    }

    ctx = build_evidence_context(
        case=sample_case,
        evidence_items=sample_multimodal_evidence,
        fusion_result=fusion_mock,
    )

    # Image details
    assert "ev_img_101" in ctx
    assert "person (confidence: 0.94" in ctx
    assert "knife (confidence: 0.81" in ctx
    assert "a person holding a sharp object" in ctx

    # Audio details
    assert "ev_aud_102" in ctx
    assert "Subject sighted at rear exit" in ctx
    assert "[4.5s - 9.8s]" in ctx

    # Video details
    assert "ev_vid_103" in ctx
    assert "@ 6.00s" in ctx
    assert "knife:0.77" in ctx

    # Fusion details
    assert "Corroborated Observations" in ctx
    assert "Bladed weapon detected" in ctx


# ── JSON Parser Tests ─────────────────────────────────────────────────────────

def test_extract_json_response_clean():
    payload = {
        "answer": "A person was detected in the surveillance frame.",
        "supporting_evidence": [{"evidence_id": "ev_001", "modality": "image", "timestamp_seconds": None, "observation": "person", "confidence": 0.95}],
        "limitations": ["Lighting was low."],
        "insufficient_evidence": False,
    }
    raw = json.dumps(payload)
    parsed = _extract_json_response(raw)
    assert parsed["answer"] == payload["answer"]
    assert len(parsed["supporting_evidence"]) == 1
    assert parsed["supporting_evidence"][0]["confidence"] == 0.95


def test_extract_json_response_markdown_codeblock():
    raw = """Here is the forensic evaluation:
```json
{
  "answer": "Detected knife in video [ev_103 @ 6.0s].",
  "supporting_evidence": [
    {
      "evidence_id": "ev_103",
      "modality": "video",
      "timestamp_seconds": 6.0,
      "observation": "Knife detected with 0.77 confidence",
      "confidence": 0.77
    }
  ],
  "limitations": [],
  "insufficient_evidence": false
}
```
Please let me know if you need more details.
"""
    parsed = _extract_json_response(raw)
    assert parsed["answer"] == "Detected knife in video [ev_103 @ 6.0s]."
    assert parsed["supporting_evidence"][0]["timestamp_seconds"] == 6.0
    assert parsed["supporting_evidence"][0]["confidence"] == 0.77


def test_extract_json_response_fallback():
    raw = "Plain text response without any JSON format."
    parsed = _extract_json_response(raw)
    assert parsed["answer"] == raw
    assert parsed["supporting_evidence"] == []
    assert len(parsed["limitations"]) > 0


# ── Chat Assistant Service Tests ──────────────────────────────────────────────

def test_chat_assistant_missing_api_key(sample_case):
    """Calling ask() with no API key and no mock client raises APIKeyMissingError."""
    with patch.dict("os.environ", {"GEMINI_API_KEY": ""}, clear=False):
        assistant = ChatAssistant(api_key=None, client=None, provider="gemini")
        with pytest.raises(APIKeyMissingError) as exc_info:
            assistant.ask("Was anyone detected?", sample_case, [])
        assert "GEMINI_API_KEY" in str(exc_info.value)


def test_chat_assistant_whitespace_key_treated_as_missing(sample_case):
    """Whitespace-only API key must be treated as missing."""
    with patch.dict("os.environ", {"GEMINI_API_KEY": "   "}, clear=False):
        assistant = ChatAssistant(api_key=None, client=None, provider="gemini")
        assert assistant.api_key is None
        with pytest.raises(APIKeyMissingError):
            assistant.ask("Was anyone detected?", sample_case, [])


def test_chat_assistant_loads_key_from_env(sample_case):
    """Verify that ChatAssistant picks up GEMINI_API_KEY from environment."""
    dummy_key = "test-dummy-key"
    with patch.dict("os.environ", {"GEMINI_API_KEY": dummy_key}, clear=False):
        assistant = ChatAssistant(api_key=None, client=None, provider="gemini")
        assert assistant.api_key == dummy_key


def test_chat_assistant_empty_query(sample_case):
    """Empty query returns structured insufficient_evidence without invoking client."""
    mock_client = MagicMock()
    assistant = ChatAssistant(api_key="fake-key", client=mock_client)
    res = assistant.ask("   ", sample_case, [])
    assert res["insufficient_evidence"] is True
    assert "No question provided" in res["answer"]
    mock_client.models.generate_content.assert_not_called()


def test_chat_assistant_mock_query_success(sample_case, sample_multimodal_evidence):
    """Test full query with mocked Gemini client returning valid structured response."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "answer": "A person was observed holding a knife at [ev_img_101] and [ev_vid_103 @ 6.0s].",
        "supporting_evidence": [
            {
                "evidence_id": "ev_img_101",
                "modality": "image",
                "timestamp_seconds": None,
                "observation": "Person detected (conf: 0.94), knife detected (conf: 0.81)",
                "confidence": 0.94,
            },
            {
                "evidence_id": "ev_vid_103",
                "modality": "video",
                "timestamp_seconds": 6.0,
                "observation": "Knife detected (conf: 0.77)",
                "confidence": 0.77,
            },
        ],
        "limitations": [
            "Facial identification cannot be confirmed due to distance.",
        ],
        "insufficient_evidence": False,
    })
    mock_client.models.generate_content.return_value = mock_response

    assistant = ChatAssistant(api_key="fake-key", client=mock_client, provider="gemini")
    res = assistant.ask(
        query="Was any weapon identified in the evidence?",
        case=sample_case,
        evidence_items=sample_multimodal_evidence,
    )

    assert "holding a knife" in res["answer"]
    assert len(res["supporting_evidence"]) == 2
    assert res["supporting_evidence"][0]["confidence"] == 0.94
    assert res["supporting_evidence"][1]["timestamp_seconds"] == 6.0
    assert res["insufficient_evidence"] is False
    assert len(res["limitations"]) == 1


# ── REST API Endpoints Integration Tests ──────────────────────────────────────

def test_chat_endpoint_missing_case(client):
    """POST /api/cases/<nonexistent>/chat returns 404."""
    resp = client.post(
        "/api/cases/nonexistent_case_999/chat",
        json={"query": "Any findings?"},
        content_type="application/json",
    )
    assert resp.status_code == 404
    assert "not found" in resp.get_json()["error"]


def test_chat_endpoint_validation(client, case_id):
    """Test validation errors for empty and oversized queries."""
    # Empty query
    resp = client.post(
        f"/api/cases/{case_id}/chat",
        json={"query": ""},
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert "empty" in resp.get_json()["error"]

    # Oversized query (> 1000 characters)
    resp = client.post(
        f"/api/cases/{case_id}/chat",
        json={"query": "A" * 1001},
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert "1000 characters" in resp.get_json()["error"]


def test_chat_endpoint_missing_api_key(client, case_id):
    """Without GEMINI_API_KEY, endpoint returns 503 with api_key_missing: true."""
    with patch.dict("os.environ", {"GEMINI_API_KEY": ""}, clear=False):
        resp = client.post(
            f"/api/cases/{case_id}/chat",
            json={"query": "Summarize the evidence."},
            content_type="application/json",
        )
        assert resp.status_code == 503
        data = resp.get_json()
        assert data.get("api_key_missing") is True
        assert "GEMINI_API_KEY" in data.get("error")


def test_chat_endpoint_success_and_persistence(client, case_id):
    """Successful chat query saves user query and assistant response in history."""
    mock_payload = {
        "answer": "Detected one person in surveillance footage [ev_001].",
        "supporting_evidence": [
            {
                "evidence_id": "ev_001",
                "modality": "image",
                "timestamp_seconds": None,
                "observation": "person",
                "confidence": 0.92,
            }
        ],
        "limitations": ["No facial recognition available."],
        "insufficient_evidence": False,
    }

    with patch.object(ChatAssistant, "ask", return_value=mock_payload):
        resp = client.post(
            f"/api/cases/{case_id}/chat",
            json={"query": "Is there a person identified?"},
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert data["case_id"] == case_id
        assert data["response"]["answer"] == mock_payload["answer"]
        assert "message_id" in data

        # Check history endpoint contains both user query and assistant response
        hist_resp = client.get(f"/api/cases/{case_id}/chat/history")
        assert hist_resp.status_code == 200
        hist_data = hist_resp.get_json()
        assert hist_data["count"] == 2
        msgs = hist_data["messages"]
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "Is there a person identified?"
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["content"] == mock_payload["answer"]
        assert msgs[1]["metadata"]["supporting_evidence"][0]["confidence"] == 0.92


def test_chat_history_clear(client, case_id):
    """Test DELETE /api/cases/<case_id>/chat/history clears all messages."""
    mock_payload = {
        "answer": "Sample response.",
        "supporting_evidence": [],
        "limitations": [],
        "insufficient_evidence": False,
    }
    with patch.object(ChatAssistant, "ask", return_value=mock_payload):
        client.post(
            f"/api/cases/{case_id}/chat",
            json={"query": "First query."},
            content_type="application/json",
        )
        client.post(
            f"/api/cases/{case_id}/chat",
            json={"query": "Second query."},
            content_type="application/json",
        )

    # Check history has 4 messages
    hist_resp = client.get(f"/api/cases/{case_id}/chat/history")
    assert hist_resp.get_json()["count"] == 4

    # Clear history
    del_resp = client.delete(f"/api/cases/{case_id}/chat/history")
    assert del_resp.status_code == 200
    assert del_resp.get_json()["status"] == "cleared"
    assert del_resp.get_json()["deleted_count"] == 4

    # Check history is now empty
    hist_resp2 = client.get(f"/api/cases/{case_id}/chat/history")
    assert hist_resp2.get_json()["count"] == 0


def test_chat_case_isolation(client):
    """Messages from Case A must not be visible or deleted from Case B."""
    # Create Case A
    resp_a = client.post("/api/cases", json={"name": "Case A"}, content_type="application/json")
    case_a_id = resp_a.get_json()["case"]["case_id"]

    # Create Case B
    resp_b = client.post("/api/cases", json={"name": "Case B"}, content_type="application/json")
    case_b_id = resp_b.get_json()["case"]["case_id"]

    mock_payload_a = {"answer": "Answer for Case A", "supporting_evidence": [], "limitations": [], "insufficient_evidence": False}
    mock_payload_b = {"answer": "Answer for Case B", "supporting_evidence": [], "limitations": [], "insufficient_evidence": False}

    # Post to Case A
    with patch.object(ChatAssistant, "ask", return_value=mock_payload_a):
        client.post(f"/api/cases/{case_a_id}/chat", json={"query": "Query A"}, content_type="application/json")

    # Post to Case B
    with patch.object(ChatAssistant, "ask", return_value=mock_payload_b):
        client.post(f"/api/cases/{case_b_id}/chat", json={"query": "Query B"}, content_type="application/json")

    # Verify Case A history
    hist_a = client.get(f"/api/cases/{case_a_id}/chat/history").get_json()
    assert hist_a["count"] == 2
    assert hist_a["messages"][0]["content"] == "Query A"

    # Verify Case B history
    hist_b = client.get(f"/api/cases/{case_b_id}/chat/history").get_json()
    assert hist_b["count"] == 2
    assert hist_b["messages"][0]["content"] == "Query B"

    # Clear Case A, verify Case B is untouched
    client.delete(f"/api/cases/{case_a_id}/chat/history")
    assert client.get(f"/api/cases/{case_a_id}/chat/history").get_json()["count"] == 0
    assert client.get(f"/api/cases/{case_b_id}/chat/history").get_json()["count"] == 2


def test_chat_assistant_offline_network_fallback(sample_case, sample_multimodal_evidence):
    """When external LLM network connection is unreachable, assistant falls back to local evidence synthesis."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = ConnectionError("[Errno 11001] getaddrinfo failed")

    assistant = ChatAssistant(api_key="valid-key", client=mock_client, provider="gemini")
    res = assistant.ask(
        query="What evidence is available in this case?",
        case=sample_case,
        evidence_items=sample_multimodal_evidence,
    )

    assert res["insufficient_evidence"] is False
    assert len(res["supporting_evidence"]) > 0
    assert any("offline or unreachable" in lim for lim in res["limitations"])
    assert "surveillance_frame_01.jpg" in res["answer"] or "radio_dispatch.wav" in res["answer"]
