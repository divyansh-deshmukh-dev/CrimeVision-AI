"""
services/spatial_mapper.py — Maps 2D forensic detections to an illustrative 3D scene.

CRITICAL FORENSIC SPECIFICATION:
Surveillance imagery and standard video streams lack calibrated depth sensors
(LiDAR / RGB-D) and camera extrinsics. This module maps 2D bounding boxes and
timeline progression onto an illustrative 3D coordinate space.

It NEVER claims metric accuracy, physical depth truth, or calibrated positioning.
All positions are labeled as illustrative proxies.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Category-specific color mapping for visual consistency
CATEGORY_COLORS: dict[str, str] = {
    # Persons & biological
    "person": "#10B981",    # Emerald
    "pedestrian": "#10B981",
    # Weapons & threats
    "knife": "#EF4444",     # Crimson
    "weapon": "#EF4444",
    "gun": "#EF4444",
    "pistol": "#EF4444",
    "scissors": "#EF4444",
    # Vehicles & transport
    "car": "#3B82F6",       # Cobalt Blue
    "truck": "#3B82F6",
    "bus": "#3B82F6",
    "motorcycle": "#06B6D4", # Cyan
    "bicycle": "#06B6D4",
    # Accessories & containers
    "backpack": "#F59E0B",  # Amber
    "bag": "#F59E0B",
    "handbag": "#F59E0B",
    "suitcase": "#F59E0B",
    # Bottles & Food/Dining
    "bottle": "#22C55E",    # Green
    "cup": "#22C55E",
    "glass": "#22C55E",
    "wine glass": "#22C55E",
    "can": "#22C55E",
    "bowl": "#22C55E",
    # Furniture
    "chair": "#D97706",     # Warm Amber / Bronze
    "couch": "#D97706",
    "sofa": "#D97706",
    "table": "#D97706",
    "bed": "#D97706",
    "bench": "#D97706",
    "desk": "#D97706",
    # Electronics
    "cell phone": "#8B5CF6", # Tech Violet
    "laptop": "#8B5CF6",
    "tv": "#8B5CF6",
    "mouse": "#8B5CF6",
    "keyboard": "#8B5CF6",
    # Signage & infrastructure
    "traffic light": "#EC4899", # Hot Pink
    "stop sign": "#EC4899",
    "fire hydrant": "#EC4899",
}
DEFAULT_COLOR = "#94A3B8"  # Slate Gray


def get_category_color(label: str) -> str:
    """Return standard hex color for a given detection label."""
    return CATEGORY_COLORS.get(label.lower().strip(), DEFAULT_COLOR)


def get_marker_type(label: str) -> str:
    """Return stylized 3D marker family for a given detection label."""
    norm = label.lower().strip()
    if norm in ("person", "pedestrian", "man", "woman", "cyclist"):
        return "person"
    if norm in ("car", "truck", "bus", "vehicle", "van", "automobile"):
        return "vehicle"
    if norm in ("motorcycle", "motorbike", "bicycle", "bike"):
        return "motorcycle"
    if norm in ("chair", "couch", "sofa", "table", "bed", "bench", "desk", "furniture"):
        return "furniture"
    if norm in ("bag", "backpack", "handbag", "suitcase"):
        return "bag"
    if norm in ("bottle", "cup", "wine glass", "glass", "can", "bowl"):
        return "bottle"
    if norm in ("knife", "gun", "pistol", "weapon", "scissors"):
        return "threat"
    if norm in ("cell phone", "laptop", "tv", "mouse", "keyboard", "remote"):
        return "device"
    if norm in ("traffic light", "fire hydrant", "stop sign", "parking meter"):
        return "signage"
    return "generic"


def normalize_box(
    box: list[float] | None,
    image_dim: dict[str, int] | None = None,
) -> list[float]:
    """Ensure bounding box coordinates are normalized to [0.0, 1.0].
    
    Returns [x1, y1, x2, y2].
    """
    if not box or len(box) < 4:
        return [0.4, 0.4, 0.6, 0.6]  # Fallback center box

    x1, y1, x2, y2 = float(box[0]), float(box[1]), float(box[2]), float(box[3])

    # If already normalized between 0 and 1
    if 0.0 <= x1 <= 1.0 and 0.0 <= x2 <= 1.0 and 0.0 <= y1 <= 1.0 and 0.0 <= y2 <= 1.0:
        return [round(x1, 4), round(y1, 4), round(x2, 4), round(y2, 4)]

    # If pixel dimensions are provided
    if image_dim and image_dim.get("width", 0) > 0 and image_dim.get("height", 0) > 0:
        w = float(image_dim["width"])
        h = float(image_dim["height"])
        return [
            round(max(0.0, min(1.0, x1 / w)), 4),
            round(max(0.0, min(1.0, y1 / h)), 4),
            round(max(0.0, min(1.0, x2 / w)), 4),
            round(max(0.0, min(1.0, y2 / h)), 4),
        ]

    # Best-effort normalization for standard video/photo resolutions (e.g. 1920x1080 or 640x480)
    max_coord = max(x2, y2, 1.0)
    norm_factor = 1920.0 if max_coord > 640 else (640.0 if max_coord > 1.0 else 1.0)
    return [
        round(max(0.0, min(1.0, x1 / norm_factor)), 4),
        round(max(0.0, min(1.0, y1 / norm_factor)), 4),
        round(max(0.0, min(1.0, x2 / norm_factor)), 4),
        round(max(0.0, min(1.0, y2 / norm_factor)), 4),
    ]


def map_case_to_spatial_scene(
    case: dict[str, Any],
    evidence_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Extract all completed detection objects from case evidence and compute
    illustrative 3D coordinates.

    Parameters
    ----------
    case : dict
        Case record from storage.
    evidence_items : list of dict
        All evidence items belonging to the case.

    Returns
    -------
    dict
        Structured 3D scene payload including objects, legend, categories,
        sources, and forensic disclaimers.
    """
    case_id = case.get("case_id", "")
    case_name = case.get("name", "Untitled Case")

    objects: list[dict[str, Any]] = []
    categories_set: set[str] = set()
    sources_summary: list[dict[str, Any]] = []

    for ev in evidence_items:
        eid = ev.get("evidence_id", "")
        ename = ev.get("original_name") or ev.get("filename", "")
        modality = ev.get("modality", "")
        status = ev.get("analysis_status", "")
        analysis = ev.get("analysis_json")

        if status != "completed" or not analysis or not isinstance(analysis, dict):
            continue

        ev_object_count = 0

        # ── 1. Image Evidence Detections ──────────────────────────────────────
        if modality == "image":
            dim = (
                analysis.get("image_dimensions")
                or analysis.get("image_metadata")
                or analysis.get("detection", {}).get("image_dimensions")
            )
            det = analysis.get("detection", {})
            rtdetr = analysis.get("rtdetr", {})
            raw_objs = (
                det.get("objects")
                or rtdetr.get("objects")
                or rtdetr.get("detections")
                or analysis.get("objects", [])
            )

            for idx, raw in enumerate(raw_objs):
                if not isinstance(raw, dict):
                    continue
                label = str(raw.get("label", "object")).strip()
                confidence = float(raw.get("confidence", 0.0))

                # Extract normalized bounding box
                norm_box = raw.get("box_normalized")
                if not norm_box:
                    box_pixels = raw.get("box_pixels") or raw.get("bbox")
                    norm_box = normalize_box(box_pixels, dim)
                else:
                    norm_box = [round(float(c), 4) for c in norm_box]

                # Compute center of 2D bounding box
                cx = (norm_box[0] + norm_box[2]) / 2.0
                cy = (norm_box[1] + norm_box[3]) / 2.0
                bbox_w = max(0.05, norm_box[2] - norm_box[0])
                bbox_h = max(0.05, norm_box[3] - norm_box[1])

                # Illustrative 3D coordinates:
                # X: Horizontal spread (-8.0 to +8.0)
                # Y: Elevation on ground plane based on proxy scale
                # Z: Perspective depth (lower in 2D frame = closer foreground)
                x = round((cx - 0.5) * 16.0, 3)
                z = round((cy - 0.5) * 12.0, 3)
                y = round(max(0.6, bbox_h * 4.0) / 2.0, 3)

                obj_id = f"sp_{eid}_{idx}"
                color = get_category_color(label)
                categories_set.add(label)

                dim_w = round(bbox_w * 3.0, 2)
                dim_h = round(bbox_h * 4.0, 2)
                dim_d = round(bbox_w * 2.0, 2)

                objects.append({
                    "object_id": obj_id,
                    "evidence_id": eid,
                    "source_evidence_id": eid,
                    "evidence_name": ename,
                    "source_evidence_filename": ename,
                    "modality": "image",
                    "label": label,
                    "category": label.lower(),
                    "marker_type": get_marker_type(label),
                    "confidence": round(confidence, 4),
                    "timestamp_seconds": None,
                    "frame_index": None,
                    "box_normalized": norm_box,
                    "box_pixels": raw.get("box_pixels") or raw.get("bbox"),
                    "position": [x, y, z],
                    "spatial_coords": {"x": x, "y": y, "z": z},
                    "estimated_dimensions": [dim_w, dim_h, dim_d],
                    "proxy_dimensions": {
                        "width": dim_w,
                        "height": dim_h,
                        "depth": dim_d,
                    },
                    "color_hex": color,
                })
                ev_object_count += 1

        # ── 2. Video Evidence Detections ──────────────────────────────────────
        elif modality == "video":
            vmeta = analysis.get("video_metadata", {})
            duration = float(vmeta.get("duration", 10.0)) or 10.0
            dim = {"width": vmeta.get("width", 1920), "height": vmeta.get("height", 1080)}
            sampled_frames = analysis.get("sampled_frames", [])

            for f_entry in sampled_frames:
                if not isinstance(f_entry, dict) or f_entry.get("status") == "failed":
                    continue

                ts = float(f_entry.get("timestamp_seconds", 0.0))
                f_idx = f_entry.get("frame_index")
                frame_objs = f_entry.get("objects") or f_entry.get("detections", [])

                for o_idx, raw in enumerate(frame_objs):
                    if not isinstance(raw, dict):
                        continue
                    label = str(raw.get("label", "object")).strip()
                    confidence = float(raw.get("confidence", 0.0))

                    norm_box = raw.get("box_normalized")
                    if not norm_box:
                        box_pixels = raw.get("box_pixels") or raw.get("bbox")
                        norm_box = normalize_box(box_pixels, dim)
                    else:
                        norm_box = [round(float(c), 4) for c in norm_box]

                    cx = (norm_box[0] + norm_box[2]) / 2.0
                    cy = (norm_box[1] + norm_box[3]) / 2.0
                    bbox_w = max(0.05, norm_box[2] - norm_box[0])
                    bbox_h = max(0.05, norm_box[3] - norm_box[1])

                    # Illustrative 3D coordinates:
                    # Video timeline progression layers along Z axis (-8.0 to +8.0)
                    # X axis maps 2D horizontal center
                    x = round((cx - 0.5) * 16.0, 3)
                    time_progress = min(1.0, max(0.0, ts / duration))
                    z = round(-6.0 + (time_progress * 12.0), 3)
                    y = round(max(0.6, bbox_h * 4.0) / 2.0, 3)

                    obj_id = f"sp_{eid}_f{f_idx}_{o_idx}"
                    color = get_category_color(label)
                    categories_set.add(label)

                    dim_w = round(bbox_w * 3.0, 2)
                    dim_h = round(bbox_h * 4.0, 2)
                    dim_d = round(bbox_w * 2.0, 2)

                    objects.append({
                        "object_id": obj_id,
                        "evidence_id": eid,
                        "source_evidence_id": eid,
                        "evidence_name": ename,
                        "source_evidence_filename": ename,
                        "modality": "video",
                        "label": label,
                        "category": label.lower(),
                        "marker_type": get_marker_type(label),
                        "confidence": round(confidence, 4),
                        "timestamp_seconds": round(ts, 2),
                        "frame_index": f_idx,
                        "box_normalized": norm_box,
                        "box_pixels": raw.get("box_pixels") or raw.get("bbox"),
                        "position": [x, y, z],
                        "spatial_coords": {"x": x, "y": y, "z": z},
                        "estimated_dimensions": [dim_w, dim_h, dim_d],
                        "proxy_dimensions": {
                            "width": dim_w,
                            "height": dim_h,
                            "depth": dim_d,
                        },
                        "color_hex": color,
                    })
                    ev_object_count += 1

        if ev_object_count > 0:
            sources_summary.append({
                "evidence_id": eid,
                "filename": ename,
                "modality": modality,
                "object_count": ev_object_count,
            })

    # Dispersion pass: gently spread overlapping objects in the XZ plane
    # so markers remain separated and distinctly selectable
    for i in range(len(objects)):
        for j in range(i + 1, len(objects)):
            o1 = objects[i]
            o2 = objects[j]
            x1, z1 = o1["position"][0], o1["position"][2]
            x2, z2 = o2["position"][0], o2["position"][2]
            dx = x2 - x1
            dz = z2 - z1
            dist_sq = dx * dx + dz * dz
            min_dist = 1.15
            if dist_sq < (min_dist * min_dist):
                dist = max(0.01, dist_sq ** 0.5)
                overlap = min_dist - dist
                nudge_x = round(((dx / dist) if dist > 0.05 else 0.707) * (overlap * 0.5), 3)
                nudge_z = round(((dz / dist) if dist > 0.05 else 0.707) * (overlap * 0.5), 3)
                o1["position"][0] = round(o1["position"][0] - nudge_x, 3)
                o1["position"][2] = round(o1["position"][2] - nudge_z, 3)
                o1["spatial_coords"]["x"] = o1["position"][0]
                o1["spatial_coords"]["z"] = o1["position"][2]
                o2["position"][0] = round(o2["position"][0] + nudge_x, 3)
                o2["position"][2] = round(o2["position"][2] + nudge_z, 3)
                o2["spatial_coords"]["x"] = o2["position"][0]
                o2["spatial_coords"]["z"] = o2["position"][2]

    # Prepare legend
    categories_list = sorted(categories_set)
    legend = [
        {
            "category": cat,
            "marker_type": get_marker_type(cat),
            "color_hex": get_category_color(cat),
            "count": sum(1 for o in objects if o["category"] == cat),
        }
        for cat in categories_list
    ]

    return {
        "status": "success",
        "case_id": case_id,
        "case_name": case_name,
        "disclaimer": {
            "is_metric": False,
            "has_genuine_3d": False,
            "title": "Estimated 3D Spatial Layout (Illustrative 2D-to-3D Projection)",
            "notice": (
                "Forensic Notice: This visualization projects 2D computer vision detections "
                "onto an illustrative 3D workspace. It does NOT represent real-world metric distances, "
                "calibrated LiDAR point clouds, or physical camera calibration. Object depths and elevations "
                "are procedural representations intended solely for visual inspection."
            ),
        },
        "summary": {
            "total_objects": len(objects),
            "categories": categories_list,
            "evidence_sources": sources_summary,
        },
        "legend": legend,
        "objects": objects,
    }
