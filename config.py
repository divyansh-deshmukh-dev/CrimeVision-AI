"""
config.py — CrimeVision AI application configuration.

Loads environment variables from .env (if present) and exposes typed
configuration values consumed by app.py and all service modules.
"""

import os
import secrets
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent


def load_environment() -> None:
    """Load environment variables from .env if present into os.environ."""
    env_path = BASE_DIR / ".env"
    if env_path.is_file():
        load_dotenv(dotenv_path=env_path, override=True)


# Load immediately upon import
load_environment()


# ── Secret Key Validation (Phase Security Hardening) ─────────────────────────
INSECURE_SECRET_PLACEHOLDERS: frozenset[str] = frozenset({
    "secret",
    "changeme",
    "change-me",
    "dev",
    "development",
    "default",
    "password",
    "test",
    "insecure",
    "admin",
    "12345678",
    "dev-insecure-secret-key-crimevision-local",
})


def validate_production_secret(secret_key: str | None) -> None:
    """Validate that production SECRET_KEY is set and securely configured.

    Never prints or logs the secret key content in errors or messages.
    """
    if not secret_key or not isinstance(secret_key, str) or not secret_key.strip():
        raise RuntimeError(
            "Production configuration error: SECRET_KEY environment variable is required in production mode. "
            "Please configure a strong SECRET_KEY in your environment."
        )
    cleaned = secret_key.strip()
    if len(cleaned) < 16 or cleaned.lower() in INSECURE_SECRET_PLACEHOLDERS:
        raise RuntimeError(
            "Production configuration error: Configured SECRET_KEY is insecure. "
            "It must be at least 16 characters long and must not use a known default placeholder."
        )


class Config:
    """Base configuration — shared by all environments."""

    # ── Flask core ────────────────────────────────────────────────────────────
    SECRET_KEY: str | None = os.getenv("SECRET_KEY")
    DEBUG: bool = os.getenv("FLASK_DEBUG", "0") == "1"
    HOST: str = os.getenv("FLASK_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("FLASK_PORT", "5000"))

    # Trusted reverse proxies (e.g. "127.0.0.1,::1")
    TRUSTED_PROXIES: frozenset[str] = frozenset(
        ip.strip() for ip in os.getenv("TRUSTED_PROXIES", "").split(",") if ip.strip()
    )

    # ── Production Database & Cloud Storage ───────────────────────────────────
    DATABASE_URL: str | None = os.getenv("DATABASE_URL")
    STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "local").lower()
    S3_BUCKET_NAME: str | None = os.getenv("S3_BUCKET_NAME")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    AWS_ACCESS_KEY_ID: str | None = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: str | None = os.getenv("AWS_SECRET_ACCESS_KEY")
    S3_ENDPOINT_URL: str | None = os.getenv("S3_ENDPOINT_URL")

    # ── Demo & Evaluator Account Configuration ────────────────────────────────
    DEMO_LOGIN_ENABLED: bool = os.getenv("DEMO_LOGIN_ENABLED", "1").lower() in ("1", "true", "yes")
    DEMO_USERNAME: str = os.getenv("DEMO_USERNAME", "user-12").strip().lower()
    DEMO_PASSWORD: str = os.getenv("DEMO_PASSWORD", "user1234")
    DEMO_EMAIL: str = os.getenv("DEMO_EMAIL", "user@gmail.com").strip().lower()
    DEMO_DISPLAY_NAME: str = os.getenv("DEMO_DISPLAY_NAME", "user").strip()
    DEMO_CASE_NAME: str = os.getenv("DEMO_CASE_NAME", "test case").strip()
    DEMO_CASE_DESCRIPTION: str = os.getenv("DEMO_CASE_DESCRIPTION", "").strip()

    # ── Storage paths (uses /tmp on serverless Vercel) ─────────────────────────
    if os.getenv("VERCEL"):
        import tempfile
        STORAGE_DIR: Path = Path(tempfile.gettempdir()) / "crimevision_storage"
    else:
        STORAGE_DIR: Path = BASE_DIR / "storage"

    CASES_DIR: Path = STORAGE_DIR / "cases"
    UPLOADS_DIR: Path = STORAGE_DIR / "uploads"
    REPORTS_DIR: Path = STORAGE_DIR / "reports"
    DB_PATH: Path = STORAGE_DIR / "crimevision.db"

    # ── Upload constraints ────────────────────────────────────────────────────
    # 500 MB total limit per upload (evidence files can be large videos)
    MAX_CONTENT_LENGTH: int = 500 * 1024 * 1024

    ALLOWED_IMAGE_EXTENSIONS: frozenset = frozenset(
        {"jpg", "jpeg", "png", "gif", "bmp", "webp", "tiff"}
    )
    ALLOWED_AUDIO_EXTENSIONS: frozenset = frozenset(
        {"mp3", "wav", "ogg", "flac", "m4a", "aac", "wma"}
    )
    ALLOWED_VIDEO_EXTENSIONS: frozenset = frozenset(
        {"mp4", "avi", "mov", "mkv", "webm", "flv", "wmv", "m4v"}
    )

    ALLOWED_EXTENSIONS: frozenset = (
        ALLOWED_IMAGE_EXTENSIONS
        | ALLOWED_AUDIO_EXTENSIONS
        | ALLOWED_VIDEO_EXTENSIONS
    )

    ALLOWED_MIME_TYPES: frozenset = frozenset(
        {
            # Images
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/bmp",
            "image/webp",
            "image/tiff",
            # Audio
            "audio/mpeg",
            "audio/wav",
            "audio/ogg",
            "audio/flac",
            "audio/x-m4a",
            "audio/aac",
            "audio/mp4",
            "audio/x-wav",
            # Video
            "video/mp4",
            "video/x-msvideo",
            "video/quicktime",
            "video/x-matroska",
            "video/webm",
            "video/x-flv",
            "video/x-ms-wmv",
            # Generic / fallback (browsers may send these for video)
            "application/octet-stream",
        }
    )

    # ── AI / LLM Chat Assistant (Phase 7) ────────────────────────────────────
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "gemini").lower()
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # ── Groq LLM ──────────────────────────────────────────────────────────────
    GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")
    GROQ_PRIMARY_MODEL: str = os.getenv(
        "GROQ_PRIMARY_MODEL", "llama-3.3-70b-versatile"
    )
    GROQ_FALLBACK_MODEL: str = os.getenv(
        "GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant"
    )

    # ── AI model identifiers (used from Phase 2 onward) ──────────────────────
    RTDETR_MODEL_NAME: str = os.getenv(
        "RTDETR_MODEL_NAME", "PekingU/rtdetr_r50vd"
    )
    CLIP_MODEL_NAME: str = os.getenv(
        "CLIP_MODEL_NAME", "openai/clip-vit-base-patch32"
    )
    BLIP_MODEL_NAME: str = os.getenv(
        "BLIP_MODEL_NAME", "Salesforce/blip-image-captioning-base"
    )
    WHISPER_MODEL_NAME: str = os.getenv(
        "WHISPER_MODEL_NAME", "openai/whisper-base"
    )

    # ── Demo / sample case ────────────────────────────────────────────────────
    DEMO_CASE_ID: str = "demo_sample_case"
    DEMO_CASE_LABEL: str = "[DEMO SAMPLE CASE]"

    @classmethod
    def ensure_dirs(cls) -> None:
        """Create all required storage directories if they do not exist."""
        for directory in (
            cls.STORAGE_DIR,
            cls.CASES_DIR,
            cls.UPLOADS_DIR,
            cls.REPORTS_DIR,
        ):
            directory.mkdir(parents=True, exist_ok=True)


class DevelopmentConfig(Config):
    DEBUG: bool = True
    SECRET_KEY: str = os.getenv("SECRET_KEY") or "dev-insecure-secret-key-crimevision-local"


class ProductionConfig(Config):
    DEBUG: bool = False
    TESTING: bool = False
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"
    SESSION_COOKIE_SECURE: bool = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
    PERMANENT_SESSION_LIFETIME: int = 86400  # 24 hours in seconds
    # In production, SECRET_KEY must come strictly from the environment; no auto-generation or fallback
    SECRET_KEY: str | None = os.getenv("SECRET_KEY")


class TestingConfig(Config):
    TESTING: bool = True
    DEBUG: bool = True
    SECRET_KEY: str = os.getenv("SECRET_KEY") or "test-secret-key-32-chars-testing-mode!"
    # Use in-memory/temp paths so tests do not pollute the real storage
    # NOTE: Use module-level BASE_DIR (not Config.BASE_DIR) to avoid
    # AttributeError during class body evaluation in Python subclasses.
    _test_storage: Path = BASE_DIR / "storage_test"
    STORAGE_DIR: Path = _test_storage
    CASES_DIR: Path = _test_storage / "cases"
    UPLOADS_DIR: Path = _test_storage / "uploads"
    REPORTS_DIR: Path = _test_storage / "reports"
    DB_PATH: Path = _test_storage / "test.db"


_ENV_CONFIG_MAP: dict[str, type[Config]] = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config() -> type[Config]:
    """Return the Config class matching the FLASK_ENV environment variable."""
    env = os.getenv("FLASK_ENV", "development").lower()
    return _ENV_CONFIG_MAP.get(env, DevelopmentConfig)
