"""
Централизованная обработка ошибок для FastAPI приложения
"""

import logging
from typing import Union

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from .exceptions import (
    AppException,
    AuthenticationError,
    DatabaseError,
    InvalidCredentialsError,
    ResourceAlreadyExistsError,
    ResourceNotFoundError,
    StorageError,
    TokenExpiredError,
    UnauthorizedError,
    ValidationError,
)

logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    """
    Регистрирует обработчики ошибок для FastAPI приложения.
    
    Args:
        app: FastAPI приложение
    """

    @app.exception_handler(ResourceNotFoundError)
    async def resource_not_found_handler(
        request: Request, exc: ResourceNotFoundError
    ) -> JSONResponse:
        """Обработка ошибок 404 Not Found"""
        logger.warning(f"Resource not found: {exc.message}", extra=exc.details)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "not_found",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(ResourceAlreadyExistsError)
    async def resource_already_exists_handler(
        request: Request, exc: ResourceAlreadyExistsError
    ) -> JSONResponse:
        """Обработка ошибок 409 Conflict"""
        logger.warning(f"Resource already exists: {exc.message}", extra=exc.details)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": "already_exists",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(InvalidCredentialsError)
    async def invalid_credentials_handler(
        request: Request, exc: InvalidCredentialsError
    ) -> JSONResponse:
        """Обработка ошибок 401 Unauthorized - неверные учетные данные"""
        logger.warning("Invalid credentials attempt")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": "invalid_credentials",
                "message": "Incorrect email or password",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(TokenExpiredError)
    async def token_expired_handler(
        request: Request, exc: TokenExpiredError
    ) -> JSONResponse:
        """Обработка ошибок 401 Unauthorized - истекший токен"""
        logger.warning("Expired token used")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": "token_expired",
                "message": "Authentication token has expired",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(UnauthorizedError)
    async def unauthorized_handler(
        request: Request, exc: UnauthorizedError
    ) -> JSONResponse:
        """Обработка ошибок 401 Unauthorized - общая"""
        logger.warning(f"Unauthorized access attempt: {exc.message}")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": "unauthorized",
                "message": exc.message or "Authentication required",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(AuthenticationError)
    async def authentication_error_handler(
        request: Request, exc: AuthenticationError
    ) -> JSONResponse:
        """Обработка общих ошибок аутентификации"""
        logger.warning(f"Authentication error: {exc.message}")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": "authentication_error",
                "message": exc.message,
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(ValidationError)
    async def validation_error_handler(
        request: Request, exc: ValidationError
    ) -> JSONResponse:
        """Обработка ошибок 400 Bad Request - валидация"""
        logger.warning(f"Validation error: {exc.message}", extra=exc.details)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "validation_error",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(DatabaseError)
    async def database_error_handler(
        request: Request, exc: DatabaseError
    ) -> JSONResponse:
        """Обработка ошибок 503 Service Unavailable - база данных"""
        logger.error(f"Database error: {exc.message}", extra=exc.details, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "database_error",
                "message": "Database service temporarily unavailable",
            },
        )

    @app.exception_handler(StorageError)
    async def storage_error_handler(
        request: Request, exc: StorageError
    ) -> JSONResponse:
        """Обработка ошибок 503 Service Unavailable - хранилище"""
        logger.error(f"Storage error: {exc.message}", extra=exc.details, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "storage_error",
                "message": "Storage service temporarily unavailable",
            },
        )

    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request, exc: AppException
    ) -> JSONResponse:
        """Обработка общих ошибок приложения"""
        logger.error(f"Application error: {exc.message}", extra=exc.details, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "application_error",
                "message": "An unexpected error occurred",
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Обработка всех необработанных исключений"""
        logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "message": "An internal server error occurred",
            },
        )
