import logging

from app.core.config import settings
from app.integrations.minio_client import ensure_bucket_exists

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Ensuring MinIO bucket exists")
    ensure_bucket_exists(settings.MINIO_BUCKET)
    logger.info("MinIO bucket is ready")


if __name__ == "__main__":
    main()
