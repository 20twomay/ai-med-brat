"""
Централизованная конфигурация приложения
"""

import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения с валидацией через Pydantic"""

    # Database
    database_endpoint: str

    # S3/MinIO
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str

    # LLM
    openrouter_api_key: str
    openrouter_base_url: str
    model_name: str

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Возвращает синглтон настроек"""
    return Settings()
