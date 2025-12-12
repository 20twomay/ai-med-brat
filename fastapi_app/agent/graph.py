"""
LangGraph сборка агента
"""

import logging

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from .nodes import (
    executor_node,
    route_after_executor,
    tools_node,
)
from .state import AgentState

logger = logging.getLogger(__name__)


def node_init_state(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    Инициализирует начальное состояние агента с дефолтными значениями.
    Этот узел отвечает за настройку параметров, которые не должны управляться сервером.
    """
    max_iterations = 25

    return {
        "react_iter": 0,
        "react_max_iter": max_iterations,
        "query": state["messages"][0].content,
        "answer": "",
        "is_solved": False,
        "charts": [],
        "tables": [],
        "input_tokens": state.get("input_tokens", 0),
        "output_tokens": state.get("output_tokens", 0),
        "total_cost": state.get("total_cost", 0.0),
    }


def build_agent_graph() -> tuple[StateGraph[AgentState], InMemorySaver]:
    """
    Создаёт и компилирует LangGraph для медицинского аналитического агента.
    """
    checkpointer = InMemorySaver()
    builder = StateGraph(AgentState)

    # Добавляем узлы
    builder.add_node("init_state", node_init_state)
    builder.add_node("executor", executor_node)
    builder.add_node("tools", tools_node)

    # Добавляем рёбра
    builder.add_edge(START, "init_state")  # START всегда идет в init_state для инициализации
    builder.add_edge("init_state", "executor")
    builder.add_conditional_edges(
        "executor",
        route_after_executor,
        {
            "tools": "tools",
            "validator": END,
        },
    )
    builder.add_edge("tools", "executor")

    compiled_graph = builder.compile(checkpointer=checkpointer)

    logger.info("Agent graph compiled successfully")
    return compiled_graph, checkpointer
