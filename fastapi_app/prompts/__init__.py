"""
Промпты для агентов
"""

from .database import database_prompt
from .system import final_report_prompt, worker_sys_prompt

__all__ = [
    "database_prompt",
    "worker_sys_prompt",
    "final_report_prompt",
]
