"""
Модели пользователей и токенов
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from .chat import Chat


class Base(DeclarativeBase):
    """Базовый класс для всех моделей"""

    pass


class User(Base):
    """
    Модель пользователя.

    Attributes:
        id: Уникальный идентификатор пользователя
        email: Email пользователя (уникальный)
        hashed_password: Хешированный пароль
        created_at: Дата и время создания аккаунта
        updated_at: Дата и время последнего обновления
        is_active: Флаг активности аккаунта
        chats: Связанные чаты пользователя
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Relationships
    chats: Mapped[List["Chat"]] = relationship(
        "Chat", back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )

    # Композитные индексы
    __table_args__ = (Index("idx_user_email_active", "email", "is_active"),)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', is_active={self.is_active})>"


# UserToken больше не используется - токены генерируются JWT
