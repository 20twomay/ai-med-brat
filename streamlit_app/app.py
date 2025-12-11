"""Главная страница - навигация и маршрутизация."""

import streamlit as st

from utils import check_authentication, init_session_state

# Настройка страницы
st.set_page_config(
    page_title="MEDBRAT.AI",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Инициализация session state
init_session_state()

# Проверка авторизации и перенаправление
if not check_authentication():
    # Перенаправляем на страницу авторизации
    st.switch_page("pages/1_auth.py")
else:
    # Перенаправляем в чат
    st.switch_page("pages/2_chat.py")
