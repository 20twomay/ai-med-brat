"""Утилиты для работы с LocalStorage через JavaScript."""

import logging
from typing import Optional

import streamlit as st
import streamlit.components.v1 as components

from constants import (
    LOCALSTORAGE_AUTH_TOKEN_KEY,
    LOCALSTORAGE_INIT_DELAY_MS,
    MAX_TOKEN_CHECK_ATTEMPTS,
    MIN_TOKEN_LENGTH,
    SESSION_LS_TOKEN,
    SESSION_LS_TOKEN_LOADED,
    SESSION_TOKEN_CHECK_ATTEMPTS,
)

logger = logging.getLogger(__name__)


def get_token_from_localstorage() -> Optional[str]:
    """
    Получить токен из localStorage через JavaScript - сохраняет в session_state.
    
    Returns:
        Токен или None если токен не найден
    """
    if not st.session_state.get(SESSION_LS_TOKEN_LOADED, False):
        # JavaScript код для получения токена и сохранения в Streamlit
        token_html = f"""
        <script>
            // Даем браузеру время для инициализации
            setTimeout(function() {{
                const token = localStorage.getItem('{LOCALSTORAGE_AUTH_TOKEN_KEY}');
                const streamlit = window.parent;

                console.log('[MEDBRAT] Reading token from localStorage:', token ? 'EXISTS (length=' + token.length + ')' : 'NOT FOUND');

                // Используем Streamlit API для установки значения
                if (token && token.length > {MIN_TOKEN_LENGTH}) {{
                    streamlit.postMessage({{
                        type: 'streamlit:setComponentValue',
                        value: token
                    }}, '*');
                }} else {{
                    streamlit.postMessage({{
                        type: 'streamlit:setComponentValue',
                        value: null
                    }}, '*');
                }}
            }}, {LOCALSTORAGE_INIT_DELAY_MS});
        </script>
        """
        token = components.html(token_html, height=0)

        # Проверяем что токен не пустая строка и имеет валидную длину
        if token and isinstance(token, str) and len(token) > MIN_TOKEN_LENGTH:
            st.session_state[SESSION_LS_TOKEN] = token
            st.session_state[SESSION_LS_TOKEN_LOADED] = True
            logger.info(f"[GET_TOKEN] Loaded token from localStorage, length: {len(token)}")
            return token
        else:
            # Первый запуск - компонент ещё не вернул значение, или токена нет
            logger.info(f"[GET_TOKEN] Component returned: {repr(token)}")
            return None
    else:
        # Токен уже загружен в session_state
        return st.session_state.get(SESSION_LS_TOKEN)


def save_token_to_localstorage(token: str) -> None:
    """
    Сохранить токен в localStorage.
    
    Args:
        token: Токен для сохранения
    """
    try:
        # JavaScript код для сохранения токена в localStorage
        save_html = f"""
        <script>
            localStorage.setItem('{LOCALSTORAGE_AUTH_TOKEN_KEY}', '{token}');
            console.log('[MEDBRAT] Token saved to localStorage');
        </script>
        """
        components.html(save_html, height=0)
        logger.info(f"[SAVE_TOKEN] Token saved to localStorage, length: {len(token)}")
    except Exception as e:
        logger.error(f"[SAVE_TOKEN] Failed to save token to localStorage: {e}", exc_info=True)


def remove_token_from_localstorage() -> None:
    """Удалить токен из localStorage."""
    try:
        remove_html = f"""
        <script>
            localStorage.removeItem('{LOCALSTORAGE_AUTH_TOKEN_KEY}');
            console.log('[MEDBRAT] Token removed from localStorage');
        </script>
        """
        components.html(remove_html, height=0)
        logger.info("[REMOVE_TOKEN] Token removed from localStorage")
    except Exception as e:
        logger.error(f"[REMOVE_TOKEN] Failed to remove token from localStorage: {e}", exc_info=True)
