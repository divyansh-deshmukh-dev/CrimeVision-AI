"""
tests/conftest.py — pytest fixtures shared across CrimeVision AI tests.

Sets up:
  - A test Flask app with an isolated temporary database and storage tree.
  - A Flask test client (``client``) authenticated as a test examiner with CSRF token.
  - An unauthenticated client (``unauthenticated_client``) for security boundary testing.
  - Synthetic media fixtures (PNG, WAV, MP4).
"""

import io
import os
from pathlib import Path
import secrets
import struct
import tempfile

import pytest

from app import create_app
from storage.users_store import create_user


# ── Tiny synthetic media helpers ──────────────────────────────────────────────

def _make_tiny_png() -> bytes:
    """Return the bytes of a valid 1×1 red pixel PNG."""
    import zlib

    def chunk(ctype: bytes, data: bytes) -> bytes:
        c = ctype + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr = chunk(b"IHDR", ihdr_data)

    raw = b"\x00\xFF\x00\x00"   # filter byte + R G B for 1 pixel
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")

    return signature + ihdr + idat + iend


def _make_tiny_wav() -> bytes:
    """Return the bytes of a valid minimal WAV file (1 sample, 8-bit mono)."""
    num_samples = 1
    sample_rate = 8000
    num_channels = 1
    bits_per_sample = 8
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    data_size = num_samples * block_align
    chunk_size = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        chunk_size,
        b"WAVE",
        b"fmt ",
        16,               # PCM subchunk size
        1,                # PCM format
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )
    sample_data = b"\x80"  # silence (128 = midpoint for unsigned 8-bit)
    return header + sample_data


def _make_tiny_mp4() -> bytes:
    """Return a minimal ftyp box that browsers / mimetypes accept as video/mp4."""
    box = b"\x00\x00\x00\x14ftypisom\x00\x00\x00\x00isom"
    return box


# ── pytest fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def tiny_png() -> bytes:
    return _make_tiny_png()


@pytest.fixture(scope="session")
def tiny_wav() -> bytes:
    return _make_tiny_wav()


@pytest.fixture(scope="session")
def tiny_mp4() -> bytes:
    return _make_tiny_mp4()


from flask.testing import FlaskClient


class AutoCSRFClient(FlaskClient):
    """Test client that automatically attaches session CSRF token to headers when not explicitly overridden."""

    def open(self, *args, **kwargs):
        headers = kwargs.get("headers")
        # If headers does not explicitly define X-CSRF-Token or X-CSRFToken
        if headers is None or ("X-CSRF-Token" not in headers and "X-CSRFToken" not in headers):
            try:
                with self.session_transaction() as sess:
                    token = sess.get("csrf_token")
                    if token:
                        if headers is None:
                            kwargs["headers"] = {}
                        kwargs["headers"]["X-CSRF-Token"] = token
            except Exception:
                pass
        return super().open(*args, **kwargs)


@pytest.fixture()
def app(tmp_path: Path):
    """Create a Flask test app with fully isolated temporary storage."""
    storage = tmp_path / "storage"
    cfg = {
        "TESTING": True,
        "DEBUG": False,
        "STORAGE_DIR": storage,
        "CASES_DIR":   storage / "cases",
        "UPLOADS_DIR": storage / "uploads",
        "REPORTS_DIR": storage / "reports",
        "DB_PATH":     storage / "test.db",
        "GROQ_API_KEY": None,
        "GEMINI_API_KEY": None,
        "SECRET_KEY": "test-super-secret-key-32-bytes-long!",
    }
    flask_app = create_app(config_override=cfg)
    flask_app.test_client_class = AutoCSRFClient
    yield flask_app


@pytest.fixture()
def test_user(app):
    """Create and return the primary test examiner user."""
    with app.app_context():
        user = create_user(
            username="test_examiner",
            email="examiner@test.local",
            password="TestPassword123!",
            display_name="Test Examiner",
            role="user",
            user_id="usr_test_default",
        )
        return user


@pytest.fixture()
def client(app, test_user):
    """Return an authenticated test client with valid session and CSRF header."""
    csrf_token = secrets.token_hex(32)
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["user_id"] = test_user["user_id"]
        sess["username"] = test_user["username"]
        sess["role"] = test_user["role"]
        sess["display_name"] = test_user["display_name"]
        sess["csrf_token"] = csrf_token
    return c


@pytest.fixture()
def unauthenticated_client(app):
    """Return an unauthenticated test client with an initial CSRF session (simulating a browser on /login or /signup)."""
    csrf_token = secrets.token_hex(32)
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["csrf_token"] = csrf_token
    return c


@pytest.fixture()
def raw_client(app):
    """Return a raw unauthenticated test client without any pre-existing session or headers."""
    # Use standard FlaskClient without AutoCSRF
    return FlaskClient(app)


@pytest.fixture()
def case_id(client) -> str:
    """Create a case and return its ID for downstream tests."""
    resp = client.post(
        "/api/cases",
        json={"name": "Test Case", "description": "Automated test case"},
        content_type="application/json",
    )
    assert resp.status_code == 201
    return resp.get_json()["case"]["case_id"]
