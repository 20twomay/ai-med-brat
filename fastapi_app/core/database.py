"""
Модуль для работы с базой данных
"""

import logging
from functools import lru_cache

from config import get_settings
from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

logger = logging.getLogger(__name__)


@lru_cache()
def get_sync_engine() -> Engine:
    """
    Создаёт синхронный SQLAlchemy engine для работы с PostgreSQL.
    Используется для совместимости с pandas.read_sql().

    Конфигурация пула:
    - pool_size=10: базовый размер пула соединений
    - max_overflow=20: дополнительные соединения при пиковой нагрузке
    - pool_pre_ping=True: проверка соединения перед использованием
    - pool_recycle=3600: переиспользование соединения каждый час
    - echo=False: отключение логирования SQL запросов
    """
    settings = get_settings()
    engine = create_engine(
        settings.database_endpoint,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,  # 1 час
        echo=False,
    )
    logger.info("Database sync engine initialized")
    return engine


@lru_cache()
def get_async_engine() -> AsyncEngine:
    """
    Создаёт асинхронный SQLAlchemy engine для будущего использования.
    Требует asyncpg driver.

    Конфигурация пула:
    - pool_size=20: базовый размер пула для асинхронных операций
    - max_overflow=10: дополнительные соединения при пиковой нагрузке
    - pool_pre_ping=True: проверка соединения перед использованием
    - pool_recycle=3600: переиспользование соединения каждый час
    - echo=False: отключение логирования SQL запросов
    """
    settings = get_settings()
    # Заменяем postgresql:// на postgresql+asyncpg://
    url = settings.database_endpoint.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(
        url,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=10,
        pool_recycle=3600,  # 1 час
        echo=False,
    )
    logger.info("Database async engine initialized")
    return engine
