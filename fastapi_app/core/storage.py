"""
Модуль для работы с S3/MinIO хранилищем
"""

import logging
from functools import lru_cache

from config import get_settings
from minio import Minio

logger = logging.getLogger(__name__)


@lru_cache()
def get_storage_client() -> Minio:
    """
    Создаёт и настраивает MinIO клиент.
    При первом вызове создаёт bucket если он не существует.
    """
    settings = get_settings()

    # Убираем схему протокола из endpoint для minio клиента
    endpoint = settings.s3_endpoint.replace("http://", "").replace("https://", "")

    client = Minio(
        endpoint,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        secure=False,
    )

    # Создаём bucket если не существует
    try:
        if not client.bucket_exists(settings.s3_bucket):
            client.make_bucket(settings.s3_bucket)
            logger.info(f"Created MinIO bucket: {settings.s3_bucket}")
        else:
            logger.info(f"MinIO bucket exists: {settings.s3_bucket}")
    except Exception as e:
        logger.error(f"Failed to check/create MinIO bucket: {e}")
        raise

    return client
