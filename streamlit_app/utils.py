"""
Утилиты для Streamlit приложения
"""

import logging
from typing import Optional

import streamlit as st
import extra_streamlit_components as stx

from api_client import APIClient

logger = logging.getLogger(__name__)

# Константы
MAX_PASSWORD_LENGTH_BYTES = 72
MIN_PASSWORD_LENGTH = 6

def get_cookie_manager():
    """Получить cookie manager (НЕ кэшируется, чтобы избежать проблем с widgets)"""
    if "cookie_manager" not in st.session_state:
        st.session_state.cookie_manager = stx.CookieManager()
    return st.session_state.cookie_manager


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
        "messages_loaded": False,
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def check_token_from_cookies():
    """Проверить токен из cookies и выполнить auto-login если возможно"""
    if not st.session_state.get("authenticated") and not st.session_state.get("token_checked"):
        st.session_state.token_checked = True
        try:
            cookie_manager = get_cookie_manager()
            token = cookie_manager.get("auth_token")
            if token:
                logger.info("Found auth token in cookies, attempting auto-login")
                client = APIClient()
                client.set_token(token)
                user_info = client.get_user_info()
                if user_info:
                    st.session_state.authenticated = True
                    st.session_state.token = token
                    st.session_state.user_info = user_info
                    logger.info(f"Auto-login successful for user: {user_info.get('email')}")
                else:
                    # Токен невалидный, удаляем из cookies
                    cookie_manager.delete("auth_token")
                    logger.warning("Auth token in cookies is invalid, removed")
        except Exception as e:
            logger.error(f"Error checking token from cookies: {e}")


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


def save_token_to_cookies(token: str):
    """Сохранить токен в cookies"""
    try:
        cookie_manager = get_cookie_manager()
        # Сохраняем токен на 30 дней
        cookie_manager.set("auth_token", token, max_age=30 * 24 * 60 * 60)
        logger.info("Token saved to cookies")
    except Exception as e:
        logger.error(f"Failed to save token to cookies: {e}")


def logout():
    """Выход из системы и очистка session state"""
    logger.info("User logged out")
    
    # Удаляем токен из cookies
    try:
        cookie_manager = get_cookie_manager()
        cookie_manager.delete("auth_token")
    except Exception as e:
        logger.error(f"Failed to delete token from cookies: {e}")
    
    st.session_state.authenticated = False
    st.session_state.token = None
    st.session_state.user_info = None
    st.session_state.messages = []
    st.session_state.chat_id = None
    st.session_state.thread_id = None
    st.session_state.total_tokens = 0
    st.session_state.messages_loaded = False


def validate_password_length(password: str) -> Optional[str]:
    """
    Валидация пароля: длина и наличие хотя бы одной заглавной буквы.
    Возвращает сообщение об ошибке (на русском) или None если всё ок.
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Пароль должен быть минимум {MIN_PASSWORD_LENGTH} символов"

    password_bytes = password.encode('utf-8')
    if len(password_bytes) > MAX_PASSWORD_LENGTH_BYTES:
        return f"Пароль не может быть длиннее {MAX_PASSWORD_LENGTH_BYTES} байт"

    # Проверка наличия хотя бы одной заглавной буквы
    if not any(ch.isupper() for ch in password):
        return "Пароль должен содержать хотя бы одну заглавную букву"

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
