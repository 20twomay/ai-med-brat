"""Страница чата с медицинским ассистентом."""

import sys
import os
import logging

# Добавляем путь к родительской директории для импорта модулей
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import plotly.io as pio
import requests
import pandas as pd
from io import StringIO
from components import (
    render_logo,
    render_chat_list,
    render_user_profile_button,
    render_context_indicator,
    render_logout_button
)
from utils import require_authentication, init_session_state, get_api_client

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='[STREAMLIT] %(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


# Конфигурация страницы
st.set_page_config(
    page_title="Чат - Medical AI",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Проверка аутентификации
require_authentication()

# Инициализация сессии
init_session_state()

# Получение API клиента
api_client = get_api_client()

# Инициализация состояния сайдбара
if "sidebar_collapsed" not in st.session_state:
    st.session_state.sidebar_collapsed = False

# Custom CSS для улучшения UI
st.markdown("""
    <style>
    /* Скрыть стандартный sidebar toggle */
    [data-testid="collapsedControl"] {
        display: none;
    }

    /* Скрыть стандартную навигацию Streamlit */
    [data-testid="stSidebarNav"] {
        display: none;
    }

    /* Стиль для кнопок чатов в сайдбаре */
    [data-testid="stSidebar"] .stButton button {
        text-align: left !important;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    /* Стиль для кнопки отправки в форме */
    [data-testid="stForm"] button[kind="primary"] {
        background-color: white !important;
        color: black !important;
        border: 2px solid #e0e0e0 !important;
        border-radius: 50% !important;
        width: 48px !important;
        height: 48px !important;
        padding: 0 !important;
        min-width: 48px !important;
        font-size: 1.5rem !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }

    [data-testid="stForm"] button[kind="primary"]:hover {
        background-color: #f0f0f0 !important;
        border-color: #d0d0d0 !important;
    }
    </style>
""", unsafe_allow_html=True)

# ===== SIDEBAR =====
with st.sidebar:
    # Логотип в самом верху
    render_logo()

    st.markdown("---")
    
    # Список чатов
    render_chat_list(api_client, current_chat_id=st.session_state.get("chat_id"))
    
    st.markdown("---")
    
    # Нижняя часть: Профиль пользователя
    render_user_profile_button(api_client)
    
    # Кнопка выхода
    render_logout_button()

# ===== MAIN CONTENT =====

# Заголовок
st.markdown("#### Медицинский ассистент")
st.markdown("")
st.markdown("")
st.markdown("")

# Индикатор контекста над чатом
total_tokens = st.session_state.get("total_tokens", 0)
render_context_indicator(total_tokens)

# Отображение истории сообщений
if "messages" not in st.session_state:
    st.session_state.messages = []

for idx, message in enumerate(st.session_state.messages):
    role = message.get("role", "user")
    content = message.get("content", "")

    # Пропускаем пустые сообщения
    if not content or content.strip() == "":
        continue

    with st.chat_message(role):
        st.markdown(content)

        # Отображение артефактов (графики, CSV)
        if "artifacts" in message:
            for artifact_idx, artifact in enumerate(message["artifacts"]):
                artifact_type = artifact.get("type", "")
                artifact_url = artifact.get("url", "")

                if artifact_type == "chart" and artifact_url:
                    try:
                        # Загружаем JSON графика Plotly с авторизацией
                        headers = {}
                        if st.session_state.get("token"):
                            headers["Authorization"] = f"Bearer {st.session_state.token}"

                        response = requests.get(artifact_url, headers=headers)
                        if response.status_code == 200:
                            fig = pio.from_json(response.text)
                            st.plotly_chart(fig, use_container_width=True, key=f"chart_{idx}_{artifact_idx}")
                        else:
                            st.error(f"Не удалось загрузить график (код {response.status_code})")
                            logger.error(f"Chart loading failed: {response.status_code} - {artifact_url}")
                    except Exception as e:
                        st.error(f"Ошибка при загрузке графика: {str(e)}")
                        logger.error(f"Error loading chart {artifact_url}: {e}")
                elif artifact_type == "csv" and artifact_url:
                    try:
                        # Загружаем CSV с авторизацией
                        headers = {}
                        if st.session_state.get("token"):
                            headers["Authorization"] = f"Bearer {st.session_state.token}"

                        response = requests.get(artifact_url, headers=headers)
                        if response.status_code == 200:
                            # Парсим CSV для получения информации о размере
                            df = pd.read_csv(StringIO(response.text))
                            st.caption(
                                f"📊 Таблица результатов: {df.shape[0]} строк, {df.shape[1]} колонок"
                            )

                            # Кнопка для скачивания CSV
                            csv_data = response.text
                            filename = artifact_url.split('/')[-1]
                            st.download_button(
                                label="📥 Скачать CSV",
                                data=csv_data,
                                file_name=f"results_{filename}",
                                mime="text/csv",
                                key=f"download_{idx}_{artifact_idx}_{filename}",
                            )
                        else:
                            st.error(f"Не удалось загрузить CSV (код {response.status_code})")
                            logger.error(f"CSV loading failed: {response.status_code} - {artifact_url}")
                    except Exception as e:
                        st.error(f"Ошибка при загрузке CSV: {str(e)}")
                        logger.error(f"Error loading CSV {artifact_url}: {e}")

# Форма ввода сообщения
with st.form(key="chat_form", clear_on_submit=True):
    col1, col2 = st.columns([9, 1])

    with col1:
        user_input = st.text_input(
            "Ваше сообщение:",
            placeholder="Спросите что-нибудь...",
            label_visibility="collapsed"
        )

    with col2:
        submit_button = st.form_submit_button("↑", type="primary")

# Обработка отправки сообщения
if submit_button and user_input:
    logger.info(f"User submitted message: {user_input[:50]}...")

    # Добавляем сообщение пользователя
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })
    logger.info(f"Added user message to session, total messages: {len(st.session_state.messages)}")

    # Перезагружаем страницу для немедленного отображения сообщения пользователя
    st.rerun()

# Обработка запроса к API (выполняется после rerun, если есть сообщение без ответа)
if st.session_state.messages and st.session_state.messages[-1].get("role") == "user":
    # Последнее сообщение от пользователя, нужно получить ответ
    user_query = st.session_state.messages[-1].get("content")

    # Отправляем запрос к API
    with st.spinner("🤔 Ассистент думает..."):
        try:
            # Если нет активного чата, создаем новый
            if not st.session_state.get("chat_id"):
                logger.info("No active chat, creating new one")
                chat_result = api_client.create_chat(title=user_query[:50])
                if chat_result:
                    st.session_state.chat_id = chat_result.get("id")
                    st.session_state.thread_id = chat_result.get("thread_id")
                    logger.info(f"Created new chat: {st.session_state.chat_id}")
                else:
                    logger.error("Failed to create chat")

            # Выполняем запрос
            logger.info(f"Executing query for chat_id={st.session_state.get('chat_id')}")
            response = api_client.execute_query(
                query=user_query,
                chat_id=st.session_state.get("chat_id")
            )
            logger.info(f"Received response: {response is not None}")
            
            if response:
                logger.info(f"Processing response: {list(response.keys())}")
                # Обновляем количество токенов
                input_tokens = response.get("input_tokens", 0)
                output_tokens = response.get("output_tokens", 0)
                st.session_state.total_tokens = input_tokens + output_tokens

                # Добавляем ответ ассистента (поле "result" из ExecuteResponse)
                result_content = response.get("result", "Извините, не удалось получить ответ.")
                logger.info(f"Assistant response content: {result_content[:200] if result_content else 'EMPTY'}")
                assistant_message = {
                    "role": "assistant",
                    "content": result_content
                }
                
                # Добавляем артефакты (графики и таблицы)
                artifacts = []
                if "charts" in response and response["charts"]:
                    for chart_path in response["charts"]:
                        artifacts.append({"type": "chart", "url": f"{api_client.base_url}/charts/{chart_path}"})
                if "tables" in response and response["tables"]:
                    for table_path in response["tables"]:
                        artifacts.append({"type": "csv", "url": f"{api_client.base_url}/charts/{table_path}"})
                
                if artifacts:
                    assistant_message["artifacts"] = artifacts
                    logger.info(f"Added {len(artifacts)} artifacts")
                
                st.session_state.messages.append(assistant_message)
                logger.info(f"Added assistant message, total messages: {len(st.session_state.messages)}")

                # Перезагружаем страницу для отображения ответа ассистента
                st.rerun()
            else:
                logger.error("No response from API")
                st.error("❌ Не удалось получить ответ от сервера")

        except Exception as e:
            logger.exception(f"Exception during query execution: {e}")
            st.error(f"❌ Произошла ошибка: {str(e)}")

# Кнопка очистки чата
if st.session_state.messages:
    col1, col2, col3 = st.columns([2, 2, 1])
    with col3:
        if st.button("🗑️ Очистить чат", type="secondary"):
            st.session_state.messages = []
            st.session_state.chat_id = None
            st.session_state.total_tokens = 0
            st.rerun()
