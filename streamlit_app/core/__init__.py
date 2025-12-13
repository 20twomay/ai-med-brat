"""Модуль core для работы с аутентификацией, сессиями и хранилищем."""

from core.auth import (
    check_token_from_localstorage,
    get_api_client,
    logout,
    require_authentication,
    validate_password_length,
)
from core.session import check_authentication, clear_session_state, init_session_state
from core.storage import (
    get_token_from_localstorage,
    remove_token_from_localstorage,
    save_token_to_localstorage,
)

__all__ = [
    # auth
    "check_token_from_localstorage",
    "get_api_client",
    "logout",
    "require_authentication",
    "validate_password_length",
    # session
    "check_authentication",
    "clear_session_state",
    "init_session_state",
    # storage
    "get_token_from_localstorage",
    "remove_token_from_localstorage",
    "save_token_to_localstorage",
]
