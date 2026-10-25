"""
storage/migrate_data.py — Data migration utility for CrimeVision AI.

Safely migrates local SQLite forensic cases, evidence media, reports, and chat
records into the production database (PostgreSQL / SQLite) and private cloud storage (Amazon S3 / Local).

Features:
  - Dry-run mode (--dry-run) to preview records, file sizes, and destinations.
  - Safe & idempotent: updates or skips existing records without duplicating data.
  - Preserves IDs, timestamps, SHA-256 hashes, and foreign-key relationships.
  - Never deletes local source files or the source SQLite database.
  - Granular selection: defaults to migrating demo/sample cases (--demo-only).
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
from typing import Any, Dict, List, Optional

from storage.database import get_db, init_db


def _sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inspect_source_data(
    source_db_path: Path,
    source_uploads_dir: Path,
    source_reports_dir: Path,
    demo_only: bool = True,
) -> Dict[str, Any]:
    """Inspect and inventory source SQLite database records and filesystem assets."""
    if not source_db_path.is_file():
        raise FileNotFoundError(f"Source database file not found: {source_db_path}")

    conn = sqlite3.connect(f"file:{source_db_path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    try:
        # Inventory cases
        if demo_only:
            cases = conn.execute(
                "SELECT * FROM cases WHERE is_demo = 1 OR user_id IS NULL ORDER BY created_at ASC"
            ).fetchall()
        else:
            cases = conn.execute("SELECT * FROM cases ORDER BY created_at ASC").fetchall()

        case_ids = [c["case_id"] for c in cases]
        case_records = [dict(c) for c in cases]

        # Inventory evidence
        evidence_records: List[Dict[str, Any]] = []
        if case_ids:
            placeholders = ",".join("?" for _ in case_ids)
            ev_rows = conn.execute(
                f"SELECT * FROM evidence WHERE case_id IN ({placeholders}) ORDER BY uploaded_at ASC",
                case_ids,
            ).fetchall()
            for r in ev_rows:
                d = dict(r)
                # Check file on disk
                rel_path = d.get("filename", "")
                disk_path = source_uploads_dir / rel_path
                d["file_exists"] = disk_path.is_file()
                d["disk_size"] = disk_path.stat().st_size if d["file_exists"] else 0
                d["disk_path"] = str(disk_path)
                evidence_records.append(d)

        # Inventory reports
        report_records: List[Dict[str, Any]] = []
        if case_ids:
            placeholders = ",".join("?" for _ in case_ids)
            rep_rows = conn.execute(
                f"SELECT * FROM reports WHERE case_id IN ({placeholders}) ORDER BY created_at ASC",
                case_ids,
            ).fetchall()
            for r in rep_rows:
                d = dict(r)
                rel_path = d.get("filename", "")
                disk_path = source_reports_dir / rel_path
                d["file_exists"] = disk_path.is_file()
                d["disk_size"] = disk_path.stat().st_size if d["file_exists"] else 0
                d["disk_path"] = str(disk_path)
                report_records.append(d)

        # Inventory chat messages
        chat_records: List[Dict[str, Any]] = []
        if case_ids:
            placeholders = ",".join("?" for _ in case_ids)
            chat_rows = conn.execute(
                f"SELECT * FROM chat_messages WHERE case_id IN ({placeholders}) ORDER BY created_at ASC",
                case_ids,
            ).fetchall()
            chat_records = [dict(r) for r in chat_rows]

        # Inventory users if not demo_only
        user_records: List[Dict[str, Any]] = []
        if not demo_only:
            u_rows = conn.execute("SELECT * FROM users ORDER BY created_at ASC").fetchall()
            user_records = [dict(u) for u in u_rows]

        return {
            "source_db": str(source_db_path),
            "cases": case_records,
            "evidence": evidence_records,
            "reports": report_records,
            "chat_messages": chat_records,
            "users": user_records,
        }
    finally:
        conn.close()


def run_migration(
    source_db_path: Path,
    source_uploads_dir: Path,
    source_reports_dir: Path,
    dry_run: bool = True,
    demo_only: bool = True,
    assign_to_user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute migration from source SQLite to target database and active storage provider."""
    from services.storage_service import get_storage_provider

    inventory = inspect_source_data(
        source_db_path=source_db_path,
        source_uploads_dir=source_uploads_dir,
        source_reports_dir=source_reports_dir,
        demo_only=demo_only,
    )

    cases = inventory["cases"]
    evidence = inventory["evidence"]
    reports = inventory["reports"]
    chat_messages = inventory["chat_messages"]
    users = inventory["users"]

    summary = {
        "dry_run": dry_run,
        "demo_only": demo_only,
        "cases_count": len(cases),
        "evidence_count": len(evidence),
        "reports_count": len(reports),
        "chat_count": len(chat_messages),
        "users_count": len(users),
        "files_uploaded": 0,
        "files_verified": 0,
        "records_migrated": 0,
        "details": [],
    }

    if dry_run:
        summary["status"] = "dry_run_completed"
        return summary

    # Ensure target database is initialized with current schema
    init_db()
    target_db = get_db()
    storage = get_storage_provider()

    # 1. Migrate users if requested
    for u in users:
        existing = target_db.execute(
            "SELECT user_id FROM users WHERE user_id = ? OR username = ?",
            (u["user_id"], u["username"]),
        ).fetchone()
        if not existing:
            target_db.execute(
                """
                INSERT INTO users (user_id, display_name, username, email, password_hash, role, created_at, is_active, is_demo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    u["user_id"],
                    u["display_name"],
                    u["username"],
                    u["email"],
                    u["password_hash"],
                    u.get("role", "user"),
                    u["created_at"],
                    u.get("is_active", 1),
                    u.get("is_demo", 0),
                ),
            )
            target_db.commit()

    # 2. Migrate cases
    for c in cases:
        uid = assign_to_user_id if assign_to_user_id else c.get("user_id")
        is_demo_val = 1 if demo_only else c.get("is_demo", 0)

        existing_case = target_db.execute(
            "SELECT case_id FROM cases WHERE case_id = ?", (c["case_id"],)
        ).fetchone()

        if existing_case is None:
            target_db.execute(
                """
                INSERT INTO cases (case_id, user_id, name, description, created_at, updated_at, status, is_demo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    c["case_id"],
                    uid,
                    c["name"],
                    c.get("description", ""),
                    c["created_at"],
                    c["updated_at"],
                    c.get("status", "active"),
                    is_demo_val,
                ),
            )
        else:
            target_db.execute(
                """
                UPDATE cases
                SET user_id = COALESCE(?, user_id), is_demo = ?, updated_at = ?
                WHERE case_id = ?
                """,
                (uid, is_demo_val, c["updated_at"], c["case_id"]),
            )
        target_db.commit()
        summary["records_migrated"] += 1

    # 3. Migrate evidence & upload media
    for ev in evidence:
        case_id = ev["case_id"]
        evidence_id = ev["evidence_id"]
        filename = ev["filename"]
        original_name = ev["original_name"]
        disk_path = Path(ev["disk_path"])

        file_bytes = b""
        if disk_path.is_file():
            file_bytes = disk_path.read_bytes()
            computed_sha = _sha256_of_bytes(file_bytes)
            if computed_sha == ev.get("sha256"):
                summary["files_verified"] += 1

        # Upload to target storage provider
        target_key = filename
        if file_bytes:
            safe_filename = Path(filename).name
            target_key = storage.upload_evidence(
                case_id=case_id,
                evidence_id=evidence_id,
                filename=safe_filename,
                file_data=file_bytes,
                mime_type=ev.get("mime_type", "application/octet-stream"),
            )
            summary["files_uploaded"] += 1

        existing_ev = target_db.execute(
            "SELECT evidence_id FROM evidence WHERE evidence_id = ?", (evidence_id,)
        ).fetchone()

        raw_analysis = ev.get("analysis_json")
        if isinstance(raw_analysis, dict):
            raw_analysis = json.dumps(raw_analysis)

        if existing_ev is None:
            target_db.execute(
                """
                INSERT INTO evidence
                  (evidence_id, case_id, filename, original_name, modality,
                   mime_type, sha256, file_size, uploaded_at, analysis_status, analysis_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence_id,
                    case_id,
                    target_key,
                    original_name,
                    ev["modality"],
                    ev["mime_type"],
                    ev["sha256"],
                    ev["file_size"],
                    ev["uploaded_at"],
                    ev.get("analysis_status", "pending"),
                    raw_analysis,
                ),
            )
        else:
            target_db.execute(
                """
                UPDATE evidence
                SET filename = ?, analysis_status = ?, analysis_json = ?
                WHERE evidence_id = ?
                """,
                (target_key, ev.get("analysis_status", "pending"), raw_analysis, evidence_id),
            )
        target_db.commit()
        summary["records_migrated"] += 1

    # 4. Migrate reports
    for rep in reports:
        case_id = rep["case_id"]
        report_id = rep["report_id"]
        filename = rep["filename"]
        disk_path = Path(rep["disk_path"])

        rep_bytes = b""
        if disk_path.is_file():
            rep_bytes = disk_path.read_bytes()

        target_rep_key = filename
        if rep_bytes:
            safe_rep_name = Path(filename).name
            target_rep_key = storage.upload_report(
                case_id=case_id,
                filename=safe_rep_name,
                report_data=rep_bytes,
            )

        existing_rep = target_db.execute(
            "SELECT report_id FROM reports WHERE report_id = ?", (report_id,)
        ).fetchone()

        if existing_rep is None:
            target_db.execute(
                """
                INSERT INTO reports (report_id, case_id, filename, created_at, file_size)
                VALUES (?, ?, ?, ?, ?)
                """,
                (report_id, case_id, target_rep_key, rep["created_at"], rep.get("file_size", len(rep_bytes))),
            )
        else:
            target_db.execute(
                "UPDATE reports SET filename = ? WHERE report_id = ?",
                (target_rep_key, report_id),
            )
        target_db.commit()
        summary["records_migrated"] += 1

    # 5. Migrate chat messages
    for msg in chat_messages:
        existing_msg = target_db.execute(
            "SELECT message_id FROM chat_messages WHERE message_id = ?", (msg["message_id"],)
        ).fetchone()
        if existing_msg is None:
            target_db.execute(
                """
                INSERT INTO chat_messages (message_id, case_id, role, content, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    msg["message_id"],
                    msg["case_id"],
                    msg["role"],
                    msg["content"],
                    msg.get("metadata_json"),
                    msg["created_at"],
                ),
            )
            target_db.commit()
            summary["records_migrated"] += 1

    summary["status"] = "migration_completed"
    return summary


def main():
    parser = argparse.ArgumentParser(description="CrimeVision AI — Data Migration Utility")
    parser.add_argument("--source-db", default="storage/crimevision.db", help="Path to source SQLite database")
    parser.add_argument("--source-uploads", default="storage/uploads", help="Path to source uploads directory")
    parser.add_argument("--source-reports", default="storage/reports", help="Path to source reports directory")
    parser.add_argument("--dry-run", action="store_true", help="Inspect and report without modifying target")
    parser.add_argument("--include-all-users", action="store_true", help="Migrate all users in addition to demo cases")
    parser.add_argument("--assign-to-user", help="Assign migrated cases to a specific user ID")
    args = parser.parse_args()

    src_db = Path(args.source_db)
    src_uploads = Path(args.source_uploads)
    src_reports = Path(args.source_reports)

    demo_only = not args.include_all_users

    print("=" * 65)
    print("  CrimeVision AI — Cloud & Production Migration Utility")
    print("=" * 65)
    print(f"  Source Database: {src_db}")
    print(f"  Dry-Run Mode:    {args.dry_run}")
    print(f"  Scope:           {'Demo Cases Only' if demo_only else 'Full Migration (All Users & Cases)'}")
    print("=" * 65)

    try:
        res = run_migration(
            source_db_path=src_db,
            source_uploads_dir=src_uploads,
            source_reports_dir=src_reports,
            dry_run=args.dry_run,
            demo_only=demo_only,
            assign_to_user_id=args.assign_to_user,
        )
        print(f"  Cases Found:      {res['cases_count']}")
        print(f"  Evidence Items:   {res['evidence_count']}")
        print(f"  Reports Found:    {res['reports_count']}")
        print(f"  Chat Messages:    {res['chat_count']}")
        if not args.dry_run:
            print(f"  Files Uploaded:   {res['files_uploaded']}")
            print(f"  Hashes Verified:  {res['files_verified']}")
            print(f"  Records Migrated: {res['records_migrated']}")
            print("=" * 65)
            print("  Migration completed successfully!")
        else:
            print("=" * 65)
            print("  Dry-run complete. Run without --dry-run to apply.")
    except Exception as exc:
        print(f"  Migration failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
