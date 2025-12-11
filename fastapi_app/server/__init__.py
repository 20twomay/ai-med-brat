"""
Модуль server с эндпоинтами FastAPI
"""

from .auth_endpoints import router as auth_router
from .chat_endpoints import router as chat_router
from .dependencies import get_current_user_from_request, get_user_id_from_request
from .endpoints import router
from .middleware import AuthMiddleware

__all__ = [
    "router",
    "auth_router",
    "chat_router",
    "AuthMiddleware",
    "get_current_user_from_request",
    "get_user_id_from_request",
]
