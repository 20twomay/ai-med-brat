"""
Middleware для логирования HTTP запросов
"""

import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware для логирования всех HTTP запросов с метриками.

    Логирует:
    - Входящие запросы с параметрами
    - Время выполнения запроса
    - Статус код ответа
    - Информацию о пользователе (если доступна)
    """

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """
        Обрабатывает каждый HTTP запрос.

        Args:
            request: HTTP запрос
            call_next: Следующий обработчик в цепочке

        Returns:
            HTTP ответ
        """
        start_time = time.time()

        # Извлекаем информацию о пользователе если доступна
        user_id = getattr(request.state, "user_id", None)
        user_email = None
        if hasattr(request.state, "user") and request.state.user:
            user_email = request.state.user.email

        # Логируем входящий запрос
        logger.info(
            "Incoming request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client_host": request.client.host if request.client else None,
                "user_id": user_id,
                "user_email": user_email,
            },
        )

        # Выполняем запрос
        try:
            response = await call_next(request)
        except Exception as e:
            # Логируем ошибку
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "Request failed with exception",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                    "user_id": user_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

        # Вычисляем время выполнения
        duration_ms = (time.time() - start_time) * 1000

        # Логируем результат
        log_level = logging.INFO
        if response.status_code >= 500:
            log_level = logging.ERROR
        elif response.status_code >= 400:
            log_level = logging.WARNING

        logger.log(
            log_level,
            "Request completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
                "user_id": user_id,
                "user_email": user_email,
            },
        )

        # Добавляем заголовки с метриками
        response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"
        response.headers["X-Request-ID"] = str(id(request))

        return response