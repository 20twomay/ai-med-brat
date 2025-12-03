from typing import List, Optional
from pydantic import BaseModel


class QueryRequest(BaseModel):
    """Запрос на обработку"""
    query: str
    session_id: Optional[str] = None


class FeedbackRequest(BaseModel):
    """Feedback от пользователя"""
    session_id: str
    feedback: str


class StatusResponse(BaseModel):
    """Ответ со статусом сессии"""
    session_id: str
    status: str
    message: Optional[str] = None
    needs_feedback: bool = False
    iteration: Optional[int] = None
    charts: List[str] = []