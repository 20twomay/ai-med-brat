import logging
import os
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from core.session_store import SessionStore
from core.task_queue import Task, TaskQueue
from models import (
    FeedbackRequest,
    QueryRequest,
    SessionState,
    SessionStatus,
    StatusResponse,
    TaskType,
)
from workers import QueryWorker, RouterWorker

load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Создаем папку для графиков
CHARTS_DIR = os.path.join(os.path.dirname(__file__), "charts")
os.makedirs(CHARTS_DIR, exist_ok=True)

# Глобальные переменные для сервисов
session_store: SessionStore = None
task_queue: TaskQueue = None
router_worker: RouterWorker = None
query_worker: QueryWorker = None

# WebSocket connections для отправки обновлений
active_connections: dict[str, list[WebSocket]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    global session_store, task_queue, router_worker, query_worker

    logger.info("Starting application...")

    # Инициализация сервисов
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    session_store = SessionStore(redis_url=redis_url, ttl=3600)
    await session_store.connect()

    task_queue = TaskQueue()

    # Создаём воркеры
    router_worker = RouterWorker(session_store, task_queue)
    query_worker = QueryWorker(session_store)

    # Запускаем воркеры
    await task_queue.start_workers(
        router_handler=router_worker.process_task,
        query_handler=query_worker.process_task,
        num_router_workers=2,
        num_query_workers=3,
    )

    logger.info("Application started successfully")

    yield

    # Остановка сервисов
    logger.info("Stopping application...")
    await task_queue.stop_workers()
    await session_store.disconnect()
    logger.info("Application stopped")


app = FastAPI(
    title="Medical Analytics Agent API",
    description="Масштабируемый API для работы с аналитическим агентом медицинских данных",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Монтируем статические файлы для графиков
app.mount("/charts", StaticFiles(directory=CHARTS_DIR), name="charts")


# ============= Эндпоинты =============


@app.post("/query", response_model=StatusResponse)
async def start_query(request: QueryRequest):
    """
    Запускает новый запрос или продолжает существующую сессию.

    - **query**: Вопрос пользователя к данным
    - **session_id**: ID сессии (опционально, создается автоматически)
    """
    session_id = request.session_id or str(uuid.uuid4())
    logger.info(f"Received query for session {session_id}: {request.query[:100]}...")

    try:
        # Проверяем, существует ли сессия
        existing_session = await session_store.get_session(session_id)

        if existing_session:
            logger.info(f"Session {session_id} already exists with status {existing_session.status}")
            # Возвращаем текущий статус
            return _session_to_response(existing_session)

        # Создаём новую сессию
        session = SessionState(
            session_id=session_id,
            status=SessionStatus.CREATED,
            messages=[{"type": "human", "content": request.query}],
            iteration=0,
            max_iterations=15,
            charts=[],
            is_request_valid=True,
            needs_clarification=False,
        )

        await session_store.create_session(session)
        logger.info(f"Created new session {session_id}")

        # Отправляем задачу в router воркер
        task = Task(
            session_id=session_id,
            task_type=TaskType.ROUTER,
            data={"query": request.query},
        )
        await task_queue.submit_task(task)

        # Уведомляем WebSocket подключения
        await notify_session_update(session_id)

        return StatusResponse(
            session_id=session_id,
            status=SessionStatus.ROUTER_PROCESSING,
            message="Query submitted for processing",
            needs_feedback=False,
            iteration=0,
            charts=[],
        )

    except Exception as e:
        logger.error(f"Error starting query for session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@app.post("/feedback", response_model=StatusResponse)
async def submit_feedback(request: FeedbackRequest):
    """
    Отправляет feedback пользователя и продолжает выполнение.

    - **session_id**: ID сессии
    - **feedback**: Ответ пользователя на уточняющий вопрос
    """
    try:
        session = await session_store.get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if session.status != SessionStatus.WAITING_FEEDBACK:
            raise HTTPException(
                status_code=400,
                detail=f"Session is not waiting for feedback (current status: {session.status})",
            )

        logger.info(f"Received feedback for session {request.session_id}: {request.feedback[:50]}...")

        # Добавляем feedback в сообщения
        session.messages.append({"type": "human", "content": request.feedback})
        session.needs_clarification = False
        session.status = SessionStatus.QUERY_PROCESSING

        await session_store.update_session(session)

        # Отправляем в query воркер
        task = Task(
            session_id=request.session_id,
            task_type=TaskType.QUERY,
            data={},
        )
        await task_queue.submit_task(task)

        # Уведомляем WebSocket подключения
        await notify_session_update(request.session_id)

        return StatusResponse(
            session_id=request.session_id,
            status=SessionStatus.QUERY_PROCESSING,
            message="Processing your feedback...",
            needs_feedback=False,
            iteration=session.iteration,
            charts=session.charts,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing feedback for session {request.session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing feedback: {str(e)}")


@app.get("/status/{session_id}", response_model=StatusResponse)
async def get_status(session_id: str):
    """
    Получает текущий статус сессии.

    - **session_id**: ID сессии
    """
    try:
        session = await session_store.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        return _session_to_response(session)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting status for session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting status: {str(e)}")


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket для real-time обновлений статуса сессии.
    """
    await websocket.accept()
    logger.info(f"WebSocket connection established for session {session_id}")

    # Добавляем соединение в список активных
    if session_id not in active_connections:
        active_connections[session_id] = []
    active_connections[session_id].append(websocket)

    try:
        # Отправляем текущий статус
        session = await session_store.get_session(session_id)
        if session:
            response = _session_to_response(session)
            await websocket.send_json(response.model_dump())

        # Ждём сообщений от клиента (keep-alive)
        while True:
            try:
                data = await websocket.receive_text()
                # Можно обрабатывать команды от клиента
                if data == "ping":
                    await websocket.send_text("pong")
            except WebSocketDisconnect:
                break

    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}", exc_info=True)
    finally:
        # Удаляем соединение
        if session_id in active_connections:
            active_connections[session_id].remove(websocket)
            if not active_connections[session_id]:
                del active_connections[session_id]
        logger.info(f"WebSocket connection closed for session {session_id}")


@app.get("/health")
async def health_check():
    """Проверка работоспособности API"""
    return {
        "status": "healthy",
        "service": "Medical Analytics Agent v2",
        "router_queue_size": task_queue.get_queue_size(TaskType.ROUTER),
        "query_queue_size": task_queue.get_queue_size(TaskType.QUERY),
    }


# ============= Вспомогательные функции =============


def _session_to_response(session: SessionState) -> StatusResponse:
    """Конвертирует SessionState в StatusResponse"""
    needs_feedback = session.status == SessionStatus.WAITING_FEEDBACK
    message = session.last_ai_message or _get_status_message(session.status)

    # Отладочное логирование
    logger.info(f"_session_to_response: session_id={session.session_id}, status={session.status}, last_ai_message_length={len(session.last_ai_message) if session.last_ai_message else 0}")
    
    if session.error_message:
        message = f"Error: {session.error_message}"

    return StatusResponse(
        session_id=session.session_id,
        status=session.status,
        message=message,
        needs_feedback=needs_feedback,
        iteration=session.iteration,
        charts=session.charts,
    )


def _get_status_message(status: SessionStatus) -> str:
    """Возвращает сообщение по умолчанию для статуса"""
    messages = {
        SessionStatus.CREATED: "Session created",
        SessionStatus.ROUTER_PROCESSING: "Validating your query...",
        SessionStatus.WAITING_FEEDBACK: "Waiting for your feedback",
        SessionStatus.QUERY_PROCESSING: "Processing your query...",
        SessionStatus.COMPLETED: "Query completed",
        SessionStatus.ERROR: "An error occurred",
    }
    return messages.get(status, "Unknown status")


async def notify_session_update(session_id: str):
    """Уведомляет WebSocket подключения об обновлении сессии"""
    if session_id in active_connections:
        session = await session_store.get_session(session_id)
        if session:
            response = _session_to_response(session)
            disconnected = []

            for websocket in active_connections[session_id]:
                try:
                    await websocket.send_json(response.model_dump())
                except Exception as e:
                    logger.error(f"Failed to send update to WebSocket: {e}")
                    disconnected.append(websocket)

            # Удаляем отключенные соединения
            for ws in disconnected:
                active_connections[session_id].remove(ws)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
