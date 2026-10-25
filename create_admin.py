"""
create_admin.py — CLI management script to bootstrap an initial administrator account.

Allows creating an administrator without hardcoded credentials or automatic promotion.
Optionally claims unowned legacy cases and assigns them to the administrator.

Usage
-----
Interactive:
    python create_admin.py

Non-interactive:
    python create_admin.py --username admin --email admin@crimevision.local --password "Secret123!" --display-name "Forensic Lead" --claim-legacy-cases
"""

import argparse
import getpass
import os
import sys
from pathlib import Path

# Ensure application root is in python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import get_config, load_environment
from storage.database import get_db, init_db
from storage.users_store import create_user, get_user_by_username


def main():
    load_environment()
    cfg = get_config()

    parser = argparse.ArgumentParser(description="Create a CrimeVision AI Administrator Account.")
    parser.add_argument("--username", help="Admin username (3-30 chars)")
    parser.add_argument("--email", help="Admin email address")
    parser.add_argument("--password", help="Admin password (min 8 chars)")
    parser.add_argument("--display-name", default="", help="Display name")
    parser.add_argument(
        "--claim-legacy-cases",
        action="store_true",
        help="Assign existing unowned legacy cases to this administrator",
    )

    args = parser.parse_args()

    # Ensure database is initialized
    init_db(cfg.DB_PATH)

    username = args.username
    if not username:
        username = input("Enter admin username [admin]: ").strip() or "admin"

    email = args.email
    if not email:
        email = input("Enter admin email [admin@crimevision.local]: ").strip() or "admin@crimevision.local"

    display_name = args.display_name
    if not display_name:
        display_name = input("Enter display name [Forensic Administrator]: ").strip() or "Forensic Administrator"

    password = args.password
    if not password:
        password = getpass.getpass("Enter admin password (min 8 chars, 1 letter, 1 number/symbol): ")
        password_confirm = getpass.getpass("Confirm admin password: ")
        if password != password_confirm:
            print("Error: Passwords do not match.", file=sys.stderr)
            sys.exit(1)

    # Check if user already exists
    existing = get_user_by_username(username)
    if existing:
        print(f"Error: User '{username}' already exists.", file=sys.stderr)
        sys.exit(1)

    try:
        user = create_user(
            username=username,
            email=email,
            password=password,
            display_name=display_name,
            role="admin",
        )
        print(f"\n[+] Administrator '{user['username']}' ({user['user_id']}) created successfully!")
    except Exception as exc:
        print(f"Error creating administrator: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.claim_legacy_cases:
        db = get_db()
        cur = db.execute(
            "UPDATE cases SET user_id = ? WHERE user_id IS NULL AND is_demo = 0",
            (user["user_id"],),
        )
        db.commit()
        print(f"[+] Claimed and assigned {cur.rowcount} legacy case(s) to administrator '{user['username']}'.")


if __name__ == "__main__":
    main()
