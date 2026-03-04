from functools import lru_cache

from minio import Minio
from minio.error import S3Error

from app.core.config import settings


@lru_cache(maxsize=1)
def get_minio_client() -> Minio:
    return Minio(
        endpoint=settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
        region=settings.MINIO_REGION,
    )


def ensure_bucket_exists(bucket_name: str) -> None:
    client = get_minio_client()
    try:
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
    except S3Error:
        raise
