import logging
import os

from agent.agents import MedicalAnalyticsAgent
from agent.models import ClarifyRequest, ClarifyResponse, ExecuteRequest, ExecuteResponse
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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

# Создаем папку для графиков
CHARTS_DIR = os.path.join(os.path.dirname(__file__), "charts")
os.makedirs(CHARTS_DIR, exist_ok=True)

# LLM setup - валидация обязательных переменных окружения
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL")
MODEL_NAME = os.getenv("MODEL_NAME")

if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY environment variable is required")
if not API_BASE_URL:
    raise ValueError("API_BASE_URL environment variable is required")
if not MODEL_NAME:
    raise ValueError("MODEL_NAME environment variable is required")

llm = ChatOpenAI(model=MODEL_NAME, base_url=API_BASE_URL, api_key=OPENROUTER_API_KEY)

ls = Client()

# Инициализация агента
agent = MedicalAnalyticsAgent(llm)

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

# Монтируем статические файлы для графиков
app.mount("/charts", StaticFiles(directory=CHARTS_DIR), name="charts")


# ============= Endpoints =============


@app.post("/clarify", response_model=ClarifyResponse)
async def clarify_query(request: ClarifyRequest):
    """
    Проверяет запрос пользователя и определяет, нужны ли уточнения.

    Возвращает:
    - need_feedback=False: запрос готов к выполнению, можно сразу отправлять в /execute
    - need_feedback=True: нужны уточнения, показать пользователю варианты (suggestions)
    """
    try:
        return agent.clarify_query(request.query)
    except Exception as e:
        logger.error(f"Error in clarify endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing clarification: {str(e)}")


@app.post("/execute", response_model=ExecuteResponse)
@traceable(name="execute_query", run_type="chain")
async def execute_query(request: ExecuteRequest):
    """
    Выполняет анализ данных по запросу пользователя.

    Принимает уже уточненный/валидированный запрос и выполняет его:
    - Строит SQL запросы
    - Визуализирует данные
    - Возвращает результат с графиками
    """
    try:
        return agent.execute_query(request.query)
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
        from agent.tools import get_s3_client

        s3_client = get_s3_client()
        if s3_client:
            s3_client.list_buckets()
            health_status["s3"] = "connected"
        else:
            health_status["s3"] = "not_configured"
    except Exception as e:
        logger.error(f"S3 health check failed: {e}")
        health_status["s3"] = "disconnected"

    return health_status


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
