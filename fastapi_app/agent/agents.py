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


def node_worker(state: State) -> State:
    sys_prompt = SystemMessage(
        f"Ты помощник, который выполняет SQL запросы к базе данных медицинских записей.\n{DB_PROMPT}"
    )
    response = llm_with_tools.invoke([sys_prompt] + state["messages"])

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


def node_tools(state: State, config: RunnableConfig) -> State:
    last_message = state["messages"][-1]
    tool_call = last_message.tool_calls[0]
    tool_name = tool_call["name"]
    tool_args = tool_call["args"]
    tool_id = tool_call["id"]

    if len(last_message.tool_calls) > 1:
        tool_message = ToolMessage(
            content="Only one tool call is allowed per iteration.", tool_call_id=tool_id
        )
        return {
            "messages": [tool_message],
            "react_iter": state["react_iter"] + 1,
        }

    # SQL
    if tool_name == "execute_sql_tool":
        result = execute_sql_tool.invoke(input=tool_args, config=config)
        try:
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
        except Exception as e:
            tool_message = ToolMessage(
                content=f"SQL Execution Error: {str(e)}",
                tool_call_id=tool_id,
            )

        return {
            "messages": [tool_message],
            "react_iter": state["react_iter"] + 1,
            "tables": tables,
        }
    # Plotting
    elif tool_name == "plot_chart_tool":
        try:
            result = plot_chart_tool.invoke(input=tool_args, config=config)
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
        except Exception as e:
            tool_message = ToolMessage(
                content=f"Plotting Error: {str(e)}",
                tool_call_id=tool_id,
            )

        return {
            "messages": [tool_message],
            "react_iter": state["react_iter"] + 1,
            "charts": charts,
        }
    # Unsupported tool
    else:
        tool_message = ToolMessage(
            content="Only one tool call is allowed per iteration.", tool_call_id=tool_id
        )
        return {
            "messages": [tool_message],
            "react_iter": state["react_iter"] + 1,
        }


def conditional_tools(state: State) -> Literal["tools", "continue"]:
    last_message = state["messages"][-1]
    if not last_message.tool_calls:
        return "continue"
    return "tools"


def node_final_report(state: State) -> State:
    sys_prompt = SystemMessage(
        "Создай краткий итоговый отчет по выполненной работе. Не искажай пути, полученные в результате выполнения инструментов."
    )
    response = llm.invoke([sys_prompt] + state["messages"])

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
