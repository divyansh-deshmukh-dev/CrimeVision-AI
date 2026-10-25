"""
services/provenance.py — Structured Analysis Provenance & Execution Tracking for CrimeVision AI.

Provides rigorous, cryptographic tracking of all analysis executions across modalities,
distinguishing:
  - fresh_inference (neural network loaded and tensor forward pass executed)
  - in_memory_model_reuse (existing in-memory model session reused, e.g. multi-frame video)
  - persisted_result_reuse (cached/persisted database row returned without inference)
  - precomputed_demo_result (pre-seeded demo case artifact returned without inference)
  - external_api_generation (external LLM provider called, e.g. Gemini, Groq)
  - deterministic_fallback (heuristic / rule-based fallback used without AI model)

Never claims inference occurred merely because an HTTP endpoint returned 200.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import time
from typing import Any, Dict, List, Optional
import uuid


class ResultSource(str, Enum):
    FRESH_INFERENCE = "fresh_inference"
    IN_MEMORY_MODEL_REUSE = "in_memory_model_reuse"
    PERSISTED_RESULT_REUSE = "persisted_result_reuse"
    PRECOMPUTED_DEMO_RESULT = "precomputed_demo_result"
    EXTERNAL_API_GENERATION = "external_api_generation"
    DETERMINISTIC_FALLBACK = "deterministic_fallback"


def generate_run_id(prefix: str = "run") -> str:
    """Generate a unique run ID for an analysis attempt."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def current_iso_timestamp() -> str:
    """Return current UTC time in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def build_provenance_record(
    modality: str,
    result_source: str | ResultSource,
    execution_status: str,
    evidence_id: Optional[str] = None,
    case_id: Optional[str] = None,
    input_sha256: Optional[str] = None,
    run_id: Optional[str] = None,
    requested_at: Optional[str] = None,
    completed_at: Optional[str] = None,
    duration_ms: Optional[float] = None,
    model_init_duration_ms: Optional[float] = None,
    inference_duration_ms: Optional[float] = None,
    models: Optional[List[Dict[str, Any]]] = None,
    submodel_statuses: Optional[Dict[str, str]] = None,
    provider: Optional[str] = None,
    is_demo: bool = False,
    diagnostic_details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Construct a comprehensive, tamper-evident provenance record.

    Guarantees that:
      - result_source is explicitly specified.
      - model_init_duration_ms is distinguished from inference_duration_ms.
      - submodel_statuses record individual submodel states (e.g. rtdetr, clip, blip).
    """
    if isinstance(result_source, ResultSource):
        source_val = result_source.value
    else:
        source_val = str(result_source)

    now_iso = current_iso_timestamp()
    rec: Dict[str, Any] = {
        "analysis_run_id": run_id or generate_run_id(),
        "evidence_id": evidence_id,
        "case_id": case_id,
        "input_sha256": input_sha256,
        "modality": modality,
        "requested_at": requested_at or now_iso,
        "completed_at": completed_at or now_iso,
        "duration_ms": round(float(duration_ms), 2) if duration_ms is not None else 0.0,
        "model_init_duration_ms": round(float(model_init_duration_ms), 2) if model_init_duration_ms is not None else 0.0,
        "inference_duration_ms": round(float(inference_duration_ms), 2) if inference_duration_ms is not None else 0.0,
        "result_source": source_val,
        "execution_status": execution_status,
        "is_demo": bool(is_demo),
        "models": models or [],
        "submodel_statuses": submodel_statuses or {},
    }

    if provider:
        rec["provider"] = provider

    if diagnostic_details:
        rec["diagnostic_details"] = diagnostic_details

    return rec
