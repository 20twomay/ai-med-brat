"""Утилиты для аутентификации и валидации."""

import logging
from typing import Optional

import streamlit as st

from api_client import APIClient
from constants import (
    MAX_PASSWORD_LENGTH_BYTES,
    MAX_TOKEN_CHECK_ATTEMPTS,
    MIN_PASSWORD_LENGTH,
    MIN_TOKEN_LENGTH,
    MSG_AUTH_REQUIRED,
    SESSION_AUTHENTICATED,
    SESSION_LS_TOKEN_LOADED,
    SESSION_TOKEN,
    SESSION_TOKEN_CHECK_ATTEMPTS,
    SESSION_TOKEN_CHECKED,
    SESSION_USER_INFO,
)
from core.session import check_authentication, clear_session_state
from core.storage import get_token_from_localstorage, remove_token_from_localstorage

logger = logging.getLogger(__name__)


def validate_password_length(password: str) -> Optional[str]:
    """
    Валидация пароля: длина и наличие хотя бы одной заглавной буквы.
    
    Args:
        password: Пароль для валидации
    
    Returns:
        Сообщение об ошибке (на русском) или None если всё ок
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


def check_token_from_localstorage() -> None:
    """Проверить токен из localStorage и выполнить auto-login если возможно."""
    # Инициализация счетчика попыток
    if SESSION_TOKEN_CHECK_ATTEMPTS not in st.session_state:
        st.session_state[SESSION_TOKEN_CHECK_ATTEMPTS] = 0

    logger.info(
        f"[CHECK_TOKEN] Called. authenticated={st.session_state.get(SESSION_AUTHENTICATED)}, "
        f"token_checked={st.session_state.get(SESSION_TOKEN_CHECKED)}, "
        f"ls_token_loaded={st.session_state.get(SESSION_LS_TOKEN_LOADED)}, "
        f"attempts={st.session_state[SESSION_TOKEN_CHECK_ATTEMPTS]}"
    )

    # Если уже авторизованы - просто возвращаемся
    if st.session_state.get(SESSION_AUTHENTICATED):
        logger.info(
            f"[CHECK_TOKEN] Already authenticated as "
            f"{st.session_state.get(SESSION_USER_INFO, {}).get('email', 'unknown')}, skipping"
        )
        if not st.session_state.get(SESSION_TOKEN_CHECKED):
            st.session_state[SESSION_TOKEN_CHECKED] = True
        st.session_state[SESSION_TOKEN_CHECK_ATTEMPTS] = 0
        return

    # Если уже проверяли и не авторизованы - не проверяем снова
    if st.session_state.get(SESSION_TOKEN_CHECKED):
        logger.info("[CHECK_TOKEN] Token already checked and auth failed, skipping")
        return

    if not st.session_state.get(SESSION_AUTHENTICATED):
        # Первая попытка - загружаем токен из localStorage
        if not st.session_state.get(SESSION_TOKEN_CHECKED):
            logger.info("[CHECK_TOKEN] Starting token check from localStorage")

            try:
                token = get_token_from_localstorage()
                logger.info(
                    f"[CHECK_TOKEN] Token from localStorage: "
                    f"{'EXISTS' if token else 'NOT FOUND'}, "
                    f"ls_token_loaded={st.session_state.get(SESSION_LS_TOKEN_LOADED)}"
                )

                if token and len(token) > MIN_TOKEN_LENGTH:  # Проверяем что это валидный токен
                    logger.info(
                        f"[CHECK_TOKEN] Found auth token in localStorage (len={len(token)}), "
                        f"attempting auto-login"
                    )
                    client = APIClient()
                    client.set_token(token)
                    user_info = client.get_user_info()

                    if user_info:
                        st.session_state[SESSION_AUTHENTICATED] = True
                        st.session_state[SESSION_TOKEN] = token
                        st.session_state[SESSION_USER_INFO] = user_info
                        st.session_state[SESSION_TOKEN_CHECKED] = True
                        st.session_state[SESSION_TOKEN_CHECK_ATTEMPTS] = 0
                        logger.info(f"[CHECK_TOKEN] Auto-login successful for user: {user_info.get('email')}")
                        st.rerun()
                    else:
                        # Токен невалидный - отмечаем что проверили
                        logger.warning("[CHECK_TOKEN] Failed to get user info with token")
                        st.session_state[SESSION_TOKEN_CHECKED] = True
                        st.session_state[SESSION_TOKEN_CHECK_ATTEMPTS] = 0
                else:
                    # Токен еще не загрузился (components.html асинхронный)
                    # Ограничиваем количество попыток
                    if (
                        not st.session_state.get(SESSION_LS_TOKEN_LOADED)
                        and st.session_state[SESSION_TOKEN_CHECK_ATTEMPTS] < MAX_TOKEN_CHECK_ATTEMPTS
                    ):
                        logger.info(
                            f"[CHECK_TOKEN] Token not loaded yet, will retry on next render "
                            f"(attempt {st.session_state[SESSION_TOKEN_CHECK_ATTEMPTS] + 1}/{MAX_TOKEN_CHECK_ATTEMPTS})"
                        )
                        st.session_state[SESSION_TOKEN_CHECK_ATTEMPTS] += 1
                        st.rerun()
                    else:
                        if st.session_state[SESSION_TOKEN_CHECK_ATTEMPTS] >= MAX_TOKEN_CHECK_ATTEMPTS:
                            logger.warning("[CHECK_TOKEN] Max retry attempts reached, marking as checked")
                        else:
                            logger.info("[CHECK_TOKEN] No valid auth token found in localStorage")
                        st.session_state[SESSION_TOKEN_CHECKED] = True
                        st.session_state[SESSION_TOKEN_CHECK_ATTEMPTS] = 0
            except Exception as e:
                logger.error(f"[CHECK_TOKEN] Error checking token from localStorage: {e}", exc_info=True)
                st.session_state[SESSION_TOKEN_CHECKED] = True
                st.session_state[SESSION_TOKEN_CHECK_ATTEMPTS] = 0


def logout() -> None:
    """Выход из системы и очистка session state."""
    logger.info("User logged out")
    remove_token_from_localstorage()
    clear_session_state()


def require_authentication() -> None:
    """Требует авторизацию, иначе перенаправляет на страницу входа."""
    # Если пользователь уже авторизован, пропускаем все проверки
    if check_authentication():
        return

    # Проверяем что проверка токена завершена
    # Если токен еще загружается (ls_token_loaded=False и попытки < MAX_TOKEN_CHECK_ATTEMPTS), ждем
    if not st.session_state.get(SESSION_TOKEN_CHECKED) or (
        not st.session_state.get(SESSION_LS_TOKEN_LOADED)
        and st.session_state.get(SESSION_TOKEN_CHECK_ATTEMPTS, 0) < MAX_TOKEN_CHECK_ATTEMPTS
    ):
        # Токен еще проверяется, показываем пустую страницу и ждем
        st.stop()

    # Проверка токена завершена, но пользователь не авторизован - редирект
    st.switch_page("pages/1_auth.py")


def get_api_client() -> APIClient:
    """
    Получить API клиент с установленным токеном.
    
    Returns:
        Настроенный API клиент
    """
    client = APIClient()
    if st.session_state.get(SESSION_TOKEN):
        client.set_token(st.session_state[SESSION_TOKEN])
    return client
