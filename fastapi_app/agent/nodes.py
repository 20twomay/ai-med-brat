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
from prompts import database_prompt, final_report_prompt, worker_sys_prompt, web_search_prompt

from .state import AgentState
from .tools import execute_sql_tool, plot_chart_tool
from langchain_core.prompts import ChatPromptTemplate

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

    try:
        response = await llm_with_tools.ainvoke([sys_prompt] + state["messages"])
    except Exception as e:
        error_str = str(e)
        # Если 401 ошибка - возвращаем сообщение об ошибке
        if "401" in error_str or "Authentication" in error_str:
            logger.error(f"Worker node: Authentication error - {error_str}")
            response = AIMessage(content="Ошибка аутентификации с LLM провайдером. Проверьте API ключ и баланс.")
        else:
            raise  # Пробрасываем другие ошибки

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

    # Санитизируем tool_id: заменяем подчеркивания на дефисы
    # Провайдер требует только a-z, A-Z, 0-9 и дефис
    tool_id = tool_id.replace("_", "-")

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
    Оптимизирован для минимизации контекста.
    """
    messages = state["messages"]

    def get_user_prompt(messages):
        for msg in messages:
            if isinstance(msg, HumanMessage):
                return msg.content
        return ""

    def get_web_search_content(messages):
        """Извлекает результаты веб-поиска из истории сообщений"""
        for msg in reversed(messages):
            if isinstance(msg, ToolMessage) and getattr(msg, "name", None) == "web_search_tool":
                return msg.content
        return None

    def filter_relevant_messages(messages):
        """
        Фильтрует только важные сообщения для финального отчета.
        Конвертирует все в текстовый формат для избежания проблем с порядком ролей.
        """
        relevant_content = []
        for msg in messages:
            # Берем только AIMessage от воркера (его рассуждения и выводы)
            if isinstance(msg, AIMessage) and not msg.tool_calls:
                relevant_content.append(f"Рассуждение агента: {msg.content}")
            # И результаты SQL/графиков (не веб-поиск)
            elif isinstance(msg, ToolMessage) and getattr(msg, "name", None) != "web_search_tool":
                # Сокращаем длинные результаты
                content = msg.content[:1000] if len(msg.content) > 1000 else msg.content
                relevant_content.append(f"Результат инструмента: {content}")
        return "\n\n".join(relevant_content)

    # Формируем компактный промпт для final report
    user_question = get_user_prompt(messages)
    web_context = get_web_search_content(messages)
    history_summary = filter_relevant_messages(messages)

    # Создаем системный промпт (без плейсхолдеров)
    sys_prompt = SystemMessage(content=final_report_prompt)

    # Формируем user message с ВСЕМИ данными
    user_content_parts = [f"Вопрос пользователя: {user_question}"]

    # Добавляем историю работы агента (SQL, графики)
    if history_summary:
        user_content_parts.append(f"\n## История работы агента:\n{history_summary}")

    # Добавляем результаты веб-поиска (если есть)
    if web_context:
        user_content_parts.append(f"\n## Результаты веб-поиска:\n{web_context}")

    user_content_parts.append("\n\nНа основе всей этой информации создай финальный отчет согласно инструкциям.")

    user_msg = HumanMessage(content="\n".join(user_content_parts))

    llm = _get_llm()

    # Retry логика для обработки 502 ошибок провайдера
    max_retries = 3
    retry_delay = 2
    last_error = None

    for attempt in range(max_retries):
        try:
            # Отправляем простую последовательность: system → user (совместимо со всеми LLM)
            response = await llm.ainvoke([sys_prompt, user_msg])
            break  # Успешно - выходим из цикла
        except Exception as e:
            last_error = e
            error_str = str(e)
            # Если 401 ошибка аутентификации - создаем fallback ответ
            if "401" in error_str or "Authentication" in error_str:
                logger.error(f"Final report: Authentication error - {error_str}")
                response = AIMessage(content="Ошибка аутентификации с LLM провайдером. Проверьте API ключ и баланс на OpenRouter.")
                break
            # Если 502 или другая временная ошибка - retry
            elif "502" in error_str or "Internal server error" in error_str:
                if attempt < max_retries - 1:
                    logger.warning(f"LLM provider error (attempt {attempt + 1}/{max_retries}): {error_str}. Retrying...")
                    import asyncio
                    await asyncio.sleep(retry_delay * (attempt + 1))  # Экспоненциальная задержка
                    continue
            # Если 400 ошибка с форматом сообщений - логируем и пробрасываем
            elif "400" in error_str and ("role" in error_str.lower() or "message_order" in error_str.lower()):
                logger.error(f"Message format error: {error_str}")
                raise
            # Другие ошибки - пробрасываем сразу
            raise
    else:
        # Если все retry исчерпаны - создаем fallback ответ
        logger.error(f"Failed to generate final report after {max_retries} attempts: {last_error}")
        response = AIMessage(content="Извините, не удалось создать финальный отчет из-за проблем с LLM провайдером. Пожалуйста, попробуйте позже.")

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


async def node_web_search(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    Web Search Node — генерирует поисковые запросы с помощью LLM и вызывает веб-поиск.
    Выполняется ТОЛЬКО если enable_web_search == True (контролируется routing в графе).
    """
    from .tools import web_search_tool

    user_prompt = None
    for msg in state["messages"]:
        if isinstance(msg, HumanMessage):
            user_prompt = msg.content
            break
    if not user_prompt:
        return {
            "messages": [ToolMessage(
                content="Ошибка: не найден исходный запрос пользователя.",
                tool_call_id="web_search_call",
                name="web_search_tool"
            )],
            "react_iter": state.get("react_iter", 0) + 1
        }

    try:
        llm = _get_llm()
        questions_count = 3
        prompt_messages = web_search_prompt.format_messages(question=user_prompt, questions_count=questions_count)
        response = await llm.ainvoke(prompt_messages)

        queries = [
            q.strip()
            for q in response.content.split('\n')
            if q.strip() and len(q.strip()) > 5
        ]
    except Exception as e:
        error_str = str(e)
        # Если 401 ошибка - пропускаем веб-поиск полностью
        if "401" in error_str or "Authentication" in error_str:
            logger.warning(f"Веб-поиск пропущен из-за проблем с аутентификацией: {error_str}")
            return {
                "messages": [ToolMessage(
                    content="Веб-поиск недоступен (проблема с API). Продолжаю анализ локальной БД.",
                    tool_call_id="web_search_call",
                    name="web_search_tool"
                )],
                "react_iter": state.get("react_iter", 0) + 1
            }
        logger.error(f"Ошибка генерации поисковых запросов: {e}")
        queries = [f"{user_prompt} медицина Россия"]

    try:
        result = await web_search_tool.ainvoke(input={"queries_list": queries}, config=config)

        tool_message = ToolMessage(
            content=result,
            tool_call_id="web_search_call",
            name="web_search_tool"
        )
        return {
            "messages": [tool_message],
            "react_iter": state.get("react_iter", 0) + 1,
        }

    except Exception as e:
        logger.error(f"Ошибка выполнения web_search_tool: {e}", exc_info=True)
        tool_message = ToolMessage(
            content=f"Ошибка веб-поиска: {str(e)}",
            tool_call_id="web_search_call",
            name="web_search_tool"
        )
        return {
            "messages": [tool_message],
            "react_iter": state.get("react_iter", 0) + 1
        }