"""
Pydantic модели для API запросов
"""

from pydantic import BaseModel, Field


class ExecuteRequest(BaseModel):
    """Запрос на выполнение анализа"""

    query: str = Field(description="Запрос пользователя (может быть уточненный)")
    thread_id: str | None = Field(
        default=None, description="Идентификатор сессии (если не передан, будет сгенерирован)"
    )
