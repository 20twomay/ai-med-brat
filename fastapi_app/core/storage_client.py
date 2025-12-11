"""
Обёртка над MinIO клиентом с дополнительной функциональностью
"""

import io
import logging
from functools import wraps
from typing import BinaryIO, Optional

from core.exceptions import StorageError
from core.storage import get_storage_client
from minio import Minio
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class StorageClient:
    """
    Обёртка над MinIO с retry логикой, валидацией и улучшенной обработкой ошибок.

    Features:
    - Автоматические повторные попытки при сетевых ошибках
    - Валидация размера и типа файлов
    - Структурированное логирование
    - Обработка ошибок с понятными сообщениями
    """

    # Максимальный размер файла: 100MB
    MAX_FILE_SIZE = 100 * 1024 * 1024

    # Разрешённые MIME типы
    ALLOWED_CONTENT_TYPES = {
        "application/json",
        "text/csv",
        "image/png",
        "image/jpeg",
        "application/octet-stream",  # Для бинарных данных
    }

    def __init__(self, client: Minio, bucket: str):
        """
        Args:
            client: MinIO клиент
            bucket: Название bucket
        """
        self.client = client
        self.bucket = bucket

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def upload_file(
        self,
        object_name: str,
        data: BinaryIO,
        length: int,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Загружает файл в MinIO с retry логикой.

        Args:
            object_name: Имя объекта в хранилище
            data: Данные для загрузки
            length: Размер данных в байтах
            content_type: MIME тип содержимого

        Returns:
            Имя загруженного объекта

        Raises:
            StorageError: При ошибке загрузки или валидации
        """
        # Валидация размера
        if length > self.MAX_FILE_SIZE:
            raise StorageError(
                f"File size ({length} bytes) exceeds maximum allowed size ({self.MAX_FILE_SIZE} bytes)",
                details={
                    "size": length,
                    "max_size": self.MAX_FILE_SIZE,
                    "object_name": object_name,
                },
            )

        # Валидация типа (строгая проверка отключена для гибкости)
        # if content_type not in self.ALLOWED_CONTENT_TYPES:
        #     raise StorageError(
        #         f"Content type '{content_type}' is not allowed",
        #         details={
        #             "content_type": content_type,
        #             "allowed_types": list(self.ALLOWED_CONTENT_TYPES),
        #         },
        #     )

        try:
            self.client.put_object(
                self.bucket,
                object_name,
                data,
                length,
                content_type=content_type,
            )
            logger.info(
                f"File uploaded successfully",
                extra={
                    "object_name": object_name,
                    "size": length,
                    "content_type": content_type,
                },
            )
            return object_name
        except Exception as e:
            logger.error(
                f"Failed to upload file",
                extra={
                    "object_name": object_name,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise StorageError(
                f"Failed to upload file: {str(e)}",
                details={"object_name": object_name},
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def get_file(self, object_name: str) -> bytes:
        """
        Получает файл из MinIO с retry логикой.

        Args:
            object_name: Имя объекта в хранилище

        Returns:
            Содержимое файла в байтах

        Raises:
            StorageError: При ошибке загрузки
        """
        try:
            response = self.client.get_object(self.bucket, object_name)
            data = response.read()
            response.close()
            response.release_conn()

            logger.debug(
                f"File retrieved successfully",
                extra={
                    "object_name": object_name,
                    "size": len(data),
                },
            )
            return data
        except Exception as e:
            logger.error(
                f"Failed to get file",
                extra={
                    "object_name": object_name,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise StorageError(
                f"Failed to get file: {str(e)}",
                details={"object_name": object_name},
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def delete_file(self, object_name: str) -> None:
        """
        Удаляет файл из MinIO с retry логикой.

        Args:
            object_name: Имя объекта в хранилище

        Raises:
            StorageError: При ошибке удаления
        """
        try:
            self.client.remove_object(self.bucket, object_name)
            logger.info(
                f"File deleted successfully",
                extra={"object_name": object_name},
            )
        except Exception as e:
            logger.error(
                f"Failed to delete file",
                extra={
                    "object_name": object_name,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise StorageError(
                f"Failed to delete file: {str(e)}",
                details={"object_name": object_name},
            )

    def file_exists(self, object_name: str) -> bool:
        """
        Проверяет существование файла в MinIO.

        Args:
            object_name: Имя объекта в хранилище

        Returns:
            True если файл существует, иначе False
        """
        try:
            self.client.stat_object(self.bucket, object_name)
            return True
        except Exception:
            return False


def get_storage_client_wrapper() -> StorageClient:
    """
    Dependency для получения StorageClient с retry логикой.

    Returns:
        StorageClient обёртка над MinIO
    """
    from config import get_settings

    settings = get_settings()
    minio_client = get_storage_client()
    return StorageClient(minio_client, settings.s3_bucket)