"""
Репозитории для работы с данными
"""

from .base_repository import BaseRepository
from .chat_repository import ChatRepository
from .user_repository import UserRepository

__all__ = ["BaseRepository", "UserRepository", "ChatRepository"]