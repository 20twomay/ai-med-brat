"""Конфигурация приложения."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class PageConfig:
    """Конфигурация страницы Streamlit."""

    title: str
    icon: str
    layout: str = "wide"
    initial_sidebar_state: str = "expanded"


@dataclass
class AppConfig:
    """Основная конфигурация приложения."""

    # API настройки
    api_url: str = os.getenv("API_URL", "http://localhost:8000")
    api_timeout: int = 60

    # Контекст модели
    context_limit: int = 256000

    # Настройки повторных попыток
    max_retries: int = 3

    # Пагинация
    default_chats_limit: int = 100
    default_messages_limit: int = 100

    # LocalStorage
    auth_token_key: str = "auth_token"

    # Пароли
    min_password_length: int = 6
    max_password_length_bytes: int = 72

    # Логирование
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_format: str = "[STREAMLIT] %(asctime)s - %(message)s"


# Конфигурации страниц
PAGE_CONFIGS = {
    "main": PageConfig(
        title="MEDBRAT.AI",
        icon="🏥",
        layout="wide",
        initial_sidebar_state="expanded"
    ),
    "auth": PageConfig(
        title="Авторизация - MedBrat.AI",
        icon="🔐",
        layout="centered",
        initial_sidebar_state="collapsed"
    ),
    "chat": PageConfig(
        title="Чат - MedBrat.AI",
        icon="💬",
        layout="wide",
        initial_sidebar_state="expanded"
    ),
}


# Глобальная конфигурация
app_config = AppConfig()