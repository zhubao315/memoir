"""S3-compatible object storage adapter (MinIO dev / S3 prod). Requires boto3 at runtime."""

from __future__ import annotations

from urllib.parse import quote

from app.core.config import settings
from app.storage.base import StorageBackend, StoredObject


class S3Storage(StorageBackend):
    def __init__(self):
        try:
            import boto3  # lazy: optional dependency
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("S3 storage requires 'boto3' to be installed") from exc
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            aws_access_key_id=settings.S3_ACCESS_KEY or None,
            aws_secret_access_key=settings.S3_SECRET_KEY or None,
            region_name=settings.S3_REGION,
        )
        self.bucket = settings.S3_BUCKET

    def save(self, key: str, data: bytes, mime_type: str) -> StoredObject:
        import hashlib
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=mime_type)
        return StoredObject(key=key, size=len(data), sha256=hashlib.sha256(data).hexdigest(), mime_type=mime_type)

    def read(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    def signed_url(self, key: str, expires_in: int, filename: str | None = None) -> str:
        params = {"ResponseContentDisposition": f'attachment; filename="{quote(filename or key)}"'} if filename else {}
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key, **params},
            ExpiresIn=expires_in,
        )
