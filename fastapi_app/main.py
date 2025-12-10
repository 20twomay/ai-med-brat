"""
FastAPI приложение для медицинского аналитического агента
"""

import logging
import time
import uuid

from agent import build_agent_graph
from config import get_settings
from core import AppException, get_storage_client, get_sync_engine
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from langsmith import Client, traceable
from schemas import ExecuteRequest, ExecuteResponse
from sqlalchemy import text

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Инициализация
settings = get_settings()
ls = Client()
compiled_graph, checkpointer = build_agent_graph()

app = FastAPI(
    title="Medical Analytics Agent API",
    description="API для анализа медицинских данных с помощью LLM агента",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/execute", response_model=ExecuteResponse)
@traceable(name="execute_query", run_type="chain")
async def execute_query(request: ExecuteRequest):
    """
    Выполняет анализ медицинских данных на основе запроса пользователя.
    """
    try:
        start_time = time.time()
        thread_id = request.thread_id or str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        # Начальное состояние
        state = {
            "messages": [{"type": "human", "content": request.query}],
            "react_iter": 0,
            "react_max_iter": 10,
            "charts": [],
            "tables": [],
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost": 0.0,
        }

        # Выполняем граф
        result = None
        async for chunk in compiled_graph.astream(state, config, stream_mode="values"):
            result = chunk

        # Собираем результат
        last_message = result["messages"][-1]
        charts = result.get("charts", [])
        tables = result.get("tables", [])
        input_tokens = result.get("input_tokens", 0)
        output_tokens = result.get("output_tokens", 0)
        total_cost = result.get("total_cost", 0.0)
        latency_ms = (time.time() - start_time) * 1000

        return ExecuteResponse(
            result=last_message.content if hasattr(last_message, "content") else str(last_message),
            charts=charts,
            tables=tables,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost=total_cost,
            thread_id=thread_id,
        )

    except AppException as e:
        logger.error(f"Application error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in execute endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error executing query: {str(e)}")


@app.get("/health")
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


@app.get("/charts/{thread_id}/{filename}")
async def get_chart(thread_id: str, filename: str):
    """
    Получение файла (график или CSV) из MinIO по thread_id и имени файла.
    """
    try:
        client = get_storage_client()
        object_name = f"{thread_id}/{filename}"
        logger.info(f"Fetching object from MinIO: {object_name}")

        response = client.get_object(settings.s3_bucket, object_name)
        content = response.read()
        response.close()
        response.release_conn()

        # Определяем content_type по расширению
        if filename.endswith(".json"):
            media_type = "application/json"
        elif filename.endswith(".csv"):
            media_type = "text/csv"
        elif filename.endswith(".png"):
            media_type = "image/png"
        else:
            media_type = "application/octet-stream"

        return Response(content=content, media_type=media_type)

    except Exception as e:
        logger.error(f"Error fetching file {thread_id}/{filename}: {e}")
        raise HTTPException(status_code=404, detail=f"File not found: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
