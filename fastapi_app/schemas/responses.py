"""
Pydantic модели для API ответов
"""

from pydantic import BaseModel, Field


class ExecuteResponse(BaseModel):
    """Результат выполнения анализа"""

    result: str = Field(description="Текстовый результат анализа")
    charts: list[str] = Field(default_factory=list, description="Пути к графикам")
    tables: list[str] = Field(default_factory=list, description="Пути к таблицам")
    input_tokens: int = Field(default=0, description="Количество входных токенов")
    output_tokens: int = Field(default=0, description="Количество выходных токенов")
    latency_ms: float = Field(default=0.0, description="Время выполнения запроса в миллисекундах")
    cost: float = Field(default=0.0, description="Стоимость запроса в USD")
    thread_id: str = Field(description="Идентификатор сессии")
