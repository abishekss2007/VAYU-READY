"""Private file storage on self-hosted MinIO (S3-compatible). Files are only reachable through short-lived signed links."""
import io
import logging
from datetime import timedelta

from .config import settings

log = logging.getLogger("vayu.storage")


def _client():
    if not settings.minio_endpoint:
        return None
    from minio import Minio
    return Minio(settings.minio_endpoint, access_key=settings.minio_access_key, secret_key=settings.minio_secret_key, secure=False)


def save(name: str, data: bytes) -> str | None:
    """Stores a file in the private bucket. Returns its name, or None if storage is not configured."""
    try:
        c = _client()
        if not c:
            return None
        if not c.bucket_exists(settings.minio_bucket):
            c.make_bucket(settings.minio_bucket)  # buckets are private by default
        c.put_object(settings.minio_bucket, name, io.BytesIO(data), len(data))
        return name
    except Exception as e:
        log.warning("File storage unavailable: %s", e)
        return None


def signed_link(name: str, minutes: int = 10) -> str | None:
    try:
        c = _client()
        if not c:
            return None
        c.stat_object(settings.minio_bucket, name)
        return c.presigned_get_object(settings.minio_bucket, name, expires=timedelta(minutes=minutes))
    except Exception:
        return None
