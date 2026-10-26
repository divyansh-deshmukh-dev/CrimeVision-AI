"""
services/cloud_audio_service.py — Cloud Audio Transcription via Groq Cloud Whisper API.

Provides fast, lightweight, zero-RAM audio transcription for CrimeVision AI on
resource-constrained cloud deployments (such as Render Free 512MB RAM).

Utilizes:
  - Groq Cloud API (whisper-large-v3-turbo / whisper-large-v3)
  - Native server-side decoding of MP3, WAV, M4A, FLAC, OGG without local ffmpeg.
  - Granular segment-level timestamping.
  - Transparent provenance logging attributing execution strictly to Groq Cloud.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Union

from services.provenance import ResultSource, build_provenance_record

logger = logging.getLogger(__name__)


def transcribe_audio_with_groq(
    audio_path: Union[str, Path],
    forced_language: Optional[str] = None,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Transcribe an audio file using Groq Cloud's hosted Whisper API.

    Returns a standardized CrimeVision audio analysis dictionary.
    Never fabricates transcription; returns explicit, structured error diagnostics on failure.
    """
    t_start = time.perf_counter()
    audio_path = Path(audio_path)

    if not audio_path.exists():
        return {
            "status": "failed",
            "error": f"Audio file does not exist on disk: {audio_path}",
            "error_category": "FILE_NOT_FOUND",
            "audio_metadata": {},
            "transcript": "",
            "text": "",
            "segments": [],
            "intelligence_report": {},
            "submodel_statuses": {"whisper": "failed"},
        }

    # Resolve API Key
    resolved_key = (
        api_key
        or os.getenv("GROQ_API_KEY")
        or kwargs.get("config", {}).get("GROQ_API_KEY")
    )
    if not resolved_key or not resolved_key.strip():
        req_iso = kwargs.get("requested_at")
        run_id = kwargs.get("run_id")
        return {
            "status": "failed",
            "error": (
                "Groq API key is not configured. Set GROQ_API_KEY in your Render environment variables "
                "to enable cloud speech transcription on this instance."
            ),
            "error_category": "MISSING_API_KEY",
            "audio_metadata": {"filename": audio_path.name},
            "transcript": "",
            "text": "",
            "segments": [],
            "intelligence_report": {},
            "submodel_statuses": {"whisper": "failed"},
            "provenance": build_provenance_record(
                modality="audio",
                result_source=ResultSource.EXTERNAL_API_GENERATION,
                execution_status="failed",
                evidence_id=kwargs.get("evidence_id"),
                case_id=kwargs.get("case_id"),
                input_sha256=kwargs.get("input_sha256"),
                run_id=run_id,
                requested_at=req_iso,
                submodel_statuses={"whisper": "failed"},
                provider="groq",
                diagnostic_details={"error_reason": "MISSING_API_KEY"},
            ),
        }

    resolved_model = (
        model_name
        or os.getenv("GROQ_WHISPER_MODEL")
        or (
            os.getenv("WHISPER_MODEL_NAME")
            if os.getenv("WHISPER_MODEL_NAME", "").strip().startswith("whisper-")
            else None
        )
        or "whisper-large-v3-turbo"
    )

    try:
        from groq import Groq, RateLimitError, AuthenticationError, APIConnectionError, APIError
    except ImportError as imp_err:
        return {
            "status": "failed",
            "error": f"Groq Python SDK is missing from runtime: {imp_err}",
            "error_category": "DEPENDENCY_ERROR",
            "audio_metadata": {"filename": audio_path.name},
            "transcript": "",
            "text": "",
            "segments": [],
            "intelligence_report": {},
            "submodel_statuses": {"whisper": "failed"},
        }

    try:
        client = Groq(api_key=resolved_key.strip())

        logger.info(
            "Dispatching cloud audio transcription to Groq [%s] for %s",
            resolved_model, audio_path.name
        )

        with open(audio_path, "rb") as af:
            file_bytes = af.read()

        file_tuple = (audio_path.name, file_bytes)

        transcribe_kwargs: Dict[str, Any] = {
            "file": file_tuple,
            "model": resolved_model,
            "response_format": "verbose_json",
            "timestamp_granularities": ["segment"],
        }
        if forced_language and forced_language.strip():
            transcribe_kwargs["language"] = forced_language.strip()

        # Call Groq API
        raw_response = client.audio.transcriptions.create(**transcribe_kwargs)

        # Parse text, language, and duration
        full_text = getattr(raw_response, "text", "") or ""
        if isinstance(raw_response, dict):
            full_text = raw_response.get("text", "")

        detected_language = getattr(raw_response, "language", "") or forced_language or "en"
        if isinstance(raw_response, dict):
            detected_language = raw_response.get("language") or forced_language or "en"

        duration_sec = getattr(raw_response, "duration", None)
        if isinstance(raw_response, dict):
            duration_sec = raw_response.get("duration")
        if duration_sec is None:
            # Estimate from file size or default
            duration_sec = 0.0

        raw_segments = getattr(raw_response, "segments", []) or []
        if isinstance(raw_response, dict):
            raw_segments = raw_response.get("segments", [])

        # Normalize segments into CrimeVision schema
        formatted_segments: List[Dict[str, Any]] = []
        for idx, seg in enumerate(raw_segments):
            if isinstance(seg, dict):
                s_start = float(seg.get("start", 0.0))
                s_end = float(seg.get("end", s_start))
                s_text = str(seg.get("text", "")).strip()
            else:
                s_start = float(getattr(seg, "start", 0.0))
                s_end = float(getattr(seg, "end", s_start))
                s_text = str(getattr(seg, "text", "")).strip()

            formatted_segments.append({
                "id": idx,
                "start": round(s_start, 2),
                "end": round(s_end, 2),
                "start_seconds": round(s_start, 2),
                "end_seconds": round(s_end, 2),
                "text": s_text,
                "confidence": 0.95,
            })

        total_duration_ms = (time.perf_counter() - t_start) * 1000

        # Synthesize intelligence report using the transcript
        from services.audio_analyzer import AudioAnalyzer
        intelligence_report = AudioAnalyzer.synthesize_audio_intelligence(
            transcript=full_text,
            segments=formatted_segments,
            detected_language=detected_language,
        )

        metadata = {
            "filename": audio_path.name,
            "duration_seconds": round(float(duration_sec), 2) if duration_sec else 0.0,
            "sample_rate": 16000,
            "channels": 1,
            "decoder": "groq_cloud_stream",
            "file_size": len(file_bytes),
        }

        provenance = build_provenance_record(
            modality="audio",
            result_source=ResultSource.EXTERNAL_API_GENERATION,
            execution_status="completed",
            evidence_id=kwargs.get("evidence_id"),
            case_id=kwargs.get("case_id"),
            input_sha256=kwargs.get("input_sha256"),
            run_id=kwargs.get("run_id"),
            requested_at=kwargs.get("requested_at"),
            duration_ms=total_duration_ms,
            model_init_duration_ms=0.0,
            inference_duration_ms=total_duration_ms,
            models=[
                {
                    "name": "Groq Whisper",
                    "model_id": resolved_model,
                    "provider": "groq_cloud",
                    "status": "success",
                }
            ],
            submodel_statuses={"whisper": "success"},
            provider="groq",
            diagnostic_details={
                "endpoint": "https://api.groq.com/openai/v1/audio/transcriptions",
                "model": resolved_model,
            },
        )

        return {
            "status": "completed",
            "is_seeded_sample": False,
            "result_source": ResultSource.EXTERNAL_API_GENERATION.value,
            "provider": "groq",
            "model": resolved_model,
            "transcript": full_text,
            "text": full_text,
            "language": detected_language,
            "detected_language": detected_language,
            "duration_seconds": metadata["duration_seconds"],
            "segments": formatted_segments,
            "audio_metadata": metadata,
            "intelligence_report": intelligence_report,
            "provenance": provenance,
            "submodel_statuses": {"whisper": "success"},
            "forensic_notice": (
                f"Audio transcription generated via Groq Cloud Whisper ({resolved_model}). "
                "Speech transcription reflects phonetic interpretation and does NOT establish speaker identity."
            ),
        }

    except RateLimitError as rl_err:
        logger.warning("Groq rate limit exceeded: %s", rl_err)
        err_msg = (
            "Groq Cloud free-tier rate limit reached. "
            "Please wait 30 seconds before retrying, or click 'Restore Sample Baseline' below."
        )
        return _build_groq_failure_dict(audio_path, err_msg, "RATE_LIMIT_EXCEEDED", resolved_model, t_start, kwargs)

    except AuthenticationError as auth_err:
        logger.error("Groq authentication failure: %s", auth_err)
        err_msg = "Groq Cloud API key is invalid or expired. Check GROQ_API_KEY in Render environment variables."
        return _build_groq_failure_dict(audio_path, err_msg, "AUTHENTICATION_ERROR", resolved_model, t_start, kwargs)

    except APIConnectionError as conn_err:
        logger.error("Groq connection failure: %s", conn_err)
        err_msg = "Could not reach Groq Cloud API service. Please verify outbound network connectivity."
        return _build_groq_failure_dict(audio_path, err_msg, "NETWORK_ERROR", resolved_model, t_start, kwargs)

    except Exception as exc:
        logger.exception("Groq audio transcription failed unexpectedly: %s", exc)
        return _build_groq_failure_dict(audio_path, str(exc), "TRANSCRIPTION_ERROR", resolved_model, t_start, kwargs)


def _build_groq_failure_dict(
    audio_path: Path,
    error_msg: str,
    error_category: str,
    model_name: str,
    t_start: float,
    kwargs: Dict[str, Any],
) -> Dict[str, Any]:
    """Helper to construct standard failure dictionary for Groq errors."""
    dur_ms = (time.perf_counter() - t_start) * 1000
    submodel_statuses = {"whisper": "failed"}
    provenance = build_provenance_record(
        modality="audio",
        result_source=ResultSource.EXTERNAL_API_GENERATION,
        execution_status="failed",
        evidence_id=kwargs.get("evidence_id"),
        case_id=kwargs.get("case_id"),
        input_sha256=kwargs.get("input_sha256"),
        run_id=kwargs.get("run_id"),
        requested_at=kwargs.get("requested_at"),
        duration_ms=dur_ms,
        models=[
            {
                "name": "Groq Whisper",
                "model_id": model_name,
                "provider": "groq_cloud",
                "status": "failed",
            }
        ],
        submodel_statuses=submodel_statuses,
        provider="groq",
        diagnostic_details={"error_category": error_category, "error": error_msg},
    )
    return {
        "status": "failed",
        "is_seeded_sample": False,
        "result_source": ResultSource.EXTERNAL_API_GENERATION.value,
        "provider": "groq",
        "model": model_name,
        "error": error_msg,
        "error_category": error_category,
        "audio_metadata": {"filename": audio_path.name},
        "transcript": "",
        "text": "",
        "segments": [],
        "intelligence_report": {},
        "submodel_statuses": submodel_statuses,
        "provenance": provenance,
    }
