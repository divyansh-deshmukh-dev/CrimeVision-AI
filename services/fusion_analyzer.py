"""
services/fusion_analyzer.py — Multimodal Evidence Fusion Service for CrimeVision AI (Phase 6).

Correlates observations across multiple forensic modalities (Image, Audio, Video) belonging to the same case:
  - Normalizes observations from RT-DETR, CLIP, BLIP, Whisper, and OpenCV frame sampling.
  - Cross-modal category matching: detects identical or related entity categories across image & video.
  - Cross-modal temporal association: correlates timestamped Whisper audio segments with video sampled frame timestamps.
  - Cross-modal semantic and scene agreement/conflict detection (e.g. caption vs scene classification).
  - Identifies repeated findings, potential contradictions, and unresolved investigative questions.
  - Strict forensic safeguards:
      * Matching entity categories do NOT prove identical physical objects or person identity.
      * Temporal co-occurrence does NOT establish causation or guilt.
      * Preserves original source confidence scores and evidence references without artificial synthetic averaging.
      * Transparently reports modality coverage, limitations, and unanalyzed gaps.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Temporal proximity window for aligning audio segments with video timestamps (in seconds)
TEMPORAL_WINDOW_SECONDS: float = 3.0

# Antonym / Contradiction keywords for simple explainable scene conflict detection
CONTRADICTION_PAIRS = [
    ("day", "night"),
    ("daylight", "nighttime"),
    ("indoor", "outdoor"),
    ("inside", "outside"),
    ("empty", "crowded"),
    ("peaceful", "violent"),
]


class FusionAnalyzer:
    """Deterministic, explainable rule-based Multimodal Forensic Evidence Fusion Engine."""

    def __init__(self, temporal_window: float = TEMPORAL_WINDOW_SECONDS):
        self.temporal_window = temporal_window

    def fuse_case_evidence(
        self,
        case: Dict[str, Any],
        evidence_items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Execute multimodal forensic fusion across all evidence items in a case.

        Parameters
        ----------
        case: dict
            Case metadata dictionary (case_id, name, etc.).
        evidence_items: list of dict
            List of evidence records from SQLite, each with modality, analysis_status, analysis_json, etc.

        Returns
        -------
        dict
            Structured fusion intelligence report.
        """
        case_id = case.get("case_id", "unknown")
        analyzed_at = datetime.now(timezone.utc).isoformat()

        # 1. Tally modality coverage and active evidence
        modality_coverage = {
            "image": {"total": 0, "analyzed": 0, "status": "unavailable"},
            "audio": {"total": 0, "analyzed": 0, "status": "unavailable"},
            "video": {"total": 0, "analyzed": 0, "status": "unavailable"},
        }

        included_evidence_ids = []
        normalized_observations: List[Dict[str, Any]] = []

        for ev in evidence_items:
            eid = ev.get("evidence_id")
            modality = ev.get("modality", "unknown")
            status = ev.get("analysis_status", "pending")
            analysis = ev.get("analysis_json") or {}

            if modality in modality_coverage:
                modality_coverage[modality]["total"] += 1
                if status in ("completed", "partial", "success") and analysis:
                    modality_coverage[modality]["analyzed"] += 1

            included_evidence_ids.append({
                "evidence_id": eid,
                "original_name": ev.get("original_name"),
                "modality": modality,
                "analysis_status": status,
                "sha256": ev.get("sha256"),
            })

            # Extract normalized observations
            obs = self._normalize_observations(ev)
            normalized_observations.extend(obs)

        # Update modality status strings
        for mod, counts in modality_coverage.items():
            if counts["total"] == 0:
                counts["status"] = "unavailable"
            elif counts["analyzed"] == counts["total"]:
                counts["status"] = "analyzed"
            elif counts["analyzed"] > 0:
                counts["status"] = "partial"
            else:
                counts["status"] = "pending"

        analyzed_modalities_count = sum(1 for m in modality_coverage.values() if m["analyzed"] > 0)

        # 2. Extract Cross-Modal Corroborations & Associations
        cross_modal_associations = self._find_cross_modal_associations(normalized_observations)

        # 3. Detect Temporal Audio-Video Alignments
        temporal_associations = self._find_temporal_associations(normalized_observations)

        # 4. Detect Potential Semantic Contradictions
        potential_contradictions = self._detect_potential_contradictions(normalized_observations)

        # 5. Formulate Unresolved Questions / Investigative Gaps
        unresolved_questions = self._formulate_unresolved_questions(
            modality_coverage,
            cross_modal_associations,
            potential_contradictions,
            len(evidence_items),
        )

        # 6. Overall Fusion Status
        if len(evidence_items) == 0:
            fusion_status = "empty"
        elif analyzed_modalities_count == 0:
            fusion_status = "pending"
        elif analyzed_modalities_count == 1:
            fusion_status = "single_modality"
        elif any(c["analyzed"] < c["total"] for c in modality_coverage.values() if isinstance(c, dict) and c.get("total", 0) > 0):
            fusion_status = "partial"
        else:
            fusion_status = "completed"

        # Provide dual-aliased keys for frontend convenience
        modality_coverage["image_count"] = modality_coverage["image"]["total"]
        modality_coverage["analyzed_image_count"] = modality_coverage["image"]["analyzed"]
        modality_coverage["audio_count"] = modality_coverage["audio"]["total"]
        modality_coverage["analyzed_audio_count"] = modality_coverage["audio"]["analyzed"]
        modality_coverage["video_count"] = modality_coverage["video"]["total"]
        modality_coverage["analyzed_video_count"] = modality_coverage["video"]["analyzed"]

        return {
            "case_id": case_id,
            "case_name": case.get("name", "Untitled Case"),
            "status": fusion_status,
            "analyzed_at": analyzed_at,
            "evidence_count": len(evidence_items),
            "total_evidence_items": len(evidence_items),
            "analyzed_modalities_count": analyzed_modalities_count,
            "modality_coverage": modality_coverage,
            "evidence_items": included_evidence_ids,
            "observation_summary": {
                "total_observations": len(normalized_observations),
                "image_observations": sum(1 for o in normalized_observations if o["modality"] == "image"),
                "audio_observations": sum(1 for o in normalized_observations if o["modality"] == "audio"),
                "video_observations": sum(1 for o in normalized_observations if o["modality"] == "video"),
            },
            "cross_modal_associations": cross_modal_associations,
            "cross_modal_corroborations": cross_modal_associations,
            "temporal_associations": temporal_associations,
            "temporal_alignments": temporal_associations,
            "potential_contradictions": potential_contradictions,
            "divergences_and_contradictions": potential_contradictions,
            "unresolved_questions": unresolved_questions,
            "unresolved_investigative_questions": unresolved_questions,
            "limitations_and_warnings": [
                "Matching entity categories across modalities represent class correlation, NOT physical identity verification.",
                "Temporal proximity between audio and video observations indicates potential co-occurrence, NOT causation or intent.",
                "Missing modalities or unanalyzed items must NOT be interpreted as negative evidence that an event did not occur.",
                "Observations are machine-generated approximations from deep learning models and require independent forensic verification.",
            ],
        }

    def _normalize_observations(self, ev: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Flatten modality-specific analysis records into standardized observation dictionaries."""
        eid = ev.get("evidence_id")
        name = ev.get("original_name")
        modality = ev.get("modality")
        analysis = ev.get("analysis_json") or {}

        observations = []

        if modality == "image":
            # RT-DETR detections
            det = analysis.get("detection") or {}
            for obj in det.get("objects", []):
                observations.append({
                    "evidence_id": eid,
                    "evidence_name": name,
                    "modality": "image",
                    "observation_type": "object_detection",
                    "category": obj.get("label", "unknown").lower(),
                    "confidence": obj.get("confidence", 0.0),
                    "box_pixels": obj.get("box_pixels"),
                    "timestamp_seconds": None,
                    "description": f"Detected object class '{obj.get('label')}' with {obj.get('confidence', 0.0):.1%} confidence",
                    "model": det.get("model", "RT-DETR"),
                })

            # BLIP Caption
            cap = analysis.get("caption") or {}
            if cap.get("status") == "success" and cap.get("caption"):
                observations.append({
                    "evidence_id": eid,
                    "evidence_name": name,
                    "modality": "image",
                    "observation_type": "scene_caption",
                    "category": "scene_description",
                    "confidence": None,
                    "timestamp_seconds": None,
                    "description": cap.get("caption"),
                    "model": cap.get("model", "BLIP"),
                })

            # CLIP Scene Matches
            clip = analysis.get("clip") or {}
            if clip.get("status") == "success":
                for match in clip.get("matches", []):
                    observations.append({
                        "evidence_id": eid,
                        "evidence_name": name,
                        "modality": "image",
                        "observation_type": "scene_similarity",
                        "category": match.get("label", "unknown").lower(),
                        "confidence": match.get("similarity_score", 0.0),
                        "timestamp_seconds": None,
                        "description": f"Scene similarity score {match.get('similarity_score', 0.0):.1%} for '{match.get('label')}'",
                        "model": "CLIP",
                    })

        elif modality == "audio":
            audio_res = analysis.get("audio") or analysis.get("whisper") or {}
            transcript = audio_res.get("transcript") or analysis.get("whisper", {}).get("transcript") or ""
            segments = audio_res.get("segments") or analysis.get("whisper", {}).get("segments") or []
            intel = analysis.get("intelligence_report") or audio_res.get("intelligence_report") or {}

            if transcript:
                observations.append({
                    "evidence_id": eid,
                    "evidence_name": name,
                    "modality": "audio",
                    "observation_type": "full_transcript",
                    "category": "speech",
                    "confidence": None,
                    "timestamp_seconds": None,
                    "description": transcript,
                    "language": audio_res.get("language"),
                    "model": audio_res.get("model", "Whisper"),
                })

            for seg in segments:
                s_start = seg.get("start_seconds")
                s_end = seg.get("end_seconds")
                observations.append({
                    "evidence_id": eid,
                    "evidence_name": name,
                    "modality": "audio",
                    "observation_type": "transcript_segment",
                    "category": "spoken_segment",
                    "confidence": None,
                    "timestamp_seconds": s_start,
                    "end_timestamp_seconds": s_end,
                    "description": seg.get("text", ""),
                    "language": audio_res.get("language"),
                    "model": audio_res.get("model", "Whisper"),
                })

            # Physical entities identified in acoustic speech or acoustic report
            keyword_entities = [
                ("car", ["car", "automobile", "sedan", "vehicle"]),
                ("motorcycle", ["motorcycle", "motorbike", "bike"]),
                ("person", ["person", "man", "woman", "individual", "pedestrian"]),
                ("bicycle", ["bicycle", "cyclist", "cycle"]),
                ("bus", ["bus"]),
                ("truck", ["truck", "van"]),
                ("knife", ["knife", "blade", "weapon"]),
                ("gun", ["gun", "pistol", "firearm"]),
                ("backpack", ["backpack", "bag"]),
            ]
            full_audio_text = f"{transcript} {intel.get('ai_summary', '')}".lower()
            for entity_cat, keywords in keyword_entities:
                if any(kw in full_audio_text for kw in keywords):
                    observations.append({
                        "evidence_id": eid,
                        "evidence_name": name,
                        "modality": "audio",
                        "observation_type": "audio_entity_mention",
                        "category": entity_cat,
                        "confidence": None,
                        "timestamp_seconds": None,
                        "description": f"Acoustic testimony refers to {entity_cat} ('{keywords[0]}')",
                        "model": "Whisper",
                    })

        elif modality == "video":
            vid_res = analysis.get("video") or {}
            sampled_frames = vid_res.get("sampled_frames", [])

            for sf in sampled_frames:
                t_sec = sf.get("timestamp_seconds")
                f_idx = sf.get("frame_index")
                for obj in sf.get("objects", []):
                    observations.append({
                        "evidence_id": eid,
                        "evidence_name": name,
                        "modality": "video",
                        "observation_type": "frame_detection",
                        "category": obj.get("label", "unknown").lower(),
                        "confidence": obj.get("confidence", 0.0),
                        "box_pixels": obj.get("box_pixels"),
                        "timestamp_seconds": t_sec,
                        "frame_index": f_idx,
                        "description": f"Frame #{f_idx} ({t_sec:.2f}s) detected '{obj.get('label')}' ({obj.get('confidence', 0.0):.1%})",
                        "model": "RT-DETR",
                    })

        return observations

    def _find_cross_modal_associations(self, observations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify entity categories that appear across distinct evidence modalities (e.g. Image & Video)."""
        category_map: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

        for obs in observations:
            cat = obs.get("category")
            modality = obs.get("modality")
            obs_type = obs.get("observation_type")

            # Correlate detection and entity classes across modalities
            if obs_type not in ("object_detection", "frame_detection", "audio_entity_mention"):
                continue

            if not cat or cat in ("unknown", "scene_description", "speech", "spoken_segment"):
                continue

            if cat not in category_map:
                category_map[cat] = {}
            if modality not in category_map[cat]:
                category_map[cat][modality] = []

            category_map[cat][modality].append(obs)

        associations = []
        for cat, mod_dict in category_map.items():
            modalities = list(mod_dict.keys())
            # Cross-modal match if detected across >= 2 modalities
            if len(modalities) >= 2:
                supporting_items = []
                for mod, obs_list in mod_dict.items():
                    for o in obs_list:
                        supporting_items.append({
                            "evidence_id": o["evidence_id"],
                            "evidence_name": o["evidence_name"],
                            "modality": o["modality"],
                            "confidence": o.get("confidence"),
                            "timestamp_seconds": o.get("timestamp_seconds"),
                        })

                desc = (
                    f"Object category '{cat}' was corroborated independently across {len(modalities)} "
                    f"modalities ({', '.join(modalities)})."
                )
                associations.append({
                    "entity": cat,
                    "category": cat,
                    "relationship_type": "cross_modal_category_corroboration",
                    "modalities_involved": modalities,
                    "observation": desc,
                    "description": desc,
                    "evidence_references": supporting_items,
                    "forensic_qualification": (
                        f"Category match for '{cat}' corroborates presence of this object type across evidence, "
                        "but does NOT establish that the instances are the exact same physical entity."
                    ),
                })

        return associations

    def _find_temporal_associations(self, observations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Correlate timestamped Whisper audio segments with video sampled frame detections."""
        audio_segs = [o for o in observations if o["observation_type"] == "transcript_segment" and o.get("timestamp_seconds") is not None]
        video_dets = [o for o in observations if o["observation_type"] == "frame_detection" and o.get("timestamp_seconds") is not None]

        temporal_associations = []

        for aseg in audio_segs:
            a_start = aseg["timestamp_seconds"]
            a_end = aseg.get("end_timestamp_seconds") or (a_start + self.temporal_window)

            matching_video_frames = []
            for vdet in video_dets:
                v_time = vdet["timestamp_seconds"]
                # Check if video frame timestamp falls within or near audio segment time window
                if (a_start - self.temporal_window) <= v_time <= (a_end + self.temporal_window):
                    matching_video_frames.append(vdet)

            if matching_video_frames:
                # Group matched objects
                detected_entities = list({v["category"] for v in matching_video_frames})
                time_range_str = f"[{a_start:.2f}s - {a_end:.2f}s]"

                temporal_associations.append({
                    "relationship_type": "temporal_audio_video_alignment",
                    "timestamp": time_range_str,
                    "audio_timestamp_range": [a_start, a_end],
                    "speech_excerpt": aseg["description"],
                    "correlated_video_objects": detected_entities,
                    "video_frames_matched": len(matching_video_frames),
                    "audio_evidence_id": aseg["evidence_id"],
                    "video_evidence_id": matching_video_frames[0]["evidence_id"],
                    "description": (
                        f"Audio speech '{aseg['description']}' at {time_range_str} temporally aligns with "
                        f"video frame detections containing {', '.join(detected_entities)}."
                    ),
                    "forensic_qualification": (
                        "Temporal co-occurrence indicates that speech and visual entities existed within the same "
                        "time window, but does NOT establish speaker identity or conversational causation."
                    ),
                })

        return temporal_associations

    def _detect_potential_contradictions(self, observations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Flag contradictory observations across evidence items (e.g. daytime outdoors vs nighttime indoors)."""
        captions_and_scenes = []
        for o in observations:
            if o["observation_type"] in ("scene_caption", "scene_similarity"):
                captions_and_scenes.append(o)

        contradictions = []
        for i in range(len(captions_and_scenes)):
            for j in range(i + 1, len(captions_and_scenes)):
                o1 = captions_and_scenes[i]
                o2 = captions_and_scenes[j]

                # Don't compare same evidence against itself
                if o1["evidence_id"] == o2["evidence_id"]:
                    continue

                t1 = o1["description"].lower()
                t2 = o2["description"].lower()

                for term_a, term_b in CONTRADICTION_PAIRS:
                    if (term_a in t1 and term_b in t2) or (term_b in t1 and term_a in t2):
                        expl = (
                            f"Evidence item '{o1['evidence_name']}' describes scene as '{term_a if term_a in t1 else term_b}' "
                            f"while evidence item '{o2['evidence_name']}' indicates '{term_b if term_a in t1 else term_a}'."
                        )
                        contradictions.append({
                            "contradiction_type": "environmental_descriptor_divergence",
                            "divergence": expl,
                            "explanation": expl,
                            "term_a": term_a,
                            "term_b": term_b,
                            "evidence_a": {"evidence_id": o1["evidence_id"], "name": o1["evidence_name"], "description": o1["description"]},
                            "evidence_b": {"evidence_id": o2["evidence_id"], "name": o2["evidence_name"], "description": o2["description"]},
                            "action_required": "Human forensic review required to verify capture timestamps, indoor/outdoor transition, or lighting changes.",
                        })

        return contradictions

    def _formulate_unresolved_questions(
        self,
        coverage: Dict[str, Any],
        cross_modal_assocs: List[Dict[str, Any]],
        contradictions: List[Dict[str, Any]],
        evidence_count: int,
    ) -> List[str]:
        """Generate explainable forensic questions and investigative gaps for examiners."""
        questions = []

        # Check unanalyzed or missing modalities
        missing_mods = [m for m, val in coverage.items() if val["total"] == 0]
        if missing_mods:
            questions.append(
                f"No evidence for modality/modalities [{', '.join(missing_mods)}] is available in this case. "
                "Observations cannot be corroborated across missing channels."
            )

        pending_mods = [m for m, val in coverage.items() if val["status"] == "pending"]
        if pending_mods:
            questions.append(
                f"Modality/modalities [{', '.join(pending_mods)}] have uploaded evidence that has not yet been analyzed. "
                "Run analysis pipeline to enable full multimodal fusion."
            )

        if contradictions:
            questions.append(
                f"{len(contradictions)} environmental divergence(s) flagged across evidence items. "
                "Did incidents occur at different times of day or in separate locations?"
            )

        if not cross_modal_assocs and evidence_count > 1:
            questions.append(
                "No overlapping object categories were detected across evidence items. "
                "Evidence items may depict distinct camera angles, separate rooms, or independent events."
            )

        if coverage["audio"]["analyzed"] > 0 and coverage["video"]["analyzed"] == 0:
            questions.append("Audio transcript is available but lacks corresponding video evidence for visual corroboration.")

        return questions
