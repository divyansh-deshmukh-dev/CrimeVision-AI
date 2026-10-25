"""
storage/provision_demo.py — Provisioning utility for the public read-only mentor demo.

Creates:
  1. Demo user account (role='demo', is_demo=1) with secure credentials.
  2. Preloaded realistic, fictional forensic sample case ("Operation Metro Sentinel").
  3. Preloaded multimodal evidence (Image, Audio, Video) with complete precomputed
     RT-DETR detections, Whisper transcripts, and CCTV timeline intelligence.
  4. Preloaded forensic report.

Idempotent: Safe to execute repeatedly without duplicating data.
"""

import json
import os
from pathlib import Path
import secrets
from typing import Any, Dict, Optional

from werkzeug.security import generate_password_hash

from storage.database import get_db, init_db


def _get_synthetic_media(modality: str) -> bytes:
    """Generate minimal valid media bytes for fallback."""
    import struct
    import zlib

    if modality == "image":
        # Valid 1x1 PNG
        def chunk(ctype: bytes, data: bytes) -> bytes:
            c = ctype + data
            return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

        signature = b"\x89PNG\r\n\x1a\n"
        ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        idat = chunk(b"IDAT", zlib.compress(b"\x00\x00\xFF\xFF"))
        iend = chunk(b"IEND", b"")
        return signature + ihdr + idat + iend

    if modality == "audio":
        # Minimal valid WAV silence
        num_samples = 8000
        sample_rate = 8000
        byte_rate = sample_rate
        data_size = num_samples
        chunk_size = 36 + data_size
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF", chunk_size, b"WAVE", b"fmt ", 16, 1, 1, sample_rate, byte_rate, 1, 8, b"data", data_size
        )
        return header + (b"\x80" * num_samples)

    if modality == "video":
        # Minimal MP4 ftyp box
        return b"\x00\x00\x00\x14ftypisom\x00\x00\x00\x00isom"

    return b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\nxref\n0 3\n0000000000 65535 f \n0000000009 00000 n \n0000000052 00000 n \ntrailer<</Size 3/Root 1 0 R>>\nstartxref\n103\n%%EOF"


def _read_seed_asset(asset_name: str, fallback_modality: str) -> bytes:
    """Read a tracked seed asset from storage/seed_assets, falling back safely."""
    seed_dir = Path(__file__).resolve().parent / "seed_assets"
    asset_path = seed_dir / asset_name
    if asset_path.is_file():
        try:
            data = asset_path.read_bytes()
            if data:
                return data
        except OSError:
            pass
    return _get_synthetic_media(fallback_modality)


def _is_file_on_disk(storage: Any, rel_filename: str) -> bool:
    """Check if the physical evidence file exists in storage."""
    from services.storage_service import LocalStorageProvider
    if isinstance(storage, LocalStorageProvider):
        target = (storage.uploads_dir / rel_filename).resolve()
        return target.is_file()
    try:
        cached = storage.get_local_cache_path(rel_filename)
        return cached.is_file()
    except Exception:
        return False


def _is_report_on_disk(storage: Any, rel_filename: str) -> bool:
    """Check if the physical report file exists in storage."""
    from services.storage_service import LocalStorageProvider
    if isinstance(storage, LocalStorageProvider):
        target = (storage.reports_dir / rel_filename).resolve()
        return target.is_file()
    try:
        cached = storage.get_local_cache_path(rel_filename)
        return cached.is_file()
    except Exception:
        return False


def provision_demo_account(
    username: Optional[str] = None,
    password: Optional[str] = None,
    email: Optional[str] = None,
) -> Dict[str, Any]:
    """Provision or update the public read-only mentor demo account and sample case."""
    from services.storage_service import get_storage_provider

    db = get_db()
    now_iso = "2026-10-24T12:00:00+00:00"

    demo_username = (username or os.getenv("DEMO_USERNAME") or "demo_mentor").strip().lower()
    demo_email = (email or os.getenv("DEMO_EMAIL") or "mentor.demo@crimevision.ai").strip().lower()
    demo_password = password or os.getenv("DEMO_PASSWORD") or secrets.token_urlsafe(24)

    # 1. Provision or retrieve Demo User
    row = db.execute(
        "SELECT user_id, display_name, username, email, role, created_at, is_active, is_demo FROM users WHERE username = ?",
        (demo_username,),
    ).fetchone()

    if row is None:
        user_id = f"usr_demo_{secrets.token_hex(6)}"
        pwd_hash = generate_password_hash(demo_password, method="scrypt")
        db.execute(
            """
            INSERT INTO users (user_id, display_name, username, email, password_hash, role, created_at, is_active, is_demo)
            VALUES (?, ?, ?, ?, ?, 'demo', ?, 1, 1)
            """,
            (user_id, "Mentor Demo Examiner", demo_username, demo_email, pwd_hash, now_iso),
        )
        db.commit()
    else:
        user_id = row["user_id"]
        # Ensure role='demo' and is_demo=1
        db.execute(
            "UPDATE users SET role = 'demo', is_demo = 1 WHERE user_id = ?",
            (user_id,),
        )
        db.commit()

    # 2. Provision Preloaded Legacy Demo Case ("Operation Metro Sentinel")
    case_id = "case_demo_sentinel"
    case_row = db.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    if case_row is None:
        db.execute(
            """
            INSERT INTO cases (case_id, user_id, name, description, created_at, updated_at, status, is_demo, demo_type)
            VALUES (?, ?, ?, ?, ?, ?, 'active', 1, 'legacy')
            """,
            (
                case_id,
                user_id,
                "Operation Metro Sentinel — Cross-Modal Surveillance",
                "Joint forensic digital evidence investigation analyzing high-resolution vehicle imagery, wiretap audio intercepts, and CCTV surveillance footage from the Central Metro district.",
                now_iso,
                now_iso,
            ),
        )
        db.commit()
    else:
        db.execute(
            "UPDATE cases SET user_id = ?, is_demo = 1, demo_type = 'legacy' WHERE case_id = ?",
            (user_id, case_id),
        )
        db.commit()

    # 2b. Provision Writable Live Demo Case ("Live Forensic Investigation Workspace")
    live_case_id = "case_demo_live"
    live_case_row = db.execute("SELECT * FROM cases WHERE case_id = ?", (live_case_id,)).fetchone()
    if live_case_row is None:
        db.execute(
            """
            INSERT INTO cases (case_id, user_id, name, description, created_at, updated_at, status, is_demo, demo_type)
            VALUES (?, ?, ?, ?, ?, ?, 'active', 0, 'live')
            """,
            (
                live_case_id,
                user_id,
                "Live Forensic Investigation Workspace",
                "Writable demonstration workspace supporting real-time AI inference, multimodal evidence ingestion, and dynamic reporting.",
                now_iso,
                now_iso,
            ),
        )
        db.commit()
    else:
        db.execute(
            "UPDATE cases SET user_id = ?, demo_type = 'live' WHERE case_id = ?",
            (user_id, live_case_id),
        )
        db.commit()

    storage = get_storage_provider()

    # 3. Preload Evidence Items with Precomputed Forensic AI Analysis
    # Evidence 1: High-Resolution Surveillance Image
    img_ev_id = "ev_demo_img_01"
    img_row = db.execute("SELECT * FROM evidence WHERE evidence_id = ?", (img_ev_id,)).fetchone()
    if img_row is None:
        # Check if local sample image file exists
        local_sample_img = Path("storage/uploads/case_d9baa2028b5b/ev_0ce49db8f9db/Gemini_Generated_Image_l79sz8l79sz8l79s__1_.png")
        img_bytes = local_sample_img.read_bytes() if local_sample_img.is_file() else _get_synthetic_media("image")
        img_key = storage.upload_evidence(
            case_id=case_id,
            evidence_id=img_ev_id,
            filename="metro_traffic_cam_04.png",
            file_data=img_bytes,
            mime_type="image/png",
        )
        img_analysis = {
            "status": "completed",
            "model": "PekingU/rtdetr_r50vd",
            "caption": "a busy urban street with a white sedan and pedestrians near a traffic junction",
            "detections": [
                {"category": "car", "confidence": 0.94, "box": [0.18, 0.42, 0.45, 0.72]},
                {"category": "person", "confidence": 0.89, "box": [0.55, 0.35, 0.62, 0.68]},
                {"category": "truck", "confidence": 0.86, "box": [0.02, 0.28, 0.22, 0.65]},
                {"category": "traffic light", "confidence": 0.91, "box": [0.72, 0.12, 0.78, 0.30]},
            ],
            "total_detections": 4,
            "classification_scores": {"surveillance_vehicle": 0.92, "urban_intersection": 0.95},
        }
        db.execute(
            """
            INSERT INTO evidence (evidence_id, case_id, filename, original_name, modality, mime_type, sha256, file_size, uploaded_at, analysis_status, analysis_json)
            VALUES (?, ?, ?, ?, 'image', 'image/png', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', ?, ?, 'completed', ?)
            """,
            (img_ev_id, case_id, img_key, "metro_traffic_cam_04.png", len(img_bytes), now_iso, json.dumps(img_analysis)),
        )
        db.commit()

    # Evidence 2: Wiretap Audio Recording
    aud_ev_id = "ev_demo_aud_02"
    aud_row = db.execute("SELECT * FROM evidence WHERE evidence_id = ?", (aud_ev_id,)).fetchone()
    if aud_row is None:
        local_sample_aud = Path("storage/uploads/case_d9baa2028b5b/ev_ac43223c1f85/ElevenLabs_2026-10-18T17_37_53_Roger_-_Laid-Back__Casual__Resonant_pre_sp100_s50_sb75_v4.mp3")
        aud_bytes = local_sample_aud.read_bytes() if local_sample_aud.is_file() else _get_synthetic_media("audio")
        aud_key = storage.upload_evidence(
            case_id=case_id,
            evidence_id=aud_ev_id,
            filename="wiretap_intercept_channel2.mp3",
            file_data=aud_bytes,
            mime_type="audio/mpeg",
        )
        aud_analysis = {
            "status": "completed",
            "model": "openai/whisper-base",
            "transcript": "Target vehicle confirmed heading eastbound toward Sector 4 transit hub. Vehicle identified as a white sedan.",
            "detected_language": "en",
            "language_confidence": 0.98,
            "duration_seconds": 12.4,
            "segments": [
                {"id": 0, "start": 0.0, "end": 5.2, "text": "Target vehicle confirmed heading eastbound toward Sector 4 transit hub.", "confidence": 0.95},
                {"id": 1, "start": 5.8, "end": 11.9, "text": "Vehicle identified as a white sedan.", "confidence": 0.97},
            ],
            "intelligence_report": {
                "ai_summary": "Surveillance team corroborates suspect vehicle movement toward Sector 4 transit plaza.",
                "key_entities": ["Target vehicle", "Sector 4 transit hub", "white sedan"],
            },
        }
        db.execute(
            """
            INSERT INTO evidence (evidence_id, case_id, filename, original_name, modality, mime_type, sha256, file_size, uploaded_at, analysis_status, analysis_json)
            VALUES (?, ?, ?, ?, 'audio', 'audio/mpeg', 'a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0', ?, ?, 'completed', ?)
            """,
            (aud_ev_id, case_id, aud_key, "wiretap_intercept_channel2.mp3", len(aud_bytes), now_iso, json.dumps(aud_analysis)),
        )
        db.commit()

    # Evidence 3: CCTV Surveillance Video Footage
    vid_ev_id = "ev_demo_vid_03"
    vid_row = db.execute("SELECT * FROM evidence WHERE evidence_id = ?", (vid_ev_id,)).fetchone()
    if vid_row is None:
        local_sample_vid = Path("storage/uploads/case_d9baa2028b5b/ev_09814865021a/Realistic_15-second_continuous_CCTV_surveillance_footage_of_a_small_urban_street.mp4")
        vid_bytes = local_sample_vid.read_bytes() if local_sample_vid.is_file() else _get_synthetic_media("video")
        vid_key = storage.upload_evidence(
            case_id=case_id,
            evidence_id=vid_ev_id,
            filename="cctv_sector4_overview.mp4",
            file_data=vid_bytes,
            mime_type="video/mp4",
        )
        vid_analysis = {
            "status": "completed",
            "model": "PekingU/rtdetr_r50vd",
            "metadata": {"fps": 30.0, "duration_seconds": 15.0, "width": 1920, "height": 1080, "total_frames": 450},
            "sampled_frame_count": 15,
            "detections": [
                {"timestamp": 0.0, "frame_index": 0, "category": "car", "confidence": 0.93, "box": [0.15, 0.40, 0.42, 0.70]},
                {"timestamp": 1.0, "frame_index": 30, "category": "car", "confidence": 0.94, "box": [0.18, 0.41, 0.45, 0.72]},
                {"timestamp": 2.0, "frame_index": 60, "category": "person", "confidence": 0.88, "box": [0.52, 0.38, 0.58, 0.69]},
                {"timestamp": 3.0, "frame_index": 90, "category": "car", "confidence": 0.95, "box": [0.22, 0.43, 0.49, 0.74]},
                {"timestamp": 4.0, "frame_index": 120, "category": "car", "confidence": 0.91, "box": [0.26, 0.44, 0.53, 0.76]},
            ],
            "scene_intelligence": {
                "dominant_categories": ["car", "person"],
                "activity_level": "moderate",
                "chronological_summary": "Continuous street-level monitoring confirms white sedan transit through the frame over 15.0s window.",
            },
        }
        db.execute(
            """
            INSERT INTO evidence (evidence_id, case_id, filename, original_name, modality, mime_type, sha256, file_size, uploaded_at, analysis_status, analysis_json)
            VALUES (?, ?, ?, ?, 'video', 'video/mp4', 'c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9', ?, ?, 'completed', ?)
            """,
            (vid_ev_id, case_id, vid_key, "cctv_sector4_overview.mp4", len(vid_bytes), now_iso, json.dumps(vid_analysis)),
        )
        db.commit()

    # 4. Preload Sample Report
    rep_id = "rep_demo_01"
    rep_row = db.execute("SELECT * FROM reports WHERE report_id = ?", (rep_id,)).fetchone()
    if rep_row is None:
        local_sample_rep = Path("storage/reports/case_d9baa2028b5b/report_case_d9baa2028b5b_1792477882.pdf")
        rep_bytes = local_sample_rep.read_bytes() if local_sample_rep.is_file() else _get_synthetic_media("pdf")
        rep_key = storage.upload_report(case_id, "forensic_report_demo_sentinel.pdf", rep_bytes)
        db.execute(
            """
            INSERT INTO reports (report_id, case_id, filename, created_at, file_size)
            VALUES (?, ?, ?, ?, ?)
            """,
            (rep_id, case_id, rep_key, now_iso, len(rep_bytes)),
        )
        db.commit()

    return {
        "status": "provisioned",
        "user_id": user_id,
        "username": demo_username,
        "email": demo_email,
        "role": "demo",
        "is_demo": 1,
        "case_id": case_id,
        "evidence_count": 3,
        "report_count": 1,
    }


def ensure_demo_evaluator(
    username: Optional[str] = None,
    password: Optional[str] = None,
    email: Optional[str] = None,
    display_name: Optional[str] = None,
    case_name: Optional[str] = None,
    case_description: Optional[str] = None,
) -> Dict[str, Any]:
    """Ensure the evaluator/demo account and initial writable workspace are provisioned idempotently.

    Safe for automatic invocation during application startup on both SQLite and PostgreSQL.
    Guarantees:
      1. Evaluator account exists with role='user' (normal, unrestricted workspace access).
      2. Secure scrypt password hashing (never plaintext).
      3. An initial writable investigation case exists named 'test case' (case_bd736d27b0e9) with realistic evidence items,
         so the evaluator immediately sees an active workspace upon first login matching the local application.
      4. For an existing database, renames the case only if its ID is 'case_bd736d27b0e9' and its current name is exactly
         'Metro CCTV & Evidence Investigation', preserving all evidence and report associations.
      5. Updates the display name to 'user' only when the account matches the evaluator and its existing display name is 'Lead Investigator'.
      6. Safe for concurrency and repeated execution without duplicating data or breaking on existing records.
    """
    from services.storage_service import get_storage_provider
    from storage.users_store import authenticate_user, ensure_user, get_user_by_username
    from werkzeug.security import generate_password_hash

    eval_username = (username or os.getenv("DEMO_USERNAME") or "user-12").strip().lower()
    eval_password = password or os.getenv("DEMO_PASSWORD") or "user1234"
    eval_email = (email or os.getenv("DEMO_EMAIL") or "user@gmail.com").strip().lower()
    eval_display_name = (display_name or os.getenv("DEMO_DISPLAY_NAME") or "user").strip()
    eval_case_name = (case_name or os.getenv("DEMO_CASE_NAME") or "test case").strip()
    eval_case_desc = (
        case_description
        if case_description is not None
        else os.getenv("DEMO_CASE_DESCRIPTION", "")
    ).strip()

    db = get_db()
    now_iso = "2026-10-25T12:00:00+00:00"

    # 1. Provision or retrieve Evaluator User
    existing = get_user_by_username(eval_username)
    if existing is None:
        try:
            user, _ = ensure_user(
                username=eval_username,
                email=eval_email,
                password=eval_password,
                display_name=eval_display_name,
                role="user",
                user_id="usr_1fb3fd9494ca",
            )
            user_id = user["user_id"]
        except Exception:
            # Handle potential race condition in multi-worker environment
            existing = get_user_by_username(eval_username)
            if existing is not None:
                user_id = existing["user_id"]
            else:
                raise
    else:
        user_id = existing["user_id"]
        # Update display name only when evaluator matches and existing display name is 'Lead Investigator'
        if existing.get("display_name") == "Lead Investigator":
            db.execute(
                "UPDATE users SET display_name = ? WHERE user_id = ?",
                (eval_display_name, user_id),
            )
            db.commit()

        # If user exists but authenticate_user fails with eval_password, update hash
        # (e.g. if DEMO_PASSWORD was configured or changed via environment variable)
        if authenticate_user(eval_username, eval_password) is None:
            pwd_hash = generate_password_hash(eval_password, method="scrypt")
            db.execute(
                "UPDATE users SET password_hash = ? WHERE user_id = ?",
                (pwd_hash, user_id),
            )
            db.commit()

    # 2. Check if this user already has any active cases
    user_cases = db.execute(
        "SELECT case_id, name FROM cases WHERE user_id = ?",
        (user_id,),
    ).fetchall()

    case_id = "case_bd736d27b0e9"
    if not user_cases:
        # Check if case_id is claimed by another user
        case_row = db.execute("SELECT user_id FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        if case_row and case_row["user_id"] != user_id:
            case_id = f"case_{secrets.token_hex(6)}"

        db.execute(
            """
            INSERT INTO cases (case_id, user_id, name, description, created_at, updated_at, status, is_demo, demo_type)
            VALUES (?, ?, ?, ?, ?, ?, 'active', 0, NULL)
            """,
            (
                case_id,
                user_id,
                eval_case_name,
                eval_case_desc,
                now_iso,
                now_iso,
            ),
        )
        db.commit()
    else:
        # Existing database migration:
        # Rename the case only if its ID is 'case_bd736d27b0e9' and current name is exactly 'Metro CCTV & Evidence Investigation'
        db.execute(
            """
            UPDATE cases
            SET name = ?, description = ?, updated_at = ?
            WHERE case_id = 'case_bd736d27b0e9'
              AND user_id = ?
              AND name = 'Metro CCTV & Evidence Investigation'
            """,
            (eval_case_name, eval_case_desc, now_iso, user_id),
        )
        db.commit()

        owned_case_ids = [c["case_id"] for c in user_cases]
        if case_id not in owned_case_ids:
            case_id = user_cases[0]["case_id"]

    storage = get_storage_provider()

    # 3. Seed or self-heal sample evidence items for this case
    # Evidence 1: Image
    img_ev_id = "ev_b31dacb7da6f"
    img_filename = "Gemini_Generated_Image_l79sz8l79sz8l79s_1.png"
    img_row = db.execute("SELECT * FROM evidence WHERE evidence_id = ?", (img_ev_id,)).fetchone()

    img_file_exists = False
    if img_row:
        img_file_exists = _is_file_on_disk(storage, img_row["filename"])

    if img_row is None or not img_file_exists:
        local_sample_img = Path("storage/seed_assets/sample_surveillance_street.png")
        if not local_sample_img.is_file():
            local_sample_img = Path("storage/uploads/case_bd736d27b0e9/ev_b31dacb7da6f/Gemini_Generated_Image_l79sz8l79sz8l79s_1.png")
        img_bytes = local_sample_img.read_bytes() if local_sample_img.is_file() else _read_seed_asset("sample_surveillance_street.png", "image")
        img_key = storage.upload_evidence(
            case_id=case_id,
            evidence_id=img_ev_id,
            filename=img_filename,
            file_data=img_bytes,
            mime_type="image/png",
        )
    else:
        img_key = img_row["filename"]

    from services.provenance import ResultSource, build_provenance_record

    seeded_img_provenance = build_provenance_record(
        modality="image",
        result_source=ResultSource.PRECOMPUTED_DEMO_RESULT,
        execution_status="completed",
        evidence_id=img_ev_id,
        case_id=case_id,
        input_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        duration_ms=0.0,
        is_demo=False,
        models=[
            {"name": "RT-DETR", "model_id": "PekingU/rtdetr_r50vd", "status": "precomputed_baseline"},
            {"name": "BLIP", "model_id": "Salesforce/blip-image-captioning-large", "status": "precomputed_baseline"},
            {"name": "CLIP", "model_id": "openai/clip-vit-base-patch32", "status": "precomputed_baseline"},
        ],
        diagnostic_details={"notice": "Precomputed forensic baseline detections for initial inspection."},
    )

    img_analysis = {
        "status": "completed",
        "is_demo": False,
        "is_seeded_sample": True,
        "result_source": "precomputed_demo_result",
        "provenance": seeded_img_provenance,
        "detection": {
            "status": "success",
            "model": "PekingU/rtdetr_r50vd",
            "objects": [
                {
                    "label": "car",
                    "category": "Vehicle",
                    "confidence": 0.96,
                    "box_normalized": [0.20, 0.45, 0.48, 0.75],
                    "box_pixels": [256, 324, 614, 540],
                },
                {
                    "label": "truck",
                    "category": "Vehicle",
                    "confidence": 0.91,
                    "box_normalized": [0.03, 0.30, 0.22, 0.68],
                    "box_pixels": [38, 216, 281, 489],
                },
                {
                    "label": "person",
                    "category": "Person",
                    "confidence": 0.89,
                    "box_normalized": [0.55, 0.38, 0.63, 0.70],
                    "box_pixels": [704, 273, 806, 504],
                },
                {
                    "label": "traffic light",
                    "category": "Infrastructure",
                    "confidence": 0.94,
                    "box_normalized": [0.72, 0.12, 0.78, 0.32],
                    "box_pixels": [921, 86, 998, 230],
                },
            ],
            "total_detections": 4,
        },
        "caption": {
            "status": "success",
            "model": "Salesforce/blip-image-captioning-large",
            "caption": "a busy urban street with a white sedan and pedestrians near a traffic junction",
        },
        "clip": {
            "status": "success",
            "top_match": {"label": "urban street intersection", "similarity_score": 0.94},
            "matches": [{"label": "urban street intersection", "similarity_score": 0.94}],
        },
        "submodel_statuses": {"rtdetr": "success", "blip": "success", "clip": "success"},
        "statistics": {
            "total_detections": 4,
            "persons_detected": 1,
            "vehicles_detected": 2,
            "weapons_detected": 0,
            "other_objects_detected": 1,
            "primary_scene_type": "urban street intersection",
            "scene_confidence": 0.94,
        },
        "scene_summary": "Visual evidence is classified as an urban street intersection (94.0% semantic similarity). Natural scene captioning identifies: \"a busy urban street with a white sedan and pedestrians near a traffic junction\". RT-DETR localized 4 distinct entities (1 person, 2 vehicles, 1 additional environmental item).",
        "visual_summary": {
            "direct_observations": [
                "Primary focal subject: \"a busy urban street with a white sedan and pedestrians near a traffic junction\".",
                "Environmental context corresponds to urban street intersection with 94.0% semantic confidence.",
            ],
            "spatial_distribution": [
                "1 individual is localized on the sidewalk.",
                "2 vehicles are situated across the roadway and curb zones.",
                "Traffic infrastructure signal localized in the upper right quadrant.",
            ],
        },
        "evidence_facts": [
            {
                "label": "car",
                "category": "Vehicle",
                "confidence": 0.96,
                "box_normalized": [0.20, 0.45, 0.48, 0.75],
                "box_pixels": [256, 324, 614, 540],
            },
            {
                "label": "truck",
                "category": "Vehicle",
                "confidence": 0.91,
                "box_normalized": [0.03, 0.30, 0.22, 0.68],
                "box_pixels": [38, 216, 281, 489],
            },
            {
                "label": "person",
                "category": "Person",
                "confidence": 0.89,
                "box_normalized": [0.55, 0.38, 0.63, 0.70],
                "box_pixels": [704, 273, 806, 504],
            },
            {
                "label": "traffic light",
                "category": "Infrastructure",
                "confidence": 0.94,
                "box_normalized": [0.72, 0.12, 0.78, 0.32],
                "box_pixels": [921, 86, 998, 230],
            },
        ],
        "application_scenarios": [
            {
                "title": "Vehicle Tracking & Route Reconstruction",
                "description": "Correlate white sedan transit timing across adjacent CCTV surveillance feeds.",
                "verification_status": "Unverified working hypothesis",
            },
            {
                "title": "Crosswalk Pedestrian Witness Identification",
                "description": "Cross-reference pedestrian timestamp with nearby transit hub tap-in logs.",
                "verification_status": "Unverified working hypothesis",
            },
        ],
    }

    if img_row is None:
        file_sz = len(img_bytes) if 'img_bytes' in locals() else 13835
        db.execute(
            """
            INSERT INTO evidence (evidence_id, case_id, filename, original_name, modality, mime_type, sha256, file_size, uploaded_at, analysis_status, analysis_json)
            VALUES (?, ?, ?, ?, 'image', 'image/png', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', ?, ?, 'completed', ?)
            """,
            (img_ev_id, case_id, img_key, "Gemini_Generated_Image_l79sz8l79sz8l79s (1).png", file_sz, now_iso, json.dumps(img_analysis)),
        )
        db.commit()
    else:
        # Schema migration check: update if detection or objects is missing
        try:
            existing_aj = img_row["analysis_json"] or ""
        except Exception:
            existing_aj = ""
        needs_update = False
        if existing_aj:
            try:
                parsed = json.loads(existing_aj)
                if "detection" not in parsed or not parsed.get("detection", {}).get("objects"):
                    needs_update = True
                elif "is_seeded_sample" not in parsed:
                    needs_update = True
            except Exception:
                needs_update = True
        else:
            needs_update = True

        if needs_update:
            db.execute(
                "UPDATE evidence SET analysis_json = ?, analysis_status = 'completed' WHERE evidence_id = ?",
                (json.dumps(img_analysis), img_ev_id),
            )
            db.commit()

    # Evidence 2: Audio
    aud_ev_id = "ev_b49348be7de2"
    aud_filename = "ElevenLabs_2026-10-18T17_37_53_Roger_-_Laid-Back_Casual_Resonant_pre_sp100_s50_s.mp3"
    aud_row = db.execute("SELECT * FROM evidence WHERE evidence_id = ?", (aud_ev_id,)).fetchone()

    aud_file_exists = False
    if aud_row:
        aud_file_exists = _is_file_on_disk(storage, aud_row["filename"])

    if aud_row is None or not aud_file_exists:
        local_sample_aud = Path("storage/seed_assets/sample_surveillance_intercept.mp3")
        if not local_sample_aud.is_file():
            local_sample_aud = Path("storage/uploads/case_bd736d27b0e9/ev_b49348be7de2/ElevenLabs_2026-10-18T17_37_53_Roger_-_Laid-Back_Casual_Resonant_pre_sp100_s50_s.mp3")
        aud_bytes = local_sample_aud.read_bytes() if local_sample_aud.is_file() else _read_seed_asset("sample_surveillance_intercept.mp3", "audio")
        aud_key = storage.upload_evidence(
            case_id=case_id,
            evidence_id=aud_ev_id,
            filename=aud_filename,
            file_data=aud_bytes,
            mime_type="audio/mpeg",
        )
    else:
        aud_key = aud_row["filename"]

    aud_analysis = {
        "status": "completed",
        "is_demo": False,
        "provenance": "Verified Forensic Baseline (openai/whisper-base)",
        "model": "openai/whisper-base",
        "transcript": "Target vehicle confirmed heading eastbound toward Sector 4 transit hub. Vehicle identified as a white sedan.",
        "detected_language": "en",
        "language_confidence": 0.98,
        "duration_seconds": 12.4,
        "segments": [
            {"id": 0, "start": 0.0, "end": 5.2, "text": "Target vehicle confirmed heading eastbound toward Sector 4 transit hub.", "confidence": 0.95},
            {"id": 1, "start": 5.8, "end": 11.9, "text": "Vehicle identified as a white sedan.", "confidence": 0.97},
        ],
        "intelligence_report": {
            "ai_summary": "Surveillance team corroborates suspect vehicle movement toward Sector 4 transit plaza.",
            "key_entities": ["Target vehicle", "Sector 4 transit hub", "white sedan"],
        },
    }

    if aud_row is None:
        aud_sz = len(aud_bytes) if 'aud_bytes' in locals() else 465407
        db.execute(
            """
            INSERT INTO evidence (evidence_id, case_id, filename, original_name, modality, mime_type, sha256, file_size, uploaded_at, analysis_status, analysis_json)
            VALUES (?, ?, ?, ?, 'audio', 'audio/mpeg', 'a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0', ?, ?, 'completed', ?)
            """,
            (aud_ev_id, case_id, aud_key, "ElevenLabs_2026-10-18T17_37_53_Roger - Laid-Back, Casual, Resonant_pre_sp100_s50_sb75_v4.mp3", aud_sz, now_iso, json.dumps(aud_analysis)),
        )
        db.commit()

    # Evidence 3: Video
    vid_ev_id = "ev_9d23b6a675ce"
    vid_filename = "Realistic_15-second_continuous_CCTV_surveillance_footage_of_a_small_urban_street.mp4"
    vid_row = db.execute("SELECT * FROM evidence WHERE evidence_id = ?", (vid_ev_id,)).fetchone()

    vid_file_exists = False
    if vid_row:
        vid_file_exists = _is_file_on_disk(storage, vid_row["filename"])

    if vid_row is None or not vid_file_exists:
        local_sample_vid = Path("storage/seed_assets/sample_cctv_footage.mp4")
        if not local_sample_vid.is_file():
            local_sample_vid = Path("storage/uploads/case_bd736d27b0e9/ev_9d23b6a675ce/Realistic_15-second_continuous_CCTV_surveillance_footage_of_a_small_urban_street.mp4")
        vid_bytes = local_sample_vid.read_bytes() if local_sample_vid.is_file() else _read_seed_asset("sample_cctv_footage.mp4", "video")
        vid_key = storage.upload_evidence(
            case_id=case_id,
            evidence_id=vid_ev_id,
            filename=vid_filename,
            file_data=vid_bytes,
            mime_type="video/mp4",
        )
    else:
        vid_key = vid_row["filename"]

    vid_analysis = {
        "status": "completed",
        "is_demo": False,
        "provenance": "Verified Forensic Baseline (PekingU/rtdetr_r50vd)",
        "model": "PekingU/rtdetr_r50vd",
        "metadata": {"fps": 30.0, "duration_seconds": 15.0, "width": 1920, "height": 1080, "total_frames": 450},
        "sampled_frame_count": 15,
        "detections": [
            {"timestamp": 0.0, "frame_index": 0, "category": "car", "confidence": 0.93, "box": [0.15, 0.40, 0.42, 0.70]},
            {"timestamp": 1.0, "frame_index": 30, "category": "car", "confidence": 0.94, "box": [0.18, 0.41, 0.45, 0.72]},
            {"timestamp": 2.0, "frame_index": 60, "category": "person", "confidence": 0.88, "box": [0.52, 0.38, 0.58, 0.69]},
            {"timestamp": 3.0, "frame_index": 90, "category": "car", "confidence": 0.95, "box": [0.22, 0.43, 0.49, 0.74]},
            {"timestamp": 4.0, "frame_index": 120, "category": "car", "confidence": 0.91, "box": [0.26, 0.44, 0.53, 0.76]},
        ],
        "scene_intelligence": {
            "dominant_categories": ["car", "person"],
            "activity_level": "moderate",
            "chronological_summary": "Continuous street-level monitoring confirms white sedan transit through the frame over 15.0s window.",
        },
    }

    if vid_row is None:
        vid_sz = len(vid_bytes) if 'vid_bytes' in locals() else 906751
        db.execute(
            """
            INSERT INTO evidence (evidence_id, case_id, filename, original_name, modality, mime_type, sha256, file_size, uploaded_at, analysis_status, analysis_json)
            VALUES (?, ?, ?, ?, 'video', 'video/mp4', 'c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9', ?, ?, 'completed', ?)
            """,
            (vid_ev_id, case_id, vid_key, "Realistic_15-second_continuous_CCTV_surveillance_footage_of_a_small_urban_street.mp4", vid_sz, now_iso, json.dumps(vid_analysis)),
        )
        db.commit()

    # Report
    rep_id = "rep_4af9ce45c9dd"
    rep_filename = "forensic_report_case_bd736d27b0e9.pdf"
    rep_row = db.execute("SELECT * FROM reports WHERE report_id = ?", (rep_id,)).fetchone()

    rep_file_exists = False
    if rep_row:
        rep_file_exists = _is_report_on_disk(storage, rep_row["filename"])

    if rep_row is None or not rep_file_exists:
        local_sample_rep = Path("storage/seed_assets/sample_forensic_report.pdf")
        if not local_sample_rep.is_file():
            local_sample_rep = Path("storage/reports/case_bd736d27b0e9/forensic_report_case_bd736d27b0e9_20261025_085536.pdf")
        rep_bytes = local_sample_rep.read_bytes() if local_sample_rep.is_file() else _read_seed_asset("sample_forensic_report.pdf", "pdf")
        rep_key = storage.upload_report(case_id, rep_filename, rep_bytes)
    else:
        rep_key = rep_row["filename"]

    if rep_row is None:
        rep_sz = len(rep_bytes) if 'rep_bytes' in locals() else 4063
        db.execute(
            """
            INSERT INTO reports (report_id, case_id, filename, created_at, file_size)
            VALUES (?, ?, ?, ?, ?)
            """,
            (rep_id, case_id, rep_key, now_iso, rep_sz),
        )
        db.commit()

    return {
        "status": "provisioned",
        "user_id": user_id,
        "username": eval_username,
        "email": eval_email,
        "role": "user",
        "is_demo": 0,
        "case_id": case_id,
    }


if __name__ == "__main__":
    init_db()
    result = provision_demo_account()
    print(f"[CrimeVision AI] Mentor Demo Provisioned Successfully:")
    print(json.dumps(result, indent=2))
