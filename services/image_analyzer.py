"""
services/image_analyzer.py — Image Analysis Engine for CrimeVision AI (Phase 2).

Integrates:
  1. RT-DETR (PekingU/rtdetr_r50vd) for object detection and bounding boxes.
  2. CLIP (openai/clip-vit-base-patch32) for controlled scene similarity scoring.
  3. BLIP (Salesforce/blip-image-captioning-base) for natural language scene captioning.

Resource & Safety Principles:
  - Models are loaded on-demand and evaluated under torch.no_grad() with CPU thread limits.
  - Transparent error handling: if weights cannot be downloaded or initialized, explicit
    diagnostic errors are returned — never fabricated detections or captions.
  - CLIP outputs are framed as zero-shot similarity scores across candidate forensic labels,
    never presented as proof of criminal events.
"""

import gc
import logging
import os
from pathlib import Path
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image

from services.provenance import ResultSource, build_provenance_record

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)

# Global thread-safe in-memory RT-DETR model cache
_RTDETR_LOCK = threading.Lock()
_CACHED_RTDETR_PROCESSOR: Any = None
_CACHED_RTDETR_MODEL: Any = None
_CACHED_RTDETR_MODEL_ID: Optional[str] = None


def get_cached_rtdetr(
    model_id: str = "PekingU/rtdetr_r50vd",
    device: str = "cpu",
) -> Tuple[Any, Any, bool]:
    """Retrieve or load cached RT-DETR model and processor thread-safely.

    Returns (processor, model, was_cached).
    """
    global _CACHED_RTDETR_PROCESSOR, _CACHED_RTDETR_MODEL, _CACHED_RTDETR_MODEL_ID
    with _RTDETR_LOCK:
        if (
            _CACHED_RTDETR_MODEL is not None
            and _CACHED_RTDETR_PROCESSOR is not None
            and _CACHED_RTDETR_MODEL_ID == model_id
        ):
            return _CACHED_RTDETR_PROCESSOR, _CACHED_RTDETR_MODEL, True

        from transformers import RTDetrForObjectDetection, RTDetrImageProcessor

        logger.info("Initializing in-memory RT-DETR model session: %s on %s", model_id, device)
        processor = _load_hf_component(RTDetrImageProcessor, model_id)
        model = _load_hf_component(RTDetrForObjectDetection, model_id)
        if hasattr(model, "to"):
            model.to(device)
        if hasattr(model, "eval"):
            model.eval()

        _CACHED_RTDETR_PROCESSOR = processor
        _CACHED_RTDETR_MODEL = model
        _CACHED_RTDETR_MODEL_ID = model_id
        return processor, model, False


def clear_rtdetr_cache() -> None:
    """Clear cached RT-DETR model and release memory."""
    global _CACHED_RTDETR_PROCESSOR, _CACHED_RTDETR_MODEL, _CACHED_RTDETR_MODEL_ID
    with _RTDETR_LOCK:
        _CACHED_RTDETR_PROCESSOR = None
        _CACHED_RTDETR_MODEL = None
        _CACHED_RTDETR_MODEL_ID = None
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


# Default forensic scene taxonomy for CLIP candidate similarity scoring
FORENSIC_SCENE_TAXONOMY: List[str] = [
    "indoor residential room",
    "commercial office or store",
    "street or roadway",
    "parking lot or vehicle garage",
    "nighttime outdoor scene",
    "industrial or warehouse facility",
    "alleyway or narrow corridor",
    "open public park or field",
]


class ImageAnalyzer:
    """Sequential CPU-friendly analyzer for RT-DETR, CLIP, and BLIP."""

    def __init__(
        self,
        rtdetr_model_id: str = "PekingU/rtdetr_r50vd",
        clip_model_id: str = "openai/clip-vit-base-patch32",
        blip_model_id: str = "Salesforce/blip-image-captioning-base",
        confidence_threshold: float = 0.45,
        max_inference_dimension: Optional[int] = None,
    ):
        self.rtdetr_model_id = rtdetr_model_id
        self.clip_model_id = clip_model_id
        self.blip_model_id = blip_model_id
        self.confidence_threshold = confidence_threshold
        if max_inference_dimension is not None:
            self.max_inference_dimension = int(max_inference_dimension)
        else:
            try:
                self.max_inference_dimension = int(os.getenv("IMAGE_MAX_INFERENCE_DIMENSION", "1280"))
            except (ValueError, TypeError):
                self.max_inference_dimension = 1280
        self.device = "cuda" if (torch and torch.cuda.is_available()) else "cpu"

    def _setup_torch_runtime(self) -> None:
        """Configure PyTorch CPU thread count to optimize CPU inference."""
        if torch and self.device == "cpu":
            try:
                num_cores = os.cpu_count() or 4
                target_threads = max(2, min(6, num_cores - 2 if num_cores > 4 else num_cores))
                torch.set_num_threads(target_threads)
            except Exception:
                pass

    def run_rtdetr_detection_on_images(
        self,
        pil_images: List[Image.Image],
        original_sizes: Optional[List[Tuple[int, int]]] = None,
    ) -> List[Dict[str, Any]]:
        """Run RT-DETR object detection across multiple PIL images reusing a single loaded model session.

        Accepts an optional original_sizes list of (width, height) tuples to correctly scale
        and normalize bounding boxes when inference images have been resized.

        Returns a list of detection result dictionaries, one per image.
        """
        if not pil_images:
            return []

        if not TORCH_AVAILABLE or torch is None:
            return [
                {
                    "status": "unavailable",
                    "error": "PyTorch (torch) is not available in this runtime environment.",
                    "objects": [],
                }
                for _ in pil_images
            ]

        self._setup_torch_runtime()
        try:
            from transformers import RTDetrForObjectDetection, RTDetrImageProcessor
        except ImportError as exc:
            return [
                {
                    "status": "unavailable",
                    "error": f"Transformers RT-DETR dependencies missing: {exc}",
                    "objects": [],
                }
                for _ in pil_images
            ]

        processor = None
        model = None
        results: List[Dict[str, Any]] = []
        init_duration_ms = 0.0
        was_cached = False

        try:
            t_init_start = time.perf_counter()
            processor, model, was_cached = get_cached_rtdetr(self.rtdetr_model_id, self.device)
            init_duration_ms = 0.0 if was_cached else (time.perf_counter() - t_init_start) * 1000

            for idx, pil_image in enumerate(pil_images):
                try:
                    t_infer_start = time.perf_counter()
                    if original_sizes and idx < len(original_sizes) and original_sizes[idx]:
                        orig_w, orig_h = original_sizes[idx]
                    else:
                        orig_w, orig_h = pil_image.size
                    inputs = processor(images=pil_image, return_tensors="pt").to(self.device)

                    if torch and hasattr(torch, "inference_mode"):
                        with torch.inference_mode():
                            outputs = model(**inputs)
                    else:
                        with torch.no_grad():
                            outputs = model(**inputs)

                    post_res = processor.post_process_object_detection(
                        outputs, target_sizes=[(orig_h, orig_w)], threshold=self.confidence_threshold
                    )[0]

                    detected_objects = []
                    class_counts: Dict[str, int] = {}

                    scores = post_res["scores"].tolist() if hasattr(post_res["scores"], "tolist") else list(post_res["scores"])
                    labels = post_res["labels"].tolist() if hasattr(post_res["labels"], "tolist") else list(post_res["labels"])
                    boxes = post_res["boxes"].tolist() if hasattr(post_res["boxes"], "tolist") else list(post_res["boxes"])

                    for score, label_idx, box in zip(scores, labels, boxes):
                        label_name = model.config.id2label.get(label_idx, f"class_{label_idx}")
                        x1, y1, x2, y2 = [round(float(coord), 2) for coord in box]
                        x1 = max(0.0, min(float(orig_w), x1))
                        y1 = max(0.0, min(float(orig_h), y1))
                        x2 = max(0.0, min(float(orig_w), x2))
                        y2 = max(0.0, min(float(orig_h), y2))
                        norm_box = [
                            round(max(0.0, min(1.0, x1 / orig_w)), 4),
                            round(max(0.0, min(1.0, y1 / orig_h)), 4),
                            round(max(0.0, min(1.0, x2 / orig_w)), 4),
                            round(max(0.0, min(1.0, y2 / orig_h)), 4),
                        ]

                        obj_record = {
                            "label": label_name,
                            "confidence": round(float(score), 4),
                            "box_pixels": [round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)],
                            "box_normalized": norm_box,
                        }
                        detected_objects.append(obj_record)
                        class_counts[label_name] = class_counts.get(label_name, 0) + 1

                    infer_duration_ms = (time.perf_counter() - t_infer_start) * 1000

                    res_dict = {
                        "status": "success",
                        "model": self.rtdetr_model_id,
                        "objects": detected_objects,
                        "class_counts": class_counts,
                        "total_detections": len(detected_objects),
                        "image_dimensions": {"width": orig_w, "height": orig_h},
                        "init_duration_ms": round(init_duration_ms, 2),
                        "inference_duration_ms": round(infer_duration_ms, 2),
                        "model_cached": was_cached,
                    }
                    if (orig_w, orig_h) != pil_image.size:
                        res_dict["inference_dimensions"] = {"width": pil_image.width, "height": pil_image.height}
                    results.append(res_dict)
                except Exception as frame_exc:
                    logger.warning("RT-DETR frame detection error: %s", frame_exc)
                    results.append({
                        "status": "failed",
                        "error": str(frame_exc),
                        "objects": [],
                        "init_duration_ms": round(init_duration_ms, 2),
                        "inference_duration_ms": 0.0,
                    })

            return results
        except Exception as exc:
            logger.exception("RT-DETR model loading or detection failed")
            return [
                {
                    "status": "failed",
                    "error": str(exc),
                    "objects": [],
                    "init_duration_ms": round(init_duration_ms, 2),
                    "inference_duration_ms": 0.0,
                }
                for _ in pil_images
            ]

    def run_rtdetr_detection(
        self,
        pil_image: Image.Image,
        original_size: Optional[Tuple[int, int]] = None,
    ) -> Dict[str, Any]:
        """Run RT-DETR object detection on a single PIL image.

        Returns detected bounding boxes in [x1, y1, x2, y2] coordinates (pixels and normalized),
        class labels, and confidence values.
        """
        original_sizes = [original_size] if original_size else None
        results = self.run_rtdetr_detection_on_images([pil_image], original_sizes=original_sizes)
        return results[0] if results else {
            "status": "failed",
            "error": "No detection results returned.",
            "objects": [],
        }

    def run_clip_similarity(
        self, pil_image: Image.Image, candidate_labels: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Compute cosine similarity between image and candidate forensic scene labels.

        Results are candidate classification rankings with zero-shot similarity scores.
        """
        self._setup_torch_runtime()
        labels = candidate_labels or FORENSIC_SCENE_TAXONOMY
        try:
            from transformers import CLIPModel, CLIPProcessor
        except ImportError as exc:
            return {
                "status": "unavailable",
                "error": f"Transformers CLIP dependencies missing: {exc}",
                "matches": [],
            }

        processor = None
        model = None
        init_duration_ms = 0.0
        try:
            logger.info("Loading CLIP processor & model (cached/local): %s", self.clip_model_id)
            t_init_start = time.perf_counter()
            processor = _load_hf_component(CLIPProcessor, self.clip_model_id)
            model = _load_hf_component(CLIPModel, self.clip_model_id)
            model.to(self.device)
            model.eval()
            init_duration_ms = (time.perf_counter() - t_init_start) * 1000

            t_infer_start = time.perf_counter()
            inputs = processor(
                text=labels,
                images=pil_image,
                return_tensors="pt",
                padding=True,
            ).to(self.device)

            with torch.no_grad():
                outputs = model(**inputs)
                logits_per_image = outputs.logits_per_image  # [1, len(labels)]
                probs = logits_per_image.softmax(dim=1)[0].tolist()

            infer_duration_ms = (time.perf_counter() - t_infer_start) * 1000

            matches = []
            for label, prob in zip(labels, probs):
                matches.append({
                    "label": label,
                    "similarity_score": round(float(prob), 4),
                })

            matches.sort(key=lambda m: m["similarity_score"], reverse=True)

            return {
                "status": "success",
                "model": self.clip_model_id,
                "matches": matches,
                "top_match": matches[0] if matches else None,
                "init_duration_ms": round(init_duration_ms, 2),
                "inference_duration_ms": round(infer_duration_ms, 2),
                "forensic_notice": (
                    "CLIP zero-shot similarity scores represent text-image semantic correlation, "
                    "not scientifically validated probabilistic proof of scene occurrence."
                ),
            }
        except Exception as exc:
            logger.exception("CLIP scene analysis failed")
            return {
                "status": "failed",
                "error": str(exc),
                "matches": [],
                "init_duration_ms": round(init_duration_ms, 2),
                "inference_duration_ms": 0.0,
            }
        finally:
            del model
            del processor
            gc.collect()

    def run_blip_captioning(self, pil_image: Image.Image) -> Dict[str, Any]:
        """Generate descriptive scene caption via BLIP."""
        self._setup_torch_runtime()
        try:
            from transformers import BlipForConditionalGeneration, BlipProcessor
        except ImportError as exc:
            return {
                "status": "unavailable",
                "error": f"Transformers BLIP dependencies missing: {exc}",
                "caption": None,
            }

        processor = None
        model = None
        init_duration_ms = 0.0
        try:
            logger.info("Loading BLIP processor & model (cached/local): %s", self.blip_model_id)
            t_init_start = time.perf_counter()
            processor = _load_hf_component(BlipProcessor, self.blip_model_id)
            model = _load_hf_component(BlipForConditionalGeneration, self.blip_model_id)
            model.to(self.device)
            model.eval()
            init_duration_ms = (time.perf_counter() - t_init_start) * 1000

            t_infer_start = time.perf_counter()
            # Ensure image is in RGB format
            rgb_image = pil_image.convert("RGB")
            inputs = processor(images=rgb_image, return_tensors="pt").to(self.device)

            with torch.no_grad():
                out = model.generate(**inputs, max_new_tokens=50)
                caption = processor.decode(out[0], skip_special_tokens=True).strip()

            infer_duration_ms = (time.perf_counter() - t_infer_start) * 1000

            return {
                "status": "success",
                "model": self.blip_model_id,
                "caption": caption,
                "init_duration_ms": round(init_duration_ms, 2),
                "inference_duration_ms": round(infer_duration_ms, 2),
            }
        except Exception as exc:
            logger.exception("BLIP captioning failed")
            return {
                "status": "failed",
                "error": str(exc),
                "caption": None,
                "init_duration_ms": round(init_duration_ms, 2),
                "inference_duration_ms": 0.0,
            }
        finally:
            del model
            del processor
            gc.collect()

    def analyze_image_pipeline(
        self,
        image_path: Path,
        candidate_labels: Optional[List[str]] = None,
        custom_labels: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute full sequential Phase 2 pipeline: RT-DETR -> CLIP -> BLIP."""
        t_pipeline_start = time.perf_counter()
        labels = custom_labels if custom_labels is not None else candidate_labels
        if not image_path.exists():
            return {
                "status": "error",
                "error": f"Evidence image file does not exist on disk: {image_path}",
            }

        try:
            with Image.open(image_path) as img:
                # Load image into memory as RGB
                pil_image = img.convert("RGB")
                img_w, img_h = pil_image.size
        except Exception as exc:
            return {
                "status": "error",
                "error": f"Failed to open or decode image: {exc}",
            }

        # Check if resize is required for inference (preserves original file on disk)
        infer_image = pil_image
        resized_for_inference = False
        infer_w, infer_h = img_w, img_h

        if self.max_inference_dimension > 0 and max(img_w, img_h) > self.max_inference_dimension:
            scale = self.max_inference_dimension / max(img_w, img_h)
            infer_w = max(1, int(round(img_w * scale)))
            infer_h = max(1, int(round(img_h * scale)))
            try:
                resample_filter = getattr(Image.Resampling, "LANCZOS", Image.LANCZOS)
            except AttributeError:
                resample_filter = Image.BILINEAR
            infer_image = pil_image.resize((infer_w, infer_h), resample_filter)
            resized_for_inference = True
            logger.info(
                "Resized image for inference from %dx%d to %dx%d (max dimension %d)",
                img_w, img_h, infer_w, infer_h, self.max_inference_dimension,
            )

        # Route to Cloud Vision Provider (Google Gemini Vision) when selected or in cloud mode
        from services.provider_manager import get_inference_provider
        active_provider = kwargs.get("provider") or get_inference_provider("image")
        if active_provider == "cloud":
            from services.cloud_vision_service import analyze_image_with_gemini
            return analyze_image_with_gemini(
                image_path=image_path,
                candidate_labels=labels,
                **kwargs,
            )

        # Pre-flight host resource check: prevent uncatchable container SIGKILL OOM
        from services.hardware_utils import is_inference_memory_sufficient
        mem_ok, actual_mb, mem_msg = is_inference_memory_sufficient(min_mb=1500, model_name="RT-DETR / CLIP / BLIP")
        if not mem_ok:
            metadata = {
                "filename": image_path.name,
                "width": img_w,
                "height": img_h,
                "inference_width": infer_w,
                "inference_height": infer_h,
                "resized_for_inference": resized_for_inference,
                "max_inference_dimension": self.max_inference_dimension,
            }
            submodel_statuses = {"rtdetr": "failed", "clip": "unavailable", "blip": "unavailable"}
            provenance = build_provenance_record(
                modality="image",
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
                "error_code": "HOST_MEMORY_LIMITATION",
                "image_metadata": metadata,
                "detection": {
                    "status": "failed",
                    "error": mem_msg,
                    "objects": [],
                },
                "clip": {"status": "unavailable", "matches": []},
                "caption": {"status": "unavailable", "caption": None},
                "submodel_statuses": submodel_statuses,
                "provenance": provenance,
                "summary": "Analysis halted safely: Host lacks sufficient RAM to execute heavy neural vision models.",
            }

        # 1. RT-DETR Object Detection (pass infer_image and original_size=(img_w, img_h))
        rtdetr_result = self.run_rtdetr_detection(infer_image, original_size=(img_w, img_h))
        gc.collect()

        # 2. CLIP Similarity Scoring
        clip_result = self.run_clip_similarity(infer_image, labels)
        gc.collect()

        # 3. BLIP Image Captioning
        blip_result = self.run_blip_captioning(infer_image)
        gc.collect()

        total_duration_ms = (time.perf_counter() - t_pipeline_start) * 1000

        # Submodel statuses
        submodel_statuses = {
            "rtdetr": rtdetr_result.get("status", "unknown"),
            "clip": clip_result.get("status", "unknown"),
            "blip": blip_result.get("status", "unknown"),
        }

        # Determine overall pipeline status
        statuses = [rtdetr_result.get("status"), clip_result.get("status"), blip_result.get("status")]
        if all(s == "success" for s in statuses):
            overall_status = "completed"
        elif any(s == "success" for s in statuses):
            overall_status = "partial"
        else:
            overall_status = "failed"

        # Model timing aggregates
        tot_init_ms = (
            rtdetr_result.get("init_duration_ms", 0.0) +
            clip_result.get("init_duration_ms", 0.0) +
            blip_result.get("init_duration_ms", 0.0)
        )
        tot_infer_ms = (
            rtdetr_result.get("inference_duration_ms", 0.0) +
            clip_result.get("inference_duration_ms", 0.0) +
            blip_result.get("inference_duration_ms", 0.0)
        )

        metadata = {
            "filename": image_path.name,
            "width": img_w,
            "height": img_h,
            "inference_width": infer_w,
            "inference_height": infer_h,
            "resized_for_inference": resized_for_inference,
            "max_inference_dimension": self.max_inference_dimension,
        }

        forensic_summaries = self.synthesize_forensic_summaries(
            detection_res=rtdetr_result,
            clip_res=clip_result,
            blip_res=blip_result,
            metadata=metadata,
        )

        models_info = [
            {"name": "RT-DETR", "model_id": self.rtdetr_model_id, "status": rtdetr_result.get("status")},
            {"name": "CLIP", "model_id": self.clip_model_id, "status": clip_result.get("status")},
            {"name": "BLIP", "model_id": self.blip_model_id, "status": blip_result.get("status")},
        ]

        provenance = build_provenance_record(
            modality="image",
            result_source=ResultSource.FRESH_INFERENCE,
            execution_status=overall_status,
            evidence_id=kwargs.get("evidence_id"),
            case_id=kwargs.get("case_id"),
            input_sha256=kwargs.get("input_sha256"),
            run_id=kwargs.get("run_id"),
            requested_at=kwargs.get("requested_at"),
            duration_ms=total_duration_ms,
            model_init_duration_ms=tot_init_ms,
            inference_duration_ms=tot_infer_ms,
            models=models_info,
            submodel_statuses=submodel_statuses,
        )

        pipeline_out: Dict[str, Any] = {
            "status": overall_status,
            "is_seeded_sample": False,
            "result_source": ResultSource.FRESH_INFERENCE.value,
            "image_metadata": metadata,
            "detection": rtdetr_result,
            "clip": clip_result,
            "caption": blip_result,
            "submodel_statuses": submodel_statuses,
            "provenance": provenance,
            **forensic_summaries,
        }
        if overall_status == "failed":
            err_msg = (
                rtdetr_result.get("error")
                or clip_result.get("error")
                or blip_result.get("error")
                or "Image analysis pipeline failed to execute on current host."
            )
            pipeline_out["error"] = err_msg

        return pipeline_out

    @staticmethod
    def synthesize_forensic_summaries(
        detection_res: Dict[str, Any],
        clip_res: Dict[str, Any],
        blip_res: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Synthesize objective, evidence-grounded forensic summaries from model predictions."""
        objects = detection_res.get("objects", [])
        class_counts = detection_res.get("class_counts", {})
        caption = (blip_res.get("caption") or "").strip()
        top_clip = clip_res.get("top_match") or (clip_res.get("matches", [{}])[0] if clip_res.get("matches") else {})
        scene_label = top_clip.get("label", "unclassified scene")
        scene_conf = float(top_clip.get("similarity_score", 0.0))

        # 1. Statistics
        person_count = class_counts.get("person", 0)
        vehicle_labels = {"car", "bus", "truck", "motorcycle", "motorbike", "bicycle", "van"}
        vehicle_count = sum(class_counts.get(k, 0) for k in vehicle_labels)
        weapon_labels = {"gun", "knife", "pistol", "rifle", "weapon", "firearm", "sword"}
        weapon_count = sum(class_counts.get(k, 0) for k in weapon_labels)
        other_count = max(0, len(objects) - person_count - vehicle_count - weapon_count)
        total_count = len(objects)

        statistics = {
            "persons_detected": person_count,
            "vehicles_detected": vehicle_count,
            "weapons_detected": weapon_count,
            "other_objects_detected": other_count,
            "total_detections": total_count,
            "primary_scene_type": scene_label,
            "scene_confidence": round(scene_conf, 4),
        }

        # 2. AI Scene Summary
        summary_parts = []
        if scene_conf > 0.4:
            summary_parts.append(f"Visual evidence is classified as a {scene_label} ({scene_conf*100:.1f}% semantic similarity).")
        elif scene_label:
            summary_parts.append(f"Scene environment exhibits characteristics of a {scene_label}.")

        if caption:
            summary_parts.append(f"Natural scene captioning identifies: \"{caption}\".")

        if total_count > 0:
            entity_summary = []
            if person_count:
                entity_summary.append(f"{person_count} person{'s' if person_count > 1 else ''}")
            if vehicle_count:
                entity_summary.append(f"{vehicle_count} vehicle{'s' if vehicle_count > 1 else ''}")
            if weapon_count:
                entity_summary.append(f"{weapon_count} weapon{'s' if weapon_count > 1 else ''}")
            if other_count > 0:
                entity_summary.append(f"{other_count} additional environmental item{'s' if other_count > 1 else ''}")
            summary_parts.append(f"RT-DETR localized {total_count} distinct entities ({', '.join(entity_summary)}).")
        else:
            summary_parts.append("No foreground objects were localized above the detection confidence threshold.")

        scene_summary = " ".join(summary_parts)

        # 3. Visual Summary
        visual_observations = []
        if caption:
            visual_observations.append(f"Primary focal subject: \"{caption}\".")
        if scene_label:
            visual_observations.append(f"Environmental context corresponds to {scene_label} with {scene_conf*100:.1f}% CLIP confidence.")

        spatial_notes = []
        persons = [o for o in objects if o.get("label") == "person"]
        vehicles = [o for o in objects if o.get("label") in vehicle_labels]
        items = [o for o in objects if o.get("label") not in vehicle_labels and o.get("label") != "person"]

        if len(persons) >= 2:
            spatial_notes.append(f"{len(persons)} persons are positioned in the midground area across distinct horizontal intervals.")
        elif len(persons) == 1:
            spatial_notes.append("1 individual is localized in the scene.")

        if len(vehicles) >= 1:
            spatial_notes.append(f"{len(vehicles)} vehicles are situated across the roadway/curb zones.")

        if items:
            item_labels = ", ".join(sorted(set(o.get("label") for o in items)))
            spatial_notes.append(f"Ground-level items identified: {item_labels}.")

        visual_summary = {
            "direct_observations": visual_observations,
            "spatial_distribution": spatial_notes,
            "uncertainty_boundaries": (
                "Observation boundaries: Camera angle, exact occluded zones, non-visible vehicle interiors, "
                "and depth coordinates cannot be conclusively verified from a single monocular still image."
            ),
        }

        # 4. Actions & Postures Detected
        postures = []
        for idx, p in enumerate(persons, 1):
            box_px = p.get("box_pixels", [])
            if len(box_px) == 4:
                w = abs(box_px[2] - box_px[0])
                h = abs(box_px[3] - box_px[1])
                ratio = (h / w) if w > 0 else 1.0
                if ratio >= 1.6:
                    posture = "Upright orientation consistent with standing or walking posture"
                elif ratio < 0.9:
                    posture = "Horizontal orientation consistent with seated or low-profile posture"
                else:
                    posture = "Neutral mid-profile posture"
                postures.append(f"Subject #{idx} (conf {p.get('confidence', 0)*100:.1f}%): {posture}.")

        actions_detected = {
            "status": "supported" if postures else "no_persons_detected",
            "observed_postures": postures,
            "forensic_notice": (
                "Static image detection evaluates geometric posture only. Dedicated dynamic action recognition "
                "is not configured for still imagery. No hostile, violent, or evasive action is inferred from posture."
            ),
        }

        # 5. Evidence Facts
        facts = []
        for obj in objects:
            facts.append({
                "label": obj.get("label"),
                "confidence": obj.get("confidence"),
                "confidence_pct": round(obj.get("confidence", 0) * 100, 1),
                "box_pixels": obj.get("box_pixels"),
                "box_normalized": obj.get("box_normalized"),
                "category": "person" if obj.get("label") == "person" else ("vehicle" if obj.get("label") in vehicle_labels else ("weapon" if obj.get("label") in weapon_labels else "item")),
            })

        evidence_facts = {
            "total_items": len(facts),
            "items": facts,
            "scene_classification": {
                "label": scene_label,
                "similarity_score": round(scene_conf, 4),
            },
            "caption": caption,
        }

        # 6. AI Application Scenarios
        scenarios = []
        if vehicle_count > 0 and person_count > 0:
            scenarios.append({
                "title": "Pedestrian & Traffic Transit Pattern",
                "description": "Spatial distribution indicates simultaneous vehicle presence and pedestrian transit along an active roadway thoroughfare.",
                "category": "Traffic / Transit",
                "verification_status": "Unverified Working Hypothesis",
            })
        if items:
            scenarios.append({
                "title": "Ground Item Proximity Evaluation",
                "description": f"Presence of localized ground item(s) ({', '.join(sorted(set(o.get('label') for o in items)))}) may be cross-referenced with sequential timestamps for custody/owner correlation.",
                "category": "Item Custody",
                "verification_status": "Unverified Working Hypothesis",
            })
        if vehicle_count > 0:
            scenarios.append({
                "title": "Surveillance Anchor Alignment",
                "description": "Prominently localized vehicle provides a reliable geometric reference point for multi-camera calibration and spatial reconstruction.",
                "category": "Spatial Calibration",
                "verification_status": "Unverified Working Hypothesis",
            })
        if not scenarios:
            scenarios.append({
                "title": "General Environmental Documentation",
                "description": f"Visual documentation of {scene_label} for archival and baseline custody reference.",
                "category": "Baseline",
                "verification_status": "Unverified Working Hypothesis",
            })

        application_scenarios = {
            "notice": (
                "INVESTIGATIVE HYPOTHESES: The scenarios below are exploratory investigative frameworks "
                "generated for forensic guidance. They do not constitute established facts, sequence of events, "
                "or proof of intent or unlawful conduct."
            ),
            "scenarios": scenarios,
        }

        return {
            "statistics": statistics,
            "scene_summary": scene_summary,
            "visual_summary": visual_summary,
            "actions_detected": actions_detected,
            "evidence_facts": evidence_facts,
            "application_scenarios": application_scenarios,
        }
