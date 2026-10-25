"""
provision_demo.py — Command-line utility to provision CrimeVision AI accounts and workspaces.

Usage:
  python provision_demo.py
  python provision_demo.py --username user-12 --password user1234
  python provision_demo.py --legacy
"""

import argparse
import json
import sys

from app import create_app
from storage.database import init_db
from storage.provision_demo import ensure_demo_evaluator, provision_demo_account


def main():
    parser = argparse.ArgumentParser(description="Provision CrimeVision AI Accounts & Workspaces")
    parser.add_argument("--username", help="Username (defaults to DEMO_USERNAME or 'user-12')")
    parser.add_argument("--email", help="Email (defaults to DEMO_EMAIL or 'user@gmail.com')")
    parser.add_argument("--password", help="Password (defaults to DEMO_PASSWORD or 'user1234')")
    parser.add_argument("--display-name", help="Display name (defaults to DEMO_DISPLAY_NAME or 'user')")
    parser.add_argument("--case-name", help="Primary case name (defaults to DEMO_CASE_NAME or 'test case')")
    parser.add_argument("--case-description", help="Primary case description (defaults to DEMO_CASE_DESCRIPTION)")
    parser.add_argument("--legacy", action="store_true", help="Also provision legacy read-only case_demo_sentinel")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        init_db()
        eval_res = ensure_demo_evaluator(
            username=args.username,
            password=args.password,
            email=args.email,
            display_name=args.display_name,
            case_name=args.case_name,
            case_description=args.case_description,
        )
        print("=" * 60)
        print("  CrimeVision AI — Evaluator Account Provisioning Report")
        print("=" * 60)
        print(f"  User ID:        {eval_res['user_id']}")
        print(f"  Username:       {eval_res['username']}")
        print(f"  Email:          {eval_res['email']}")
        print(f"  Role:           {eval_res['role']} (is_demo={eval_res['is_demo']})")
        print(f"  Primary Case:   {eval_res['case_id']}")
        print("=" * 60)
        print("Evaluator account is active and ready for full workspace testing.")

        if args.legacy:
            demo_res = provision_demo_account()
            print("=" * 60)
            print("  CrimeVision AI — Legacy Demo Case Provisioned")
            print("=" * 60)
            print(f"  Demo User:      {demo_res['username']}")
            print(f"  Legacy Case:    {demo_res['case_id']}")
            print("=" * 60)


if __name__ == "__main__":
    main()
