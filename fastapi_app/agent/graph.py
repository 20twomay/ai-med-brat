"""
LangGraph сборка агента
"""

import logging

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from .nodes import conditional_tools, node_final_report, node_tools, node_worker, node_web_search
from .state import AgentState
logger = logging.getLogger(__name__)


def build_agent_graph():
    """
    Создаёт и компилирует LangGraph для медицинского аналитического агента.

    Граф состоит из следующих узлов:
    - worker: LLM агент, который планирует действия и вызывает tools
    - tools: Выполняет вызовы инструментов (SQL, графики)
    - web_search: Выполняет веб-поиск при необходимости
    - final_report: Создаёт итоговый отчёт

    Returns:
        tuple: (compiled_graph, checkpointer)
    """
    checkpointer = InMemorySaver()
    builder = StateGraph(AgentState)

    # Добавляем узлы
    builder.add_node("worker", node_worker)
    builder.add_node("tools", node_tools)
    builder.add_node("final_report", node_final_report)
    builder.add_node("web_search", node_web_search)

    def route_start(state: AgentState) -> str:
        if state.get("enable_web_search", True):
            return "web_search"
        else:
            return "worker"

    builder.add_conditional_edges(
        START,
        route_start,
        {
            "web_search": "web_search",
            "worker": "worker"
        }
    )

    # Добавляем рёбра
    builder.add_edge("web_search", "worker")
    builder.add_conditional_edges(
        "worker",
        conditional_tools,
        {
            "tools": "tools",
            "continue": "final_report",
        },
    )
    builder.add_edge("tools", "worker")
    builder.add_edge("final_report", END)

    # Компилируем граф
    compiled_graph = builder.compile(checkpointer=checkpointer)

    logger.info("Agent graph compiled successfully")
    return compiled_graph, checkpointer
