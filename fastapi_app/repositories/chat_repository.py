"""
Репозиторий для работы с чатами
"""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from models import Chat
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ChatRepository:
    """Репозиторий для операций с чатами"""

    def __init__(self, db: Session):
        """
        Args:
            db: Сессия базы данных
        """
        self.db = db

    def get_by_id(self, chat_id: int, user_id: int) -> Optional[Chat]:
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

    def get_by_thread_id(self, thread_id: str) -> Optional[Chat]:
        """
        Получить чат по thread_id.

        Args:
            thread_id: Thread ID от LangGraph

        Returns:
            Чат или None если не найден
        """
        return self.db.execute(
            select(Chat).where(Chat.thread_id == thread_id, Chat.is_active == True)
        ).scalar_one_or_none()

    def get_user_chats(
        self, user_id: int, skip: int = 0, limit: int = 100
    ) -> List[Chat]:
        """
        Получить список чатов пользователя.

        Args:
            user_id: ID пользователя
            skip: Сколько записей пропустить
            limit: Максимальное количество записей

        Returns:
            Список чатов
        """
        return (
            self.db.execute(
                select(Chat)
                .where(Chat.user_id == user_id, Chat.is_active == True)
                .order_by(Chat.updated_at.desc())
                .offset(skip)
                .limit(limit)
            )
            .scalars()
            .all()
        )

    def count_user_chats(self, user_id: int) -> int:
        """
        Подсчитать количество чатов пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Количество чатов
        """
        from sqlalchemy import func

        return self.db.execute(
            select(func.count(Chat.id)).where(
                Chat.user_id == user_id, Chat.is_active == True
            )
        ).scalar()

    def create(self, user_id: int, title: Optional[str] = None) -> Chat:
        """
        Создать новый чат.

        Args:
            user_id: ID пользователя
            title: Название чата (опционально)

        Returns:
            Созданный чат
        """
        chat = Chat(
            user_id=user_id,
            title=title or "Новый чат",
            thread_id=str(uuid4()),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True,
        )
        self.db.add(chat)
        self.db.commit()
        self.db.refresh(chat)

        logger.info(
            f"Created chat: id={chat.id}, user_id={user_id}, thread_id={chat.thread_id}"
        )
        return chat

    def update(self, chat: Chat, title: Optional[str] = None) -> Chat:
        """
        Обновить чат.

        Args:
            chat: Объект чата для обновления
            title: Новое название (опционально)

        Returns:
            Обновленный чат
        """
        if title is not None:
            chat.title = title

        chat.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(chat)
        return chat

    def update_timestamp(self, chat: Chat) -> Chat:
        """
        Обновить timestamp последнего сообщения.

        Args:
            chat: Объект чата

        Returns:
            Обновленный чат
        """
        chat.updated_at = datetime.utcnow()
        self.db.commit()
        return chat

    def deactivate(self, chat_id: int, user_id: int) -> bool:
        """
        Деактивировать чат (мягкое удаление).

        Args:
            chat_id: ID чата
            user_id: ID пользователя (для проверки владельца)

        Returns:
            True если чат деактивирован, False если не найден
        """
        chat = self.get_by_id(chat_id, user_id)
        if not chat:
            return False

        chat.is_active = False
        self.db.commit()
        logger.info(f"Deactivated chat: id={chat.id}, user_id={user_id}")
        return True