"""
api/index.py — WSGI entry point for Vercel Serverless Functions.

Exposes the configured Flask application instance as ``app`` for the
Vercel Python runtime (@vercel/python).
"""

from pathlib import Path
import sys

# Ensure repository root is on sys.path for serverless imports
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app

app = create_app()
