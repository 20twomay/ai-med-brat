"""
Репозиторий для работы с чатами
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from models import Chat
from repositories.base_repository import BaseRepository
from sqlalchemy import func, select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ChatRepository(BaseRepository[Chat]):
    """
    Репозиторий для операций с чатами.

    Наследуется от BaseRepository для использования базовых CRUD операций.
    """

    def __init__(self, db: Session):
        """
        Args:
            db: Сессия базы данных
        """
        super().__init__(db, Chat)

    def get_by_id_and_user(self, chat_id: int, user_id: int) -> Optional[Chat]:
        """
        Получить чат по ID и user_id (для проверки владельца).

        Args:
            chat_id: ID чата
            user_id: ID пользователя

        Returns:
            Чат или None если не найден
        """
        return self.db.execute(
            select(Chat).where(
                Chat.id == chat_id, Chat.user_id == user_id, Chat.is_active == True
            )
        ).scalar_one_or_none()

    def get_user_chats(
        self, user_id: int, skip: int = 0, limit: int = 100, include_inactive: bool = False
    ) -> Tuple[List[Chat], int]:
        """
        Получить список чатов пользователя с общим количеством.

        Args:
            user_id: ID пользователя
            skip: Сколько записей пропустить
            limit: Максимальное количество записей
            include_inactive: Включать ли неактивные чаты

        Returns:
            Кортеж (список чатов, общее количество)
        """
        # Базовый запрос
        query = select(Chat).where(Chat.user_id == user_id)
        count_query = select(func.count()).select_from(Chat).where(Chat.user_id == user_id)

        # Фильтр по активности
        if not include_inactive:
            query = query.where(Chat.is_active == True)
            count_query = count_query.where(Chat.is_active == True)

        # Получаем общее количество (оптимизированный запрос)
        total = self.db.execute(count_query).scalar()

        # Получаем чаты с сортировкой и пагинацией
        chats = (
            self.db.execute(
                query.order_by(Chat.updated_at.desc()).offset(skip).limit(limit)
            )
            .scalars()
            .all()
        )

        return chats, total