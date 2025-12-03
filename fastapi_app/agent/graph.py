import logging
import os
from datetime import datetime
from typing import Literal, Optional

from dotenv import load_dotenv
from langchain.tools import ToolRuntime, tool
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolCall,
    ToolMessage,
)
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph, add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import Command
from langsmith import Client
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text

from .prompts import DB_PROMPT, ROUTER_SYS_PROMPT, SUMMARIZER_SYS_PROMPT, WORKER_SYS_PROMPT
from .state import AgentState
from .tools import execute_sql_tool, plot_chart_tool

# Настройка логирования
logger = logging.getLogger(__name__)

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL")
MODEL_NAME = os.getenv("MODEL_NAME")

LLM = ChatOpenAI(model=MODEL_NAME, base_url=API_BASE_URL, api_key=OPENROUTER_API_KEY)
TOOLS = [execute_sql_tool, plot_chart_tool]
LLM_WITH_TOOLS = LLM.bind_tools(TOOLS)


class RouterOutput(BaseModel):
    is_request_valid: bool = Field(description="True если запрос валиден и понятен, иначе False")
    needs_clarification: bool | None = Field(
        description="True если требуется уточнение, иначе False"
    )
    your_response: Optional[str] = Field(
        default=None,
        description="Твое уточнение, если needs_clarification равно True. Иначе объяснение почему is_request_valid равно False.",
    )


def router(state: AgentState) -> AgentState:
    """Определяет, нужно ли запросить уточнение у пользователя/валиден ли запрос."""
    logger.info("Router: Starting...")
    messages = state["messages"]
    logger.info(f"Router: Processing {len(messages)} messages")

    sys_msg = SystemMessage(
        content=ROUTER_SYS_PROMPT.format(
            db_prompt=DB_PROMPT,
            current_datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
    )
    llm_with_structured_output = LLM.with_structured_output(RouterOutput)

    logger.info("Router: Calling LLM...")
    try:
        response = llm_with_structured_output.invoke([sys_msg] + messages)
        logger.info(
            f"Router: LLM response - is_valid={response.is_request_valid}, needs_clarification={response.needs_clarification}"
        )
        logger.info(f"Router: response.your_response={response.your_response}")
    except Exception as e:
        logger.error(f"Router: LLM error - {str(e)}")
        raise

    your_response = response.your_response
    if your_response is None:
        your_response = "Запрос валиден и не требует уточнений."

    result = {
        **state,
        "needs_clarification": response.needs_clarification,
        "is_request_valid": response.is_request_valid,
        "messages": messages + [AIMessage(content=your_response)],
    }
    logger.info(
        f"Router: Returning state with needs_clarification={result['needs_clarification']}, is_valid={result['is_request_valid']}"
    )
    return result


def route_after_router(
    state: AgentState,
) -> Literal["needs_clarification", "continue", "invalid_request"]:
    logger.info("route_after_router: CALLED")
    logger.info(f"route_after_router: state keys = {list(state.keys())}")
    logger.info(
        f"route_after_router: is_valid={state.get('is_request_valid')}, needs_clarification={state.get('needs_clarification')}"
    )
    if not state["is_request_valid"]:
        logger.info("route_after_router: -> invalid_request")
        return "invalid_request"
    if state["needs_clarification"]:
        logger.info("route_after_router: -> needs_clarification")
        return "needs_clarification"
    logger.info("route_after_router: -> continue")
    return "continue"


def get_human_feedback(state: AgentState) -> AgentState:
    """Запрашивает уточнение у пользователя."""
    # Сбрасываем флаг needs_clarification после получения ответа
    # Ответ пользователя уже добавлен в messages через API
    return {
        **state,
        "needs_clarification": False,  # Сбрасываем флаг
    }


def worker(state: AgentState) -> AgentState:
    logger.info("Worker: Starting...")
    messages = state["messages"]
    sys_msg = SystemMessage(
        content=WORKER_SYS_PROMPT.format(
            db_prompt=DB_PROMPT, current_datetime=datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        )
    )
    logger.info("Worker: Calling LLM with tools...")
    try:
        response = LLM_WITH_TOOLS.invoke([sys_msg] + messages)
        logger.info(f"Worker: LLM response received. Has tool calls: {bool(response.tool_calls)}")
    except Exception as e:
        logger.error(f"Worker: LLM error - {str(e)}")
        raise

    return {
        **state,
        "messages": messages + [response],
        "iteration": state["iteration"] + 1,
    }


def should_continue(state: AgentState) -> Literal["go", "stop"]:
    last_msg = state["messages"][-1]
    logger.info(f"should_continue: iteration={state['iteration']}, max={state['max_iterations']}")
    if isinstance(last_msg, AIMessage) and state["iteration"] >= state["max_iterations"]:
        logger.info("should_continue: -> stop (max iterations)")
        return "stop"
    if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
        logger.info("should_continue: -> go (has tool calls)")
        return "go"
    logger.info("should_continue: -> stop")
    return "stop"


def summarizer(state: AgentState) -> AgentState:
    logger.info("Summarizer: Starting...")
    messages = state["messages"]
    sys_msg = SystemMessage(
        content=SUMMARIZER_SYS_PROMPT.format(
            current_datetime=datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        )
    )
    logger.info("Summarizer: Calling LLM...")
    summary = LLM.invoke([sys_msg] + messages)
    logger.info("Summarizer: Done")
    return {**state, "messages": messages + [summary]}


def build_agent_graph() -> StateGraph[AgentState]:
    builder = StateGraph(AgentState)

    builder.add_node("router", router)
    builder.add_node("get_human_feedback", get_human_feedback)
    builder.add_node("worker", worker)
    builder.add_node("tools", ToolNode(TOOLS))
    builder.add_node("summarizer", summarizer)

    builder.add_edge(START, "router")
    builder.add_conditional_edges(
        "router",
        route_after_router,
        {
            "needs_clarification": "get_human_feedback",
            "continue": "worker",
            "invalid_request": "summarizer",
        },
    )
    # После получения feedback идём сразу в worker, а не обратно в router
    builder.add_edge("get_human_feedback", "worker")
    builder.add_conditional_edges(
        "worker",
        should_continue,
        {
            "stop": "summarizer",
            "go": "tools",
        },
    )
    builder.add_edge("tools", "worker")
    builder.add_edge("summarizer", END)

    memory = MemorySaver()
    agent_graph = builder.compile(checkpointer=memory, interrupt_before=["get_human_feedback"])
    return agent_graph
