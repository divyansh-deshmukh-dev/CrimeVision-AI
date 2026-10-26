"""
services/audio_analyzer.py — Multilingual Audio Transcription Engine for CrimeVision AI (Phase 4).

Integrates:
  1. OpenAI Whisper (openai/whisper-base) via Hugging Face Transformers.
  2. Audio loading, decoding, and 16kHz resampling via soundfile / librosa / ffmpeg.
  3. Timestamped segment extraction and language identification.

Resource & Safety Principles:
  - Executes sequentially under torch.no_grad() with CPU thread limits.
  - Transparent failure reporting: returns explicit diagnostics if weights or codecs fail,
    never fabricated transcripts.
  - Discloses that speech transcription does not prove speaker identity or statement truth.
"""

import gc
import json
import logging
import os
from pathlib import Path
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from services.provenance import ResultSource, build_provenance_record

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)

# Global thread-safe in-memory Whisper model cache
_WHISPER_LOCK = threading.Lock()
_INFERENCE_LOCK = threading.Lock()
_CACHED_WHISPER_PROCESSOR: Any = None
_CACHED_WHISPER_MODEL: Any = None
_CACHED_WHISPER_MODEL_ID: Optional[str] = None

# Audio duration safety bounds for synchronous inference
MAX_AUDIO_CHUNK_SECONDS: float = 30.0
MAX_SUPPORTED_AUDIO_SECONDS: float = 180.0  # 3 minutes max for CPU stability


def get_cached_whisper(
    model_id: str = "openai/whisper-base",
    device: str = "cpu",
) -> Tuple[Any, Any, bool]:
    """Retrieve or load cached Whisper model and processor thread-safely.

    Returns (processor, model, was_cached).
    """
    global _CACHED_WHISPER_PROCESSOR, _CACHED_WHISPER_MODEL, _CACHED_WHISPER_MODEL_ID
    with _WHISPER_LOCK:
        if (
            _CACHED_WHISPER_MODEL is not None
            and _CACHED_WHISPER_PROCESSOR is not None
            and _CACHED_WHISPER_MODEL_ID == model_id
        ):
            return _CACHED_WHISPER_PROCESSOR, _CACHED_WHISPER_MODEL, True

        from transformers import WhisperForConditionalGeneration, WhisperProcessor

        logger.info("Initializing in-memory Whisper model session: %s on %s", model_id, device)
        processor = _load_hf_component(WhisperProcessor, model_id)
        model = _load_hf_component(WhisperForConditionalGeneration, model_id)
        if hasattr(model, "to"):
            model.to(device)
        if hasattr(model, "eval"):
            model.eval()

        _CACHED_WHISPER_PROCESSOR = processor
        _CACHED_WHISPER_MODEL = model
        _CACHED_WHISPER_MODEL_ID = model_id
        return processor, model, False


def clear_whisper_cache() -> None:
    """Clear cached Whisper model and release memory."""
    global _CACHED_WHISPER_PROCESSOR, _CACHED_WHISPER_MODEL, _CACHED_WHISPER_MODEL_ID
    with _WHISPER_LOCK:
        _CACHED_WHISPER_PROCESSOR = None
        _CACHED_WHISPER_MODEL = None
        _CACHED_WHISPER_MODEL_ID = None
        gc.collect()


def _load_hf_component(cls: Any, model_id: str, **kwargs: Any) -> Any:
    """Load a HuggingFace model or processor preferring cached local files.

    If local_files_only raises (e.g. weights not yet downloaded), falls back to
    standard Hub download.
    """
    try:
        return cls.from_pretrained(model_id, local_files_only=True, **kwargs)
    except Exception:
        return cls.from_pretrained(model_id, **kwargs)


class AudioAnalyzer:
    """Sequential CPU-friendly audio transcription engine using Whisper."""

    def __init__(
        self,
        whisper_model_id: str = "openai/whisper-base",
    ):
        self.whisper_model_id = whisper_model_id
        self.device = "cuda" if (torch and torch.cuda.is_available()) else "cpu"

    def _setup_torch_runtime(self) -> None:
        """Configures optimal PyTorch CPU threads without exhausting CPU."""
        if torch and self.device == "cpu":
            try:
                num_cores = os.cpu_count() or 4
                target_threads = max(2, min(6, num_cores - 2 if num_cores > 4 else num_cores))
                torch.set_num_threads(target_threads)
            except Exception:
                pass

    @staticmethod
    def load_and_resample_audio(audio_path: Union[str, Path], target_sr: int = 16000):
        """Decode and resample audio file to target_sr mono float32 array.

        Prioritizes fast direct decoding via ffmpeg, with soundfile and librosa fallbacks.
        Returns (waveform, sample_rate, metadata_dict).
        Raises FileNotFoundError if file is missing.
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # 1. Fast direct decode and resample via ffmpeg pipe (supports MP3, AAC, WAV, OGG, FLAC)
        try:
            import subprocess
            cmd = [
                "ffmpeg", "-nostdin", "-threads", "2",
                "-i", str(audio_path),
                "-f", "s16le", "-ac", "1", "-acodec", "pcm_s16le",
                "-ar", str(target_sr), "-"
            ]
            out = subprocess.run(cmd, capture_output=True, check=True)
            if out.stdout:
                waveform = np.frombuffer(out.stdout, np.int16).flatten().astype(np.float32) / 32768.0
                duration_sec = round(len(waveform) / target_sr, 2)
                meta = {
                    "original_sample_rate": "auto",
                    "target_sample_rate": target_sr,
                    "channels": 1,
                    "duration_seconds": duration_sec,
                    "decoder": "ffmpeg_stream",
                }
                return waveform, target_sr, meta
        except Exception as ffmpeg_exc:
            logger.debug("ffmpeg direct decode failed on %s (%s), falling back to soundfile/librosa", audio_path, ffmpeg_exc)

        # 2. Try soundfile
        try:
            import soundfile as sf
            import librosa
            waveform, sample_rate = sf.read(str(audio_path), dtype="float32")
            orig_sr = sample_rate
            if waveform.ndim > 1:
                waveform = np.mean(waveform, axis=1)
            if sample_rate != target_sr:
                waveform = librosa.resample(waveform, orig_sr=sample_rate, target_sr=target_sr)
            duration_sec = round(len(waveform) / target_sr, 2)
            meta = {
                "original_sample_rate": orig_sr,
                "target_sample_rate": target_sr,
                "channels": 1,
                "duration_seconds": duration_sec,
                "decoder": "soundfile",
            }
            return waveform, target_sr, meta
        except Exception as sf_exc:
            logger.debug("soundfile failed to read %s (%s), trying librosa", audio_path, sf_exc)

        # 3. Try librosa
        try:
            import librosa
            try:
                orig_sr = librosa.get_samplerate(str(audio_path))
            except Exception:
                orig_sr = target_sr
            waveform, sample_rate = librosa.load(str(audio_path), sr=target_sr, mono=True)
            duration_sec = round(len(waveform) / target_sr, 2)
            meta = {
                "original_sample_rate": orig_sr,
                "target_sample_rate": target_sr,
                "channels": 1,
                "duration_seconds": duration_sec,
                "decoder": "librosa",
            }
            return waveform, target_sr, meta
        except Exception as librosa_exc:
            raise ValueError(f"All audio decoders failed to decode audio stream for {audio_path.name}: {librosa_exc}") from librosa_exc

    def load_audio_waveform(self, audio_path: Union[str, Path], target_sr: int = 16000) -> Dict[str, Any]:
        """Decode audio file into a 16kHz mono float32 numpy array."""
        try:
            audio_path = Path(audio_path)
            waveform, sr, meta = self.load_and_resample_audio(audio_path, target_sr=target_sr)
            return {
                "status": "success",
                "waveform": waveform,
                "sample_rate": sr,
                "duration_seconds": meta["duration_seconds"],
                "audio_metadata": meta,
            }
        except Exception as exc:
            logger.warning("Audio decoding failed: %s", exc)
            return {
                "status": "failed",
                "error": str(exc),
                "waveform": None,
                "sample_rate": target_sr,
                "duration_seconds": 0.0,
                "audio_metadata": {},
            }


    def _load_audio_via_ffmpeg(self, audio_path: Path, target_sr: int = 16000) -> Dict[str, Any]:
        """Fallback decoder using ffmpeg command line."""
        import subprocess

        cmd = [
            "ffmpeg",
            "-nostdin",
            "-threads", "0",
            "-i", str(audio_path),
            "-f", "s16le",
            "-ac", "1",
            "-acodec", "pcm_s16le",
            "-ar", str(target_sr),
            "-"
        ]
        try:
            out = subprocess.run(cmd, capture_output=True, check=True)
            waveform = np.frombuffer(out.stdout, np.int16).flatten().astype(np.float32) / 32768.0
            duration_sec = round(len(waveform) / target_sr, 2)
            return {
                "status": "success",
                "waveform": waveform,
                "sample_rate": target_sr,
                "duration_seconds": duration_sec,
            }
        except Exception as exc:
            logger.exception("ffmpeg audio decode failed")
            return {
                "status": "error",
                "error": f"Failed to decode audio stream: {exc}",
            }

    def transcribe_audio_pipeline(
        self,
        audio_path: Union[str, Path],
        forced_language: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute full Whisper transcription pipeline on audio evidence."""
        t_start = time.perf_counter()
        audio_path = Path(audio_path)
        if not audio_path.exists():
            return {
                "status": "failed",
                "error": f"Audio file does not exist on disk: {audio_path}",
                "audio_metadata": {},
                "transcript": "",
                "text": "",
                "segments": [],
            }

        # Route to Cloud Audio Provider (Groq Whisper) when selected or in cloud mode
        from services.provider_manager import get_inference_provider
        active_provider = kwargs.get("provider") or get_inference_provider("audio")
        if active_provider == "cloud":
            from services.cloud_audio_service import transcribe_audio_with_groq
            return transcribe_audio_with_groq(
                audio_path=audio_path,
                forced_language=forced_language,
                **kwargs,
            )

        # Pre-flight host resource check: prevent uncatchable container SIGKILL OOM
        from services.hardware_utils import is_inference_memory_sufficient
        mem_ok, actual_mb, mem_msg = is_inference_memory_sufficient(min_mb=800, model_name="OpenAI Whisper")
        if not mem_ok:
            submodel_statuses = {"whisper": "failed"}
            provenance = build_provenance_record(
                modality="audio",
                result_source=ResultSource.FRESH_INFERENCE,
                execution_status="failed",
                evidence_id=kwargs.get("evidence_id"),
                case_id=kwargs.get("case_id"),
                input_sha256=kwargs.get("input_sha256"),
                run_id=kwargs.get("run_id"),
                requested_at=kwargs.get("requested_at"),
                submodel_statuses=submodel_statuses,
                diagnostic_details={"hardware_constraint": mem_msg},
            )
            return {
                "status": "failed",
                "is_seeded_sample": False,
                "result_source": ResultSource.FRESH_INFERENCE.value,
                "error": mem_msg,
                "error_category": "HOST_MEMORY_LIMITATION",
                "audio_metadata": {"filename": audio_path.name},
                "transcript": "",
                "text": "",
                "segments": [],
                "intelligence_report": {},
                "submodel_statuses": submodel_statuses,
                "provenance": provenance,
            }

        load_res = self.load_audio_waveform(audio_path)
        if load_res.get("status") != "success":
            return {
                "status": "failed",
                "error": load_res.get("error", "Failed to load audio waveform"),
                "audio_metadata": {},
                "transcript": "",
                "text": "",
                "segments": [],
            }

        waveform = load_res["waveform"]
        duration = load_res["duration_seconds"]
        audio_meta = dict(load_res.get("audio_metadata", {}))
        audio_meta.setdefault("filename", audio_path.name)
        audio_meta.setdefault("duration_seconds", duration)
        audio_meta.setdefault("sample_rate", 16000)
        audio_meta.setdefault("target_sample_rate", 16000)

        if len(waveform) == 0:
            return {
                "status": "failed",
                "error": "Audio file contains 0 audio frames or is completely silent.",
                "audio_metadata": audio_meta,
                "transcript": "",
                "text": "",
                "segments": [],
            }

        self._setup_torch_runtime()

        try:
            from transformers import WhisperForConditionalGeneration, WhisperProcessor
        except ImportError as exc:
            return {
                "status": "unavailable",
                "error": f"Transformers Whisper dependencies missing: {exc}",
                "audio_metadata": audio_meta,
                "transcript": "",
                "text": "",
                "segments": [],
            }

        processor = None
        model = None
        init_duration_ms = 0.0
        was_cached = False
        try:
            t_init_start = time.perf_counter()
            processor, model, was_cached = get_cached_whisper(self.whisper_model_id, self.device)
            init_duration_ms = 0.0 if was_cached else (time.perf_counter() - t_init_start) * 1000

            t_infer_start = time.perf_counter()

            # Handle chunking for audio > 30s up to MAX_SUPPORTED_AUDIO_SECONDS
            samples_per_chunk = int(16000 * MAX_AUDIO_CHUNK_SECONDS)  # 480,000 samples = 30s
            if duration > MAX_SUPPORTED_AUDIO_SECONDS:
                max_samples = int(MAX_SUPPORTED_AUDIO_SECONDS * 16000)
                waveform = waveform[:max_samples]
                audio_meta["audio_duration_notice"] = (
                    f"Audio duration ({duration}s) capped at {int(MAX_SUPPORTED_AUDIO_SECONDS)}s for CPU stability. "
                    "Original file preserved."
                )

            all_segments: List[Dict[str, Any]] = []
            all_texts: List[str] = []
            detected_language = forced_language or "unknown"

            # Generate token kwargs
            generate_kwargs: Dict[str, Any] = {
                "return_timestamps": True,
            }
            if forced_language:
                generate_kwargs["language"] = forced_language

            total_chunks = max(1, int(np.ceil(len(waveform) / float(samples_per_chunk))))

            for chunk_idx in range(total_chunks):
                c_start = chunk_idx * samples_per_chunk
                c_end = min(len(waveform), (chunk_idx + 1) * samples_per_chunk)
                chunk_wave = waveform[c_start:c_end]
                if len(chunk_wave) == 0:
                    continue

                chunk_offset_sec = round(c_start / 16000.0, 2)
                chunk_dur_sec = round(len(chunk_wave) / 16000.0, 2)

                inputs = processor(
                    chunk_wave,
                    sampling_rate=16000,
                    return_tensors="pt"
                )
                input_features = inputs.input_features.to(self.device)

                # Detect language once on chunk 0 if not forced
                if chunk_idx == 0 and not forced_language:
                    try:
                        tokens = model.detect_language(input_features)
                        lang_id = tokens[0].item() if hasattr(tokens[0], "item") else tokens[0]
                        detected_language = processor.tokenizer.decode([lang_id]).strip("<|> ")
                    except Exception as lang_exc:
                        logger.warning("Whisper language detection error: %s", lang_exc)
                        detected_language = "en"
                    if detected_language and detected_language != "unknown":
                        generate_kwargs["language"] = detected_language

                with _INFERENCE_LOCK:
                    if torch and hasattr(torch, "inference_mode"):
                        with torch.inference_mode():
                            predicted_ids = model.generate(input_features, **generate_kwargs)
                    else:
                        with torch.no_grad():
                            predicted_ids = model.generate(input_features, **generate_kwargs)

                transcription_output = processor.batch_decode(
                    predicted_ids,
                    decode_with_timestamps=True,
                    skip_special_tokens=False
                )[0]

                clean_chunk_text = processor.batch_decode(
                    predicted_ids,
                    skip_special_tokens=True
                )[0].strip()

                chunk_segs = self._parse_whisper_segments(transcription_output, chunk_dur_sec, time_offset=chunk_offset_sec)
                all_segments.extend(chunk_segs)
                if clean_chunk_text:
                    all_texts.append(clean_chunk_text)

            clean_text = " ".join(all_texts).strip()
            infer_duration_ms = (time.perf_counter() - t_infer_start) * 1000

            # Synthesize structured AI Intelligence Report
            intelligence_report = self.synthesize_audio_intelligence(clean_text, all_segments, detected_language)

            total_duration_ms = (time.perf_counter() - t_start) * 1000

            submodel_statuses = {"whisper": "success"}
            models_info = [{"name": "Whisper", "model_id": self.whisper_model_id, "status": "success", "cached": was_cached}]
            provenance = build_provenance_record(
                modality="audio",
                result_source=ResultSource.IN_MEMORY_MODEL_REUSE if was_cached else ResultSource.FRESH_INFERENCE,
                execution_status="completed",
                evidence_id=kwargs.get("evidence_id"),
                case_id=kwargs.get("case_id"),
                input_sha256=kwargs.get("input_sha256"),
                run_id=kwargs.get("run_id"),
                requested_at=kwargs.get("requested_at"),
                duration_ms=total_duration_ms,
                model_init_duration_ms=init_duration_ms,
                inference_duration_ms=infer_duration_ms,
                models=models_info,
                submodel_statuses=submodel_statuses,
            )

            logger.info(
                "[AUDIO_TRANSCRIPTION_SUCCESS] run_id=%s evidence_id=%s chunks=%d init_ms=%.1f infer_ms=%.1f total_ms=%.1f cached=%s",
                kwargs.get("run_id", "direct"),
                kwargs.get("evidence_id", "unknown"),
                total_chunks,
                init_duration_ms,
                infer_duration_ms,
                total_duration_ms,
                was_cached,
            )

            return {
                "status": "completed",
                "model": self.whisper_model_id,
                "audio_metadata": audio_meta,
                "detected_language": detected_language,
                "language": detected_language,
                "transcript": clean_text,
                "text": clean_text,
                "segments": all_segments,
                "segment_count": len(all_segments),
                "chunks_analyzed": total_chunks,
                "model_cached": was_cached,
                "intelligence_report": intelligence_report,
                "submodel_statuses": submodel_statuses,
                "provenance": provenance,
                "forensic_notice": (
                    "Automated Whisper transcript provides phoneme-to-text estimation. "
                    "It does not establish speaker identity or verify the factual veracity of spoken statements."
                ),
            }
        except Exception as exc:
            logger.exception("Whisper transcription failed")
            return {
                "status": "failed",
                "error": str(exc),
                "audio_metadata": audio_meta,
                "transcript": "",
                "text": "",
                "segments": [],
                "submodel_statuses": {"whisper": "failed"},
                "provenance": build_provenance_record(
                    modality="audio",
                    result_source=ResultSource.FRESH_INFERENCE,
                    execution_status="failed",
                    evidence_id=kwargs.get("evidence_id"),
                    case_id=kwargs.get("case_id"),
                    input_sha256=kwargs.get("input_sha256"),
                    run_id=kwargs.get("run_id"),
                    requested_at=kwargs.get("requested_at"),
                    duration_ms=(time.perf_counter() - t_start) * 1000,
                    model_init_duration_ms=init_duration_ms,
                    inference_duration_ms=0.0,
                    models=[{"name": "Whisper", "model_id": self.whisper_model_id, "status": "failed"}],
                    submodel_statuses={"whisper": "failed"},
                ),
            }

    def _parse_whisper_segments(
        self,
        raw_output: str,
        total_duration: float,
        time_offset: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Extract timestamped chunks from raw Whisper decoded string with <|0.00|> tags."""
        import re

        segments = []
        # Matches patterns like <|0.00|> Hello world <|2.40|>
        pattern = re.compile(r"<\|(\d+\.\d+)\|>(.*?)<\|(\d+\.\d+)\|>")
        matches = pattern.findall(raw_output)

        if matches:
            for start, text, end in matches:
                clean_seg = text.strip()
                if clean_seg:
                    s_sec = round(float(start) + time_offset, 2)
                    e_sec = round(float(end) + time_offset, 2)
                    segments.append({
                        "start_seconds": s_sec,
                        "end_seconds": e_sec,
                        "start": s_sec,
                        "end": e_sec,
                        "text": clean_seg,
                    })
        elif raw_output.strip():
            # Fallback if timestamp tags were not present
            clean_text = re.sub(r"<\|.*?\|>", "", raw_output).strip()
            if clean_text:
                s_sec = round(time_offset, 2)
                e_sec = round(time_offset + total_duration, 2)
                segments.append({
                    "start_seconds": s_sec,
                    "end_seconds": e_sec,
                    "start": s_sec,
                    "end": e_sec,
                    "text": clean_text,
                })

        return segments

    @staticmethod
    def synthesize_audio_intelligence(
        transcript: str,
        segments: List[Dict[str, Any]],
        detected_language: str = "en",
    ) -> Dict[str, Any]:
        """Synthesize structured AI Intelligence Report from speech transcript.

        Extracts:
          - ai_summary: concise summary of speaker's statement, main reported event.
          - event_type: reported event classification (distinguishes allegation from fact).
          - location: extracted location, or 'Not specified'.
          - translations: translations in English, Hindi, Telugu, and French.
          - timeline: chronological table of events with actual timestamps.
        """
        clean_text = (transcript or "").strip()
        if not clean_text:
            return {
                "ai_summary": "No intelligible speech detected in this audio recording.",
                "event_type": "Undetermined (No Speech Detected)",
                "event_type_confidence": 0.0,
                "location": "Not specified",
                "entities": [],
                "translations": {
                    "status": "translation_unavailable",
                    "explanation": "No speech detected in audio recording.",
                    "original": "",
                    "en": "No speech detected in audio file.",
                    "hi": {
                        "status": "translation_unavailable",
                        "explanation": "No speech detected in audio recording.",
                    },
                    "te": {
                        "status": "translation_unavailable",
                        "explanation": "No speech detected in audio recording.",
                    },
                    "fr": {
                        "status": "translation_unavailable",
                        "explanation": "No speech detected in audio recording.",
                    },
                },
                "timeline": [],
                "provenance": {
                    "provider": "deterministic_rule_engine",
                    "result_source": ResultSource.DETERMINISTIC_FALLBACK.value,
                },
            }

        # Try Gemini via ChatAssistant
        try:
            from services.chat_assistant import ChatAssistant
            assistant = ChatAssistant()
            prompt = (
                f"You are a senior forensic audio intelligence analyst.\n"
                f"Analyze the following audio speech transcript and timestamped segments:\n"
                f"FULL TRANSCRIPT:\n\"{clean_text}\"\n\n"
                f"TIMESTAMPED SEGMENTS:\n{json.dumps(segments, indent=2)}\n\n"
                f"Generate an objective, strictly grounded forensic audio intelligence report in valid JSON with EXACTLY this structure:\n"
                f"{{\n"
                f"  \"ai_summary\": \"Concise factual summary of the speaker's statement, identifying the main reported event and observable details. Never invent facts not in the transcript.\",\n"
                f"  \"event_type\": \"Classification of the reported event (e.g. 'Suspicious Activity / Observation (Witness Allegation)', 'Theft / Burglary (Alleged)', 'Traffic Incident', or 'Undetermined'). Clearly state if it is an allegation versus verified fact.\",\n"
                f"  \"event_type_confidence\": 0.85,\n"
                f"  \"location\": \"Exact location mentioned in transcript, or 'Not specified'\",\n"
                f"  \"entities\": [\n"
                f"    {{\n"
                f"      \"category\": \"Vehicles | Persons & Clothing | Location / Setting | Timeframe\",\n"
                f"      \"value\": \"Entity name and description\",\n"
                f"      \"context\": \"Context from speech transcript\"\n"
                f"    }}\n"
                f"  ],\n"
                f"  \"translations\": {{\n"
                f"    \"original\": \"{clean_text}\",\n"
                f"    \"en\": \"English translation or verbatim if already English\",\n"
                f"    \"hi\": \"Accurate Hindi translation in Devanagari script\",\n"
                f"    \"te\": \"Accurate Telugu translation in Telugu script\",\n"
                f"    \"fr\": \"Accurate French translation\"\n"
                f"  }},\n"
                f"  \"timeline\": [\n"
                f"    {{\n"
                f"      \"timestamp_display\": \"00:00\",\n"
                f"      \"timestamp_seconds\": 0.0,\n"
                f"      \"is_estimated\": false,\n"
                f"      \"event_description\": \"Objective description of what the witness reports observing\",\n"
                f"      \"transcript_excerpt\": \"Quote from transcript\"\n"
                f"    }}\n"
                f"  ]\n"
                f"}}"
            )
            report = assistant._query_gemini(prompt)
            if isinstance(report, dict) and report.get("ai_summary") and report.get("translations"):
                if isinstance(report["translations"], dict):
                    report["translations"]["status"] = "completed"
                report["provenance"] = {
                    "provider": "gemini",
                    "result_source": ResultSource.EXTERNAL_API_GENERATION.value,
                }
                return report
        except Exception as exc:
            logger.warning("Gemini audio intelligence synthesis failed: %s; using deterministic fallback", exc)

        # Deterministic fallback synthesis
        fallback_report = AudioAnalyzer._deterministic_audio_intelligence(clean_text, segments, detected_language)
        fallback_report["provenance"] = {
            "provider": "deterministic_rule_engine",
            "result_source": ResultSource.DETERMINISTIC_FALLBACK.value,
        }
        return fallback_report

    @staticmethod
    def _extract_sentence_context(text: str, target: str) -> str:
        """Find the sentence or clause from text that contains target."""
        import re
        if not text or not target:
            return ""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        target_lower = target.lower()
        for sent in sentences:
            if target_lower in sent.lower():
                return sent.strip()
        return text.strip()

    @staticmethod
    def _deterministic_audio_intelligence(
        transcript: str,
        segments: List[Dict[str, Any]],
        detected_language: str = "en",
    ) -> Dict[str, Any]:
        """Deterministic rule-based intelligence report generator when LLM is offline."""
        import re

        clean_txt = transcript.strip()
        lower_txt = clean_txt.lower()

        # 1. Location extraction (strictly grounded in text, bounded to avoid swallowing sentences)
        location = "Not specified"
        loc_match = re.search(
            r"\b(?:near|at|around|on)\s+([^.;!?\n]+?\b(?:street|road|stop|station|corner|avenue|lane|store|building|shop|market|park))\b",
            clean_txt,
            re.IGNORECASE,
        )
        if loc_match:
            location = loc_match.group(0).strip("., ")

        # 2. Event type classification (cautious, objective framing)
        if any(w in lower_txt for w in ["stole", "steal", "theft", "thief", "burglary", "break-in", "robbed"]):
            event_type = "Theft / Burglary (Witness Allegation)"
            confidence = 0.80
        elif any(w in lower_txt for w in ["accident", "collision", "crash", "hit and run"]):
            event_type = "Traffic Incident / Collision (Reported)"
            confidence = 0.80
        elif any(w in lower_txt for w in ["fight", "assault", "attack", "violence", "threat"]):
            event_type = "Physical Disturbance / Altercation (Alleged)"
            confidence = 0.80
        elif any(w in lower_txt for w in ["car", "motorcycle", "bike", "vehicle", "standing", "walked", "noticed", "observed"]):
            event_type = "Suspicious Presence / Observation (Witness Statement)"
            confidence = 0.75
        else:
            event_type = "Undetermined Observation (Witness Statement)"
            confidence = 0.50

        # 3. Timeline (strictly grounded in segments and their actual text)
        timeline = []
        for seg in segments:
            st = seg.get("start_seconds") if "start_seconds" in seg else seg.get("start", 0.0)
            txt = (seg.get("text") or "").strip()
            if not txt:
                continue
            mins = int(st // 60)
            secs = int(st % 60)
            ts_str = f"{mins:02d}:{secs:02d}"
            timeline.append({
                "timestamp_display": ts_str,
                "timestamp_seconds": float(st),
                "is_estimated": False,
                "event_description": f"Witness statement: \"{txt}\"",
                "transcript_excerpt": txt,
            })

        # 4. Summary (factual, grounded in actual transcript text; no invented narratives)
        if len(clean_txt) > 220:
            summary = f"Witness statement recorded: {clean_txt[:220].rstrip()}…"
        else:
            summary = clean_txt

        # 5. Translations (explicit translation_unavailable status; no placeholder text)
        is_english = (detected_language or "en").lower().startswith("en")
        translations = {
            "status": "translation_unavailable",
            "explanation": "Machine translation was not generated. Offline deterministic fallback does not perform neural machine translation.",
            "original": clean_txt,
            "en": clean_txt if is_english else {
                "status": "translation_unavailable",
                "explanation": "English translation was not generated because external AI service is offline.",
            },
            "hi": {
                "status": "translation_unavailable",
                "explanation": "Hindi translation was not generated because external AI service is offline.",
            },
            "te": {
                "status": "translation_unavailable",
                "explanation": "Telugu translation was not generated because external AI service is offline.",
            },
            "fr": {
                "status": "translation_unavailable",
                "explanation": "French translation was not generated because external AI service is offline.",
            },
        }

        # 6. Entity extraction (strictly grounded in transcript words and their actual context)
        entities = []

        # Vehicles: extract matched vehicle phrase and the actual sentence it appears in
        vehicle_matches = re.finditer(
            r"\b((?:white|black|red|blue|silver|gray|grey|green|dark|light)?\s*(?:car|sedan|suv|truck|van|motorcycle|motorbike|bike|scooter|vehicle))\b",
            lower_txt,
        )
        seen_vehicles = set()
        for vm in vehicle_matches:
            val_raw = vm.group(1).strip()
            if not val_raw or val_raw in ("a", "the", "an"):
                continue
            val_norm = val_raw.lower()
            if val_norm not in seen_vehicles:
                seen_vehicles.add(val_norm)
                entities.append({
                    "category": "Vehicles",
                    "value": val_raw.capitalize(),
                    "context": AudioAnalyzer._extract_sentence_context(clean_txt, val_raw),
                })

        # Persons & Clothing: extract matched person/clothing phrase and actual sentence context
        person_matches = re.finditer(
            r"\b((?:person|man|woman|individual|witness|driver|rider|pedestrian|suspect)\s+(?:in|wearing)\s+(?:a\s+)?(?:blue|black|white|red|green|dark|light|grey|gray)?\s*(?:shirt|jacket|hoodie|coat|pants|jeans|hat|cap|mask))\b|"
            r"\b((?:blue|black|white|red|green|dark|light|grey|gray)\s+(?:shirt|jacket|hoodie|coat|pants|jeans|hat|cap|mask))\b|"
            r"\b(person|man|woman|individual|witness|driver|rider|pedestrian|suspect)\b",
            lower_txt,
        )
        seen_persons = set()
        for pm in person_matches:
            val_raw = (pm.group(1) or pm.group(2) or pm.group(3) or "").strip()
            if not val_raw:
                continue
            val_norm = val_raw.lower()
            if any(val_norm in sp for sp in seen_persons):
                continue
            seen_persons.add(val_norm)
            entities.append({
                "category": "Persons & Clothing",
                "value": val_raw.capitalize(),
                "context": AudioAnalyzer._extract_sentence_context(clean_txt, val_raw),
            })

        # Location: only add if explicitly localized
        if location != "Not specified":
            entities.append({
                "category": "Location / Setting",
                "value": location,
                "context": AudioAnalyzer._extract_sentence_context(clean_txt, location),
            })

        # Timeframe: strictly match actual time expressions in transcript
        time_matches = re.finditer(
            r"\b\d{1,2}(?::|\.)\d{2}\s*(?:am|pm|a\.m\.|p\.m\.)\b|"
            r"\b\d{1,2}\s*(?:am|pm|a\.m\.|p\.m\.)\b|"
            r"\b(?:yesterday\s+(?:morning|afternoon|evening|night)|yesterday|today|last\s+night|this\s+morning|morning|afternoon|evening)\b",
            lower_txt,
        )
        found_times = []
        for tm in time_matches:
            val_raw = tm.group(0).strip()
            if val_raw and not any(val_raw in ft.lower() for ft in found_times):
                found_times.append(clean_txt[tm.start():tm.end()])

        if found_times:
            combined_time = ", ".join(found_times)
            entities.append({
                "category": "Timeframe",
                "value": combined_time,
                "context": AudioAnalyzer._extract_sentence_context(clean_txt, found_times[0]),
            })

        return {
            "ai_summary": summary,
            "event_type": event_type,
            "event_type_confidence": confidence,
            "location": location,
            "entities": entities,
            "translations": translations,
            "timeline": timeline,
        }
