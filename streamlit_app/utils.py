"""
Утилиты для Streamlit приложения
"""

import logging
from typing import Optional

import streamlit as st

from api_client import APIClient

logger = logging.getLogger(__name__)

# Константы
MAX_PASSWORD_LENGTH_BYTES = 72
MIN_PASSWORD_LENGTH = 6


def init_session_state():
    """Инициализация session state с значениями по умолчанию"""
    defaults = {
        "authenticated": False,
        "token": None,
        "user_info": None,
        "messages": [],
        "chat_id": None,
        "thread_id": None,
        "total_tokens": 0,
        "context_limit": 256000,
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_api_client() -> APIClient:
    """
    Получить API клиент с установленным токеном
    
    Returns:
        Настроенный API клиент
    """
    client = APIClient()
    if st.session_state.get("token"):
        client.set_token(st.session_state.token)
    return client


def logout():
    """Выход из системы и очистка session state"""
    logger.info("User logged out")
    st.session_state.authenticated = False
    st.session_state.token = None
    st.session_state.user_info = None
    st.session_state.messages = []
    st.session_state.chat_id = None
    st.session_state.thread_id = None
    st.session_state.total_tokens = 0


def validate_password_length(password: str) -> Optional[str]:
    """
    Валидация длины пароля
    
    Args:
        password: Пароль для проверки
        
    Returns:
        Сообщение об ошибке или None если валидация прошла
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Пароль должен быть минимум {MIN_PASSWORD_LENGTH} символов"
    
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > MAX_PASSWORD_LENGTH_BYTES:
        return f"Пароль не может быть длиннее {MAX_PASSWORD_LENGTH_BYTES} байт"
    
    return None


def check_authentication() -> bool:
    """
    Проверка авторизации пользователя
    
    Returns:
        True если пользователь авторизован, иначе False
    """
    return st.session_state.get("authenticated", False)


def require_authentication():
    """Требует авторизацию, иначе перенаправляет на страницу входа"""
    if not check_authentication():
        st.warning("⚠️ Пожалуйста, войдите в систему")
        if st.button("← Перейти к авторизации"):
            st.switch_page("pages/1_auth.py")
        st.stop()
