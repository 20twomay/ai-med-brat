"""
Модели чатов и сообщений
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .user import Base

if TYPE_CHECKING:
    from .user import User


class Chat(Base):
    """
    Модель чата пользователя.

    Attributes:
        id: Уникальный идентификатор чата
        user_id: ID пользователя-владельца чата
        title: Название чата
        created_at: Дата и время создания чата
        updated_at: Дата и время последнего обновления
        is_active: Флаг активности чата (для мягкого удаления)
        user: Связанный пользователь
    """

    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255), nullable=False, default="Новый чат"
    )
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
    total_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Суммарное количество токенов в чате"
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="chats", lazy="selectin")
    messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="chat",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    # Композитные индексы для оптимизации частых запросов
    __table_args__ = (
        Index("idx_chat_user_active", "user_id", "is_active"),
        Index("idx_chat_updated_at_desc", "updated_at"),
    )

    def __repr__(self) -> str:
        return f"<Chat(id={self.id}, user_id={self.user_id}, title='{self.title}', is_active={self.is_active})>"


class Message(Base):
    """
    Модель сообщения в чате.

    Attributes:
        id: Уникальный идентификатор сообщения
        chat_id: ID чата
        role: Роль отправителя (user/assistant/system)
        content: Содержимое сообщения
        artifacts: JSON с артефактами (графики, таблицы)
        created_at: Дата и время создания сообщения
        chat: Связанный чат
    """

    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    chat_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    artifacts: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Relationships
    chat: Mapped["Chat"] = relationship("Chat", back_populates="messages")

    # Индексы
    __table_args__ = (
        Index("idx_messages_chat_created", "chat_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, chat_id={self.chat_id}, role='{self.role}')>"