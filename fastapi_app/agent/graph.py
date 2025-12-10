"""
LangGraph сборка агента
"""

import logging

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from .nodes import conditional_tools, node_final_report, node_tools, node_worker
from .state import AgentState

logger = logging.getLogger(__name__)


def build_agent_graph():
    """
    Создаёт и компилирует LangGraph для медицинского аналитического агента.

    Граф состоит из следующих узлов:
    - worker: LLM агент, который планирует действия и вызывает tools
    - tools: Выполняет вызовы инструментов (SQL, графики)
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

    # Добавляем рёбра
    builder.add_edge(START, "worker")
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
