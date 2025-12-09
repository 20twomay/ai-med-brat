import logging
import os

from agent.agents import build_agent_graph
from agent.models import ExecuteRequest, ExecuteResponse
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from langchain_openai import ChatOpenAI
from langsmith import Client, traceable
from sqlalchemy import text

load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

ls = Client()
compiled_graph, checkpointer = build_agent_graph()

app = FastAPI(
    title="Medical Analytics Agent API v2",
    description="Упрощенный API с двумя независимыми эндпоинтами",
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
    try:
        import time
        import uuid

        # Засекаем время начала
        start_time = time.time()

        thread_id = request.thread_id or str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        state = {
            "messages": [{"type": "human", "content": request.query}],
            "react_iter": 0,
            "react_max_iter": 5,
            "charts": [],
            "tables": [],
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost": 0.0,
            "start_time": start_time,
        }
        result = None
        for chunk in compiled_graph.stream(state, config, stream_mode="values"):
            result = chunk

        # Собираем ответ
        last_message = result["messages"][-1]

        # Получаем ссылки напрямую из state (без парсинга)
        charts = result.get("charts", [])
        tables = result.get("tables", [])
        input_tokens = result.get("input_tokens", 0)
        output_tokens = result.get("output_tokens", 0)
        total_cost = result.get("total_cost", 0.0)

        # Вычисляем latency
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
    except Exception as e:
        logger.error(f"Error in execute endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error executing query: {str(e)}")


@app.get("/health")
async def health_check():
    """Проверка работоспособности API и подключения к БД"""
    health_status = {
        "status": "healthy",
        "service": "Medical Analytics Agent v2",
        "version": "2.0.0",
        "database": "unknown",
        "s3": "unknown",
    }

    # Проверка подключения к БД
    try:
        from agent.tools import get_db_engine

        engine = get_db_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        health_status["database"] = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_status["database"] = "disconnected"
        health_status["status"] = "degraded"

    # Проверка подключения к S3
    try:
        from agent.tools import MINIO_CLIENT, S3_BUCKET

        MINIO_CLIENT.list_buckets()
        health_status["s3"] = "connected"
    except Exception as e:
        logger.error(f"S3 health check failed: {e}")
        health_status["s3"] = "disconnected"

    return health_status


@app.get("/charts/{thread_id}/{filename}")
async def get_chart(thread_id: str, filename: str):
    """Получение файла (график, CSV) из MinIO по thread_id и имени файла"""
    try:
        from agent.tools import MINIO_CLIENT, S3_BUCKET

        object_name = f"{thread_id}/{filename}"
        logger.info(f"Fetching object from MinIO: {object_name}")

        response = MINIO_CLIENT.get_object(S3_BUCKET, object_name)
        content = response.read()
        response.close()
        response.release_conn()

        # Определяем content_type по расширению файла
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
