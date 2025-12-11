"""
LangGraph сборка агента
"""

import logging

from core.constants import DEFAULT_MAX_REACT_ITERATIONS
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from .nodes import conditional_tools, node_final_report, node_tools, node_worker, node_web_search
from .state import AgentState
logger = logging.getLogger(__name__)


def node_init_state(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    Инициализирует начальное состояние агента с дефолтными значениями.
    Этот узел отвечает за настройку параметров, которые не должны управляться сервером.
    """
    # Получаем max_iterations из config если передан
    configurable = config.get("configurable", {})
    max_iterations = configurable.get("max_iterations", DEFAULT_MAX_REACT_ITERATIONS)

    return {
        "react_iter": 0,
        "react_max_iter": max_iterations,
        "charts": [],
        "tables": [],
        "input_tokens": 0,
        "output_tokens": 0,
        "total_cost": 0.0,
    }


def build_agent_graph():
    """
    Создаёт и компилирует LangGraph для медицинского аналитического агента.

    Граф состоит из следующих узлов:
    - init_state: Инициализирует начальное состояние с дефолтными значениями
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
    builder.add_node("init_state", node_init_state)
    builder.add_node("worker", node_worker)
    builder.add_node("tools", node_tools)
    builder.add_node("final_report", node_final_report)
    builder.add_node("web_search", node_web_search)

    # START всегда идет в init_state для инициализации
    builder.add_edge(START, "init_state")

    def route_after_init(state: AgentState) -> str:
        """Роутинг после инициализации - в web_search или сразу в worker"""
        if state.get("enable_web_search", False):
            return "web_search"
        else:
            return "worker"

    builder.add_conditional_edges(
        "init_state",
        route_after_init,
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
