"""
Агенты для обработки запросов
"""

import ast
import io
import logging
import os
import re
import time
import uuid
from datetime import datetime
from io import BytesIO
from typing import Annotated, Any, Dict, Literal, Optional, TypedDict

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import seaborn as sns
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
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver, MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph, add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import Command
from langsmith import Client, traceable
from minio import Minio
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text

from .models import ClarificationOutput, ClarifyResponse, ExecuteResponse
from .prompts import CLARIFICATION_PROMPT, DB_PROMPT, EXECUTION_PROMPT, SUMMARIZER_PROMPT
from .tools import execute_sql_tool, plot_chart_tool

logger = logging.getLogger(__name__)

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL")
MODEL_NAME = os.getenv("MODEL_NAME")

llm = ChatOpenAI(model=MODEL_NAME, base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY)
llm_with_tools = llm.bind_tools([execute_sql_tool, plot_chart_tool])


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    react_iter: int
    react_max_iter: int
    charts: list[str]  # Список путей к графикам
    tables: list[str]  # Список путей к таблицам
    input_tokens: int  # Входные токены
    output_tokens: int  # Выходные токены
    total_cost: float  # Стоимость запроса в USD
    start_time: float  # Время начала выполнения


async def node_worker(state: State) -> State:
    react_iter = state.get("react_iter", 0)
    react_max_iter = state.get("react_max_iter", 10)

    sys_prompt = SystemMessage(
        f"""Ты помощник, который выполняет SQL запросы к базе данных медицинских записей.

ВАЖНЫЕ ПРАВИЛА:
- Ты можешь вызывать ТОЛЬКО ОДИН инструмент за итерацию
- Текущая итерация: {react_iter + 1}/{react_max_iter}
- Когда ты получил достаточно данных для ответа, НЕ вызывай больше инструментов
- Если ты уже выполнил SQL и/или построил график, отвечай пользователю текстом БЕЗ новых вызовов инструментов

{DB_PROMPT}"""
    )
    response = await llm_with_tools.ainvoke([sys_prompt] + state["messages"])

    # Подсчет токенов и cost из response_metadata
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


async def node_tools(state: State, config: RunnableConfig) -> State:
    last_message = state["messages"][-1]

    # Обрабатываем только первый tool call, остальные игнорируем
    if not last_message.tool_calls:
        return {"messages": [], "react_iter": state["react_iter"] + 1}

    tool_call = last_message.tool_calls[0]
    tool_name = tool_call["name"]
    tool_args = tool_call["args"]
    tool_id = tool_call["id"]

    # Если больше одного tool call, создаем ToolMessage для каждого с ошибкой
    if len(last_message.tool_calls) > 1:
        tool_messages = [
            ToolMessage(
                content="Only one tool call is allowed per iteration.", tool_call_id=tc["id"]
            )
            for tc in last_message.tool_calls
        ]
        return {
            "messages": tool_messages,
            "react_iter": state["react_iter"] + 1,
        }

    # SQL
    if tool_name == "execute_sql_tool":
        try:
            result = await execute_sql_tool.ainvoke(input=tool_args, config=config)
            tool_message = ToolMessage(
                content=result,
                tool_call_id=tool_id,
            )
            # Извлекаем путь к таблице из результата
            tables = state.get("tables", [])
            if "File saved to MinIO at '" in result:
                import re

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
    # Plotting
    elif tool_name == "plot_chart_tool":
        try:
            result = await plot_chart_tool.ainvoke(input=tool_args, config=config)
            tool_message = ToolMessage(
                content=result,
                tool_call_id=tool_id,
            )
            # Извлекаем путь к графику из результата
            charts = state.get("charts", [])
            if "Plotly figure JSON saved to MinIO:" in result:
                import re

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
    # Unsupported tool
    else:
        tool_message = ToolMessage(content=f"Unsupported tool: {tool_name}", tool_call_id=tool_id)
        return {
            "messages": [tool_message],
            "react_iter": state["react_iter"] + 1,
        }


def conditional_tools(state: State) -> Literal["tools", "continue"]:
    """Проверяет, нужно ли вызвать инструменты или перейти к итоговому отчету"""
    # Проверка на превышение лимита итераций
    react_iter = state.get("react_iter", 0)
    react_max_iter = state.get("react_max_iter", 10)

    if react_iter >= react_max_iter:
        logger.warning(f"Reached max iterations: {react_iter}/{react_max_iter}")
        return "continue"

    last_message = state["messages"][-1]
    if not last_message.tool_calls:
        return "continue"
    return "tools"


async def node_final_report(state: State) -> State:
    sys_prompt = SystemMessage(
        "Создай краткий итоговый отчет по выполненной работе. Не искажай пути, полученные в результате выполнения инструментов."
    )

    # Очищаем историю от tool_calls и ToolMessage для совместимости с Mistral API
    # Mistral требует: user → assistant → user → assistant (без tool роли)
    cleaned_messages = []
    for msg in state["messages"]:
        # Пропускаем все ToolMessage (роль 'tool')
        if isinstance(msg, ToolMessage):
            continue
        # Убираем tool_calls из AIMessage
        elif isinstance(msg, AIMessage) and msg.tool_calls:
            cleaned_msg = AIMessage(content=msg.content or "Выполняю запрос...")
            cleaned_messages.append(cleaned_msg)
        else:
            cleaned_messages.append(msg)

    response = await llm.ainvoke([sys_prompt] + cleaned_messages)

    # Подсчет токенов и cost из response_metadata
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


def build_agent_graph() -> StateGraph[State]:
    checkpointer = InMemorySaver()
    builder = StateGraph(State)

    builder.add_node("worker", node_worker)
    builder.add_node("tools", node_tools)
    builder.add_node("final_report", node_final_report)

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

    compiled_graph = builder.compile(checkpointer=checkpointer)

    return compiled_graph, checkpointer
