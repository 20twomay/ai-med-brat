"""
Узлы (nodes) для LangGraph агента
"""

import logging
import re
from datetime import datetime
from typing import Literal

from config import get_settings
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from prompts import database_prompt, final_report_prompt, worker_sys_prompt

from .state import AgentState
from .tools import execute_sql_tool, plot_chart_tool

logger = logging.getLogger(__name__)


def _get_llm() -> ChatOpenAI:
    """Создаёт LLM клиент"""
    settings = get_settings()
    return ChatOpenAI(
        model=settings.model_name,
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_api_key,
    )


def _get_llm_with_tools() -> ChatOpenAI:
    """Создаёт LLM клиент с подключенными инструментами"""
    llm = _get_llm()
    return llm.bind_tools([execute_sql_tool, plot_chart_tool])


async def node_worker(state: AgentState) -> AgentState:
    """
    ReAct агент - планирует действия и вызывает инструменты.
    """
    react_iter = state.get("react_iter", 0)
    react_max_iter = state.get("react_max_iter", 10)

    sys_prompt = SystemMessage(
        worker_sys_prompt.format(
            database_prompt=database_prompt,
            current_datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_cost": total_cost,
    }


async def node_tools(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    Tools node - выполняет вызовы инструментов.
    Обрабатывает только один tool call за раз.
    """
    last_message = state["messages"][-1]

    # Если нет tool calls
    if not last_message.tool_calls:
        return {"messages": [], "react_iter": state["react_iter"] + 1}

    # Берём только первый tool call
    tool_call = last_message.tool_calls[0]
    tool_name = tool_call["name"]
    tool_args = tool_call["args"]
    tool_id = tool_call["id"]

    # Выполняем SQL tool
    if tool_name == "execute_sql_tool":
        try:
            result = await execute_sql_tool.ainvoke(input=tool_args, config=config)
            tool_message = ToolMessage(content=result, tool_call_id=tool_id)

            # Извлекаем путь к таблице
            tables = state.get("tables", [])
            match = re.search(r"File saved to MinIO at '(.+?)'", result)
            if match:
                tables.append(match.group(1))

            return {
                "messages": [tool_message],
                "react_iter": state["react_iter"] + 1,
                "tables": tables,
            }
        except Exception as e:
            logger.error(f"SQL tool error: {e}", exc_info=True)
            tool_message = ToolMessage(
                content=f"SQL Execution Error: {str(e)}",
                tool_call_id=tool_id,
            )
            return {
                "messages": [tool_message],
                "react_iter": state["react_iter"] + 1,
            }

    # Выполняем plotting tool
    elif tool_name == "plot_chart_tool":
        try:
            result = await plot_chart_tool.ainvoke(input=tool_args, config=config)
            tool_message = ToolMessage(content=result, tool_call_id=tool_id)

            # Извлекаем путь к графику
            charts = state.get("charts", [])
            match = re.search(r"Plotly figure JSON saved to MinIO:\s*(.+\.json)", result)
            if match:
                charts.append(match.group(1))

            return {
                "messages": [tool_message],
                "react_iter": state["react_iter"] + 1,
                "charts": charts,
            }
        except Exception as e:
            logger.error(f"Plotting tool error: {e}", exc_info=True)
            tool_message = ToolMessage(
                content=f"Plotting Error: {str(e)}",
                tool_call_id=tool_id,
            )
            return {
                "messages": [tool_message],
                "react_iter": state["react_iter"] + 1,
            }

    # Неподдерживаемый tool
    else:
        tool_message = ToolMessage(
            content=f"Unsupported tool: {tool_name}",
            tool_call_id=tool_id,
        )
        return {
            "messages": [tool_message],
            "react_iter": state["react_iter"] + 1,
        }


def conditional_tools(state: AgentState) -> Literal["tools", "continue"]:
    """
    Роутинг: определяет, нужно ли выполнять tools или перейти к final_report.
    """
    react_iter = state.get("react_iter", 0)
    react_max_iter = state.get("react_max_iter", 10)

    # Превышен лимит итераций
    if react_iter >= react_max_iter:
        logger.warning(f"Reached max iterations: {react_iter}/{react_max_iter}")
        return "continue"

    # Проверяем, есть ли tool calls в последнем сообщении
    last_message = state["messages"][-1]
    if not last_message.tool_calls:
        return "continue"

    return "tools"


async def node_final_report(state: AgentState) -> AgentState:
    """
    Final report node - создаёт итоговый отчёт на основе истории.
    """
    react_iter = state.get("react_iter", 0)
    react_max_iter = state.get("react_max_iter", 10)
    sys_prompt = SystemMessage(
        worker_sys_prompt.format(
            database_prompt=database_prompt,
            current_datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            react_iter=react_iter + 1,
            react_max_iter=react_max_iter,
        )
    )
    prompt = SystemMessage(content=final_report_prompt)

    llm = _get_llm()
    response = await llm.ainvoke([sys_prompt] + state["messages"] + [prompt])

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
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_cost": total_cost,
    }
