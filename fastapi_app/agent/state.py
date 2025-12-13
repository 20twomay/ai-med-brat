"""
Определение состояния (State) для LangGraph агента
"""

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages


class AgentState(TypedDict):
    """Состояние агента, управляемое LangGraph"""

    messages: Annotated[list[AnyMessage], add_messages]
    summary: str  # Краткое содержание диалога

    query: str  # Исходный запрос пользователя
    answer: str  # Итоговый ответ агента
    is_solved: bool  # Флаг, указывающий, решён ли запрос

    react_iter: int  # Текущая итерация ReAct цикла
    react_max_iter: int  # Максимальное количество итераций

    charts: list[str]  # Список путей к графикам в MinIO
    tables: list[str]  # Список путей к таблицам в MinIO

    # Веб-поиск
    web_search_content: str  # Результаты веб-поиска для финальной суммаризации

    # В пределах одного запроса
    input_tokens: int  # Количество входных токенов
    output_tokens: int  # Количество выходных токенов
