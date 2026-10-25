"""
services/storage_service.py — Unified storage abstraction for CrimeVision AI.

Supports:
  1. Local filesystem storage (for development, testing, and air-gapped environments).
  2. Amazon S3 / S3-compatible cloud object storage (for production serverless deployments like Vercel).

Ensures:
  - Private by default: forensic evidence is never publicly readable.
  - Streaming support: large video files are streamed in chunks without full memory loading.
  - Local path caching: AI models and OpenCV decoders receive local filesystem paths when needed.
  - Secure credential management via environment variables.
"""

from abc import ABC, abstractmethod
import io
import mimetypes
import os
from pathlib import Path
import shutil
import stat
import tempfile
from typing import BinaryIO, Generator, Iterable, Optional, Tuple

from flask import current_app


class BaseStorageProvider(ABC):
    """Abstract base class defining the storage contract."""

    @abstractmethod
    def upload_evidence(
        self,
        case_id: str,
        evidence_id: str,
        filename: str,
        file_data: bytes,
        mime_type: str,
    ) -> str:
        """Upload evidence file and return the relative storage key."""
        pass

    @abstractmethod
    def get_evidence_stream(
        self, storage_key: str, chunk_size: int = 65536
    ) -> Tuple[Iterable[bytes], Optional[int], str]:
        """Return (chunk_generator, file_size, mime_type) for streaming."""
        pass

    @abstractmethod
    def get_evidence_bytes(self, storage_key: str) -> bytes:
        """Retrieve raw evidence bytes."""
        pass

    @abstractmethod
    def delete_evidence(
        self, case_id: str, evidence_id: str, storage_key: Optional[str] = None
    ) -> bool:
        """Delete evidence files/objects from storage."""
        pass

    @abstractmethod
    def upload_report(
        self, case_id: str, filename: str, report_data: bytes
    ) -> str:
        """Upload generated report and return relative storage key."""
        pass

    @abstractmethod
    def get_report_stream(
        self, storage_key: str, chunk_size: int = 65536
    ) -> Tuple[Iterable[bytes], Optional[int], str]:
        """Return (chunk_generator, file_size, mime_type) for report streaming."""
        pass

    @abstractmethod
    def get_local_cache_path(
        self, storage_key: str, is_report: bool = False
    ) -> Path:
        """Ensure file is available on local disk and return its Path."""
        pass

    @abstractmethod
    def generate_presigned_url(
        self,
        storage_key: str,
        is_report: bool = False,
        expires_in: int = 3600,
        download_name: Optional[str] = None,
    ) -> Optional[str]:
        """Return a temporary signed URL if supported by provider, else None."""
        pass


class LocalStorageProvider(BaseStorageProvider):
    """Local filesystem storage provider for development and testing."""

    def __init__(
        self, uploads_dir: Optional[Path] = None, reports_dir: Optional[Path] = None
    ):
        if uploads_dir is not None:
            self._uploads_dir = Path(uploads_dir).resolve()
        else:
            try:
                self._uploads_dir = Path(current_app.config["UPLOADS_DIR"]).resolve()
            except RuntimeError:
                from config import get_config
                self._uploads_dir = Path(get_config().UPLOADS_DIR).resolve()

        if reports_dir is not None:
            self._reports_dir = Path(reports_dir).resolve()
        else:
            try:
                self._reports_dir = Path(current_app.config["REPORTS_DIR"]).resolve()
            except RuntimeError:
                from config import get_config
                self._reports_dir = Path(get_config().REPORTS_DIR).resolve()

        self._uploads_dir.mkdir(parents=True, exist_ok=True)
        self._reports_dir.mkdir(parents=True, exist_ok=True)

    @property
    def uploads_dir(self) -> Path:
        from flask import has_app_context
        if has_app_context() and "UPLOADS_DIR" in current_app.config:
            p = Path(current_app.config["UPLOADS_DIR"]).resolve()
            p.mkdir(parents=True, exist_ok=True)
            return p
        return self._uploads_dir

    @property
    def reports_dir(self) -> Path:
        from flask import has_app_context
        if has_app_context() and "REPORTS_DIR" in current_app.config:
            p = Path(current_app.config["REPORTS_DIR"]).resolve()
            p.mkdir(parents=True, exist_ok=True)
            return p
        return self._reports_dir

    def upload_evidence(
        self,
        case_id: str,
        evidence_id: str,
        filename: str,
        file_data: bytes,
        mime_type: str,
    ) -> str:
        evidence_dir = self.uploads_dir / case_id / evidence_id
        evidence_dir.mkdir(parents=True, exist_ok=True)
        target_file = evidence_dir / filename
        if target_file.is_file():
            try:
                target_file.chmod(stat.S_IWRITE)
            except OSError:
                pass
        target_file.write_bytes(file_data)

        # Make file read-only on disk (forensic chain-of-custody practice)
        try:
            current_mode = target_file.stat().st_mode
            target_file.chmod(current_mode & ~(stat.S_IWRITE | stat.S_IWGRP | stat.S_IWOTH))
        except OSError:
            pass

        return str(target_file.relative_to(self.uploads_dir)).replace("\\", "/")

    def get_evidence_stream(
        self, storage_key: str, chunk_size: int = 65536
    ) -> Tuple[Iterable[bytes], Optional[int], str]:
        file_path = (self.uploads_dir / storage_key).resolve()
        if not file_path.is_file():
            raise FileNotFoundError(f"Evidence file not found: {storage_key}")

        # Path traversal guard
        try:
            file_path.relative_to(self.uploads_dir)
        except ValueError:
            raise PermissionError("Access forbidden: path traversal detected")

        file_size = file_path.stat().st_size
        mime_type, _ = mimetypes.guess_type(str(file_path))
        mime_type = mime_type or "application/octet-stream"

        def _chunk_generator() -> Generator[bytes, None, None]:
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk

        return _chunk_generator(), file_size, mime_type

    def get_evidence_bytes(self, storage_key: str) -> bytes:
        file_path = (self.uploads_dir / storage_key).resolve()
        if not file_path.is_file():
            raise FileNotFoundError(f"Evidence file not found: {storage_key}")
        return file_path.read_bytes()

    def delete_evidence(
        self, case_id: str, evidence_id: str, storage_key: Optional[str] = None
    ) -> bool:
        evidence_dir = self.uploads_dir / case_id / evidence_id
        if evidence_dir.exists():
            def _remove_readonly(func, path, exc_info):
                try:
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                except Exception:
                    pass

            shutil.rmtree(evidence_dir, onerror=_remove_readonly)
            return True
        return False

    def upload_report(
        self, case_id: str, filename: str, report_data: bytes
    ) -> str:
        case_dir = self.reports_dir / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        target_file = case_dir / filename
        if target_file.is_file():
            try:
                target_file.chmod(stat.S_IWRITE)
            except OSError:
                pass
        target_file.write_bytes(report_data)
        return str(target_file.relative_to(self.reports_dir)).replace("\\", "/")

    def get_report_stream(
        self, storage_key: str, chunk_size: int = 65536
    ) -> Tuple[Iterable[bytes], Optional[int], str]:
        file_path = (self.reports_dir / storage_key).resolve()
        if not file_path.is_file():
            raise FileNotFoundError(f"Report file not found: {storage_key}")

        try:
            file_path.relative_to(self.reports_dir)
        except ValueError:
            raise PermissionError("Access forbidden: path traversal detected")

        file_size = file_path.stat().st_size

        def _chunk_generator() -> Generator[bytes, None, None]:
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk

        return _chunk_generator(), file_size, "application/pdf"

    def get_local_cache_path(
        self, storage_key: str, is_report: bool = False
    ) -> Path:
        base = self.reports_dir if is_report else self.uploads_dir
        path = (base / storage_key).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"File not found on local storage: {storage_key}")
        return path

    def generate_presigned_url(
        self,
        storage_key: str,
        is_report: bool = False,
        expires_in: int = 3600,
        download_name: Optional[str] = None,
    ) -> Optional[str]:
        # Local filesystem does not produce remote presigned URLs
        return None


class S3StorageProvider(BaseStorageProvider):
    """Production Amazon S3 / S3-compatible cloud object storage provider."""

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        region: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        s3_client: Optional[object] = None,
    ):
        self.bucket_name = (
            bucket_name
            or os.getenv("S3_BUCKET_NAME")
            or "crimevision-evidence"
        )
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self.endpoint_url = endpoint_url or os.getenv("S3_ENDPOINT_URL")
        self.access_key_id = access_key_id or os.getenv("AWS_ACCESS_KEY_ID")
        self.secret_access_key = secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY")

        # Cache directory for local AI inference runs
        if cache_dir:
            self.cache_dir = Path(cache_dir).resolve()
        else:
            temp_root = Path(tempfile.gettempdir())
            self.cache_dir = temp_root / "crimevision_s3_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._s3_client = s3_client

    def _get_client(self):
        """Lazy-initialize boto3 S3 client."""
        if self._s3_client is not None:
            return self._s3_client

        import boto3
        from botocore.config import Config as BotoConfig

        kwargs = {
            "region_name": self.region,
            "config": BotoConfig(signature_version="s3v4"),
        }
        if self.endpoint_url:
            kwargs["endpoint_url"] = self.endpoint_url
        if self.access_key_id and self.secret_access_key:
            kwargs["aws_access_key_id"] = self.access_key_id
            kwargs["aws_secret_access_key"] = self.secret_access_key

        self._s3_client = boto3.client("s3", **kwargs)
        return self._s3_client

    def upload_evidence(
        self,
        case_id: str,
        evidence_id: str,
        filename: str,
        file_data: bytes,
        mime_type: str,
    ) -> str:
        s3_key = f"{case_id}/{evidence_id}/{filename}"
        client = self._get_client()
        client.put_object(
            Bucket=self.bucket_name,
            Key=s3_key,
            Body=file_data,
            ContentType=mime_type,
            Metadata={
                "case_id": case_id,
                "evidence_id": evidence_id,
                "original_filename": filename,
            },
        )
        return s3_key

    def get_evidence_stream(
        self, storage_key: str, chunk_size: int = 65536
    ) -> Tuple[Iterable[bytes], Optional[int], str]:
        client = self._get_client()
        response = client.get_object(Bucket=self.bucket_name, Key=storage_key)
        body = response["Body"]
        content_length = response.get("ContentLength")
        mime_type = response.get("ContentType", "application/octet-stream")

        def _chunk_generator() -> Generator[bytes, None, None]:
            try:
                while True:
                    chunk = body.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
            finally:
                body.close()

        return _chunk_generator(), content_length, mime_type

    def get_evidence_bytes(self, storage_key: str) -> bytes:
        client = self._get_client()
        response = client.get_object(Bucket=self.bucket_name, Key=storage_key)
        return response["Body"].read()

    def delete_evidence(
        self, case_id: str, evidence_id: str, storage_key: Optional[str] = None
    ) -> bool:
        client = self._get_client()
        prefix = f"{case_id}/{evidence_id}/"
        try:
            # List objects with prefix and delete
            paginator = client.get_paginator("list_objects_v2")
            deleted_any = False
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                objects = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
                if objects:
                    client.delete_objects(
                        Bucket=self.bucket_name, Delete={"Objects": objects}
                    )
                    deleted_any = True
            if storage_key and not deleted_any:
                client.delete_object(Bucket=self.bucket_name, Key=storage_key)
                return True
            return deleted_any
        except Exception:
            return False

    def upload_report(
        self, case_id: str, filename: str, report_data: bytes
    ) -> str:
        s3_key = f"reports/{case_id}/{filename}"
        client = self._get_client()
        client.put_object(
            Bucket=self.bucket_name,
            Key=s3_key,
            Body=report_data,
            ContentType="application/pdf",
            Metadata={"case_id": case_id, "report_filename": filename},
        )
        return s3_key

    def get_report_stream(
        self, storage_key: str, chunk_size: int = 65536
    ) -> Tuple[Iterable[bytes], Optional[int], str]:
        client = self._get_client()
        key = storage_key if storage_key.startswith("reports/") else f"reports/{storage_key}"
        response = client.get_object(Bucket=self.bucket_name, Key=key)
        body = response["Body"]
        content_length = response.get("ContentLength")
        mime_type = response.get("ContentType", "application/pdf")

        def _chunk_generator() -> Generator[bytes, None, None]:
            try:
                while True:
                    chunk = body.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
            finally:
                body.close()

        return _chunk_generator(), content_length, mime_type

    def get_local_cache_path(
        self, storage_key: str, is_report: bool = False
    ) -> Path:
        """Download file from S3 into a local temporary cache path and return it."""
        norm_key = storage_key.replace("\\", "/").strip("/")
        local_path = (self.cache_dir / norm_key).resolve()

        if local_path.is_file() and local_path.stat().st_size > 0:
            return local_path

        local_path.parent.mkdir(parents=True, exist_ok=True)
        client = self._get_client()
        full_key = norm_key
        if is_report and not norm_key.startswith("reports/"):
            full_key = f"reports/{norm_key}"

        client.download_file(self.bucket_name, full_key, str(local_path))
        return local_path

    def generate_presigned_url(
        self,
        storage_key: str,
        is_report: bool = False,
        expires_in: int = 3600,
        download_name: Optional[str] = None,
    ) -> Optional[str]:
        client = self._get_client()
        full_key = storage_key
        if is_report and not storage_key.startswith("reports/"):
            full_key = f"reports/{storage_key}"

        params = {"Bucket": self.bucket_name, "Key": full_key}
        if download_name:
            params["ResponseContentDisposition"] = f'attachment; filename="{download_name}"'

        url = client.generate_presigned_url(
            "get_object", Params=params, ExpiresIn=max(60, expires_in)
        )
        return url


# ── Global Storage Provider Accessor ──────────────────────────────────────────

_storage_provider: Optional[BaseStorageProvider] = None


def get_storage_provider() -> BaseStorageProvider:
    """Return the active storage provider instance based on runtime configuration."""
    global _storage_provider
    if _storage_provider is not None:
        return _storage_provider

    backend = os.getenv("STORAGE_BACKEND", "").lower()
    s3_bucket = os.getenv("S3_BUCKET_NAME")

    # In production on Vercel or when S3_BUCKET_NAME / STORAGE_BACKEND=s3 is set
    if backend == "s3" or (s3_bucket and backend != "local"):
        _storage_provider = S3StorageProvider()
    else:
        _storage_provider = LocalStorageProvider()

    return _storage_provider


def set_storage_provider(provider: Optional[BaseStorageProvider]) -> None:
    """Explicitly set or reset the active storage provider (primarily for tests)."""
    global _storage_provider
    _storage_provider = provider
