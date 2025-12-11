"""
Схемы для работы с чатами
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ChatCreate(BaseModel):
    """Схема для создания нового чата"""

    title: Optional[str] = Field(default="Новый чат", max_length=255, description="Название чата")


class ChatUpdate(BaseModel):
    """Схема для обновления чата"""

    title: Optional[str] = Field(None, max_length=255, description="Новое название чата")
    is_active: Optional[bool] = Field(None, description="Активность чата")


class ChatResponse(BaseModel):
    """Схема ответа с информацией о чате"""

    id: int
    user_id: int
    title: str
    thread_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class ChatListResponse(BaseModel):
    """Схема ответа со списком чатов"""

    chats: list[ChatResponse]
    total: int