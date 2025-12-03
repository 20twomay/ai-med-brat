import json
import logging
from typing import Optional
import redis.asyncio as aioredis
from models.session import SessionState, SessionStatus

logger = logging.getLogger(__name__)


class SessionStore:
    """Хранилище сессий на базе Redis"""

    def __init__(self, redis_url: str = "redis://localhost:6379", ttl: int = 3600):
        """
        Args:
            redis_url: URL для подключения к Redis
            ttl: Время жизни сессии в секундах (по умолчанию 1 час)
        """
        self.redis_url = redis_url
        self.ttl = ttl
        self.redis: Optional[aioredis.Redis] = None

    async def connect(self):
        """Подключение к Redis"""
        if self.redis is None:
            self.redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            logger.info("Connected to Redis")

    async def disconnect(self):
        """Отключение от Redis"""
        if self.redis:
            await self.redis.close()
            self.redis = None
            logger.info("Disconnected from Redis")

    def _session_key(self, session_id: str) -> str:
        """Генерирует ключ для сессии"""
        return f"session:{session_id}"

    async def create_session(self, session: SessionState) -> None:
        """Создает новую сессию"""
        if not self.redis:
            await self.connect()

        key = self._session_key(session.session_id)
        data = session.model_dump_json()

        await self.redis.setex(key, self.ttl, data)
        logger.info(f"Created session {session.session_id}")

    async def get_session(self, session_id: str) -> Optional[SessionState]:
        """Получает сессию по ID"""
        if not self.redis:
            await self.connect()

        key = self._session_key(session_id)
        data = await self.redis.get(key)

        if data is None:
            logger.warning(f"Session {session_id} not found")
            return None

        return SessionState.model_validate_json(data)

    async def update_session(self, session: SessionState) -> None:
        """Обновляет существующую сессию"""
        if not self.redis:
            await self.connect()

        key = self._session_key(session.session_id)
        data = session.model_dump_json()

        # Продлеваем TTL при обновлении
        await self.redis.setex(key, self.ttl, data)
        logger.info(f"Updated session {session.session_id}")

    async def delete_session(self, session_id: str) -> None:
        """Удаляет сессию"""
        if not self.redis:
            await self.connect()

        key = self._session_key(session_id)
        await self.redis.delete(key)
        logger.info(f"Deleted session {session_id}")

    async def session_exists(self, session_id: str) -> bool:
        """Проверяет существование сессии"""
        if not self.redis:
            await self.connect()

        key = self._session_key(session_id)
        return await self.redis.exists(key) > 0

    async def extend_ttl(self, session_id: str) -> None:
        """Продлевает время жизни сессии"""
        if not self.redis:
            await self.connect()

        key = self._session_key(session_id)
        await self.redis.expire(key, self.ttl)
        logger.debug(f"Extended TTL for session {session_id}")