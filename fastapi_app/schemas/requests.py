"""
Pydantic модели для API запросов
"""

import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ExecuteRequest(BaseModel):
    """
    Запрос на выполнение анализа агентом.

    Attributes:
        query: Текстовый запрос пользователя к агенту
        chat_id: ID существующего чата (опционально)
        enable_web_search: Включить ли веб-поиск
        max_iterations: Максимальное количество ReAct итераций
    """

    query: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Запрос пользователя к агенту",
        examples=["Сколько пациентов с диабетом в базе?"],
    )
    chat_id: Optional[int] = Field(
        default=None,
        ge=1,
        description="ID существующего чата (если не передан, создается новый)",
        examples=[42],
    )
    enable_web_search: bool = Field(
        default=False,
        description="Включить веб-поиск для дополнительной информации",
        examples=[False],
    )
    max_iterations: Optional[int] = Field(
        default=None,
        ge=1,
        le=20,
        description="Максимальное количество итераций агента (1-20)",
        examples=[10],
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """
        Валидация запроса.

        - Удаляет лишние пробелы
        - Проверяет на потенциально опасные команды
        """
        # Удаление лишних пробелов
        v = v.strip()

        # Базовая проверка на SQL инъекции в тексте запроса
        # (агент всё равно использует LLM для генерации SQL, но лучше перестраховаться)
        dangerous_patterns = [
            r";\s*DROP\s+TABLE",
            r";\s*DELETE\s+FROM\s+(?!.*WHERE)",  # DELETE без WHERE
            r";\s*TRUNCATE\s+TABLE",
            r"--\s*$",  # SQL комментарии в конце
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError(
                    "Запрос содержит потенциально опасные команды. "
                    "Пожалуйста, переформулируйте ваш вопрос."
                )

        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "Покажи статистику по пациентам с гипертонией",
                    "chat_id": None,
                    "enable_web_search": False,
                    "max_iterations": 10,
                }
            ]
        }
    }
