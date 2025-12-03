from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    """Статус сессии"""
    CREATED = "created"
    ROUTER_PROCESSING = "router_processing"
    WAITING_FEEDBACK = "waiting_feedback"
    QUERY_PROCESSING = "query_processing"
    COMPLETED = "completed"
    ERROR = "error"


class TaskType(str, Enum):
    """Тип задачи"""
    ROUTER = "router"
    QUERY = "query"


class SessionState(BaseModel):
    """Состояние сессии пользователя"""
    session_id: str
    status: SessionStatus
    messages: List[dict] = Field(default_factory=list)
    iteration: int = 0
    max_iterations: int = 15
    charts: List[str] = Field(default_factory=list)
    is_request_valid: bool = True
    needs_clarification: bool = False
    error_message: Optional[str] = None
    last_ai_message: Optional[str] = None

    class Config:
        use_enum_values = True