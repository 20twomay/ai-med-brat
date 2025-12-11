"""
Промпты для агентов
"""

from .database import database_prompt
from .system import final_report_prompt, worker_sys_prompt
from .web_search import web_search_prompt

__all__ = [
    "database_prompt",
    "worker_sys_prompt",
    "final_report_prompt",
    "web_search_prompt",
]
