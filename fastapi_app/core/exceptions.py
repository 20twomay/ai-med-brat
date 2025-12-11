"""
Кастомные исключения приложения
"""

from typing import Any, Dict, Optional


class AppException(Exception):
    """Базовое исключение приложения с поддержкой HTTP статус кодов"""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: Optional[int] = None,
    ):
        self.message = message
        self.details = details or {}
        if status_code:
            self.status_code = status_code
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация исключения в словарь для JSON ответа"""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class DatabaseError(AppException):
    """Ошибки при работе с базой данных"""

    status_code = 503
    error_code = "DATABASE_ERROR"


class StorageError(AppException):
    """Ошибки при работе с S3/MinIO"""

    status_code = 503
    error_code = "STORAGE_ERROR"


class AgentError(AppException):
    """Ошибки при работе агента"""

    status_code = 500
    error_code = "AGENT_ERROR"


class LLMError(AppException):
    """Ошибки при работе с LLM"""

    status_code = 502
    error_code = "LLM_ERROR"


# Auth exceptions
class AuthenticationError(AppException):
    """Ошибка аутентификации"""

    status_code = 401
    error_code = "AUTHENTICATION_ERROR"


class UnauthorizedError(AppException):
    """Неавторизованный доступ"""

    status_code = 401
    error_code = "UNAUTHORIZED"


class InvalidCredentialsError(AuthenticationError):
    """Неверные учетные данные"""

    status_code = 401
    error_code = "INVALID_CREDENTIALS"


class TokenExpiredError(AuthenticationError):
    """Истек срок действия токена"""

    status_code = 401
    error_code = "TOKEN_EXPIRED"


class ForbiddenError(AppException):
    """Доступ запрещен"""

    status_code = 403
    error_code = "FORBIDDEN"


# Resource exceptions
class ResourceNotFoundError(AppException):
    """Ресурс не найден"""

    status_code = 404
    error_code = "NOT_FOUND"

    def __init__(self, resource_type: str, resource_id: str | int):
        super().__init__(
            message=f"{resource_type} with id '{resource_id}' not found",
            details={"resource_type": resource_type, "resource_id": resource_id},
        )


class ResourceAlreadyExistsError(AppException):
    """Ресурс уже существует"""

    status_code = 409
    error_code = "ALREADY_EXISTS"

    def __init__(self, resource_type: str, identifier: str):
        super().__init__(
            message=f"{resource_type} with identifier '{identifier}' already exists",
            details={"resource_type": resource_type, "identifier": identifier},
        )


# Validation exceptions
class ValidationError(AppException):
    """Ошибка валидации данных"""

    status_code = 400
    error_code = "VALIDATION_ERROR"


# Rate limiting
class RateLimitError(AppException):
    """Превышен лимит запросов"""

    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"

    def __init__(self, message: str = "Too many requests", retry_after: Optional[int] = None):
        super().__init__(message=message)
        if retry_after:
            self.details["retry_after"] = retry_after
