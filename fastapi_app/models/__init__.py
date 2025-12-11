"""
Модели данных приложения
"""

from .user import User, Base
from .chat import Chat

__all__ = ["User", "Chat", "Base"]
