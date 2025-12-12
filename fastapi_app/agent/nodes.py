"""
Узлы (nodes) для LangGraph агента
"""

import json
import logging
import re
from datetime import datetime
from typing import Literal

from config import get_settings
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_mistralai import ChatMistralAI
from langchain_openai import ChatOpenAI
from prompts import database_prompt, worker_sys_prompt
from pydantic import BaseModel, Field

from .state import AgentState
from .tools import (
    correlation_tool,
    create_custom_dataframe,
    execute_sql_tool,
    forecast_tool,
    get_dataframe_head,
    get_dataframe_tail,
    plot_chart_tool,
)

logger = logging.getLogger(__name__)


def _get_llm() -> ChatMistralAI:
    """Создаёт LLM клиент"""
    settings = get_settings()
    return ChatMistralAI(
        model=settings.model_name,
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_api_key,
        temperature=0,
    )


def _get_llm_with_tools() -> ChatMistralAI:
    """Создаёт LLM клиент с подключенными инструментами"""
    llm = _get_llm()
    return llm.bind_tools([execute_sql_tool, plot_chart_tool, forecast_tool, correlation_tool])


async def executor_node(state: AgentState) -> AgentState:
    react_iter = state.get("react_iter", 0)
    react_max_iter = state.get("react_max_iter", 10)

    sys_prompt = SystemMessage(
        worker_sys_prompt.format(
            database_prompt=database_prompt,
            # current_datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            react_iter=react_iter + 1,
            react_max_iter=react_max_iter,
        )
    )

    llm_with_tools = _get_llm_with_tools()

    response = await llm_with_tools.ainvoke([sys_prompt] + state["messages"])

    # Подсчёт токенов и стоимости
    input_tokens = state.get("input_tokens", 0)
    output_tokens = state.get("output_tokens", 0)
    total_cost = state.get("total_cost", 0.0)

    if hasattr(response, "response_metadata") and response.response_metadata:
        usage = response.response_metadata.get("token_usage", {})
        input_tokens += usage.get("prompt_tokens", 0)
        output_tokens += usage.get("completion_tokens", 0)
        total_cost += usage.get("cost", 0.0)

    return {
        "messages": [response],
        # Экономика
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_cost": total_cost,
    }


async def tools_node(state: AgentState, config: RunnableConfig) -> AgentState:
    last_message = state["messages"][-1]

    if "_tool{" in last_message.content:
        message = HumanMessage("Некорректный вызов инструмента.")
        logger.warning("Tool call syntax error.")
        return {
            "messages": [message],
            "react_iter": state["react_iter"] + 1,
        }

    result_messages = []

    tables = state.get("tables", [])
    charts = state.get("charts", [])

    if not last_message.tool_calls:
        return state

    logger.info(f"Executing {last_message.tool_calls}")
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]

        try:
            if tool_name == "execute_sql_tool":
                result_str = await execute_sql_tool.ainvoke(input=tool_args, config=config)
                result = json.loads(result_str)
                tool_message = ToolMessage(content=result_str, tool_call_id=tool_id)
                tables.append(result["result_filename"])
            elif tool_name == "plot_chart_tool":
                result_str = await plot_chart_tool.ainvoke(input=tool_args, config=config)
                result = json.loads(result_str)
                tool_message = ToolMessage(content=result_str, tool_call_id=tool_id)
                charts.append(result["result_filename"])
            elif tool_name == "get_dataframe_head":
                result_str = await get_dataframe_head.ainvoke(input=tool_args, config=config)
                tool_message = ToolMessage(content=result_str, tool_call_id=tool_id)
            elif tool_name == "get_dataframe_tail":
                result_str = await get_dataframe_tail.ainvoke(input=tool_args, config=config)
                tool_message = ToolMessage(content=result_str, tool_call_id=tool_id)
            elif tool_name == "create_custom_dataframe":
                result_str = await create_custom_dataframe.ainvoke(input=tool_args, config=config)
                result = json.loads(result_str)
                tool_message = ToolMessage(content=result_str, tool_call_id=tool_id)
                tables.append(result["result_filename"])
            elif tool_name == "forecast_tool":
                result_str = await forecast_tool.ainvoke(input=tool_args, config=config)
                logger.info(f"Forecast tool result: {result_str}")
                tool_message = ToolMessage(content=result_str, tool_call_id=tool_id)
            elif tool_name == "correlation_tool":
                result_str = await correlation_tool.ainvoke(input=tool_args, config=config)
                tool_message = ToolMessage(content=str(result_str), tool_call_id=tool_id)
            else:
                tool_message = ToolMessage(
                    content=f"Unsupported tool: {tool_name}", tool_call_id=tool_id
                )
        except Exception as e:
            tool_message = ToolMessage(
                content=f"Tool execution error: {str(e)}", tool_call_id=tool_id
            )
        result_messages.append(tool_message)

    return {
        "messages": result_messages,
        "react_iter": state["react_iter"] + 1,
        "tables": tables,
        "charts": charts,
    }


def route_after_executor(state: AgentState) -> Literal["tools", "validator"]:
    react_iter = state.get("react_iter", 0)
    react_max_iter = state.get("react_max_iter", 10)

    if react_iter >= react_max_iter:
        logger.warning(f"Reached max iterations: {react_iter}/{react_max_iter}")
        return "validator"

    last_message = state["messages"][-1]

    if "_tool{" in last_message.content:
        logger.warning("Tool call syntax error detected.")
        return "tools"
    if not last_message.tool_calls:
        return "validator"
    return "tools"


async def final_report_node(state: AgentState) -> AgentState:
    # q = state["query"]
    # sys_message = SystemMessage(
    #     content=(
    #         "Создай итоговый отчёт по выполнению задачи агента.",
    #         f"Предоставь краткий и информативный ответ на запрос пользователя: {q}.",
    #     )
    # )

    # llm = _get_llm()
    # response = await llm.ainvoke([sys_message] + messages)

    # Подсчёт токенов и стоимости
    """input_tokens = state.get("input_tokens", 0)
    output_tokens = state.get("output_tokens", 0)
    total_cost = state.get("total_cost", 0.0)

    if hasattr(response, "response_metadata") and response.response_metadata:
        usage = response.response_metadata.get("token_usage", {})
        input_tokens += usage.get("prompt_tokens", 0)
        output_tokens += usage.get("completion_tokens", 0)
        total_cost += usage.get("cost", 0.0)"""

    return {
        "answer": state["messages"][-1].content,
        "is_solved": True,
    }
