"""
Репозиторий для работы с пользователями
"""

import logging
from datetime import datetime
from typing import Optional

from models import User
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class UserRepository:
    """Репозиторий для операций с пользователями"""

    def __init__(self, db: Session):
        """
        Args:
            db: Сессия базы данных
        """
        self.db = db

    def get_by_id(self, user_id: int) -> Optional[User]:
        """
        Получить пользователя по ID.

        Args:
            user_id: ID пользователя

        Returns:
            Пользователь или None если не найден
        """
        return self.db.execute(
            select(User).where(User.id == user_id, User.is_active == True)
        ).scalar_one_or_none()

    def get_by_email(self, email: str) -> Optional[User]:
        """
        Получить пользователя по email.

        Args:
            email: Email пользователя

        Returns:
            Пользователь или None если не найден
        """
        return self.db.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()

    def get_active_by_email(self, email: str) -> Optional[User]:
        """
        Получить активного пользователя по email.

        Args:
            email: Email пользователя

        Returns:
            Активный пользователь или None если не найден
        """
        return self.db.execute(
            select(User).where(User.email == email, User.is_active == True)
        ).scalar_one_or_none()

    def create(self, email: str, hashed_password: str) -> User:
        """
        Создать нового пользователя.

        Args:
            email: Email пользователя
            hashed_password: Хешированный пароль

        Returns:
            Созданный пользователь

        Raises:
            ValueError: Если пользователь с таким email уже существует
        """
        existing_user = self.get_by_email(email)
        if existing_user:
            raise ValueError(f"User with email '{email}' already exists")

        user = User(
            email=email,
            hashed_password=hashed_password,
            created_at=datetime.utcnow(),
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        logger.info(f"Created user: {user.email} (ID: {user.id})")
        return user

    def update(self, user: User) -> User:
        """
        Обновить пользователя.

        Args:
            user: Объект пользователя для обновления

        Returns:
            Обновленный пользователь
        """
        self.db.commit()
        self.db.refresh(user)
        return user

    def deactivate(self, user_id: int) -> bool:
        """
        Деактивировать пользователя (мягкое удаление).

        Args:
            user_id: ID пользователя

        Returns:
            True если пользователь деактивирован, False если не найден
        """
        user = self.get_by_id(user_id)
        if not user:
            return False

        user.is_active = False
        self.db.commit()
        logger.info(f"Deactivated user: {user.email} (ID: {user.id})")
        return True