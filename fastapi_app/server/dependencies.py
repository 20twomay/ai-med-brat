"""
Dependencies для эндпоинтов
"""

from typing import Optional

from fastapi import Request
from models import User


def get_current_user_from_request(request: Request) -> Optional[User]:
    """
    Получает текущего пользователя из request.state.
    Пользователь добавляется в state middleware'ом AuthMiddleware.
    
    Args:
        request: HTTP запрос
        
    Returns:
        Объект User или None если пользователь не найден
    """
    return getattr(request.state, "user", None)


def get_user_id_from_request(request: Request) -> Optional[int]:
    """
    Получает ID текущего пользователя из request.state.
    
    Args:
        request: HTTP запрос
        
    Returns:
        ID пользователя или None
    """
    return getattr(request.state, "user_id", None)
