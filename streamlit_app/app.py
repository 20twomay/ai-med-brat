"""Главная страница - навигация и маршрутизация."""

import streamlit as st

from config import PAGE_CONFIGS
from core import check_authentication, check_token_from_localstorage, init_session_state

# Настройка страницы
page_config = PAGE_CONFIGS["main"]
st.set_page_config(
    page_title=page_config.title,
    page_icon=page_config.icon,
    layout=page_config.layout,
    initial_sidebar_state=page_config.initial_sidebar_state,
)

# Инициализация session state
init_session_state()

# Проверка токена из localStorage перед проверкой авторизации
check_token_from_localstorage()

# Проверка авторизации и перенаправление
if not check_authentication():
    # Перенаправляем на страницу авторизации
    st.switch_page("pages/1_auth.py")
else:
    # Перенаправляем в чат
    st.switch_page("pages/2_chat.py")
