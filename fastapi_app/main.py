"""
FastAPI приложение для медицинского аналитического агента
"""

import logging

from config import get_settings
from core import register_error_handlers
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langsmith import Client

from server import auth_router, chat_router, router
from server.middleware import AuthMiddleware

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Инициализация LangSmith
ls = Client()


def create_app() -> FastAPI:
    """
    Создает и настраивает FastAPI приложение.
    """
    settings = get_settings()

    app = FastAPI(
        title="Medical Analytics Agent API",
        description="API для анализа медицинских данных с помощью LLM агента",
        version="2.0.0",
    )

    # Настройка CORS с whitelist доменов из конфигурации
    allowed_origins = [origin.strip() for origin in settings.cors_allowed_origins.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Добавление middleware для авторизации
    app.add_middleware(AuthMiddleware, require_auth=True)

    # Регистрация обработчиков ошибок
    register_error_handlers(app)

    # Подключение роутеров с эндпоинтами
    app.include_router(router)
    app.include_router(auth_router)
    app.include_router(chat_router)

    return app


# Создаем приложение
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
