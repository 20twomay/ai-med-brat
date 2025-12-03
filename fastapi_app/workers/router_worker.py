import logging
import os
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from agent.prompts import DB_PROMPT, ROUTER_SYS_PROMPT
from core.session_store import SessionStore
from core.task_queue import Task, TaskQueue
from models.session import SessionStatus, TaskType

load_dotenv()

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL")
MODEL_NAME = os.getenv("MODEL_NAME")


class RouterOutput(BaseModel):
    is_request_valid: bool = Field(description="True если запрос валиден и понятен, иначе False")
    needs_clarification: bool | None = Field(
        description="True если требуется уточнение, иначе False"
    )
    your_response: Optional[str] = Field(
        default=None,
        description="Твое уточнение, если needs_clarification равно True. Иначе объяснение почему is_request_valid равно False.",
    )


class RouterWorker:
    """Воркер для валидации и роутинга запросов"""

    def __init__(self, session_store: SessionStore, task_queue: TaskQueue):
        self.session_store = session_store
        self.task_queue = task_queue
        self.llm = ChatOpenAI(model=MODEL_NAME, base_url=API_BASE_URL, api_key=OPENROUTER_API_KEY)
        self.llm_with_structured_output = self.llm.with_structured_output(RouterOutput)

    async def process_task(self, task: Task):
        """Обрабатывает задачу валидации"""
        try:
            session_id = task.session_id
            logger.info(f"RouterWorker: Processing session {session_id}")

            # Получаем сессию
            session = await self.session_store.get_session(session_id)
            if not session:
                logger.error(f"RouterWorker: Session {session_id} not found")
                return

            # Обновляем статус
            session.status = SessionStatus.ROUTER_PROCESSING
            await self.session_store.update_session(session)

            # Формируем сообщения для LLM
            messages = []
            for msg_dict in session.messages:
                if msg_dict["type"] == "human":
                    messages.append(HumanMessage(content=msg_dict["content"]))
                elif msg_dict["type"] == "ai":
                    messages.append(AIMessage(content=msg_dict["content"]))

            sys_msg = SystemMessage(
                content=ROUTER_SYS_PROMPT.format(
                    db_prompt=DB_PROMPT,
                    current_datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                )
            )

            logger.info(f"RouterWorker: Calling LLM for session {session_id}")
            response = self.llm_with_structured_output.invoke([sys_msg] + messages)

            logger.info(
                f"RouterWorker: LLM response - is_valid={response.is_request_valid}, "
                f"needs_clarification={response.needs_clarification}"
            )

            # Обновляем сессию
            session.is_request_valid = response.is_request_valid
            session.needs_clarification = response.needs_clarification or False

            your_response = response.your_response or "Запрос валиден и не требует уточнений."
            session.messages.append({"type": "ai", "content": your_response})
            session.last_ai_message = your_response

            # Определяем следующий статус
            if not response.is_request_valid:
                session.status = SessionStatus.COMPLETED
                logger.info(f"RouterWorker: Request invalid for session {session_id}")
            elif response.needs_clarification:
                session.status = SessionStatus.WAITING_FEEDBACK
                logger.info(f"RouterWorker: Needs clarification for session {session_id}")
            else:
                # Запрос валиден - отправляем в query воркер
                session.status = SessionStatus.QUERY_PROCESSING
                logger.info(f"RouterWorker: Submitting to query worker for session {session_id}")

                # Сохраняем сессию перед отправкой в query воркер
                await self.session_store.update_session(session)

                # Отправляем задачу в query воркер
                query_task = Task(
                    session_id=session_id,
                    task_type=TaskType.QUERY,
                    data={},
                )
                await self.task_queue.submit_task(query_task)
                return  # Не сохраняем сессию повторно

            await self.session_store.update_session(session)
            logger.info(f"RouterWorker: Completed session {session_id}")

        except Exception as e:
            logger.error(f"RouterWorker: Error processing task {task.session_id}: {e}", exc_info=True)

            # Обновляем сессию с ошибкой
            try:
                session = await self.session_store.get_session(task.session_id)
                if session:
                    session.status = SessionStatus.ERROR
                    session.error_message = str(e)
                    await self.session_store.update_session(session)
            except Exception as update_error:
                logger.error(f"RouterWorker: Failed to update error state: {update_error}")