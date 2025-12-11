"""
Pydantic модели для API запросов
"""

from typing import Optional

from pydantic import BaseModel, Field


class ExecuteRequest(BaseModel):
    """Запрос на выполнение анализа"""

    query: str = Field(description="Запрос пользователя")
    chat_id: Optional[int] = Field(default=None, description="ID чата (если не передан, создается новый)")
    thread_id: Optional[str] = Field(default=None, description="Идентификатор thread (deprecated, используйте chat_id)")
