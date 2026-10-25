"""
services/pdf_report.py — Forensic PDF Report Generator for CrimeVision AI (Phase 3).

Generates formal, multi-page forensic reports utilizing ReportLab:
  - Header & Case Information
  - Evidence Item Verification & SHA-256 Checksum
  - Visual Evidence with optional Bounding Box Annotations
  - RT-DETR Detection Tables (Coordinates, Confidence, Class Counts)
  - BLIP Scene Caption Findings
  - CLIP Zero-Shot Scene Classification & Similarity Scores
  - Scientific & Legal Uncertainty Disclaimers
"""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from PIL import Image as PILImage, ImageDraw

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


class ForensicReportGenerator:
    """Generates structured PDF forensic reports from case and evidence records."""

    def __init__(self, output_path: Path):
        self.output_path = output_path
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self) -> None:
        """Define forensic report typography and color palettes."""
        self.title_style = ParagraphStyle(
            "ForensicTitle",
            parent=self.styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0F172A"),
            spaceAfter=4,
        )
        self.subtitle_style = ParagraphStyle(
            "ForensicSubtitle",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#2563EB"),
            spaceAfter=12,
        )
        self.section_heading = ParagraphStyle(
            "ForensicSection",
            parent=self.styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#1E293B"),
            spaceBefore=12,
            spaceAfter=6,
        )
        self.body_style = ParagraphStyle(
            "ForensicBody",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#334155"),
        )
        self.mono_style = ParagraphStyle(
            "ForensicMono",
            parent=self.styles["Normal"],
            fontName="Courier",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#0F172A"),
        )
        self.callout_style = ParagraphStyle(
            "ForensicCallout",
            parent=self.styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#1E293B"),
        )
        self.disclaimer_style = ParagraphStyle(
            "ForensicDisclaimer",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#64748B"),
        )

    def _draw_annotated_image(self, source_path: Path, objects: List[Dict[str, Any]], target_path: Path) -> Optional[Path]:
        """Produce an annotated version of the image with bounding boxes drawn."""
        try:
            with PILImage.open(source_path) as img:
                annotated = img.convert("RGB")
                draw = ImageDraw.Draw(annotated)
                w, h = annotated.size

                for obj in objects:
                    coords = obj.get("box_pixels")
                    if coords and len(coords) == 4:
                        x1, y1, x2, y2 = coords
                        label = f"{obj.get('label', 'object')} ({int(obj.get('confidence', 0)*100)}%)"
                        draw.rectangle([x1, y1, x2, y2], outline="#2563EB", width=max(2, int(w / 400)))
                        draw.rectangle([x1, max(0, y1 - 16), x1 + len(label) * 8, y1], fill="#0F172A")
                        draw.text((x1 + 3, max(0, y1 - 14)), label, fill="#38BDF8")

                target_path.parent.mkdir(parents=True, exist_ok=True)
                annotated.save(target_path, format="JPEG", quality=85)
                return target_path
        except Exception:
            return None

    def build_report(
        self,
        case: Dict[str, Any],
        evidence_items: List[Dict[str, Any]],
        uploads_dir: Path,
        scratch_dir: Path,
        fusion_result: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """Assemble and write the multi-page forensic PDF."""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        doc = SimpleDocTemplate(
            str(self.output_path),
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        story = []
        gen_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # ── 1. Document Header ──────────────────────────────────────────────
        story.append(Paragraph("CRIMEVISION AI — FORENSIC ANALYSIS REPORT", self.title_style))
        story.append(Paragraph("CONFIDENTIAL & AUDIT-TRACKED DIGITAL EVIDENCE INTELLIGENCE", self.subtitle_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563EB"), spaceAfter=10))

        # ── 2. Case Overview Summary Table ──────────────────────────────────
        case_data = [
            [
                Paragraph("<b>Case Identifier:</b>", self.body_style),
                Paragraph(f"<font name='Courier'>{case.get('case_id', 'Unknown')}</font>", self.body_style),
                Paragraph("<b>Report Date:</b>", self.body_style),
                Paragraph(gen_timestamp, self.body_style),
            ],
            [
                Paragraph("<b>Case Name:</b>", self.body_style),
                Paragraph(case.get("name", "Untitled Case"), self.body_style),
                Paragraph("<b>Case Status:</b>", self.body_style),
                Paragraph(case.get("status", "active").upper(), self.body_style),
            ],
            [
                Paragraph("<b>Description:</b>", self.body_style),
                Paragraph(case.get("description") or "No description provided.", self.body_style),
                Paragraph("<b>Evidence Count:</b>", self.body_style),
                Paragraph(str(len(evidence_items)), self.body_style),
            ],
        ]

        t_case = Table(case_data, colWidths=[1.3 * inch, 2.5 * inch, 1.2 * inch, 2.0 * inch])
        t_case.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t_case)
        story.append(Spacer(1, 14))

        # ── 3. Evidence Items & Forensic Deep Dives ──────────────────────────
        if not evidence_items:
            story.append(Paragraph("No evidence records have been associated with this case container.", self.body_style))
        else:
            for idx, ev in enumerate(evidence_items, 1):
                ev_id = ev.get("evidence_id", "Unknown")
                modality = ev.get("modality", "unknown")
                sha256 = ev.get("sha256", "UNKNOWN")
                orig_name = ev.get("original_name", "unnamed")
                analysis_status = ev.get("analysis_status", "pending")
                analysis = ev.get("analysis_json") or {}

                story.append(Paragraph(f"Evidence #{idx}: {orig_name} ({modality.upper()})", self.section_heading))

                # Integrity & Provenance Box
                integrity_rows = [
                    [Paragraph("<b>Evidence ID:</b>", self.body_style), Paragraph(f"<font name='Courier'>{ev_id}</font>", self.mono_style)],
                    [Paragraph("<b>Original Filename:</b>", self.body_style), Paragraph(orig_name, self.body_style)],
                    [Paragraph("<b>Cryptographic SHA-256:</b>", self.body_style), Paragraph(f"<font name='Courier'>{sha256}</font>", self.mono_style)],
                    [Paragraph("<b>File Size / Ingest Date:</b>", self.body_style), Paragraph(f"{ev.get('file_size', 0):,} bytes | Ingested: {ev.get('uploaded_at', 'N/A')}", self.body_style)],
                    [Paragraph("<b>Analysis Pipeline State:</b>", self.body_style), Paragraph(analysis_status.upper(), self.body_style)],
                ]
                t_int = Table(integrity_rows, colWidths=[1.8 * inch, 5.2 * inch])
                t_int.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#94A3B8")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]))
                story.append(t_int)
                story.append(Spacer(1, 8))

                # Visual presentation for Image Evidence
                if modality == "image":
                    rel_path = ev.get("filename", "")
                    full_img_path = uploads_dir / rel_path

                    det = analysis.get("detection") or {}
                    objects = det.get("objects") or []

                    if full_img_path.is_file():
                        # Prepare annotated image in scratch dir
                        ann_target = scratch_dir / f"{ev_id}_annotated.jpg"
                        annotated_img_path = self._draw_annotated_image(full_img_path, objects, ann_target)
                        render_path = annotated_img_path if (annotated_img_path and annotated_img_path.is_file()) else full_img_path

                        try:
                            # Constrain preview image to letter page width
                            story.append(Paragraph("<b>Visual Examination (Annotated Detections Preview):</b>", self.body_style))
                            story.append(Spacer(1, 4))
                            story.append(Image(str(render_path), width=4.5 * inch, height=2.6 * inch, kind="proportional"))
                            story.append(Spacer(1, 8))
                        except Exception:
                            story.append(Paragraph("<i>[Image preview rendering failed during PDF generation]</i>", self.body_style))

                    # AI Scene Summary
                    scene_sum = analysis.get("scene_summary")
                    if scene_sum:
                        story.append(Paragraph("<b>AI Scene Summary:</b>", self.body_style))
                        story.append(Paragraph(f'"{scene_sum}"', self.callout_style))
                        story.append(Spacer(1, 6))

                    # 1. RT-DETR Findings
                    story.append(Paragraph("<b>1. RT-DETR Object Detection Findings</b>", self.body_style))
                    if det.get("status") == "success":
                        if objects:
                            det_table_data = [
                                [
                                    Paragraph("<b>Class Label</b>", self.body_style),
                                    Paragraph("<b>Confidence</b>", self.body_style),
                                    Paragraph("<b>Bounding Box [x1, y1, x2, y2]</b>", self.body_style),
                                ]
                            ]
                            for obj in objects:
                                det_table_data.append([
                                    Paragraph(str(obj.get("label", "unknown")), self.body_style),
                                    Paragraph(f"{obj.get('confidence', 0.0):.2%}", self.mono_style),
                                    Paragraph(str(obj.get("box_pixels", [])), self.mono_style),
                                ])
                            t_det = Table(det_table_data, colWidths=[1.8 * inch, 1.4 * inch, 3.8 * inch])
                            t_det.setStyle(TableStyle([
                                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                                ("TOPPADDING", (0, 0), (-1, -1), 3),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                            ]))
                            story.append(t_det)
                        else:
                            story.append(Paragraph("No foreground objects detected above confidence threshold.", self.body_style))
                    elif det.get("status") == "failed":
                        story.append(Paragraph(f"<font color='#EF4444'>RT-DETR Inference Failed: {det.get('error', 'Error')}</font>", self.body_style))
                    else:
                        story.append(Paragraph("<i>RT-DETR Analysis pending or not executed.</i>", self.body_style))

                    story.append(Spacer(1, 6))

                    # 2. BLIP Findings
                    cap = analysis.get("caption") or {}
                    story.append(Paragraph("<b>2. BLIP Natural Language Caption</b>", self.body_style))
                    if cap.get("status") == "success" and cap.get("caption"):
                        story.append(Paragraph(f'"{cap.get("caption")}"', self.callout_style))
                    elif cap.get("status") == "failed":
                        story.append(Paragraph(f"<font color='#EF4444'>BLIP Captioning Failed: {cap.get('error', 'Error')}</font>", self.body_style))
                    else:
                        story.append(Paragraph("<i>BLIP Captioning pending or not executed.</i>", self.body_style))

                    story.append(Spacer(1, 6))

                    # 3. CLIP Findings
                    clip = analysis.get("clip") or {}
                    story.append(Paragraph("<b>3. CLIP Scene Similarity Scoring</b>", self.body_style))
                    if clip.get("status") == "success" and clip.get("matches"):
                        clip_data = [
                            [
                                Paragraph("<b>Candidate Forensic Taxonomy</b>", self.body_style),
                                Paragraph("<b>Zero-Shot Similarity Score</b>", self.body_style),
                            ]
                        ]
                        for match in clip.get("matches", [])[:5]:
                            clip_data.append([
                                Paragraph(str(match.get("label", "")), self.body_style),
                                Paragraph(f"{match.get('similarity_score', 0.0):.2%}", self.mono_style),
                            ])
                        t_clip = Table(clip_data, colWidths=[4.5 * inch, 2.5 * inch])
                        t_clip.setStyle(TableStyle([
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                            ("TOPPADDING", (0, 0), (-1, -1), 3),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                        ]))
                        story.append(t_clip)
                    elif clip.get("status") == "failed":
                        story.append(Paragraph(f"<font color='#EF4444'>CLIP Scoring Failed: {clip.get('error', 'Error')}</font>", self.body_style))
                    else:
                        story.append(Paragraph("<i>CLIP Scene Classification pending or not executed.</i>", self.body_style))

                elif modality == "audio":
                    audio_res = analysis.get("audio") or analysis.get("whisper") or {}
                    audio_meta = audio_res.get("audio_metadata") or analysis.get("audio_metadata") or {}
                    transcript = audio_res.get("transcript") or analysis.get("whisper", {}).get("transcript") or ""
                    segments = audio_res.get("segments") or analysis.get("whisper", {}).get("segments") or []
                    lang = (
                        audio_res.get("language")
                        or audio_res.get("detected_language")
                        or analysis.get("whisper", {}).get("language")
                        or "unknown"
                    )
                    duration_sec = audio_meta.get("duration_seconds", 0.0)
                    a_status = audio_res.get("status") or analysis.get("status")

                    # 1. Audio Stream Metadata Box
                    story.append(Paragraph("<b>1. Acoustic Stream Ingest Metadata</b>", self.body_style))
                    meta_rows = [
                        [Paragraph("<b>Duration (sec):</b>", self.body_style), Paragraph(f"{duration_sec:.2f} s", self.mono_style)],
                        [Paragraph("<b>Sample Rate / Channels:</b>", self.body_style), Paragraph(f"{audio_meta.get('sample_rate', 'N/A')} Hz | {audio_meta.get('channels', 'N/A')} channel(s)", self.body_style)],
                        [Paragraph("<b>Detected Language:</b>", self.body_style), Paragraph(str(lang).upper(), self.body_style)],
                    ]
                    t_ameta = Table(meta_rows, colWidths=[2.2 * inch, 4.8 * inch])
                    t_ameta.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ]))
                    story.append(t_ameta)
                    story.append(Spacer(1, 6))

                    # 2. Whisper Speech-to-Text Transcription
                    story.append(Paragraph("<b>2. OpenAI Whisper Base Speech-to-Text Findings</b>", self.body_style))
                    if a_status in ("success", "completed"):
                        if transcript:
                            story.append(Paragraph(f'"{transcript}"', self.callout_style))
                            story.append(Spacer(1, 4))
                        else:
                            story.append(Paragraph("<i>No audible speech was detected or transcribed from the recording.</i>", self.body_style))

                        # Segment Table with Timestamps
                        if segments:
                            story.append(Paragraph("<b>Timestamped Audio Segments:</b>", self.body_style))
                            seg_table_data = [
                                [
                                    Paragraph("<b>Interval [Start - End]</b>", self.body_style),
                                    Paragraph("<b>Transcribed Text Segment</b>", self.body_style),
                                ]
                            ]
                            for seg in segments:
                                s_start = seg.get("start_seconds")
                                s_end = seg.get("end_seconds")
                                time_str = f"{s_start:.2f}s - {s_end:.2f}s" if (s_start is not None and s_end is not None) else "N/A"
                                seg_table_data.append([
                                    Paragraph(time_str, self.mono_style),
                                    Paragraph(str(seg.get("text", "")), self.body_style),
                                ])
                            t_seg = Table(seg_table_data, colWidths=[2.0 * inch, 5.0 * inch])
                            t_seg.setStyle(TableStyle([
                                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                                ("TOPPADDING", (0, 0), (-1, -1), 3),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                            ]))
                            story.append(t_seg)
                    elif a_status == "failed":
                        story.append(Paragraph(f"<font color='#EF4444'>Whisper Transcription Failed: {audio_res.get('error', 'Error')}</font>", self.body_style))
                    else:
                        story.append(Paragraph("<i>Whisper audio transcription pending or not executed.</i>", self.body_style))

                    # 3. Audio Forensic Intelligence Report
                    intel = analysis.get("intelligence_report") or audio_res.get("intelligence_report") or analysis.get("whisper", {}).get("intelligence_report")
                    if intel and isinstance(intel, dict):
                        story.append(Spacer(1, 6))
                        story.append(Paragraph("<b>3. AI Audio Intelligence & Event Reconstruction</b>", self.body_style))

                        intel_rows = []
                        if intel.get("event_type"):
                            conf_str = f" ({intel.get('event_type_confidence', 0):.0%})" if intel.get("event_type_confidence") else ""
                            intel_rows.append([Paragraph("<b>Event Type:</b>", self.body_style), Paragraph(f"{intel.get('event_type')}{conf_str}", self.body_style)])
                        if intel.get("location"):
                            intel_rows.append([Paragraph("<b>Extracted Location:</b>", self.body_style), Paragraph(str(intel.get("location")), self.body_style)])
                        if intel.get("ai_summary"):
                            intel_rows.append([Paragraph("<b>AI Summary:</b>", self.body_style), Paragraph(str(intel.get("ai_summary")), self.body_style)])

                        if intel_rows:
                            t_intel = Table(intel_rows, colWidths=[2.0 * inch, 5.0 * inch])
                            t_intel.setStyle(TableStyle([
                                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                                ("TOPPADDING", (0, 0), (-1, -1), 3),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                            ]))
                            story.append(t_intel)
                            story.append(Spacer(1, 4))

                        timeline = intel.get("timeline") or []
                        if timeline:
                            story.append(Paragraph("<b>Acoustic Event Timeline:</b>", self.body_style))
                            tl_data = [[Paragraph("<b>Time / Phase</b>", self.body_style), Paragraph("<b>Observed Auditory Action</b>", self.body_style)]]
                            for itm in timeline[:5]:
                                if isinstance(itm, dict):
                                    t_str = itm.get("time") or itm.get("timestamp") or "—"
                                    desc_str = itm.get("event") or itm.get("action") or itm.get("description") or ""
                                    tl_data.append([Paragraph(str(t_str), self.mono_style), Paragraph(str(desc_str), self.body_style)])
                                elif isinstance(itm, str):
                                    tl_data.append([Paragraph("Event", self.mono_style), Paragraph(itm, self.body_style)])
                            if len(tl_data) > 1:
                                t_tl = Table(tl_data, colWidths=[1.8 * inch, 5.2 * inch])
                                t_tl.setStyle(TableStyle([
                                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                                ]))
                                story.append(t_tl)

                    # Audio Forensics Disclaimer
                    story.append(Spacer(1, 4))
                    story.append(Paragraph(
                        "<b>Forensic Notice:</b> Transcribing speech does NOT establish speaker identity, "
                        "voice biometrics, or prove the veracity of spoken statements.",
                        self.disclaimer_style
                    ))

                elif modality == "video":
                    vid_res = analysis.get("video") or {}
                    vid_meta = vid_res.get("video_metadata") or {}
                    sampled_frames = vid_res.get("sampled_frames") or []
                    agg_det = vid_res.get("aggregated_detections") or {}
                    v_status = vid_res.get("status") or analysis.get("status")
                    duration_sec = vid_meta.get("duration_seconds", 0.0)

                    # 1. Video Stream Ingest Metadata Box
                    story.append(Paragraph("<b>1. Video Stream Ingest Metadata</b>", self.body_style))
                    meta_rows = [
                        [Paragraph("<b>Duration / Total Frames:</b>", self.body_style), Paragraph(f"{duration_sec:.2f} s | {vid_meta.get('total_frames', 'N/A')} frames", self.mono_style)],
                        [Paragraph("<b>Resolution / Framerate:</b>", self.body_style), Paragraph(f"{vid_meta.get('width', 0)}x{vid_meta.get('height', 0)} @ {vid_meta.get('fps', 0.0)} fps", self.body_style)],
                        [Paragraph("<b>Container Codec:</b>", self.body_style), Paragraph(str(vid_meta.get("codec", "N/A")).upper(), self.body_style)],
                        [Paragraph("<b>Aggregated Detections:</b>", self.body_style), Paragraph(f"{agg_det.get('total_detections', 0)} object(s) across {len(sampled_frames)} sampled frame(s)", self.body_style)],
                    ]
                    t_vmeta = Table(meta_rows, colWidths=[2.2 * inch, 4.8 * inch])
                    t_vmeta.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ]))
                    story.append(t_vmeta)
                    story.append(Spacer(1, 6))

                    # 2. Sampled Frame Detections Table
                    story.append(Paragraph("<b>2. Sampled Frame RT-DETR Detections Timeline</b>", self.body_style))
                    if v_status in ("completed", "partial", "success"):
                        if sampled_frames:
                            frame_table_data = [
                                [
                                    Paragraph("<b>Timestamp / Frame #</b>", self.body_style),
                                    Paragraph("<b>Status</b>", self.body_style),
                                    Paragraph("<b>Detected Objects (Class & Confidence)</b>", self.body_style),
                                ]
                            ]
                            for sf in sampled_frames:
                                t_val = sf.get("timestamp_seconds", 0.0)
                                f_idx = sf.get("frame_index", 0)
                                sf_status = sf.get("status", "unknown")
                                objs = sf.get("objects", [])

                                if objs:
                                    obj_summary = ", ".join(f"{o.get('label', 'obj')} ({o.get('confidence', 0.0):.1%})" for o in objs[:5])
                                    if len(objs) > 5:
                                        obj_summary += f" +{len(objs) - 5} more"
                                elif sf_status == "failed":
                                    obj_summary = f"<font color='#EF4444'>Frame analysis error: {sf.get('error', 'Error')}</font>"
                                else:
                                    obj_summary = "<i>No objects detected above threshold</i>"

                                frame_table_data.append([
                                    Paragraph(f"<font name='Courier'>{t_val:.2f}s (frame #{f_idx})</font>", self.mono_style),
                                    Paragraph(sf_status.upper(), self.body_style),
                                    Paragraph(obj_summary, self.body_style),
                                ])

                            t_frames = Table(frame_table_data, colWidths=[2.0 * inch, 1.2 * inch, 3.8 * inch])
                            t_frames.setStyle(TableStyle([
                                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                                ("TOPPADDING", (0, 0), (-1, -1), 3),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                            ]))
                            story.append(t_frames)
                        else:
                            story.append(Paragraph("<i>No frames could be extracted or analyzed from video stream.</i>", self.body_style))
                    elif v_status == "failed":
                        story.append(Paragraph(f"<font color='#EF4444'>Video Analysis Failed: {vid_res.get('error', 'Error')}</font>", self.body_style))
                    else:
                        story.append(Paragraph("<i>Video frame sampling and analysis pending or not executed.</i>", self.body_style))

                    # Video Forensics Disclaimer
                    story.append(Spacer(1, 4))
                    story.append(Paragraph(
                        "<b>Forensic Notice:</b> Sampled frame analysis captures discrete snapshot intervals. "
                        "Frame detections do not demonstrate continuous activity, intent, or comprehensive event reconstruction "
                        "during unanalyzed intervals.",
                        self.disclaimer_style
                    ))

                else:
                    # Other evidence placeholders
                    story.append(Paragraph(f"Detailed timeline and modal extraction for {modality} will appear once analyzed in upcoming pipeline phases.", self.body_style))

                story.append(Spacer(1, 14))

        # ── 4. Multimodal Evidence Fusion Intelligence (Phase 6) ─────────────
        if fusion_result and fusion_result.get("evidence_count", 0) > 0:
            story.append(Paragraph("Multimodal Forensic Evidence Fusion Summary", self.section_heading))
            cov = fusion_result.get("modality_coverage") or {}
            cov_summary = (
                f"Image: {cov.get('image', {}).get('status', 'N/A').upper()} | "
                f"Audio: {cov.get('audio', {}).get('status', 'N/A').upper()} | "
                f"Video: {cov.get('video', {}).get('status', 'N/A').upper()}"
            )

            fusion_meta = [
                [Paragraph("<b>Fusion Status:</b>", self.body_style), Paragraph(fusion_result.get("status", "unknown").upper(), self.body_style)],
                [Paragraph("<b>Modality Coverage:</b>", self.body_style), Paragraph(cov_summary, self.body_style)],
                [Paragraph("<b>Total Observations:</b>", self.body_style), Paragraph(str(fusion_result.get("observation_summary", {}).get("total_observations", 0)), self.body_style)],
            ]
            t_fmeta = Table(fusion_meta, colWidths=[2.0 * inch, 5.0 * inch])
            t_fmeta.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(t_fmeta)
            story.append(Spacer(1, 8))

            # Cross-modal associations table
            assocs = fusion_result.get("cross_modal_corroborations") or fusion_result.get("cross_modal_associations") or []
            if assocs:
                story.append(Paragraph("<b>Cross-Modal Corroborated Entities:</b>", self.body_style))
                assoc_data = [
                    [
                        Paragraph("<b>Entity Category</b>", self.body_style),
                        Paragraph("<b>Modalities</b>", self.body_style),
                        Paragraph("<b>Forensic Finding</b>", self.body_style),
                    ]
                ]
                for a in assocs:
                    cat_name = str(a.get("entity") or a.get("category", "")).upper()
                    desc = str(a.get("observation") or a.get("description", ""))
                    assoc_data.append([
                        Paragraph(f"<b>{cat_name}</b>", self.body_style),
                        Paragraph(", ".join(a.get("modalities_involved", [])), self.mono_style),
                        Paragraph(desc, self.body_style),
                    ])
                t_assoc = Table(assoc_data, colWidths=[1.8 * inch, 1.6 * inch, 3.6 * inch])
                t_assoc.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]))
                story.append(t_assoc)
                story.append(Spacer(1, 6))

            # Temporal Audio-Video Alignments
            temp_assocs = fusion_result.get("temporal_alignments") or fusion_result.get("temporal_associations") or []
            if temp_assocs:
                story.append(Paragraph("<b>Temporal Audio-Video Alignments:</b>", self.body_style))
                for ta in temp_assocs[:4]:
                    story.append(Paragraph(f"• {ta.get('description', '')}", self.callout_style))
                story.append(Spacer(1, 6))

            # Potential Contradictions / Divergences
            contradictions = fusion_result.get("divergences_and_contradictions") or fusion_result.get("potential_contradictions") or []
            if contradictions:
                story.append(Paragraph("<b>Potential Divergences / Inconsistencies Flagged for Human Review:</b>", self.body_style))
                for c in contradictions:
                    story.append(Paragraph(f"<font color='#EF4444'>⚠ {c.get('divergence') or c.get('explanation', '')}</font>", self.body_style))
                story.append(Spacer(1, 6))

            # Unresolved questions / investigative gaps
            unresolved = fusion_result.get("unresolved_investigative_questions") or fusion_result.get("unresolved_questions") or []
            if unresolved:
                story.append(Paragraph("<b>Forensic Investigative Gaps & Unresolved Questions:</b>", self.body_style))
                for q in unresolved:
                    story.append(Paragraph(f"• {q}", self.body_style))
                story.append(Spacer(1, 6))

            # Fusion notice
            story.append(Paragraph(
                "<b>Fusion Forensic Safeguard:</b> Matching entity categories and temporal proximity represent "
                "observational correlation, NOT proof of physical identity, causation, or criminal responsibility.",
                self.disclaimer_style
            ))
            story.append(Spacer(1, 10))

        # ── 5. Legal & Algorithmic Uncertainty Notice ────────────────────────
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceBefore=10, spaceAfter=8))
        disclaimer_text = (
            "<b>LEGAL & FORENSIC DISCLAIMER:</b> This document contains machine-assisted observations "
            "generated by deep learning models (RT-DETR, CLIP, BLIP, OpenAI Whisper, OpenCV Frame Sampler, Multimodal Fusion). "
            "AI outputs do not constitute scientifically definitive proof, judicial findings of fact, speaker identity verification, "
            "or unassailable certainty. Detected bounding boxes, scene descriptions, semantic similarity rankings, audio transcripts, "
            "video frame timelines, and cross-modal correlations must be independently corroborated by qualified digital evidence examiners. "
            "Hash values guarantee digital provenance and file integrity as ingested."
        )
        story.append(Paragraph(disclaimer_text, self.disclaimer_style))

        # Build document
        doc.build(story)
        return self.output_path
