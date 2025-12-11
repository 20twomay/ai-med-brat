"""
Кастомные исключения приложения
"""


class AppException(Exception):
    """Базовое исключение приложения"""

    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class DatabaseError(AppException):
    """Ошибки при работе с базой данных"""

    pass


class StorageError(AppException):
    """Ошибки при работе с S3/MinIO"""

    pass


class AgentError(AppException):
    """Ошибки при работе агента"""

    pass


class LLMError(AppException):
    """Ошибки при работе с LLM"""

    pass


# Auth exceptions
class AuthenticationError(AppException):
    """Ошибка аутентификации"""

    pass


class UnauthorizedError(AppException):
    """Неавторизованный доступ"""

    pass


class InvalidCredentialsError(AuthenticationError):
    """Неверные учетные данные"""

    pass


class TokenExpiredError(AuthenticationError):
    """Истек срок действия токена"""

    pass


# Resource exceptions
class ResourceNotFoundError(AppException):
    """Ресурс не найден"""

    def __init__(self, resource_type: str, resource_id: str | int):
        super().__init__(
            message=f"{resource_type} with id '{resource_id}' not found",
            details={"resource_type": resource_type, "resource_id": resource_id},
        )


class ResourceAlreadyExistsError(AppException):
    """Ресурс уже существует"""

    def __init__(self, resource_type: str, identifier: str):
        super().__init__(
            message=f"{resource_type} with identifier '{identifier}' already exists",
            details={"resource_type": resource_type, "identifier": identifier},
        )


# Validation exceptions
class ValidationError(AppException):
    """Ошибка валидации данных"""

    pass
