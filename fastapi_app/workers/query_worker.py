import logging
import os
import re
from datetime import datetime

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from agent.prompts import DB_PROMPT, SUMMARIZER_SYS_PROMPT, WORKER_SYS_PROMPT
from agent.tools import execute_sql_tool, plot_chart_tool
from core.session_store import SessionStore
from core.task_queue import Task
from models.session import SessionStatus

load_dotenv()

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL")
MODEL_NAME = os.getenv("MODEL_NAME")

TOOLS = [execute_sql_tool, plot_chart_tool]


def extract_charts_from_messages(messages) -> list[str]:
    """Извлекает пути к графикам из сообщений"""
    charts = []
    for msg_dict in messages:
        if "content" in msg_dict and isinstance(msg_dict["content"], str):
            matches = re.findall(r"CHART_GENERATED:([^\s]+\.png)", msg_dict["content"])
            for match in matches:
                charts.append(f"/charts/{match}")
    return charts


class QueryWorker:
    """Воркер для обработки SQL запросов и визуализации"""

    def __init__(self, session_store: SessionStore):
        self.session_store = session_store
        self.llm = ChatOpenAI(model=MODEL_NAME, base_url=API_BASE_URL, api_key=OPENROUTER_API_KEY)
        self.llm_with_tools = self.llm.bind_tools(TOOLS)

    async def process_task(self, task: Task):
        """Обрабатывает задачу выполнения запроса"""
        try:
            session_id = task.session_id
            logger.info(f"QueryWorker: Processing session {session_id}")

            # Получаем сессию
            session = await self.session_store.get_session(session_id)
            if not session:
                logger.error(f"QueryWorker: Session {session_id} not found")
                return

            # Обновляем статус
            session.status = SessionStatus.QUERY_PROCESSING
            await self.session_store.update_session(session)

            # Формируем сообщения для LLM
            messages = []
            for msg_dict in session.messages:
                if msg_dict["type"] == "human":
                    messages.append(HumanMessage(content=msg_dict["content"]))
                elif msg_dict["type"] == "ai":
                    messages.append(AIMessage(content=msg_dict["content"]))

            sys_msg = SystemMessage(
                content=WORKER_SYS_PROMPT.format(
                    db_prompt=DB_PROMPT,
                    current_datetime=datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
                )
            )

            # Выполняем итерации worker
            iteration = session.iteration
            max_iterations = session.max_iterations

            while iteration < max_iterations:
                logger.info(f"QueryWorker: Iteration {iteration}/{max_iterations} for session {session_id}")

                # Вызываем LLM
                response = self.llm_with_tools.invoke([sys_msg] + messages)
                messages.append(response)

                # Сохраняем AI сообщение в сессии
                session.messages.append({
                    "type": "ai",
                    "content": response.content,
                })

                # Если нет tool calls - заканчиваем
                if not response.tool_calls:
                    logger.info(f"QueryWorker: No tool calls, ending iteration for session {session_id}")
                    break

                # Выполняем tool calls
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]

                    logger.info(f"QueryWorker: Executing tool {tool_name} for session {session_id}")

                    try:
                        if tool_name == "execute_sql_tool":
                            result = execute_sql_tool.invoke(tool_args)
                        elif tool_name == "plot_chart_tool":
                            result = plot_chart_tool.invoke(tool_args)
                        else:
                            result = f"Unknown tool: {tool_name}"

                        # Создаём ToolMessage
                        tool_message = ToolMessage(
                            content=str(result),
                            tool_call_id=tool_call["id"],
                        )
                        messages.append(tool_message)

                        # Сохраняем tool message в сессии
                        session.messages.append({
                            "type": "tool",
                            "content": str(result),
                        })

                    except Exception as tool_error:
                        logger.error(f"QueryWorker: Tool error {tool_name}: {tool_error}", exc_info=True)
                        error_message = ToolMessage(
                            content=f"Error executing {tool_name}: {str(tool_error)}",
                            tool_call_id=tool_call["id"],
                        )
                        messages.append(error_message)

                        session.messages.append({
                            "type": "tool",
                            "content": f"Error: {str(tool_error)}",
                        })

                iteration += 1
                session.iteration = iteration
                await self.session_store.update_session(session)

            # Финальная суммаризация
            logger.info(f"QueryWorker: Generating summary for session {session_id}")
            summary_sys_msg = SystemMessage(
                content=SUMMARIZER_SYS_PROMPT.format(
                    current_datetime=datetime.now().strftime("%d-%m-%Y %H:%M:%S")
                )
            )
            summary = self.llm.invoke([summary_sys_msg] + messages)

            # Проверяем и обрабатываем summary
            summary_text = summary.content if summary.content else ""
            summary_text = summary_text.strip()
            
            # Если summary пустой, формируем ответ на основе последних сообщений
            if not summary_text:
                logger.warning(f"QueryWorker: Empty summary received for session {session_id}, generating fallback")
                # Проверяем последнее AI сообщение
                ai_messages = [msg for msg in session.messages if msg.get("type") == "ai" and msg.get("content")]
                if ai_messages:
                    summary_text = ai_messages[-1]["content"]
                else:
                    summary_text = "Извините, не удалось сформировать ответ на ваш запрос. Попробуйте переформулировать вопрос."
            
            logger.info(f"QueryWorker: Summary length: {len(summary_text)}")
            logger.info(f"QueryWorker: Summary preview: {summary_text[:200]}...")

            # Сохраняем summary
            session.messages.append({
                "type": "ai",
                "content": summary_text,
            })
            session.last_ai_message = summary_text

            # Извлекаем графики
            session.charts = extract_charts_from_messages(session.messages)

            # Завершаем сессию
            session.status = SessionStatus.COMPLETED
            await self.session_store.update_session(session)

            logger.info(f"QueryWorker: Completed session {session_id}")

        except Exception as e:
            logger.error(f"QueryWorker: Error processing task {task.session_id}: {e}", exc_info=True)

            # Обновляем сессию с ошибкой
            try:
                session = await self.session_store.get_session(task.session_id)
                if session:
                    session.status = SessionStatus.ERROR
                    session.error_message = str(e)
                    await self.session_store.update_session(session)
            except Exception as update_error:
                logger.error(f"QueryWorker: Failed to update error state: {update_error}")