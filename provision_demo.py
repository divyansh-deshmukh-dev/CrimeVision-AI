"""
provision_demo.py — Command-line utility to provision the read-only mentor demo account.

Usage:
  python provision_demo.py
  python provision_demo.py --username demo_mentor --email demo@crimevision.ai
"""

import argparse
import json
import sys

from app import create_app
from storage.database import init_db
from storage.provision_demo import provision_demo_account


def main():
    parser = argparse.ArgumentParser(description="Provision CrimeVision AI Mentor Demo Account & Case")
    parser.add_argument("--username", help="Demo username (defaults to DEMO_USERNAME or 'demo_mentor')")
    parser.add_argument("--email", help="Demo email (defaults to DEMO_EMAIL or 'mentor.demo@crimevision.ai')")
    parser.add_argument("--password", help="Demo password (defaults to DEMO_PASSWORD or random)")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        init_db()
        result = provision_demo_account(
            username=args.username,
            password=args.password,
            email=args.email,
        )
        print("=" * 60)
        print("  CrimeVision AI — Mentor Demo Provisioning Report")
        print("=" * 60)
        print(f"  User ID:        {result['user_id']}")
        print(f"  Username:       {result['username']}")
        print(f"  Email:          {result['email']}")
        print(f"  Role:           {result['role']} (is_demo={result['is_demo']})")
        print(f"  Sample Case:    {result['case_id']}")
        print(f"  Evidence Items: {result['evidence_count']}")
        print(f"  Reports:        {result['report_count']}")
        print("=" * 60)
        print("Demo account is ready for public exploration in read-only mode.")


if __name__ == "__main__":
    main()
