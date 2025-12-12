"""
Эндпоинты FastAPI приложения
"""

import logging
import time
import uuid
from datetime import datetime, timezone

from agent import build_agent_graph
from config import get_settings
from core import (
    AppException,
    ResourceNotFoundError,
    SUPPORTED_MEDIA_TYPES,
    get_storage_client,
    get_sync_engine,
)
from core.auth import get_current_user, get_db_session
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from langsmith import traceable
from models import Chat, Message, User
from schemas import ExecuteRequest, ExecuteResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
settings = get_settings()

# Инициализация агента
compiled_graph, checkpointer = build_agent_graph()

# Создаем роутер
router = APIRouter()


@router.post("/execute", response_model=ExecuteResponse)
@traceable(name="execute_query", run_type="chain")
async def execute_query(
    request: ExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """
    Выполняет анализ медицинских данных на основе запроса пользователя.
    Создает новый чат или использует существующий.
    """
    try:
        start_time = time.time()

        # Получаем или создаем чат
        chat = None
        if request.chat_id:
            # Проверяем существующий чат
            chat = db.execute(
                select(Chat).where(Chat.id == request.chat_id, Chat.user_id == current_user.id)
            ).scalar_one_or_none()

            if not chat:
                raise ResourceNotFoundError("Chat", request.chat_id)

            logger.info(f"[EXECUTE] Using existing chat: id={chat.id}")
        else:
            # Создаем новый чат
            chat = Chat(
                user_id=current_user.id,
                title="Новый чат",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(chat)
            db.commit()
            db.refresh(chat)
            logger.info(f"[EXECUTE] Created new chat: id={chat.id}")

        # Конфигурация для LangGraph с thread_id = chat.id
        config = {"configurable": {"thread_id": str(chat.id)}}

        # Начальное состояние - только пользовательский запрос и настройки
        state = {
            "messages": [{"type": "human", "content": request.query}],
            "enable_web_search": request.enable_web_search,
        }

        # Передаем max_iterations через config если указан
        if request.max_iterations:
            config["configurable"]["max_iterations"] = request.max_iterations

        # Выполняем граф
        result = None
        try:
            async for chunk in compiled_graph.astream(state, config, stream_mode="values"):
                result = chunk
        except Exception as llm_error:
            # Обработка ошибок от LLM провайдера (Together AI и др.)
            logger.error(f"LLM provider error: {llm_error}", exc_info=True)

            # Обновляем время последнего сообщения в чате даже при ошибке
            chat.updated_at = datetime.now(timezone.utc)
            db.commit()

            # Возвращаем понятное сообщение об ошибке
            error_message = str(llm_error)
            if "502" in error_message or "Internal server error" in error_message:
                error_text = "Извините, сервис обработки запросов временно недоступен. Попробуйте позже."
            elif "rate limit" in error_message.lower():
                error_text = "Превышен лимит запросов. Пожалуйста, подождите немного и попробуйте снова."
            else:
                error_text = f"Произошла ошибка при обработке запроса: {error_message[:200]}"

            return ExecuteResponse(
                result=error_text,
                charts=[],
                tables=[],
                input_tokens=0,
                output_tokens=0,
                latency_ms=(time.time() - start_time) * 1000,
                cost=0.0,
                chat_id=chat.id,
            )

        # Собираем результат
        last_message = result["messages"][-1]
        charts = result.get("charts", [])
        tables = result.get("tables", [])
        input_tokens = result.get("input_tokens", 0)
        output_tokens = result.get("output_tokens", 0)
        total_cost = result.get("total_cost", 0.0)
        latency_ms = (time.time() - start_time) * 1000

        # Сохраняем сообщения в базу данных
        try:
            # Сохраняем сообщение пользователя
            user_message = Message(
                chat_id=chat.id,
                role="user",
                content=request.query,
                created_at=datetime.now(timezone.utc),
            )
            db.add(user_message)

            # Сохраняем ответ ассистента
            assistant_content = (
                last_message.content
                if hasattr(last_message, "content")
                else str(last_message)
            )
            
            # Формируем артефакты
            artifacts = {}
            if charts:
                artifacts["charts"] = charts
            if tables:
                artifacts["tables"] = tables
            
            assistant_message = Message(
                chat_id=chat.id,
                role="assistant",
                content=assistant_content,
                artifacts=artifacts if artifacts else None,
                created_at=datetime.now(timezone.utc),
            )
            db.add(assistant_message)

            # Обновляем время последнего сообщения и количество токенов в чате
            chat.updated_at = datetime.now(timezone.utc)
            chat.total_tokens += input_tokens + output_tokens
            db.commit()

            logger.info(f"[EXECUTE] Saved messages for chat_id={chat.id}")
        except Exception as db_error:
            logger.error(f"Failed to save messages: {db_error}", exc_info=True)
            # Продолжаем выполнение, даже если не удалось сохранить сообщения
            db.rollback()

        # Добавляем chat_id к путям артефактов для корректной загрузки
        charts_with_chat_id = [f"{chat.id}/{chart}" for chart in charts]
        tables_with_chat_id = [f"{chat.id}/{table}" for table in tables]

        return ExecuteResponse(
            result=assistant_content,
            charts=charts_with_chat_id,
            tables=tables_with_chat_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost=total_cost,
            chat_id=chat.id,
        )

    except Exception as e:
        # Все кастомные исключения обрабатываются error handlers
        logger.error(f"Unexpected error in execute endpoint: {e}", exc_info=True)
        raise


@router.get("/health")
async def health_check():
    """
    Проверка работоспособности API и подключения к внешним сервисам.
    """
    health_status = {
        "status": "healthy",
        "service": "Medical Analytics Agent",
        "version": "2.0.0",
        "database": "unknown",
        "s3": "unknown",
    }

    # Проверка подключения к БД
    try:
        engine = get_sync_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        health_status["database"] = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_status["database"] = "disconnected"
        health_status["status"] = "degraded"

    # Проверка подключения к S3/MinIO
    try:
        client = get_storage_client()
        client.list_buckets()
        health_status["s3"] = "connected"
    except Exception as e:
        logger.error(f"S3 health check failed: {e}")
        health_status["s3"] = "disconnected"

    return health_status


@router.get("/charts/{chat_id}/{filename}")
async def get_chart(chat_id: int, filename: str):
    """
    Получение файла (график или CSV) из MinIO по chat_id и имени файла.
    """
    try:
        client = get_storage_client()
        object_name = f"{chat_id}/{filename}"
        logger.info(f"Fetching object from MinIO: {object_name}")

        response = client.get_object(settings.s3_bucket, object_name)
        content = response.read()
        response.close()
        response.release_conn()

        # Определяем content_type по расширению
        file_extension = None
        for ext in SUPPORTED_MEDIA_TYPES:
            if filename.endswith(ext):
                file_extension = ext
                break
        
        media_type = SUPPORTED_MEDIA_TYPES.get(file_extension, "application/octet-stream")

        return Response(content=content, media_type=media_type)

    except Exception as e:
        logger.error(f"Error fetching file from chat {chat_id}, filename: {filename}: {e}")
        raise ResourceNotFoundError("File", filename)
