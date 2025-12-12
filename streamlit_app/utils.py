"""
Утилиты для Streamlit приложения
"""

import logging
from typing import Optional

import streamlit as st
import streamlit.components.v1 as components

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
        "messages_loaded": False,
        "token_checked": False,
        "ls_token": None,
        "ls_token_loaded": False,
        "token_check_attempts": 0,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_token_from_localstorage():
    """Получить токен из localStorage через JavaScript - сохраняет в session_state"""
    if "ls_token_loaded" not in st.session_state:
        st.session_state.ls_token_loaded = False

    if not st.session_state.ls_token_loaded:
        # JavaScript код для получения токена и сохранения в Streamlit
        token_html = """
        <script>
            const token = localStorage.getItem('auth_token');
            const streamlit = window.parent;

            // Используем Streamlit API для установки значения
            if (token && token.length > 10) {
                streamlit.postMessage({
                    type: 'streamlit:setComponentValue',
                    value: token
                }, '*');
            } else {
                streamlit.postMessage({
                    type: 'streamlit:setComponentValue',
                    value: null
                }, '*');
            }
        </script>
        """
        token = components.html(token_html, height=0)

        # Проверяем что токен не пустая строка и имеет валидную длину
        if token and isinstance(token, str) and len(token) > 10:
            st.session_state.ls_token = token
            st.session_state.ls_token_loaded = True
            logger.info(f"[GET_TOKEN] Loaded token from localStorage, length: {len(token)}")
            return token
        else:
            # Первый запуск - компонент ещё не вернул значение, или токена нет
            logger.info(f"[GET_TOKEN] Component returned: {repr(token)}")
            return None
    else:
        # Токен уже загружен в session_state
        return st.session_state.get("ls_token")


def check_token_from_cookies():
    """Проверить токен из localStorage и выполнить auto-login если возможно"""
    # Инициализация счетчика попыток
    if "token_check_attempts" not in st.session_state:
        st.session_state.token_check_attempts = 0

    logger.info(f"[CHECK_TOKEN] Called. authenticated={st.session_state.get('authenticated')}, token_checked={st.session_state.get('token_checked')}, ls_token_loaded={st.session_state.get('ls_token_loaded')}, attempts={st.session_state.token_check_attempts}")

    if not st.session_state.get("authenticated"):
        # Первая попытка - загружаем токен из localStorage
        if not st.session_state.get("token_checked"):
            st.session_state.token_checked = True
            logger.info("[CHECK_TOKEN] Starting token check from localStorage")

            try:
                token = get_token_from_localstorage()
                logger.info(f"[CHECK_TOKEN] Token from localStorage: {'EXISTS' if token else 'NOT FOUND'}, ls_token_loaded={st.session_state.get('ls_token_loaded')}")

                if token and len(token) > 10:  # Проверяем что это валидный токен
                    logger.info(f"[CHECK_TOKEN] Found auth token in localStorage (len={len(token)}), attempting auto-login")
                    client = APIClient()
                    client.set_token(token)
                    user_info = client.get_user_info()

                    if user_info:
                        st.session_state.authenticated = True
                        st.session_state.token = token
                        st.session_state.user_info = user_info
                        st.session_state.token_check_attempts = 0  # Сбрасываем счетчик
                        logger.info(f"[CHECK_TOKEN] Auto-login successful for user: {user_info.get('email')}")
                        st.rerun()  # Перезагружаем чтобы перейти на страницу чата
                    else:
                        # Токен невалидный - НЕ удаляем, просто логируем
                        logger.warning("[CHECK_TOKEN] Failed to get user info with token, but keeping it for next attempt")
                else:
                    # Токен еще не загрузился (components.html асинхронный)
                    # Ограничиваем количество попыток до 3
                    if not st.session_state.get('ls_token_loaded') and st.session_state.token_check_attempts < 3:
                        logger.info(f"[CHECK_TOKEN] Token not loaded yet, will retry on next render (attempt {st.session_state.token_check_attempts + 1}/3)")
                        st.session_state.token_checked = False
                        st.session_state.token_check_attempts += 1
                        st.rerun()  # Перезагружаем для повторной попытки
                    else:
                        if st.session_state.token_check_attempts >= 3:
                            logger.warning("[CHECK_TOKEN] Max retry attempts reached, skipping token check")
                        else:
                            logger.info("[CHECK_TOKEN] No valid auth token found in localStorage")
                        st.session_state.token_check_attempts = 0  # Сбрасываем счетчик
            except Exception as e:
                logger.error(f"[CHECK_TOKEN] Error checking token from localStorage: {e}", exc_info=True)
                st.session_state.token_check_attempts = 0  # Сбрасываем счетчик при ошибке
    else:
        logger.info(f"[CHECK_TOKEN] Skipped. Already authenticated")
        st.session_state.token_check_attempts = 0  # Сбрасываем счетчик


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
    """Сохранить токен в localStorage"""
    try:
        # JavaScript код для сохранения токена в localStorage
        save_html = f"""
        <script>
            localStorage.setItem('auth_token', '{token}');
            console.log('[MEDBRAT] Token saved to localStorage');
        </script>
        """
        components.html(save_html, height=0)
        logger.info(f"[SAVE_TOKEN] Token saved to localStorage, length: {len(token)}")
    except Exception as e:
        logger.error(f"[SAVE_TOKEN] Failed to save token to localStorage: {e}", exc_info=True)


def remove_token_from_localstorage():
    """Удалить токен из localStorage"""
    try:
        remove_html = """
        <script>
            localStorage.removeItem('auth_token');
            console.log('[MEDBRAT] Token removed from localStorage');
        </script>
        """
        components.html(remove_html, height=0)
        logger.info("[REMOVE_TOKEN] Token removed from localStorage")
    except Exception as e:
        logger.error(f"[REMOVE_TOKEN] Failed to remove token from localStorage: {e}", exc_info=True)


def logout():
    """Выход из системы и очистка session state"""
    logger.info("User logged out")

    # Удаляем токен из localStorage
    remove_token_from_localstorage()

    st.session_state.authenticated = False
    st.session_state.token = None
    st.session_state.user_info = None
    st.session_state.messages = []
    st.session_state.chat_id = None
    st.session_state.thread_id = None
    st.session_state.total_tokens = 0
    st.session_state.messages_loaded = False
    st.session_state.token_checked = False
    st.session_state.ls_token = None
    st.session_state.ls_token_loaded = False
    st.session_state.token_check_attempts = 0


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
