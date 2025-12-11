"""
Core модуль с инфраструктурными компонентами
"""

from .auth import authenticate_user, create_access_token, create_user, get_current_user, verify_token
from .constants import (
    DEFAULT_CONTEXT_LIMIT,
    DEFAULT_MAX_REACT_ITERATIONS,
    HTTP_TIMEOUT_SECONDS,
    MAX_PASSWORD_LENGTH_BYTES,
    MAX_PASSWORD_LENGTH_CHARS,
    MIN_PASSWORD_LENGTH,
    SUPPORTED_MEDIA_TYPES,
    TOKEN_TYPE_BEARER,
)
from .database import get_async_engine, get_sync_engine
from .exceptions import (
    AgentError,
    AppException,
    AuthenticationError,
    DatabaseError,
    ForbiddenError,
    InvalidCredentialsError,
    LLMError,
    RateLimitError,
    ResourceAlreadyExistsError,
    ResourceNotFoundError,
    StorageError,
    TokenExpiredError,
    UnauthorizedError,
    ValidationError,
)
from .error_handlers import register_error_handlers
from .logging_config import get_logger, setup_logging
from .storage import get_storage_client
from .storage_client import StorageClient, get_storage_client_wrapper

__all__ = [
    # Database
    "get_sync_engine",
    "get_async_engine",
    # Storage
    "get_storage_client",
    "StorageClient",
    "get_storage_client_wrapper",
    # Error Handlers
    "register_error_handlers",
    # Logging
    "setup_logging",
    "get_logger",
    # Exceptions
    "AppException",
    "DatabaseError",
    "StorageError",
    "AgentError",
    "LLMError",
    "AuthenticationError",
    "UnauthorizedError",
    "ForbiddenError",
    "InvalidCredentialsError",
    "TokenExpiredError",
    "ResourceNotFoundError",
    "ResourceAlreadyExistsError",
    "ValidationError",
    "RateLimitError",
    # Auth
    "create_user",
    "authenticate_user",
    "create_access_token",
    "verify_token",
    "get_current_user",
    # Constants
    "MAX_PASSWORD_LENGTH_BYTES",
    "MIN_PASSWORD_LENGTH",
    "MAX_PASSWORD_LENGTH_CHARS",
    "TOKEN_TYPE_BEARER",
    "HTTP_TIMEOUT_SECONDS",
    "DEFAULT_MAX_REACT_ITERATIONS",
    "DEFAULT_CONTEXT_LIMIT",
    "SUPPORTED_MEDIA_TYPES",
]
