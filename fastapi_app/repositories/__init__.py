"""
Репозитории для работы с данными
"""

from .user_repository import UserRepository
from .chat_repository import ChatRepository

__all__ = ["UserRepository", "ChatRepository"]