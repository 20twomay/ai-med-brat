import logging
import os
import re
import uuid
from typing import List, Optional

from agent.graph import build_agent_graph
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import HumanMessage
from langsmith import Client
from pydantic import BaseModel

load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем папку для графиков
CHARTS_DIR = os.path.join(os.path.dirname(__file__), "charts")
os.makedirs(CHARTS_DIR, exist_ok=True)

app = FastAPI(
    title="Medical Analytics Agent API",
    description="API для работы с аналитическим агентом медицинских данных",
    version="1.0.0",
)

# Монтируем статические файлы для графиков
app.mount("/charts", StaticFiles(directory=CHARTS_DIR), name="charts")

ls_client = Client()

LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT")
LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT")

# Инициализируем граф один раз при запуске
graph = build_agent_graph()


# ============= Модели данных =============
class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class FeedbackRequest(BaseModel):
    session_id: str
    feedback: str


class StatusResponse(BaseModel):
    session_id: str
    status: str  # "running", "waiting_feedback", "completed", "error"
    message: Optional[str] = None
    needs_feedback: bool = False
    iteration: Optional[int] = None
    charts: List[str] = []  # Список URL графиков


def extract_charts_from_messages(messages) -> List[str]:
    """Извлекает пути к графикам из сообщений агента."""
    charts = []
    for msg in messages:
        if hasattr(msg, "content") and isinstance(msg.content, str):
            # Ищем паттерн CHART_GENERATED:filename.png
            matches = re.findall(r"CHART_GENERATED:([^\s]+\.png)", msg.content)
            for match in matches:
                charts.append(f"/charts/{match}")
    return charts


# ============= Эндпоинты =============
@app.post("/query", response_model=StatusResponse)
async def start_query(request: QueryRequest):
    """
    Запускает нового агента или продолжает существующую сессию.

    - **query**: Вопрос пользователя к данным
    - **session_id**: ID сессии (опционально, создается автоматически)

    Возвращает статус выполнения и флаг needs_feedback, если требуется уточнение.
    """
    session_id = request.session_id or str(uuid.uuid4())
    logger.info(f"Processing query for session {session_id}: {request.query[:100]}...")

    try:
        config = {"configurable": {"thread_id": session_id}}

        # Получаем текущее состояние сессии
        logger.info("Getting current state...")
        current_state = graph.get_state(config)
        logger.info(f"Current state values: {bool(current_state.values)}")

        # Если сессия новая - инициализируем
        if not current_state.values:
            logger.info("New session - initializing state...")
            initial_state = {
                "messages": [HumanMessage(content=request.query)],
                "iteration": 0,
                "max_iterations": 15,
                "charts": [],
                "is_request_valid": True,
                "needs_clarification": False,
            }

            # Запускаем до первого interrupt
            logger.info("Invoking graph with initial state...")
            result = graph.invoke(initial_state, config)
            logger.info(f"Graph invoked. Messages count: {len(result.get('messages', []))}")
        else:
            # Продолжаем существующую сессию
            logger.info("Continuing existing session...")
            result = graph.invoke(None, config)
            logger.info(f"Graph invoked. Messages count: {len(result.get('messages', []))}")

        # Проверяем состояние после выполнения
        state_snapshot = graph.get_state(config)

        # Если есть следующая нода для выполнения
        if state_snapshot.next:
            if "get_human_feedback" in state_snapshot.next:
                # Агент ждет обратной связи
                last_message = result["messages"][-1].content
                charts = extract_charts_from_messages(result["messages"])
                return StatusResponse(
                    session_id=session_id,
                    status="waiting_feedback",
                    message=last_message,
                    needs_feedback=True,
                    iteration=result.get("iteration", 0),
                    charts=charts,
                )
            else:
                # Граф еще работает
                charts = extract_charts_from_messages(result["messages"])
                return StatusResponse(
                    session_id=session_id,
                    status="running",
                    message="Agent is processing...",
                    needs_feedback=False,
                    iteration=result.get("iteration", 0),
                    charts=charts,
                )
        else:
            # Граф завершён - ищем последнее AI сообщение
            final_message = ""
            for msg in reversed(result["messages"]):
                if hasattr(msg, "__class__") and msg.__class__.__name__ == "AIMessage":
                    final_message = msg.content
                    break

            charts = extract_charts_from_messages(result["messages"])
            return StatusResponse(
                session_id=session_id,
                status="completed",
                message=final_message,
                needs_feedback=False,
                iteration=result.get("iteration", 0),
                charts=charts,
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@app.post("/feedback", response_model=StatusResponse)
async def submit_feedback(request: FeedbackRequest):
    """
    Отправляет feedback пользователя и продолжает выполнение агента.

    - **session_id**: ID сессии
    - **feedback**: Ответ пользователя на уточняющий вопрос

    Агент продолжит работу с учётом полученного ответа.
    """
    try:
        config = {"configurable": {"thread_id": request.session_id}}

        # Проверяем состояние
        state_snapshot = graph.get_state(config)
        logger.info(f"Feedback received for session {request.session_id}")
        logger.info(f"Current state next nodes: {state_snapshot.next}")

        if not state_snapshot.values:
            raise HTTPException(status_code=404, detail="Session not found")

        if not state_snapshot.next or "get_human_feedback" not in state_snapshot.next:
            raise HTTPException(status_code=400, detail="Session is not waiting for feedback")

        # Обновляем состояние с ответом пользователя и сбрасываем флаг уточнения
        logger.info(f"Updating state with feedback: {request.feedback[:50]}...")
        graph.update_state(
            config,
            {"messages": [HumanMessage(content=request.feedback)]},
        )

        # Продолжаем выполнение
        logger.info("Continuing graph execution after feedback...")
        result = graph.invoke(None, config)
        logger.info(f"Graph execution completed. Result iteration: {result.get('iteration', 0)}")

        # Проверяем новое состояние
        state_snapshot = graph.get_state(config)

        if state_snapshot.next and "get_human_feedback" in state_snapshot.next:
            # Снова требуется уточнение
            charts = extract_charts_from_messages(result["messages"])
            return StatusResponse(
                session_id=request.session_id,
                status="waiting_feedback",
                message=result["messages"][-1].content,
                needs_feedback=True,
                iteration=result.get("iteration", 0),
                charts=charts,
            )
        elif state_snapshot.next:
            # Продолжает работать
            charts = extract_charts_from_messages(result["messages"])
            return StatusResponse(
                session_id=request.session_id,
                status="running",
                message="Processing continues...",
                needs_feedback=False,
                iteration=result.get("iteration", 0),
                charts=charts,
            )
        else:
            # Завершено - ищем последнее AI сообщение
            final_message = ""
            for msg in reversed(result["messages"]):
                if hasattr(msg, "__class__") and msg.__class__.__name__ == "AIMessage":
                    final_message = msg.content
                    break

            charts = extract_charts_from_messages(result["messages"])
            return StatusResponse(
                session_id=request.session_id,
                status="completed",
                message=final_message,
                needs_feedback=False,
                iteration=result.get("iteration", 0),
                charts=charts,
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing feedback: {str(e)}")


@app.get("/status/{session_id}", response_model=StatusResponse)
async def get_status(session_id: str):
    """
    Получает текущий статус сессии.

    - **session_id**: ID сессии

    Возвращает текущее состояние: running, waiting_feedback, completed или not_found.
    """
    try:
        config = {"configurable": {"thread_id": session_id}}
        state_snapshot = graph.get_state(config)

        if not state_snapshot.values:
            raise HTTPException(status_code=404, detail="Session not found")

        if state_snapshot.next and "get_human_feedback" in state_snapshot.next:
            charts = extract_charts_from_messages(state_snapshot.values["messages"])
            return StatusResponse(
                session_id=session_id,
                status="waiting_feedback",
                message=state_snapshot.values["messages"][-1].content,
                needs_feedback=True,
                iteration=state_snapshot.values.get("iteration", 0),
                charts=charts,
            )
        elif state_snapshot.next:
            charts = extract_charts_from_messages(state_snapshot.values["messages"])
            return StatusResponse(
                session_id=session_id,
                status="running",
                message="Agent is still processing",
                needs_feedback=False,
                iteration=state_snapshot.values.get("iteration", 0),
                charts=charts,
            )
        else:
            final_message = ""
            for msg in reversed(state_snapshot.values["messages"]):
                if hasattr(msg, "__class__") and msg.__class__.__name__ == "AIMessage":
                    final_message = msg.content
                    break

            charts = extract_charts_from_messages(state_snapshot.values["messages"])
            return StatusResponse(
                session_id=session_id,
                status="completed",
                message=final_message,
                needs_feedback=False,
                iteration=state_snapshot.values.get("iteration", 0),
                charts=charts,
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting status: {str(e)}")


@app.get("/health")
async def health_check():
    """Проверка работоспособности API."""
    return {"status": "healthy", "service": "Medical Analytics Agent"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
