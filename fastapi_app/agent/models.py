"""
Модели данных для API
"""

from pydantic import BaseModel, Field


class ClarifyRequest(BaseModel):
    """Запрос на уточнение"""

    query: str = Field(description="Исходный запрос пользователя")


class ClarifyResponse(BaseModel):
    """Ответ с уточнениями"""

    is_request_valid: bool = Field(description="Валиден ли запрос")
    needs_clarification: bool = Field(description="Нужно ли уточнение от пользователя")
    message: str = Field(description="Сообщение для пользователя")
    suggestions: list[str] | None = Field(
        default=None, description="Варианты уточнения запроса (если needs_clarification=True)"
    )


class ExecuteRequest(BaseModel):
    """Запрос на выполнение анализа"""

    query: str = Field(description="Запрос пользователя (может быть уточненный)")
    thread_id: str | None = Field(
        default=None, description="Идентификатор сессии (если не передан, будет сгенерирован)"
    )


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


class ClarificationOutput(BaseModel):
    """Структурированный ответ агента уточнений"""

    is_request_valid: bool = Field(description="True если запрос валиден и понятен, иначе False")
    needs_clarification: bool = Field(description="True если требуется уточнение, иначе False")
    message: str = Field(description="Сообщение для пользователя")
    suggestions: list[str] | None = Field(
        default=None, description="3 варианта уточненных запросов (если needs_clarification=True)"
    )
