"""
routes/cases.py — Case management REST endpoints.

POST   /api/cases                                  Create a new case
GET    /api/cases                                  List accessible cases
GET    /api/cases/<case_id>                       Retrieve a single case
DELETE /api/cases/<case_id>                       Delete a case
POST   /api/cases/<case_id>/evidence              Upload evidence to a case
GET    /api/cases/<case_id>/evidence              List evidence for a case
GET    /api/cases/<case_id>/evidence/<evidence_id> Get single evidence item
DELETE /api/cases/<case_id>/evidence/<evidence_id> Delete evidence item
GET    /api/cases/<case_id>/evidence/<evidence_id>/file Stream raw evidence file
"""

from datetime import datetime, timezone
import mimetypes
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file

from services.audio_analyzer import AudioAnalyzer
from services.auth_service import get_current_user, login_required, verify_case_access
from services.chat_assistant import APIKeyMissingError, ChatAssistant
from services.fusion_analyzer import FusionAnalyzer
from services.image_analyzer import ImageAnalyzer
from services.pdf_report import ForensicReportGenerator
from services.spatial_mapper import map_case_to_spatial_scene
from services.video_analyzer import VideoAnalyzer
from storage.cases_store import (
    create_case,
    delete_case,
    get_case,
    is_legacy_demo_case,
    is_live_demo_case,
    list_cases,
)
from storage.chat_store import clear_messages, list_messages, save_message
from storage.evidence_store import (
    delete_evidence,
    get_evidence,
    list_evidence,
    save_evidence,
    update_analysis,
)
from storage.reports_store import create_report, get_report, list_reports

cases_bp = Blueprint("cases", __name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _allowed_extension(filename: str, cfg) -> bool:
    ext = Path(filename).suffix.lstrip(".").lower()
    return ext in cfg["ALLOWED_EXTENSIONS"]


def _detect_modality(mime_type: str, filename: str) -> str | None:
    """Return 'image', 'audio', or 'video' based on mime or extension."""
    mime_lower = mime_type.lower()
    if mime_lower.startswith("image/"):
        return "image"
    if mime_lower.startswith("audio/"):
        return "audio"
    if mime_lower.startswith("video/"):
        return "video"

    # Fallback: infer from extension
    ext = Path(filename).suffix.lstrip(".").lower()
    cfg = current_app.config
    if ext in cfg["ALLOWED_IMAGE_EXTENSIONS"]:
        return "image"
    if ext in cfg["ALLOWED_AUDIO_EXTENSIONS"]:
        return "audio"
    if ext in cfg["ALLOWED_VIDEO_EXTENSIONS"]:
        return "video"
    return None


def _error(message: str, code: int = 400):
    return jsonify({"error": message}), code


# ── Case endpoints ────────────────────────────────────────────────────────────

@cases_bp.route("/api/cases", methods=["POST"])
@login_required
def create_case_endpoint():
    """Create a new investigation case owned by the current user."""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return _error("'name' is required and must be non-empty.")

    description = (data.get("description") or "").strip()
    user = get_current_user()
    user_id = user["user_id"] if user else None
    is_demo_user = bool(user and (user.get("role") == "demo" or user.get("is_demo")))
    demo_type = "live" if is_demo_user else None

    try:
        case = create_case(
            name=name,
            description=description,
            user_id=user_id,
            is_demo=False,
            demo_type=demo_type,
        )
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Failed to create case")
        return _error(f"Internal error: {exc}", 500)

    return jsonify({"status": "created", "case": case}), 201


@cases_bp.route("/api/cases", methods=["GET"])
@login_required
def list_cases_endpoint():
    """Return cases accessible to the authenticated user."""
    raw_include = request.args.get("include_demo")
    user = get_current_user()
    user_id = user["user_id"] if user else None
    is_admin = bool(user and user.get("role") == "admin")
    is_demo_user = bool(user and (user.get("role") == "demo" or user.get("is_demo") == 1))

    if raw_include is not None:
        include_demo = raw_include.lower() in ("true", "1", "yes")
    else:
        # Normal authenticated examiners/mentors see their own writable cases without legacy demo pollution
        include_demo = is_admin or is_demo_user

    try:
        cases = list_cases(user_id=user_id, is_admin=is_admin, include_demo=include_demo)
        for c in cases:
            c["is_readonly"] = is_legacy_demo_case(c)
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Failed to list cases")
        return _error(f"Internal error: {exc}", 500)

    return jsonify({"cases": cases, "count": len(cases)}), 200


@cases_bp.route("/api/cases/<string:case_id>", methods=["GET"])
@login_required
def get_case_endpoint(case_id: str):
    """Return a single case if authorized."""
    case, err = verify_case_access(case_id, write=False)
    if err:
        return err
    case_dict = dict(case)
    case_dict["is_readonly"] = is_legacy_demo_case(case_dict)
    return jsonify({"case": case_dict}), 200


@cases_bp.route("/api/cases/<string:case_id>", methods=["DELETE"])
@login_required
def delete_case_endpoint(case_id: str):
    """Delete a case and its related records if authorized."""
    case, err = verify_case_access(case_id, write=True)
    if err:
        return err

    if is_legacy_demo_case(case):
        return jsonify({
            "error": "The legacy demo case cannot be deleted.",
            "code": "DEMO_CASE_READ_ONLY",
        }), 403

    deleted = delete_case(case_id)
    if not deleted:
        return _error(f"Failed to delete case '{case_id}'.", 500)

    return jsonify({
        "status": "deleted",
        "message": f"Case '{case_id}' successfully deleted.",
        "case_id": case_id,
    }), 200


# ── Evidence endpoints ────────────────────────────────────────────────────────

@cases_bp.route("/api/cases/<string:case_id>/evidence", methods=["POST"])
@login_required
def upload_evidence(case_id: str):
    """Upload an evidence file to an existing case."""
    case, err = verify_case_access(case_id, write=True)
    if err:
        return err

    if "file" not in request.files:
        return _error("No 'file' field in request.")

    file_storage = request.files["file"]
    if not file_storage or not file_storage.filename:
        return _error("Uploaded file has no filename.")

    original_name: str = file_storage.filename
    file_data: bytes = file_storage.read()

    if not file_data:
        return _error("Uploaded file is empty.")

    cfg = current_app.config

    if len(file_data) > cfg["MAX_CONTENT_LENGTH"]:
        return _error(
            f"File exceeds maximum allowed size of {cfg['MAX_CONTENT_LENGTH']} bytes.",
            413,
        )

    if not _allowed_extension(original_name, cfg):
        ext = Path(original_name).suffix.lstrip(".")
        return _error(
            f"File extension '.{ext}' is not permitted. Allowed: "
            f"{', '.join(sorted(cfg['ALLOWED_EXTENSIONS']))}."
        )

    mime_type: str = file_storage.mimetype or ""
    if not mime_type or mime_type == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(original_name)
        mime_type = guessed or "application/octet-stream"

    if mime_type not in cfg["ALLOWED_MIME_TYPES"]:
        ext = Path(original_name).suffix.lstrip(".").lower()
        if not (
            ext in cfg["ALLOWED_IMAGE_EXTENSIONS"]
            or ext in cfg["ALLOWED_AUDIO_EXTENSIONS"]
            or ext in cfg["ALLOWED_VIDEO_EXTENSIONS"]
        ):
            return _error(f"MIME type '{mime_type}' is not permitted.")

    modality = _detect_modality(mime_type, original_name)
    if modality is None:
        return _error(
            "Could not determine evidence modality (image/audio/video) for this file."
        )

    try:
        evidence = save_evidence(
            case_id=case_id,
            file_data=file_data,
            original_name=original_name,
            mime_type=mime_type,
            modality=modality,
        )
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Failed to persist evidence")
        return _error(f"Internal error while saving evidence: {exc}", 500)

    return jsonify({"status": "uploaded", "evidence": evidence}), 201


@cases_bp.route("/api/cases/<string:case_id>/evidence", methods=["GET"])
@login_required
def list_evidence_endpoint(case_id: str):
    """List all evidence items for a case."""
    case, err = verify_case_access(case_id, write=False)
    if err:
        return err

    items = list_evidence(case_id)
    return jsonify({"evidence": items, "count": len(items)}), 200


@cases_bp.route(
    "/api/cases/<string:case_id>/evidence/<string:evidence_id>",
    methods=["GET"],
)
@login_required
def get_evidence_endpoint(case_id: str, evidence_id: str):
    """Return a single evidence item."""
    case, err = verify_case_access(case_id, write=False)
    if err:
        return err

    ev = get_evidence(evidence_id)
    if ev is None or ev["case_id"] != case_id:
        return _error(f"Evidence '{evidence_id}' not found in case '{case_id}'.", 404)

    return jsonify({"evidence": ev}), 200


@cases_bp.route(
    "/api/cases/<string:case_id>/evidence/<string:evidence_id>",
    methods=["DELETE"],
)
@login_required
def delete_evidence_endpoint(case_id: str, evidence_id: str):
    """Delete an evidence artifact and its physical files."""
    case, err = verify_case_access(case_id, write=True)
    if err:
        return err

    ev = get_evidence(evidence_id)
    if ev is None or ev["case_id"] != case_id:
        return _error(f"Evidence '{evidence_id}' not found in case '{case_id}'.", 404)

    deleted = delete_evidence(evidence_id)
    if not deleted:
        return _error(f"Failed to delete evidence '{evidence_id}'.", 500)

    return jsonify({
        "status": "deleted",
        "message": f"Evidence '{evidence_id}' successfully deleted.",
        "evidence_id": evidence_id,
        "case_id": case_id,
    }), 200


@cases_bp.route(
    "/api/cases/<string:case_id>/evidence/<string:evidence_id>/file",
    methods=["GET"],
)
@login_required
def get_evidence_file_endpoint(case_id: str, evidence_id: str):
    """Stream evidence file with case authorization and path traversal guards."""
    case, err = verify_case_access(case_id, write=False)
    if err:
        return err

    ev = get_evidence(evidence_id)
    if ev is None or ev["case_id"] != case_id:
        return _error(f"Evidence '{evidence_id}' not found in case '{case_id}'.", 404)

    rel_filename = ev.get("filename", "")
    from services.storage_service import LocalStorageProvider, get_storage_provider
    storage = get_storage_provider()

    if isinstance(storage, LocalStorageProvider):
        uploads_dir = Path(current_app.config["UPLOADS_DIR"]).resolve()
        target_file = (uploads_dir / rel_filename).resolve()

        # Path traversal guard: must be strictly inside uploads_dir
        try:
            target_file.relative_to(uploads_dir)
        except ValueError:
            return _error("Forbidden path access.", 403)

        if not target_file.is_file():
            return _error("Evidence file missing from disk repository.", 404)

        resp = send_file(
            str(target_file),
            mimetype=ev.get("mime_type", "application/octet-stream"),
            as_attachment=False,
            download_name=ev.get("original_name", target_file.name),
        )
        resp.headers["Cache-Control"] = "no-cache, must-revalidate, max-age=0"
        return resp

    # Cloud storage streaming without full memory loading
    try:
        stream, size, mime = storage.get_evidence_stream(rel_filename)
        from flask import Response
        resp = Response(stream, mimetype=mime or ev.get("mime_type", "application/octet-stream"))
        if size is not None:
            resp.headers["Content-Length"] = str(size)
        download_name = ev.get("original_name") or Path(rel_filename).name
        resp.headers["Content-Disposition"] = f'inline; filename="{download_name}"'
        return resp
    except (FileNotFoundError, OSError):
        return _error("Evidence file missing from disk repository.", 404)
    except PermissionError:
        return _error("Forbidden path access.", 403)


@cases_bp.route(
    "/api/cases/<string:case_id>/evidence/<string:evidence_id>/analyze/image",
    methods=["POST"],
)
@login_required
def analyze_image_endpoint(case_id: str, evidence_id: str):
    """Trigger Phase 2 Image Analysis (RT-DETR + CLIP + BLIP) for an image evidence item."""
    user = get_current_user()
    case_peek = get_case(case_id)
    is_legacy = is_legacy_demo_case(case_peek)

    case, err = verify_case_access(case_id, write=not is_legacy)
    if err:
        return err

    ev = get_evidence(evidence_id)
    if ev is None or ev["case_id"] != case_id:
        return _error(f"Evidence '{evidence_id}' not found in case '{case_id}'.", 404)

    # For legacy demo mode: if analysis is already completed, return precomputed analysis immediately
    if is_legacy and ev.get("analysis_status") in ("completed", "partial") and ev.get("analysis_json"):
        demo_analysis = dict(ev.get("analysis_json"))
        if "provenance" not in demo_analysis:
            from services.provenance import ResultSource, build_provenance_record
            demo_analysis["provenance"] = build_provenance_record(
                modality="image",
                result_source=ResultSource.PRECOMPUTED_DEMO_RESULT,
                execution_status=ev.get("analysis_status", "completed"),
                evidence_id=evidence_id,
                case_id=case_id,
                input_sha256=ev.get("sha256") or ev.get("sha256_hash"),
                duration_ms=0.0,
                is_demo=True,
            )
        return jsonify({
            "status": ev.get("analysis_status", "completed"),
            "evidence_id": evidence_id,
            "case_id": case_id,
            "analysis": demo_analysis,
        }), 200

    if ev.get("modality") != "image":
        return _error(
            f"Evidence '{evidence_id}' is of modality '{ev.get('modality')}'. "
            "Only 'image' modality can be analyzed by the image analysis pipeline.",
            400,
        )

    rel_filename = ev.get("filename", "")
    from services.storage_service import get_storage_provider
    storage = get_storage_provider()

    try:
        target_file = storage.get_local_cache_path(rel_filename)
    except (FileNotFoundError, OSError):
        return _error("Evidence file missing from disk repository.", 404)
    except PermissionError:
        return _error("Forbidden path access.", 403)

    body = request.get_json(silent=True) or {}
    if "candidate_labels" in body and not isinstance(body["candidate_labels"], list):
        return _error("'candidate_labels' must be a list of strings.", 400)
    if "labels" in body and not isinstance(body["labels"], list):
        return _error("'labels' must be a list of strings.", 400)
    custom_labels = body.get("candidate_labels") or body.get("labels")

    update_analysis(evidence_id, status="analyzing")

    from services.provenance import current_iso_timestamp, generate_run_id, ResultSource, build_provenance_record
    req_iso = current_iso_timestamp()
    run_id = generate_run_id("img")

    try:
        analyzer = ImageAnalyzer()
        analysis_result = analyzer.analyze_image_pipeline(
            image_path=target_file,
            custom_labels=custom_labels,
            evidence_id=evidence_id,
            case_id=case_id,
            input_sha256=ev.get("sha256") or ev.get("sha256_hash"),
            requested_at=req_iso,
            run_id=run_id,
        )
        final_status = analysis_result.get("status", "completed")
        if final_status == "error":
            final_status = "failed"
            analysis_result["status"] = "failed"
        updated = update_analysis(
            evidence_id,
            status=final_status,
            analysis_data=analysis_result,
        )
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Image analysis failed unexpectedly")
        error_msg = str(exc)
        if len(error_msg) > 300:
            error_msg = error_msg[:300] + "..."
        error_payload = {
            "status": "failed",
            "is_seeded_sample": False,
            "error": error_msg,
            "detections": [],
            "caption": "",
            "summary": "Analysis failed due to runtime execution error.",
            "submodel_statuses": {"rtdetr": "failed", "clip": "failed", "blip": "failed"},
            "provenance": build_provenance_record(
                modality="image",
                result_source=ResultSource.FRESH_INFERENCE,
                execution_status="failed",
                evidence_id=evidence_id,
                case_id=case_id,
                input_sha256=ev.get("sha256") or ev.get("sha256_hash"),
                run_id=run_id,
                requested_at=req_iso,
                submodel_statuses={"rtdetr": "failed", "clip": "failed", "blip": "failed"},
            ),
        }
        updated = update_analysis(evidence_id, status="failed", analysis_data=error_payload)
        return jsonify({
            "status": "failed",
            "evidence_id": evidence_id,
            "case_id": case_id,
            "analysis": error_payload,
            "error": error_msg,
        }), 200

    res_payload = {
        "status": updated.get("analysis_status", final_status) if updated else final_status,
        "evidence_id": evidence_id,
        "case_id": case_id,
        "analysis": updated.get("analysis_json") if updated else analysis_result,
    }
    if final_status == "failed":
        res_payload["error"] = analysis_result.get("error", "Image analysis failed.")

    return jsonify(res_payload), 200


@cases_bp.route(
    "/api/cases/<string:case_id>/evidence/<string:evidence_id>/restore_seeded_sample",
    methods=["POST"],
)
@login_required
def restore_seeded_sample_endpoint(case_id: str, evidence_id: str):
    """Restore verified seeded forensic baseline sample data for a demo evidence item."""
    case, err = verify_case_access(case_id, write=True)
    if err:
        return err

    ev = get_evidence(evidence_id)
    if ev is None or ev["case_id"] != case_id:
        return _error(f"Evidence '{evidence_id}' not found.", 404)

    if evidence_id in ("ev_b31dacb7da6f", "ev_b49348be7de2", "ev_9d23b6a675ce"):
        from storage.database import get_db
        db = get_db()
        # Mark as failed to trigger clean restoration in ensure_demo_evaluator
        db.execute("UPDATE evidence SET analysis_status = 'failed' WHERE evidence_id = ?", (evidence_id,))
        db.commit()

        from storage.provision_demo import ensure_demo_evaluator
        ensure_demo_evaluator()
        updated_ev = get_evidence(evidence_id)
        return jsonify({
            "status": "success",
            "message": f"Restored precomputed baseline sample for evidence '{evidence_id}'.",
            "evidence": updated_ev,
            "analysis": updated_ev.get("analysis_json"),
        }), 200

    return _error("Evidence item does not have a seeded baseline sample.", 400)


@cases_bp.route(
    "/api/cases/<string:case_id>/evidence/<string:evidence_id>/analysis",
    methods=["GET"],
)
@login_required
def get_evidence_analysis_endpoint(case_id: str, evidence_id: str):
    """Retrieve stored analysis results for an evidence item."""
    case, err = verify_case_access(case_id, write=False)
    if err:
        return err

    ev = get_evidence(evidence_id)
    if ev is None or ev["case_id"] != case_id:
        return _error(f"Evidence '{evidence_id}' not found in case '{case_id}'.", 404)

    return jsonify({
        "evidence_id": evidence_id,
        "case_id": case_id,
        "analysis_status": ev.get("analysis_status", "pending"),
        "analysis": ev.get("analysis_json"),
    }), 200


@cases_bp.route(
    "/api/cases/<string:case_id>/evidence/<string:evidence_id>/analyze/audio",
    methods=["POST"],
)
@login_required
def analyze_audio_endpoint(case_id: str, evidence_id: str):
    """Trigger Phase 4 Audio Transcription (Whisper) for an audio evidence item."""
    user = get_current_user()
    case_peek = get_case(case_id)
    is_legacy = is_legacy_demo_case(case_peek)

    case, err = verify_case_access(case_id, write=not is_legacy)
    if err:
        return err

    ev = get_evidence(evidence_id)
    if ev is None or ev["case_id"] != case_id:
        return _error(f"Evidence '{evidence_id}' not found in case '{case_id}'.", 404)

    # For legacy demo mode: if analysis is already completed, return precomputed analysis immediately
    if is_legacy and ev.get("analysis_status") in ("completed", "partial") and ev.get("analysis_json"):
        demo_analysis = dict(ev.get("analysis_json"))
        if "provenance" not in demo_analysis:
            from services.provenance import ResultSource, build_provenance_record
            demo_analysis["provenance"] = build_provenance_record(
                modality="audio",
                result_source=ResultSource.PRECOMPUTED_DEMO_RESULT,
                execution_status=ev.get("analysis_status", "completed"),
                evidence_id=evidence_id,
                case_id=case_id,
                input_sha256=ev.get("sha256") or ev.get("sha256_hash"),
                duration_ms=0.0,
                is_demo=True,
            )
        return jsonify({
            "status": ev.get("analysis_status", "completed"),
            "evidence_id": evidence_id,
            "case_id": case_id,
            "analysis": demo_analysis,
        }), 200

    if ev.get("modality") != "audio":
        return _error(
            f"Evidence '{evidence_id}' is of modality '{ev.get('modality')}'. "
            "Only 'audio' modality can be transcribed by the audio analysis pipeline.",
            400,
        )

    rel_filename = ev.get("filename", "")
    from services.storage_service import get_storage_provider
    storage = get_storage_provider()

    try:
        target_file = storage.get_local_cache_path(rel_filename)
    except (FileNotFoundError, OSError):
        return _error("Audio evidence file missing on disk.", 404)
    except PermissionError:
        return _error("Forbidden path access.", 403)

    body = request.get_json(silent=True) or {}
    forced_language = body.get("language")

    update_analysis(evidence_id, status="analyzing")

    from services.provenance import current_iso_timestamp, generate_run_id, ResultSource, build_provenance_record
    req_iso = current_iso_timestamp()
    run_id = generate_run_id("aud")

    current_app.logger.info(
        "[AUDIO_ANALYSIS_START] run_id=%s evidence_id=%s case_id=%s language=%s",
        run_id, evidence_id, case_id, forced_language
    )

    try:
        analyzer = AudioAnalyzer(
            whisper_model_id=current_app.config.get("WHISPER_MODEL_NAME", "openai/whisper-base"),
        )
        audio_pipeline_result = analyzer.transcribe_audio_pipeline(
            audio_path=target_file,
            forced_language=forced_language,
            evidence_id=evidence_id,
            case_id=case_id,
            input_sha256=ev.get("sha256") or ev.get("sha256_hash"),
            requested_at=req_iso,
            run_id=run_id,
        )
        final_status = audio_pipeline_result.get("status", "completed")
        payload = {
            "status": final_status,
            "is_seeded_sample": False,
            "result_source": ResultSource.FRESH_INFERENCE.value,
            "audio": audio_pipeline_result,
            "whisper": audio_pipeline_result,
            "audio_metadata": audio_pipeline_result.get("audio_metadata", {}),
            "intelligence_report": audio_pipeline_result.get("intelligence_report", {}),
            "provenance": audio_pipeline_result.get("provenance"),
            "submodel_statuses": audio_pipeline_result.get("submodel_statuses"),
        }
        updated = update_analysis(evidence_id, status=final_status, analysis_data=payload)
        current_app.logger.info(
            "[AUDIO_ANALYSIS_COMPLETE] run_id=%s evidence_id=%s status=%s chunks=%s",
            run_id, evidence_id, final_status, audio_pipeline_result.get("chunks_analyzed", 1)
        )
    except Exception as exc:
        current_app.logger.exception("[AUDIO_ANALYSIS_ERROR] run_id=%s evidence_id=%s error=%s", run_id, evidence_id, exc)
        err_msg = str(exc)
        err_cat = "DECODING_ERROR" if any(w in err_msg.lower() for w in ("decode", "codec", "soundfile", "ffmpeg")) else "TRANSCRIPTION_ERROR"
        error_payload = {
            "status": "failed",
            "error_category": err_cat,
            "audio": {
                "status": "failed",
                "error": err_msg,
                "error_category": err_cat,
                "transcript": "",
                "text": "",
                "segments": [],
            },
            "whisper": {
                "status": "failed",
                "error": err_msg,
                "transcript": "",
                "text": "",
                "segments": [],
            },
            "audio_metadata": {},
            "intelligence_report": {},
            "submodel_statuses": {"whisper": "failed"},
            "provenance": build_provenance_record(
                modality="audio",
                result_source=ResultSource.FRESH_INFERENCE,
                execution_status="failed",
                evidence_id=evidence_id,
                case_id=case_id,
                input_sha256=ev.get("sha256") or ev.get("sha256_hash"),
                run_id=run_id,
                requested_at=req_iso,
                submodel_statuses={"whisper": "failed"},
                diagnostic_details={"error_category": err_cat},
            ),
        }
        updated = update_analysis(evidence_id, status="failed", analysis_data=error_payload)
        return jsonify({
            "status": "failed",
            "evidence_id": evidence_id,
            "case_id": case_id,
            "analysis": error_payload,
            "error": err_msg,
            "error_category": err_cat,
        }), 200

    res_payload = {
        "status": updated.get("analysis_status", final_status) if updated else final_status,
        "evidence_id": evidence_id,
        "case_id": case_id,
        "analysis": updated.get("analysis_json") if updated else payload,
    }
    if final_status == "failed":
        res_payload["error"] = audio_pipeline_result.get("error", "Audio analysis failed.")
        res_payload["error_category"] = audio_pipeline_result.get("error_category", "TRANSCRIPTION_ERROR")

    return jsonify(res_payload), 200


@cases_bp.route(
    "/api/cases/<string:case_id>/evidence/<string:evidence_id>/analyze/audio/intelligence",
    methods=["POST"],
)
@login_required
def audio_intelligence_endpoint(case_id: str, evidence_id: str):
    """Generate or retrieve AI Intelligence Report for an audio evidence item."""
    user = get_current_user()
    case_peek = get_case(case_id)
    is_legacy = is_legacy_demo_case(case_peek)

    case, err = verify_case_access(case_id, write=not is_legacy)
    if err:
        return err

    ev = get_evidence(evidence_id)
    if ev is None or ev["case_id"] != case_id:
        return _error(f"Evidence '{evidence_id}' not found in case '{case_id}'.", 404)

    analysis = ev.get("analysis_json") or {}
    audio_data = analysis.get("audio") or analysis.get("whisper") or analysis
    transcript = (audio_data.get("transcript") or audio_data.get("text") or "").strip()
    segments = audio_data.get("segments") or []
    detected_lang = audio_data.get("detected_language") or audio_data.get("language") or "en"

    existing_report = analysis.get("intelligence_report") or audio_data.get("intelligence_report")
    body = request.get_json(silent=True) or {}
    if existing_report and existing_report.get("ai_summary") and not body.get("refresh"):
        reused_report = dict(existing_report)
        reused_report["provenance"] = {
            "provider": existing_report.get("provenance", {}).get("provider", "persisted_cache"),
            "result_source": "persisted_result_reuse",
        }
        return jsonify({
            "status": "completed",
            "evidence_id": evidence_id,
            "intelligence_report": reused_report,
        }), 200

    intel_report = AudioAnalyzer.synthesize_audio_intelligence(
        transcript=transcript,
        segments=segments,
        detected_language=detected_lang,
    )

    analysis["intelligence_report"] = intel_report
    if isinstance(analysis.get("audio"), dict):
        analysis["audio"]["intelligence_report"] = intel_report
    if isinstance(analysis.get("whisper"), dict):
        analysis["whisper"]["intelligence_report"] = intel_report

    if not is_legacy:
        update_analysis(evidence_id, status=ev.get("analysis_status", "completed"), analysis_data=analysis)

    return jsonify({
        "status": "completed",
        "evidence_id": evidence_id,
        "intelligence_report": intel_report,
    }), 200


@cases_bp.route(
    "/api/cases/<string:case_id>/evidence/<string:evidence_id>/analyze/video",
    methods=["POST"],
)
@login_required
def analyze_video_endpoint(case_id: str, evidence_id: str):
    """Trigger Phase 5 Video Frame Extraction & RT-DETR Detection for video evidence."""
    user = get_current_user()
    case_peek = get_case(case_id)
    is_legacy = is_legacy_demo_case(case_peek)

    case, err = verify_case_access(case_id, write=not is_legacy)
    if err:
        return err

    ev = get_evidence(evidence_id)
    if ev is None or ev["case_id"] != case_id:
        return _error(f"Evidence '{evidence_id}' not found in case '{case_id}'.", 404)

    # For legacy demo mode: if analysis is already completed, return precomputed analysis immediately
    if is_legacy and ev.get("analysis_status") in ("completed", "partial") and ev.get("analysis_json"):
        demo_analysis = dict(ev.get("analysis_json"))
        if "provenance" not in demo_analysis:
            from services.provenance import ResultSource, build_provenance_record
            demo_analysis["provenance"] = build_provenance_record(
                modality="video",
                result_source=ResultSource.PRECOMPUTED_DEMO_RESULT,
                execution_status=ev.get("analysis_status", "completed"),
                evidence_id=evidence_id,
                case_id=case_id,
                input_sha256=ev.get("sha256") or ev.get("sha256_hash"),
                duration_ms=0.0,
                is_demo=True,
            )
        return jsonify({
            "status": ev.get("analysis_status", "completed"),
            "evidence_id": evidence_id,
            "case_id": case_id,
            "analysis": demo_analysis,
        }), 200

    if ev.get("modality") != "video":
        return _error(
            f"Evidence '{evidence_id}' is of modality '{ev.get('modality')}'. "
            "Only 'video' modality can be processed by the video analysis pipeline.",
            400,
        )

    rel_filename = ev.get("filename", "")
    from services.storage_service import get_storage_provider
    storage = get_storage_provider()

    try:
        target_file = storage.get_local_cache_path(rel_filename)
    except (FileNotFoundError, OSError):
        return _error("Video evidence file missing on disk.", 404)
    except PermissionError:
        return _error("Forbidden path access.", 403)

    body = request.get_json(silent=True) or {}
    sample_interval = body.get("sample_interval_seconds", 1.0)
    try:
        sample_interval = float(sample_interval)
        if sample_interval <= 0:
            sample_interval = 1.0
    except (ValueError, TypeError):
        sample_interval = 1.0

    max_frames = body.get("max_frames")
    if max_frames is not None:
        try:
            max_frames = int(max_frames)
        except (ValueError, TypeError):
            max_frames = None

    update_analysis(evidence_id, status="analyzing")

    from services.provenance import current_iso_timestamp, generate_run_id, ResultSource, build_provenance_record
    req_iso = current_iso_timestamp()
    run_id = generate_run_id("vid")

    current_app.logger.info(
        "[VIDEO_ANALYSIS_START] run_id=%s evidence_id=%s case_id=%s interval=%.2f max_frames=%s",
        run_id, evidence_id, case_id, sample_interval, max_frames
    )

    try:
        analyzer = VideoAnalyzer()
        video_result = analyzer.analyze_video_pipeline(
            video_path=target_file,
            sample_interval_seconds=sample_interval,
            max_frames=max_frames,
            evidence_id=evidence_id,
            case_id=case_id,
            input_sha256=ev.get("sha256") or ev.get("sha256_hash"),
            requested_at=req_iso,
            run_id=run_id,
        )
        final_status = video_result.get("status", "completed")
        payload = {
            **video_result,
            "status": final_status,
            "video": video_result,
            "video_metadata": video_result.get("metadata", {}),
            "detections": video_result.get("detections", []),
            "sampled_frames": video_result.get("sampled_frames", []),
            "scene_intelligence": video_result.get("scene_intelligence") or video_result.get("intelligence_report", {}),
            "total_frames_sampled": video_result.get("sampled_frame_count", 0),
            "intelligence_report": video_result.get("intelligence_report", {}),
            "provenance": video_result.get("provenance"),
            "submodel_statuses": video_result.get("submodel_statuses"),
        }
        updated = update_analysis(evidence_id, status=final_status, analysis_data=payload)
        current_app.logger.info(
            "[VIDEO_ANALYSIS_COMPLETE] run_id=%s evidence_id=%s status=%s frames_sampled=%d",
            run_id, evidence_id, final_status, len(video_result.get("sampled_frames", []))
        )
    except Exception as exc:
        current_app.logger.exception("[VIDEO_ANALYSIS_ERROR] run_id=%s evidence_id=%s error=%s", run_id, evidence_id, exc)
        error_payload = {
            "status": "failed",
            "error": str(exc),
            "video_metadata": {},
            "detections": [],
            "sampled_frames": [],
            "scene_intelligence": {},
            "total_frames_sampled": 0,
            "intelligence_report": {},
            "submodel_statuses": {"video_pipeline": "failed"},
            "provenance": build_provenance_record(
                modality="video",
                result_source=ResultSource.IN_MEMORY_MODEL_REUSE,
                execution_status="failed",
                evidence_id=evidence_id,
                case_id=case_id,
                input_sha256=ev.get("sha256") or ev.get("sha256_hash"),
                run_id=run_id,
                requested_at=req_iso,
                submodel_statuses={"video_pipeline": "failed"},
            ),
        }
        updated = update_analysis(evidence_id, status="failed", analysis_data=error_payload)
        return jsonify({
            "status": "failed",
            "evidence_id": evidence_id,
            "case_id": case_id,
            "analysis": error_payload,
            "error": str(exc),
        }), 200

    res_payload = {
        "status": updated.get("analysis_status", final_status) if updated else final_status,
        "evidence_id": evidence_id,
        "case_id": case_id,
        "analysis": updated.get("analysis_json") if updated else payload,
    }
    if final_status == "failed":
        res_payload["error"] = video_result.get("error", "Video analysis failed.")

    return jsonify(res_payload), 200


# ── Multimodal Fusion endpoint (Phase 6) ────────────────────────────────────

@cases_bp.route("/api/cases/<string:case_id>/analyze/fusion", methods=["POST"])
@login_required
def analyze_fusion_endpoint(case_id: str):
    """Trigger Phase 6 Multimodal Forensic Evidence Fusion across all case evidence."""
    user = get_current_user()
    case_peek = get_case(case_id)
    is_legacy = is_legacy_demo_case(case_peek)

    case, err = verify_case_access(case_id, write=not is_legacy)
    if err:
        return err

    evidence_items = list_evidence(case_id)

    body = request.get_json(silent=True) or {}
    temporal_window = body.get("temporal_window_seconds", 3.0)
    try:
        temporal_window = float(temporal_window)
        if temporal_window <= 0 or temporal_window > 60:
            temporal_window = 3.0
    except (ValueError, TypeError):
        temporal_window = 3.0

    try:
        analyzer = FusionAnalyzer(temporal_window=temporal_window)
        fusion_result = analyzer.fuse_case_evidence(case=case, evidence_items=evidence_items)
    except Exception as exc:
        current_app.logger.exception("Multimodal evidence fusion failed")
        return _error(f"Multimodal evidence fusion failed: {exc}", 500)

    return jsonify({
        "case_id": case_id,
        "status": fusion_result.get("status", "completed"),
        "fusion": fusion_result,
    }), 200


# ── Report endpoints ─────────────────────────────────────────────────────────

@cases_bp.route("/api/cases/<string:case_id>/report", methods=["POST"])
@cases_bp.route("/api/cases/<string:case_id>/reports/pdf", methods=["POST"])
@login_required
def generate_case_report_endpoint(case_id: str):
    """Generate a structured PDF forensic report for a case and its evidence."""
    user = get_current_user()
    case_peek = get_case(case_id)
    is_legacy = is_legacy_demo_case(case_peek)

    case, err = verify_case_access(case_id, write=not is_legacy)
    if err:
        return err

    body = request.get_json(silent=True) or {}
    evidence_id = body.get("evidence_id")

    # If legacy demo mode and reports already exist, return the preloaded report
    if is_legacy and not evidence_id:
        existing_reports = list_reports(case_id)
        if existing_reports:
            rep = existing_reports[0]
            return jsonify({
                "status": "generated",
                "report": {
                    **rep,
                    "download_url": f"/api/reports/{rep['report_id']}",
                },
            }), 201

    if evidence_id:
        ev = get_evidence(evidence_id)
        if ev is None or ev["case_id"] != case_id:
            return _error(f"Evidence '{evidence_id}' not found in case '{case_id}'.", 404)
        evidence_items = [ev]
    else:
        evidence_items = list_evidence(case_id)

    reports_dir = Path(current_app.config["REPORTS_DIR"])
    case_reports_dir = reports_dir / case_id
    case_reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    pdf_filename = f"forensic_report_{case_id}_{timestamp_str}.pdf"
    pdf_path = case_reports_dir / pdf_filename

    fusion_result = None
    if len(evidence_items) > 1 and not evidence_id:
        try:
            fusion_analyzer = FusionAnalyzer()
            fusion_result = fusion_analyzer.fuse_case_evidence(case=case, evidence_items=evidence_items)
        except Exception as f_err:
            current_app.logger.warning("Optional fusion for report skipped: %s", f_err)

    try:
        uploads_dir = Path(current_app.config["UPLOADS_DIR"])
        scratch_dir = Path(current_app.config["STORAGE_DIR"]) / "scratch"
        scratch_dir.mkdir(parents=True, exist_ok=True)
        generator = ForensicReportGenerator(output_path=pdf_path)
        generator.build_report(
            case=case,
            evidence_items=evidence_items,
            uploads_dir=uploads_dir,
            scratch_dir=scratch_dir,
            fusion_result=fusion_result,
        )
    except Exception as exc:
        current_app.logger.exception("PDF generation failed")
        return _error(f"PDF report generation failed: {exc}", 500)

    from services.storage_service import LocalStorageProvider, get_storage_provider
    storage = get_storage_provider()
    storage_key = storage.upload_report(case_id, pdf_filename, pdf_path.read_bytes())

    try:
        file_size = pdf_path.stat().st_size
    except OSError:
        file_size = len(pdf_path.read_bytes()) if pdf_path.exists() else 0

    report_record = create_report(
        case_id=case_id,
        filename=storage_key,
        file_size=file_size,
    )

    download_url = f"/api/reports/{report_record['report_id']}"

    return jsonify({
        "status": "generated",
        "report": {
            **report_record,
            "download_url": download_url,
        },
    }), 201


@cases_bp.route("/api/reports/<string:report_id>", methods=["GET"])
@login_required
def download_report_endpoint(report_id: str):
    """Download a generated forensic PDF report after verifying case authorization."""
    report = get_report(report_id)
    if report is None:
        return _error(f"Report '{report_id}' not found.", 404)

    # Enforce case-level authorization on direct report downloads
    case_id = report.get("case_id")
    case, err = verify_case_access(case_id, write=False)
    if err:
        return err

    rel_filename = report.get("filename", "")
    from services.storage_service import LocalStorageProvider, get_storage_provider
    storage = get_storage_provider()

    if isinstance(storage, LocalStorageProvider):
        reports_dir = Path(current_app.config["REPORTS_DIR"]).resolve()
        target_pdf = (reports_dir / rel_filename).resolve()

        # Path traversal protection
        try:
            target_pdf.relative_to(reports_dir)
        except ValueError:
            return _error("Forbidden path access.", 403)

        if not target_pdf.is_file():
            return _error("Report file missing on disk.", 404)

        return send_file(
            str(target_pdf),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=target_pdf.name,
        )

    # Cloud storage streaming without full memory loading
    try:
        stream, size, mime = storage.get_report_stream(rel_filename)
        from flask import Response
        resp = Response(stream, mimetype="application/pdf")
        if size is not None:
            resp.headers["Content-Length"] = str(size)
        resp.headers["Content-Disposition"] = f'attachment; filename="{Path(rel_filename).name}"'
        return resp
    except (FileNotFoundError, OSError):
        return _error("Report file missing on disk.", 404)
    except PermissionError:
        return _error("Forbidden path access.", 403)


@cases_bp.route("/api/cases/<string:case_id>/reports", methods=["GET"])
@login_required
def list_case_reports_endpoint(case_id: str):
    """List all reports generated for a given case."""
    case, err = verify_case_access(case_id, write=False)
    if err:
        return err

    items = list_reports(case_id)
    return jsonify({"reports": items, "count": len(items)}), 200


# ── Chat Assistant endpoints (Phase 7) ────────────────────────────────────────

@cases_bp.route("/api/cases/<string:case_id>/chat", methods=["POST"])
@login_required
def case_chat_endpoint(case_id: str):
    """Ask a question about a case's evidence using the AI chat assistant."""
    case, err = verify_case_access(case_id, write=False)
    if err:
        return err

    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    evidence_id = (data.get("evidence_id") or "").strip()
    if not query:
        return _error("'query' is required and cannot be empty.", 400)
    if len(query) > 1000:
        return _error("Query exceeds the maximum allowed length of 1000 characters.", 400)

    save_message(case_id=case_id, role="user", content=query)
    history = list_messages(case_id, limit=10)

    evidence_items = list_evidence(case_id)
    if evidence_id:
        target_ev = get_evidence(evidence_id)
        if target_ev and target_ev.get("case_id") == case_id:
            evidence_items = [target_ev]

    try:
        assistant = ChatAssistant()
        response_data = assistant.ask(
            query=query,
            case=case,
            evidence_items=evidence_items,
            history=history,
        )
    except APIKeyMissingError as exc:
        return jsonify({
            "error": str(exc),
            "api_key_missing": True,
        }), 503
    except Exception as exc:
        current_app.logger.exception("AI Assistant query failed")
        return _error(f"AI Assistant query failed: {exc}", 500)

    assistant_msg = save_message(
        case_id=case_id,
        role="assistant",
        content=response_data.get("answer", ""),
        metadata=response_data,
    )

    return jsonify({
        "status": "success",
        "case_id": case_id,
        "query": query,
        "response": response_data,
        "message_id": assistant_msg["message_id"],
        "created_at": assistant_msg["created_at"],
    }), 200


@cases_bp.route("/api/cases/<string:case_id>/evidence/<string:evidence_id>/chat", methods=["POST"])
@login_required
def evidence_chat_endpoint(case_id: str, evidence_id: str):
    """Ask a question specifically focused on a single evidence item."""
    case, err = verify_case_access(case_id, write=False)
    if err:
        return err

    ev = get_evidence(evidence_id)
    if ev is None or ev.get("case_id") != case_id:
        return _error(f"Evidence '{evidence_id}' not found in case '{case_id}'.", 404)

    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    if not query:
        return _error("'query' is required and cannot be empty.", 400)
    if len(query) > 1000:
        return _error("Query exceeds the maximum allowed length of 1000 characters.", 400)

    displayName = ev.get("original_name") or evidence_id
    save_message(case_id=case_id, role="user", content=f"[{displayName}] {query}")

    history = list_messages(case_id, limit=10)

    try:
        assistant = ChatAssistant()
        response_data = assistant.ask(
            query=query,
            case=case,
            evidence_items=[ev],
            history=history,
        )
    except APIKeyMissingError as exc:
        return jsonify({
            "error": str(exc),
            "api_key_missing": True,
        }), 503
    except Exception as exc:
        current_app.logger.exception("AI Evidence Chat query failed")
        return _error(f"AI Assistant query failed: {exc}", 500)

    assistant_msg = save_message(
        case_id=case_id,
        role="assistant",
        content=response_data.get("answer", ""),
        metadata={**response_data, "evidence_id": evidence_id},
    )

    return jsonify({
        "status": "success",
        "case_id": case_id,
        "evidence_id": evidence_id,
        "query": query,
        "response": response_data,
        "message_id": assistant_msg["message_id"],
        "created_at": assistant_msg["created_at"],
    }), 200


@cases_bp.route("/api/cases/<string:case_id>/chat/history", methods=["GET"])
@login_required
def get_chat_history_endpoint(case_id: str):
    """Retrieve chat history for a specific case."""
    case, err = verify_case_access(case_id, write=False)
    if err:
        return err

    limit = request.args.get("limit", 50)
    try:
        limit_val = int(limit)
    except (ValueError, TypeError):
        limit_val = 50

    messages = list_messages(case_id, limit=limit_val)
    return jsonify({
        "case_id": case_id,
        "messages": messages,
        "count": len(messages),
    }), 200


@cases_bp.route("/api/cases/<string:case_id>/chat/history", methods=["DELETE"])
@login_required
def clear_chat_history_endpoint(case_id: str):
    """Clear chat history for a specific case."""
    case, err = verify_case_access(case_id, write=True)
    if err:
        return err

    deleted_count = clear_messages(case_id)
    return jsonify({
        "status": "cleared",
        "case_id": case_id,
        "deleted_count": deleted_count,
    }), 200


# ── 3D Spatial Visualization endpoint (Phase 8) ──────────────────────────────

@cases_bp.route("/api/cases/<string:case_id>/visualization/spatial", methods=["GET"])
@login_required
def get_spatial_visualization_endpoint(case_id: str):
    """Retrieve 3D spatial scene mapping of detected objects for a case."""
    case, err = verify_case_access(case_id, write=False)
    if err:
        return err

    try:
        evidence_items = list_evidence(case_id)
        scene_data = map_case_to_spatial_scene(case=case, evidence_items=evidence_items)
        return jsonify(scene_data), 200
    except Exception as exc:
        current_app.logger.exception("Failed to build 3D spatial visualization for case %s", case_id)
        return _error(f"Internal error building 3D visualization: {exc}", 500)
