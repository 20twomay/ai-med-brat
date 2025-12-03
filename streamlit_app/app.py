"""Streamlit интерфейс для чата с медицинским аналитическим агентом."""

import asyncio
import os
import sys
import uuid
from pathlib import Path

import requests
import streamlit as st

# Настройки API
API_URL = os.getenv("API_URL", "http://localhost:8000")

# Настройка страницы
st.set_page_config(
    page_title="Медицинский аналитический агент",
    page_icon="🏥",
    layout="wide",
)

# Заголовок
st.title("🏥 MEDBRAT.AI")
st.markdown("Задавайте вопросы о медицинских данных и получайте аналитику")

# Инициализация session state
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.messages = []
    st.session_state.waiting_for_feedback = False
    st.session_state.agent_status = None
    st.session_state.charts = []  # Список графиков

# Sidebar с информацией о сессии
with st.sidebar:
    st.header("📊 Информация о сессии")
    st.text(f"ID сессии:\n{st.session_state.session_id[:8]}...")

    if st.button("🔄 Начать новую сессию"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.waiting_for_feedback = False
        st.session_state.agent_status = None
        st.session_state.charts = []
        st.rerun()

    st.divider()

    # Проверка соединения с API
    st.header("🔌 Статус API")
    try:
        response = requests.get(f"{API_URL}/health", timeout=2)
        if response.status_code == 200:
            st.success("✅ API доступен")
        else:
            st.error("❌ API недоступен")
    except Exception as e:
        st.error(f"❌ Ошибка соединения: {str(e)[:50]}")

    st.divider()

    # Информация о статусе агента
    if st.session_state.agent_status:
        st.header("🤖 Статус агента")
        status = st.session_state.agent_status
        status_emoji = {"running": "⏳", "waiting_feedback": "❓", "completed": "✅", "error": "❌"}
        st.info(f"{status_emoji.get(status, '❓')} {status}")


def send_query(query: str):
    """Отправка запроса агенту."""
    try:
        response = requests.post(
            f"{API_URL}/query",
            json={"query": query, "session_id": st.session_state.session_id},
            timeout=120,
        )

        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Ошибка API: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        st.error(f"Ошибка при отправке запроса: {str(e)}")
        return None


def send_feedback(feedback: str):
    """Отправка обратной связи агенту."""
    try:
        response = requests.post(
            f"{API_URL}/feedback",
            json={"session_id": st.session_state.session_id, "feedback": feedback},
            timeout=120,
        )

        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Ошибка API: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        st.error(f"Ошибка при отправке обратной связи: {str(e)}")
        return None


def get_status():
    """Получение статуса сессии."""
    try:
        response = requests.get(f"{API_URL}/status/{st.session_state.session_id}", timeout=10)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return None
        else:
            st.error(f"Ошибка при получении статуса: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Ошибка при получении статуса: {str(e)}")
        return None


# Отображение истории сообщений
st.header("💬 Чат")

chat_container = st.container()

with chat_container:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            # Отображаем графики если они есть в сообщении
            if "charts" in msg and msg["charts"]:
                for chart_url in msg["charts"]:
                    st.image(f"{API_URL}{chart_url}", width=500)

# Форма для ввода сообщения
if st.session_state.agent_status == "completed":
    # Сессия завершена - показываем сообщение
    st.success(
        "✅ Сессия завершена. Нажмите «Начать новую сессию» в боковой панели для нового вопроса."
    )

elif st.session_state.waiting_for_feedback:
    st.info("🤖 Агент ожидает уточнение от вас")

    with st.form(key="feedback_form", clear_on_submit=True):
        feedback_input = st.text_area(
            "Ваш ответ:",
            placeholder="Введите уточняющую информацию...",
            height=100,
            key="feedback_input",
        )
        submit_feedback = st.form_submit_button("📤 Отправить ответ")

        if submit_feedback and feedback_input:
            # Добавляем сообщение пользователя
            st.session_state.messages.append({"role": "user", "content": feedback_input})

            # Отправляем обратную связь
            with st.spinner("⏳ Агент обрабатывает ваш ответ..."):
                result = send_feedback(feedback_input)

            if result:
                st.session_state.agent_status = result["status"]

                if result["message"]:
                    # Добавляем сообщение с графиками
                    msg_data = {
                        "role": "assistant",
                        "content": result["message"],
                        "charts": result.get("charts", []),
                    }
                    st.session_state.messages.append(msg_data)

                # Проверяем, нужно ли еще уточнение
                st.session_state.waiting_for_feedback = result.get("needs_feedback", False)

            st.rerun()

else:
    # Обычный ввод запроса
    with st.form(key="query_form", clear_on_submit=True):
        user_input = st.text_area(
            "Ваш вопрос:",
            placeholder="Например: Сколько пациентов в базе данных?",
            height=100,
            key="user_input",
        )
        submit_query = st.form_submit_button("📤 Отправить")

        if submit_query and user_input:
            # Добавляем сообщение пользователя
            st.session_state.messages.append({"role": "user", "content": user_input})

            # Отправляем запрос агенту
            with st.spinner("⏳ Агент обрабатывает ваш запрос..."):
                result = send_query(user_input)

            if result:
                st.session_state.agent_status = result["status"]

                if result["message"]:
                    # Добавляем сообщение с графиками
                    msg_data = {
                        "role": "assistant",
                        "content": result["message"],
                        "charts": result.get("charts", []),
                    }
                    st.session_state.messages.append(msg_data)

                # Проверяем, требуется ли обратная связь
                st.session_state.waiting_for_feedback = result.get("needs_feedback", False)

            st.rerun()
