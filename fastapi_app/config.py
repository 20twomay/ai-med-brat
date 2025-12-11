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

    # Security
    auth_secret_key: str
    auth_algorithm: str = "HS256"
    auth_access_token_expire_days: int = 30

    # CORS
    cors_allowed_origins: str = "http://localhost:8501,http://localhost:3000"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Возвращает синглтон настроек"""
    return Settings()
