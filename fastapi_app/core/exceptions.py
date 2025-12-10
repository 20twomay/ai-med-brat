"""
Кастомные исключения приложения
"""


class AppException(Exception):
    """Базовое исключение приложения"""

    pass


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
