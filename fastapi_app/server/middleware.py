"""
Middleware для проверки авторизации
"""

import logging
from typing import Optional

from core.auth import get_db_session, verify_token
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware для проверки авторизации по токену.
    Проверяет Bearer токен в заголовке Authorization для всех эндпоинтов,
    кроме публичных (health, docs, auth endpoints).
    """

    # Публичные пути, не требующие авторизации
    PUBLIC_PATHS = {
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/auth/register",
        "/auth/login",
    }

    # Префиксы публичных путей
    PUBLIC_PREFIXES = (
        "/docs",
        "/redoc",
        "/static",
        "/charts",
    )

    def __init__(self, app, require_auth: bool = True):
        """
        Args:
            app: FastAPI приложение
            require_auth: Требовать ли авторизацию (можно отключить для разработки)
        """
        super().__init__(app)
        self.require_auth = require_auth

    async def dispatch(self, request: Request, call_next):
        """
        Обрабатывает каждый запрос, проверяя авторизацию.
        """
        # Пропускаем публичные пути
        if self._is_public_path(request.url.path):
            return await call_next(request)

        # Если авторизация отключена (для разработки)
        if not self.require_auth:
            return await call_next(request)

        # Проверяем наличие токена
        token = self._extract_token(request)
        
        if not token:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "Missing authorization token",
                    "error": "unauthorized",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Проверяем валидность токена
        db_gen = get_db_session()
        db = next(db_gen)

        try:
            user = verify_token(token, db)

            if not user:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "detail": "Invalid or expired token",
                        "error": "unauthorized",
                    },
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Добавляем информацию о пользователе в state запроса
            request.state.user = user
            request.state.user_id = user.id

            logger.debug(f"Authenticated user: {user.email} (ID: {user.id})")

        except Exception as e:
            logger.error(f"Error verifying token: {e}", exc_info=True)
            db.close()
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "Authentication error",
                    "error": "internal_error",
                },
            )
        finally:
            db.close()

        # Продолжаем обработку запроса (вне блока try-except для аутентификации)
        # Ошибки из endpoint'ов будут обработаны глобальными error handlers
        response = await call_next(request)
        return response

    def _is_public_path(self, path: str) -> bool:
        """
        Проверяет, является ли путь публичным.
        
        Args:
            path: Путь запроса
            
        Returns:
            True если путь публичный, иначе False
        """
        # Точное совпадение
        if path in self.PUBLIC_PATHS:
            return True
        
        # Проверка префиксов
        if path.startswith(self.PUBLIC_PREFIXES):
            return True
        
        return False

    def _extract_token(self, request: Request) -> Optional[str]:
        """
        Извлекает Bearer токен из заголовка Authorization.
        
        Args:
            request: HTTP запрос
            
        Returns:
            Токен или None если токен не найден
        """
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            return None
        
        parts = auth_header.split()
        
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        
        return parts[1]
