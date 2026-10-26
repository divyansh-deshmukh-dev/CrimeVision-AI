"""
services/provider_manager.py — Centralized Inference Provider Routing for CrimeVision AI.

Coordinates selection between:
  1. Local PyTorch Models:
     - RT-DETR (PekingU/rtdetr_r50vd)
     - CLIP (openai/clip-vit-base-patch32)
     - BLIP (Salesforce/blip-image-captioning-base)
     - Whisper (openai/whisper-base)
     - OpenCV Video Temporal
  2. Zero-Budget Cloud Hosted APIs (Render Free 512MB RAM target):
     - Audio: Groq Cloud Hosted Whisper (whisper-large-v3-turbo)
     - Image Vision: Google Gemini Vision API (gemini-2.0-flash)
     - Video Temporal: OpenCV Frame Sampling + Batched Gemini Vision API

Routing Modes:
  - 'cloud': Forces cloud API execution.
  - 'local': Forces local PyTorch execution.
  - 'auto' (default): Automatically selects 'cloud' if API keys are configured or if host
    memory is constrained (< 1500MB / Render container); otherwise defaults to 'local'.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from services.hardware_utils import get_system_memory_mb

logger = logging.getLogger(__name__)


def get_inference_provider(modality: str = "audio") -> str:
    """Resolve active inference provider ('cloud' or 'local') for the specified modality.

    Args:
        modality: One of 'audio', 'image', 'video'.

    Returns:
        'cloud' or 'local'
    """
    raw_mode = os.getenv("INFERENCE_PROVIDER")
    if not raw_mode and os.getenv("AI_PROVIDER", "").strip().lower() in ("cloud", "remote", "api"):
        configured_mode = "cloud"
    else:
        configured_mode = (raw_mode or "auto").strip().lower()

    if configured_mode in ("cloud", "remote", "api"):
        return "cloud"
    if configured_mode in ("local", "pytorch", "offline"):
        return "local"

    # 'auto' mode evaluation:
    # 1. Check Render cloud environment or constrained host memory
    is_render = bool(os.getenv("RENDER") or os.getenv("RENDER_SERVICE_ID"))
    mem_mb = get_system_memory_mb()

    # Audio Whisper requires >= 800MB RAM; Vision RT-DETR/BLIP requires >= 1500MB RAM
    min_required_ram = 800 if modality == "audio" else 1500

    if is_render or (mem_mb is not None and mem_mb < min_required_ram):
        # On constrained cloud environments (such as Render Free 512MB), route to cloud
        # to prevent catastrophic uncatchable container SIGKILL OOM terminations.
        return "cloud"

    # 2. On standard workstations with ample RAM, default to local models
    # to preserve zero-network offline execution and local PyTorch fidelity.
    return "local"


def get_provider_details(modality: str = "audio") -> Dict[str, Any]:
    """Return descriptive status of the active inference provider for diagnostics and telemetry."""
    provider_mode = get_inference_provider(modality)

    if modality == "audio":
        if provider_mode == "cloud":
            model = (
                os.getenv("GROQ_WHISPER_MODEL")
                or (
                    os.getenv("WHISPER_MODEL_NAME")
                    if os.getenv("WHISPER_MODEL_NAME", "").strip().startswith("whisper-")
                    else None
                )
                or "whisper-large-v3-turbo"
            )
            has_key = bool(os.getenv("GROQ_API_KEY", "").strip())
            return {
                "mode": "cloud",
                "provider": "groq",
                "model": model,
                "api_key_configured": has_key,
                "description": f"Groq Cloud Hosted Whisper ({model})",
            }
        else:
            model = os.getenv("WHISPER_MODEL_NAME", "openai/whisper-base")
            return {
                "mode": "local",
                "provider": "local_whisper",
                "model": model,
                "api_key_configured": True,
                "description": f"Local PyTorch Transformers Whisper ({model})",
            }

    elif modality == "image":
        if provider_mode == "cloud":
            model = os.getenv("GEMINI_VISION_MODEL") or os.getenv("GEMINI_MODEL") or "gemini-2.0-flash"
            has_key = bool(os.getenv("GEMINI_API_KEY", "").strip())
            return {
                "mode": "cloud",
                "provider": "gemini",
                "model": model,
                "api_key_configured": has_key,
                "description": f"Google Gemini 2.0 Flash Vision ({model})",
            }
        else:
            return {
                "mode": "local",
                "provider": "local_rtdetr_blip",
                "model": "RT-DETR + BLIP + CLIP",
                "api_key_configured": True,
                "description": "Local PyTorch RT-DETR + BLIP + CLIP",
            }

    elif modality == "video":
        if provider_mode == "cloud":
            model = os.getenv("GEMINI_VISION_MODEL") or os.getenv("GEMINI_MODEL") or "gemini-2.0-flash"
            has_key = bool(os.getenv("GEMINI_API_KEY", "").strip())
            return {
                "mode": "cloud",
                "provider": "gemini",
                "model": model,
                "api_key_configured": has_key,
                "description": f"OpenCV Frame Extraction + Gemini Vision ({model})",
            }
        else:
            return {
                "mode": "local",
                "provider": "local_opencv_rtdetr",
                "model": "OpenCV + RT-DETR",
                "api_key_configured": True,
                "description": "Local OpenCV + PyTorch RT-DETR",
            }

    return {"mode": provider_mode, "provider": "unknown"}
