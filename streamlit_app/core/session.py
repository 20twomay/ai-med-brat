"""Утилиты для работы с сессиями Streamlit."""

import logging
from typing import Any, Dict

import streamlit as st

from constants import (
    DEFAULT_CONTEXT_LIMIT,
    SESSION_AUTHENTICATED,
    SESSION_CHAT_ID,
    SESSION_CONTEXT_LIMIT,
    SESSION_LS_TOKEN,
    SESSION_LS_TOKEN_LOADED,
    SESSION_MESSAGES,
    SESSION_MESSAGES_LOADED,
    SESSION_SHOW_PROFILE_MODAL,
    SESSION_SIDEBAR_COLLAPSED,
    SESSION_THREAD_ID,
    SESSION_TOKEN,
    SESSION_TOKEN_CHECK_ATTEMPTS,
    SESSION_TOKEN_CHECKED,
    SESSION_TOTAL_TOKENS,
    SESSION_USER_INFO,
)

logger = logging.getLogger(__name__)


def init_session_state() -> None:
    """Инициализация session state с значениями по умолчанию."""
    defaults: Dict[str, Any] = {
        SESSION_AUTHENTICATED: False,
        SESSION_TOKEN: None,
        SESSION_USER_INFO: None,
        SESSION_MESSAGES: [],
        SESSION_CHAT_ID: None,
        SESSION_THREAD_ID: None,
        SESSION_TOTAL_TOKENS: 0,
        SESSION_CONTEXT_LIMIT: DEFAULT_CONTEXT_LIMIT,
        SESSION_MESSAGES_LOADED: False,
        SESSION_TOKEN_CHECKED: False,
        SESSION_LS_TOKEN: None,
        SESSION_LS_TOKEN_LOADED: False,
        SESSION_TOKEN_CHECK_ATTEMPTS: 0,
        SESSION_SIDEBAR_COLLAPSED: False,
        SESSION_SHOW_PROFILE_MODAL: False,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def check_authentication() -> bool:
    """
    Проверка авторизации пользователя.
    
    Returns:
        True если пользователь авторизован, иначе False
    """
    return st.session_state.get(SESSION_AUTHENTICATED, False)


def clear_session_state() -> None:
    """Очистка session state (logout)."""
    logger.info("Clearing session state")
    
    st.session_state[SESSION_AUTHENTICATED] = False
    st.session_state[SESSION_TOKEN] = None
    st.session_state[SESSION_USER_INFO] = None
    st.session_state[SESSION_MESSAGES] = []
    st.session_state[SESSION_CHAT_ID] = None
    st.session_state[SESSION_THREAD_ID] = None
    st.session_state[SESSION_TOTAL_TOKENS] = 0
    st.session_state[SESSION_MESSAGES_LOADED] = False
    st.session_state[SESSION_TOKEN_CHECKED] = False
    st.session_state[SESSION_LS_TOKEN] = None
    st.session_state[SESSION_LS_TOKEN_LOADED] = False
    st.session_state[SESSION_TOKEN_CHECK_ATTEMPTS] = 0
    st.session_state[SESSION_SHOW_PROFILE_MODAL] = False
