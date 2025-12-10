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
    """
    settings = get_settings()
    engine = create_engine(
        settings.database_endpoint,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    logger.info("Database sync engine initialized")
    return engine


@lru_cache()
def get_async_engine() -> AsyncEngine:
    """
    Создаёт асинхронный SQLAlchemy engine для будущего использования.
    Требует asyncpg driver.
    """
    settings = get_settings()
    # Заменяем postgresql:// на postgresql+asyncpg://
    url = settings.database_endpoint.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(
        url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    logger.info("Database async engine initialized")
    return engine
