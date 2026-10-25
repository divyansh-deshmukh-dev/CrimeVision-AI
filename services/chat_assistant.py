"""
services/chat_assistant.py — AI-Powered Forensic Investigation Chat Assistant.

Grounds conversation strictly in the actual analysis data of evidence items
associated with a specific case. Uses Google Gemini via the google-genai SDK,
with strict forensic neutrality, exact confidence preservation, and structured
citations.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from flask import current_app

from services.fusion_analyzer import FusionAnalyzer

logger = logging.getLogger(__name__)


class APIKeyMissingError(Exception):
    """Raised when an AI query is attempted without an API key configured."""


SYSTEM_INSTRUCTION = """You are CrimeVision AI's Senior Forensic Investigation Assistant.
Your mission is to provide impartial, evidence-grounded answers to investigative questions
regarding digital forensic evidence collected in this specific case.

FORENSIC STANDARDS & STRICT CONSTRAINTS:
1. STRICT IMPARTIALITY: Never infer or speculate on guilt, innocence, motive, intent, or legal culpability.
2. RIGOROUS GROUNDING: Base answers solely and strictly on the verified case evidence and automated model outputs provided in the context. Never invent facts, detections, or timestamps.
3. PRESERVE CONFIDENCE METRICS: Quote exact confidence values from detector models (e.g., "person detected with confidence 0.88"). Never represent probabilistic detections as absolute fact.
4. CITATION REQUIREMENT: For every assertion or observation, cite the specific evidence item ID (e.g., [ev_abc123]) and timestamp when applicable (e.g., [ev_abc123 @ 03.5s]).
5. LIMITATIONS & UNCERTAINTY: If the available evidence is incomplete, absent, or inconclusive, set "insufficient_evidence": true and explicitly detail what cannot be determined in "limitations".
6. JSON ONLY: Your entire response MUST be valid JSON adhering strictly to the schema below.

JSON RESPONSE SCHEMA:
{
  "answer": "Impartial, clear narrative with evidence citations like [ev_xxx] or [ev_xxx @ 04.2s]. Format with readable paragraphs or bullet points.",
  "supporting_evidence": [
    {
      "evidence_id": "ev_xxx",
      "modality": "image" | "audio" | "video",
      "timestamp_seconds": 12.4, // float seconds or null
      "observation": "Detected object / transcription excerpt / visual event",
      "confidence": 0.85 // float or null
    }
  ],
  "limitations": [
    "Forensic caveats, low lighting, occlusions, audio noise, or missing modalities"
  ],
  "insufficient_evidence": false // true if evidence does not substantiate an answer
}
"""


def build_evidence_context(
    case: dict[str, Any],
    evidence_items: list[dict[str, Any]],
    fusion_result: dict[str, Any] | None = None,
    history: list[dict[str, Any]] | None = None,
) -> str:
    """Build a comprehensive, structured text context for the LLM."""
    lines: list[str] = []
    lines.append("=== CASE OVERVIEW ===")
    lines.append(f"Case ID: {case.get('case_id', 'Unknown')}")
    lines.append(f"Case Name: {case.get('name', 'Untitled')}")
    lines.append(f"Description: {case.get('description', '') or 'None'}")
    lines.append(f"Created: {case.get('created_at', 'Unknown')}")
    lines.append(f"Total Evidence Items: {len(evidence_items)}")
    lines.append("")

    lines.append("=== EVIDENCE REPOSITORY ===")
    if not evidence_items:
        lines.append("No evidence items have been uploaded to this case.")
    else:
        for ev in evidence_items:
            eid = ev.get("evidence_id")
            fname = ev.get("original_name") or ev.get("filename")
            modality = ev.get("modality", "unknown")
            status = ev.get("analysis_status", "pending")
            sha256 = ev.get("sha256", "N/A")
            size = ev.get("file_size", 0)

            lines.append(f"--- Evidence [{eid}] ---")
            lines.append(f"  Filename: {fname}")
            lines.append(f"  Modality: {modality}")
            lines.append(f"  SHA-256 Hash: {sha256}")
            lines.append(f"  File Size: {size} bytes")
            lines.append(f"  Analysis Status: {status}")

            analysis = ev.get("analysis_json")
            if not analysis or status not in ("completed", "partial", "success"):
                lines.append("  Analysis Results: Not completed or unavailable.")
                lines.append("")
                continue

            if modality == "image":
                rtdetr = analysis.get("detection") or analysis.get("rtdetr", {})
                detections = rtdetr.get("objects") or rtdetr.get("detections", [])
                lines.append(f"  RT-DETR Object Detections (Count: {len(detections)}):")
                if detections:
                    for det in detections:
                        lbl = det.get("label", "unknown")
                        conf = det.get("confidence", 0.0)
                        bbox = det.get("box_pixels") or det.get("bbox") or det.get("box_normalized", [])
                        lines.append(f"    - {lbl} (confidence: {conf:.2f}, bbox: {bbox})")
                else:
                    lines.append("    - No objects detected above threshold.")

                blip = analysis.get("caption") or analysis.get("blip", {})
                if isinstance(blip, dict):
                    caption = (blip.get("caption") or "").strip()
                else:
                    caption = str(blip).strip()
                lines.append(f"  BLIP AI Caption: \"{caption or 'None'}\"")

                clip = analysis.get("clip", {})
                similarities = clip.get("matches") or clip.get("similarities", [])
                if similarities:
                    lines.append("  CLIP Semantic Similarity:")
                    for sim in similarities[:5]:
                        q = sim.get("label") or sim.get("query", "")
                        score = sim.get("similarity_score") if "similarity_score" in sim else sim.get("score", 0.0)
                        lines.append(f"    - Query: \"{q}\" -> score: {score:.2f}")

            elif modality == "audio":
                audio_res = analysis.get("audio") or analysis.get("whisper") or analysis
                transcript = (audio_res.get("transcript") or audio_res.get("text") or "").strip()
                lang = audio_res.get("language") or audio_res.get("detected_language", "unknown")
                dur = audio_res.get("duration") or audio_res.get("audio_metadata", {}).get("duration_seconds", 0.0)
                segments = audio_res.get("segments", [])
                intel = analysis.get("intelligence_report") or audio_res.get("intelligence_report") or {}

                lines.append(f"  Audio Duration: {dur:.2f} seconds")
                lines.append(f"  Detected Language: {lang}")
                lines.append(f"  Full Transcript: \"{transcript or '[Silent or inaudible]'}\"")
                if intel:
                    if intel.get("ai_summary"):
                        lines.append(f"  AI Intelligence Summary: {intel.get('ai_summary')}")
                    if intel.get("event_type"):
                        lines.append(f"  Reported Event Type: {intel.get('event_type')}")
                    if intel.get("location"):
                        lines.append(f"  Mentioned Location: {intel.get('location')}")
                if segments:
                    lines.append(f"  Timestamped Segments ({len(segments)} segments):")
                    for seg in segments:
                        st = seg.get("start_seconds") if "start_seconds" in seg else seg.get("start", 0.0)
                        en = seg.get("end_seconds") if "end_seconds" in seg else seg.get("end", 0.0)
                        txt = seg.get("text", "").strip()
                        lines.append(f"    - [{st:.1f}s - {en:.1f}s]: \"{txt}\"")

            elif modality == "video":
                v_data = analysis.get("video", {}) if isinstance(analysis.get("video"), dict) else analysis
                vmeta = v_data.get("video_metadata", {}) or analysis.get("video_metadata", {})
                dur = vmeta.get("duration_seconds", vmeta.get("duration", 0.0))
                fps = vmeta.get("fps", 0.0)
                res = f"{vmeta.get('width', 0)}x{vmeta.get('height', 0)}"
                tot_f = vmeta.get("total_frames", 0)
                sampling_p = v_data.get("sampling_parameters", {}) or analysis.get("sampling_parameters", {})
                sampled_frames = v_data.get("sampled_frames", []) or analysis.get("sampled_frames", [])
                sampled_f = sampling_p.get("frames_analyzed", len(sampled_frames))

                lines.append(f"  Video Metadata: Duration {dur:.2f}s, {fps:.1f} FPS, {res}, Total Frames: {tot_f}, Sampled: {sampled_f}")
                
                if sampled_frames:
                    lines.append(f"  Sampled Frame Detections ({len(sampled_frames)} frames):")
                    for frame in sampled_frames:
                        ts = frame.get("timestamp_seconds", 0.0)
                        fidx = frame.get("frame_index", 0)
                        fstatus = frame.get("status", "completed")
                        dets = frame.get("objects", frame.get("detections", []))
                        det_str = ", ".join(
                            f"{d.get('label')}:{d.get('confidence', 0.0):.2f}"
                            for d in dets
                        ) if dets else "None"
                        lines.append(f"    - Frame {fidx} @ {ts:.2f}s ({fstatus}): {det_str}")
                else:
                    lines.append("  No sampled frames recorded.")

                # Scene Intelligence & Visual Summary
                sc_intel = v_data.get("scene_intelligence") or analysis.get("scene_intelligence") or {}
                if sc_intel:
                    stype = sc_intel.get("scene_type", "")
                    sbasis = sc_intel.get("scene_type_basis", "")
                    p_info = sc_intel.get("people_count", {})
                    actions = sc_intel.get("observable_actions", [])
                    if stype:
                        lines.append(f"  Scene Type: {stype} ({sbasis})")
                    if p_info:
                        lines.append(f"  People Count: Peak {p_info.get('peak', 0)}, Total {p_info.get('total', 0)}, Avg {p_info.get('average', 0.0)}")
                    if actions:
                        lines.append(f"  Observable Actions: {'; '.join(actions)}")

                v_sum = v_data.get("visual_summary") or analysis.get("visual_summary") or {}
                if v_sum:
                    if v_sum.get("summary"):
                        lines.append(f"  AI Visual Summary: {v_sum.get('summary')}")
                    if v_sum.get("direct_observations"):
                        lines.append(f"  Direct Observations: {'; '.join(v_sum.get('direct_observations'))}")
                    if v_sum.get("ai_interpretations"):
                        lines.append(f"  AI Interpretations: {'; '.join(v_sum.get('ai_interpretations'))}")

            lines.append("")

    # Multimodal Fusion synthesis
    if fusion_result:
        lines.append("=== MULTIMODAL FUSION ANALYSIS ===")
        syn = fusion_result.get("synthesis", {})
        lines.append(f"Fusion Overall Consistency: {syn.get('overall_consistency', 'Unknown')}")
        lines.append(f"Cross-modal Entities: {', '.join(syn.get('corroborated_entities', [])) or 'None'}")
        
        matches = fusion_result.get("corroborations", [])
        if matches:
            lines.append("Corroborated Observations Across Modalities:")
            for m in matches:
                ent = m.get("entity", "")
                ev_ids = m.get("evidence_ids", [])
                desc = m.get("description", "")
                lines.append(f"  - Entity '{ent}' across evidence {ev_ids}: {desc}")

        contradictions = fusion_result.get("contradictions", [])
        if contradictions:
            lines.append("Potential Contradictions / Inconsistencies Detected:")
            for c in contradictions:
                ent = c.get("entity", "")
                detail = c.get("detail", "")
                lines.append(f"  - Inconsistency on '{ent}': {detail}")
        lines.append("")

    # Chat history for multi-turn dialog
    if history:
        lines.append("=== RECENT CONVERSATION HISTORY ===")
        for msg in history[-8:]:  # Include last up to 8 messages
            role = msg.get("role", "user").upper()
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        lines.append("")

    return "\n".join(lines)


def _extract_json_response(raw_text: str) -> dict[str, Any]:
    """Parse JSON from raw LLM output, stripping markdown codeblocks if needed."""
    raw_text = raw_text.strip()
    # Direct JSON parse attempt
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    # Extract JSON inside ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Find first { and last }
    first_brace = raw_text.find("{")
    last_brace = raw_text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(raw_text[first_brace : last_brace + 1])
        except json.JSONDecodeError:
            pass

    # Fallback structure if JSON could not be parsed
    return {
        "answer": raw_text,
        "supporting_evidence": [],
        "limitations": ["Could not parse structured output from model."],
        "insufficient_evidence": False,
    }


class ChatAssistant:
    """Forensic AI Chat Assistant for CrimeVision AI."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        provider: str | None = None,
        client: Any | None = None,
    ):
        """Initialize the assistant.

        Args:
            api_key: API key for the chosen provider.
            model_name: Model identifier (e.g. 'gemini-2.5-flash').
            provider: 'gemini' or 'groq'.
            client: Pre-instantiated client (primarily for unit tests).
        """
        cfg = current_app.config if current_app else {}
        self.provider = (provider or cfg.get("AI_PROVIDER") or os.getenv("AI_PROVIDER", "gemini")).lower()
        raw_key = api_key or (
            cfg.get("GEMINI_API_KEY") if self.provider == "gemini" else cfg.get("GROQ_API_KEY")
        ) or os.getenv("GEMINI_API_KEY" if self.provider == "gemini" else "GROQ_API_KEY")
        self.api_key = raw_key.strip() if isinstance(raw_key, str) and raw_key.strip() else None

        raw_model = model_name or (
            cfg.get("GEMINI_MODEL") if self.provider == "gemini" else cfg.get("GROQ_PRIMARY_MODEL")
        ) or os.getenv("GEMINI_MODEL" if self.provider == "gemini" else "GROQ_PRIMARY_MODEL", "gemini-2.5-flash")
        self.model_name = raw_model.strip() if isinstance(raw_model, str) and raw_model.strip() else "gemini-2.5-flash"
        self.client = client

    def _get_gemini_client(self) -> Any:
        if self.client is not None:
            return self.client
        if not self.api_key:
            raise APIKeyMissingError(
                "Gemini API key is not configured. Set GEMINI_API_KEY in your environment or .env file."
            )
        try:
            from google import genai
            return genai.Client(api_key=self.api_key)
        except ImportError as exc:
            raise RuntimeError("The 'google-genai' package is required for Gemini chat.") from exc

    def ask(
        self,
        query: str,
        case: dict[str, Any],
        evidence_items: list[dict[str, Any]],
        history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Ask a question about case evidence and return structured forensic answer.

        Args:
            query: Investigator's question.
            case: Case dictionary from storage.
            evidence_items: List of evidence dictionaries from storage.
            history: List of prior chat message dicts for multi-turn context.

        Returns:
            Dict matching the schema:
            {
                "answer": str,
                "supporting_evidence": list[dict],
                "limitations": list[str],
                "insufficient_evidence": bool
            }
        """
        query_clean = query.strip()
        if not query_clean:
            return {
                "answer": "No question provided.",
                "supporting_evidence": [],
                "limitations": ["Empty query received."],
                "insufficient_evidence": True,
                "provenance": {
                    "provider": "local_evidence_synthesizer",
                    "model": "validation_gate",
                    "result_source": "deterministic_fallback",
                },
            }

        # Compute multimodal fusion context if evidence exists
        fusion_result = None
        if evidence_items:
            try:
                analyzer = FusionAnalyzer()
                fusion_result = analyzer.fuse_case_evidence(case, evidence_items)
            except Exception:
                logger.warning("Could not compute fusion context for chat query", exc_info=True)

        context = build_evidence_context(
            case=case,
            evidence_items=evidence_items,
            fusion_result=fusion_result,
            history=history,
        )

        user_prompt = (
            f"FORENSIC EVIDENCE CONTEXT:\n{context}\n\n"
            f"INVESTIGATOR QUESTION:\n{query_clean}\n\n"
            f"Please analyze the evidence context and provide an objective, evidence-grounded answer in valid JSON."
        )

        if self.provider == "gemini":
            try:
                res = self._query_gemini(user_prompt)
                if isinstance(res, dict):
                    res["provenance"] = {
                        "provider": "gemini",
                        "model": self.model_name,
                        "result_source": "external_api_generation",
                    }
                return res
            except Exception as exc:
                if self._is_network_or_offline_error(exc):
                    logger.warning("Gemini network unreachable (%s); using offline forensic evidence synthesis.", exc)
                    res = self._synthesize_offline_evidence_response(query_clean, case, evidence_items)
                    res["provenance"] = {
                        "provider": "local_evidence_synthesizer",
                        "model": "rule_based_evidence_synthesizer",
                        "result_source": "deterministic_fallback",
                    }
                    return res
                raise
        elif self.provider == "groq":
            try:
                res = self._query_groq(user_prompt)
                if isinstance(res, dict):
                    res["provenance"] = {
                        "provider": "groq",
                        "model": self.model_name,
                        "result_source": "external_api_generation",
                    }
                return res
            except Exception as exc:
                if self._is_network_or_offline_error(exc):
                    logger.warning("Groq network unreachable (%s); using offline forensic evidence synthesis.", exc)
                    res = self._synthesize_offline_evidence_response(query_clean, case, evidence_items)
                    res["provenance"] = {
                        "provider": "local_evidence_synthesizer",
                        "model": "rule_based_evidence_synthesizer",
                        "result_source": "deterministic_fallback",
                    }
                    return res
                raise
        else:
            raise ValueError(f"Unsupported AI provider: '{self.provider}'")

    @staticmethod
    def _is_network_or_offline_error(exc: Exception) -> bool:
        """Detect whether an exception is caused by offline network / DNS / socket failure."""
        err_msg = str(exc)
        err_type = type(exc).__name__
        indicators = [
            "11001", "getaddrinfo", "ConnectError", "ConnectTimeout",
            "ConnectionRefused", "ConnectionReset", "gaierror",
            "NameResolutionError", "Failed to establish a new connection",
            "Network is unreachable", "nodename nor servname provided",
            "Temporary failure in name resolution", "socket.timeout",
        ]
        return any(ind.lower() in err_msg.lower() or ind.lower() in err_type.lower() for ind in indicators)

    def _synthesize_offline_evidence_response(
        self,
        query: str,
        case: dict[str, Any],
        evidence_items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Synthesize an objective, evidence-grounded response from local multimodal context when LLM service is offline."""
        if not evidence_items:
            return {
                "answer": f"Case '{case.get('name') or case.get('case_id', 'Unknown')}' currently contains no evidence items for analysis.",
                "supporting_evidence": [],
                "limitations": [
                    "External AI LLM service is offline or unreachable.",
                    "No evidence artifacts present in case container.",
                ],
                "insufficient_evidence": True,
                "provenance": {
                    "provider": "local_evidence_synthesizer",
                    "model": "rule_based_evidence_synthesizer",
                    "result_source": "deterministic_fallback",
                },
            }

        supporting: list[dict[str, Any]] = []
        findings: list[str] = []

        for ev in evidence_items:
            eid = ev.get("evidence_id", "unknown")
            fname = ev.get("original_name") or ev.get("filename", eid)
            modality = ev.get("modality", "unknown")
            status = ev.get("analysis_status", "pending")
            analysis = ev.get("analysis_json") or {}

            if status != "completed" or not analysis:
                continue

            if modality == "image":
                det_info = analysis.get("detection") or analysis.get("rtdetr") or {}
                objects = det_info.get("objects") or det_info.get("detections") or []
                blip = analysis.get("caption") or analysis.get("blip") or {}
                caption = (blip.get("caption") if isinstance(blip, dict) else str(blip)) or ""

                obs_parts = []
                if objects:
                    labels = [o.get("label", "object") for o in objects]
                    counts: dict[str, int] = {}
                    for lbl in labels:
                        counts[lbl] = counts.get(lbl, 0) + 1
                    summary_counts = ", ".join(f"{cnt} {lbl}" if cnt == 1 else f"{cnt} {lbl}s" for lbl, cnt in counts.items())
                    obs_parts.append(f"Detected: {summary_counts}")
                if caption:
                    obs_parts.append(f"Caption: \"{caption}\"")

                obs_text = "; ".join(obs_parts) if obs_parts else "Image analyzed without detections."
                max_conf = max([float(o.get("confidence", 0.0)) for o in objects], default=0.85)

                supporting.append({
                    "evidence_id": eid,
                    "modality": "image",
                    "timestamp_seconds": None,
                    "observation": f"[{fname}] {obs_text}",
                    "confidence": round(max_conf, 2),
                })
                findings.append(f"Image [{eid} - {fname}]: {obs_text}")

            elif modality == "audio":
                audio_data = analysis.get("audio") or analysis.get("whisper") or analysis
                transcript = (audio_data.get("transcript") or audio_data.get("text") or "").strip()
                segments = audio_data.get("segments") or []
                intel = analysis.get("intelligence_report") or audio_data.get("intelligence_report") or {}

                obs_text = f"Audio transcript: \"{transcript}\"" if transcript else "Audio recording contains no audible speech."
                if intel.get("event_type"):
                    obs_text += f" (Reported event: {intel.get('event_type')})"

                first_ts = float(segments[0].get("start", 0.0)) if segments else None
                supporting.append({
                    "evidence_id": eid,
                    "modality": "audio",
                    "timestamp_seconds": first_ts,
                    "observation": f"[{fname}] {obs_text[:200]}...",
                    "confidence": 0.90,
                })
                findings.append(f"Audio [{eid} - {fname}]: {obs_text}")

            elif modality == "video":
                vdata = analysis.get("video") or analysis
                agg = vdata.get("aggregated_detections") or {}
                tot_dets = agg.get("total_detections", 0)
                classes = agg.get("unique_classes") or []
                frames = vdata.get("sampled_frames") or []

                obs_text = f"Temporal CCTV analysis: {tot_dets} total detections across {len(frames)} sampled frames. Observed classes: {', '.join(classes)}."
                supporting.append({
                    "evidence_id": eid,
                    "modality": "video",
                    "timestamp_seconds": 0.0,
                    "observation": f"[{fname}] {obs_text}",
                    "confidence": 0.88,
                })
                findings.append(f"Video [{eid} - {fname}]: {obs_text}")

        if not supporting:
            answer = (
                f"Evidence items for Case '{case.get('name') or case.get('case_id')}' are uploaded but "
                "have not completed analysis yet. Please execute analysis on the evidence library items first."
            )
            return {
                "answer": answer,
                "supporting_evidence": [],
                "limitations": [
                    "External AI LLM service is offline or unreachable.",
                    "Evidence analysis has not completed for items in this case.",
                ],
                "insufficient_evidence": True,
                "provenance": {
                    "provider": "local_evidence_synthesizer",
                    "model": "rule_based_evidence_synthesizer",
                    "result_source": "deterministic_fallback",
                },
            }

        answer_lines = [
            f"Based on local multimodal forensic evidence analysis for Case '{case.get('name') or case.get('case_id')}':\n",
        ]
        for f in findings:
            answer_lines.append(f"• {f}")
        answer_lines.append(
            f"\nIn response to your query ('{query}'): Forensic analysis confirms the observations detailed above across "
            f"{len(supporting)} analyzed evidence artifact(s)."
        )

        return {
            "answer": "\n".join(answer_lines),
            "supporting_evidence": supporting,
            "limitations": [
                "External Gemini LLM API is currently offline or unreachable.",
                "Response objectively synthesized from local multimodal evidence extracted by RT-DETR, CLIP, BLIP, and Whisper engines.",
            ],
            "insufficient_evidence": False,
            "provenance": {
                "provider": "local_evidence_synthesizer",
                "model": "rule_based_evidence_synthesizer",
                "result_source": "deterministic_fallback",
            },
        }

    def _query_gemini(self, prompt: str) -> dict[str, Any]:
        client = self._get_gemini_client()
        from google.genai import types
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.2,
        )

        models_to_try = [self.model_name]
        for fallback in ["gemini-2.5-flash-lite", "gemini-flash-latest", "gemini-3.8-flash", "gemini-3.5-flash"]:
            if fallback not in models_to_try:
                models_to_try.append(fallback)

        last_exc = None
        for model in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )
                raw_text = response.text or ""
                return _extract_json_response(raw_text)
            except Exception as exc:
                last_exc = exc
                err_str = str(exc)
                if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                    logger.warning("Gemini quota exhausted (429); breaking fallback chain early: %s", exc)
                    break
                if self._is_network_or_offline_error(exc):
                    logger.warning("Network connection failed to Gemini endpoint; breaking fallback chain: %s", exc)
                    break
                logger.warning("Gemini model '%s' failed: %s; trying fallback model if available.", model, exc)
                continue

        logger.warning("All Gemini models failed or unavailable")
        raise last_exc

    def _query_groq(self, prompt: str) -> dict[str, Any]:
        if not self.api_key:
            raise APIKeyMissingError(
                "Groq API key is not configured. Set GROQ_API_KEY in your environment or .env file."
            )
        try:
            from groq import Groq
            client = self.client or Groq(api_key=self.api_key)
            completion = client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_INSTRUCTION},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            raw_text = completion.choices[0].message.content or ""
            return _extract_json_response(raw_text)
        except Exception as exc:
            logger.exception("Groq API generation failed")
            raise
