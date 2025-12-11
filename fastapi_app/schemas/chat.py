"""
Схемы для работы с чатами и сообщениями
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

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
    created_at: datetime
    updated_at: datetime
    is_active: bool
    total_tokens: int = Field(default=0, description="Суммарное количество токенов")

    class Config:
        from_attributes = True


class ChatListResponse(BaseModel):
    """Схема ответа со списком чатов"""

    chats: list[ChatResponse]
    total: int


class MessageCreate(BaseModel):
    """Схема для создания нового сообщения"""

    role: str = Field(..., description="Роль отправителя (user/assistant/system)")
    content: str = Field(..., description="Содержимое сообщения")
    artifacts: Optional[Dict[str, Any]] = Field(None, description="Артефакты (графики, таблицы)")


class MessageResponse(BaseModel):
    """Схема ответа с информацией о сообщении"""

    id: UUID
    chat_id: int
    role: str
    content: str
    artifacts: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


class MessageListResponse(BaseModel):
    """Схема ответа со списком сообщений"""

    messages: List[MessageResponse]
    total: int