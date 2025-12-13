"""Страница чата с медицинским ассистентом."""

import logging
from io import StringIO

import pandas as pd
import plotly.io as pio
import requests
import streamlit as st

from components import (
    render_chat_list,
    render_context_indicator,
    render_logo,
    render_logout_button,
    render_user_profile_button,
)
from config import PAGE_CONFIGS
from constants import (
    ARTIFACT_TYPE_CHART,
    ARTIFACT_TYPE_CSV,
    ENDPOINT_CHARTS,
    HTTP_OK,
    MSG_API_ERROR,
    ROLE_ASSISTANT,
    ROLE_USER,
    SESSION_CHAT_ID,
    SESSION_MESSAGES,
    SESSION_MESSAGES_LOADED,
    SESSION_TOKEN,
    SESSION_TOTAL_TOKENS,
)
from core import (
    check_token_from_localstorage,
    get_api_client,
    init_session_state,
    require_authentication,
)
from styles import CHAT_FORM_STYLE

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="[STREAMLIT] %(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

# Конфигурация страницы
page_config = PAGE_CONFIGS["chat"]
st.set_page_config(
    page_title=page_config.title,
    page_icon=page_config.icon,
    layout=page_config.layout,
    initial_sidebar_state=page_config.initial_sidebar_state,
)

# Инициализация сессии
init_session_state()

# Проверка токена из localStorage
check_token_from_localstorage()

# Проверка аутентификации (останавливает выполнение если не авторизован)
require_authentication()

# Получение API клиента
api_client = get_api_client()

# Custom CSS для улучшения UI
st.markdown(CHAT_FORM_STYLE, unsafe_allow_html=True)

# ===== SIDEBAR =====
with st.sidebar:
    # Логотип в самом верху
    render_logo()

    # Аккаунт и список чатов
    render_user_profile_button(api_client)
    render_chat_list(api_client, current_chat_id=st.session_state.get(SESSION_CHAT_ID))

    st.markdown(" ")
    st.markdown(" ")
    st.markdown("---")

    # Кнопка выхода
    render_logout_button()

# ===== MAIN CONTENT =====

# Заголовок
st.markdown("## Медицинский ассистент")
st.markdown("")
st.markdown("")
st.markdown("")

# Индикатор контекста над чатом
total_tokens = st.session_state.get(SESSION_TOTAL_TOKENS, 0)
render_context_indicator(total_tokens)

# Загрузка истории сообщений при открытии чата
if st.session_state.get(SESSION_CHAT_ID) and not st.session_state.get(SESSION_MESSAGES_LOADED, False):
    chat_id = st.session_state[SESSION_CHAT_ID]
    logger.info(f"Loading message history for chat_id={chat_id}")
    with st.spinner("Загрузка истории чата..."):
        messages_data = api_client.get_chat_messages(chat_id)
        if messages_data and "messages" in messages_data:
            # Преобразуем сообщения из API в формат для отображения
            st.session_state[SESSION_MESSAGES] = []
            for msg in messages_data["messages"]:
                message_dict = {"role": msg["role"], "content": msg["content"]}
                # Добавляем артефакты если они есть
                if msg.get("artifacts"):
                    artifacts = []
                    if "charts" in msg["artifacts"]:
                        for chart_path in msg["artifacts"]["charts"]:
                            logger.info(f"Adding chart artifact: {chart_path}")
                            artifacts.append(
                                {
                                    "type": ARTIFACT_TYPE_CHART,
                                    "url": f"{api_client.base_url}{ENDPOINT_CHARTS}/{chart_path}",
                                }
                            )
                    if "tables" in msg["artifacts"]:
                        for table_path in msg["artifacts"]["tables"]:
                            logger.info(f"Adding table artifact: {table_path}")
                            artifacts.append(
                                {
                                    "type": ARTIFACT_TYPE_CSV,
                                    "url": f"{api_client.base_url}{ENDPOINT_CHARTS}/{table_path}",
                                }
                            )
                    if artifacts:
                        message_dict["artifacts"] = artifacts
                st.session_state[SESSION_MESSAGES].append(message_dict)
            st.session_state[SESSION_MESSAGES_LOADED] = True
            logger.info(f"Loaded {len(st.session_state[SESSION_MESSAGES])} messages from history")

# Отображение истории сообщений
if SESSION_MESSAGES not in st.session_state:
    st.session_state[SESSION_MESSAGES] = []

for idx, message in enumerate(st.session_state[SESSION_MESSAGES]):
    role = message.get("role", ROLE_USER)
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

                if artifact_type == ARTIFACT_TYPE_CHART and artifact_url:
                    try:
                        # Загружаем JSON графика Plotly с авторизацией
                        headers = {}
                        if st.session_state.get(SESSION_TOKEN):
                            headers["Authorization"] = f"Bearer {st.session_state[SESSION_TOKEN]}"

                        response = requests.get(artifact_url, headers=headers)
                        if response.status_code == HTTP_OK:
                            fig = pio.from_json(response.text)
                            st.plotly_chart(
                                fig, use_container_width=True, key=f"chart_{idx}_{artifact_idx}"
                            )
                        else:
                            st.error(f"Не удалось загрузить график (код {response.status_code})")
                            logger.error(
                                f"Chart loading failed: {response.status_code} - {artifact_url}"
                            )
                    except Exception as e:
                        st.error(f"Ошибка при загрузке графика: {str(e)}")
                        logger.error(f"Error loading chart {artifact_url}: {e}")
                elif artifact_type == ARTIFACT_TYPE_CSV and artifact_url:
                    try:
                        # Загружаем CSV с авторизацией
                        headers = {}
                        if st.session_state.get(SESSION_TOKEN):
                            headers["Authorization"] = f"Bearer {st.session_state[SESSION_TOKEN]}"

                        response = requests.get(artifact_url, headers=headers)
                        if response.status_code == HTTP_OK:
                            # Парсим CSV для получения информации о размере
                            df = pd.read_csv(StringIO(response.text))
                            st.caption(
                                f"📊 Таблица результатов: {df.shape[0]} строк, {df.shape[1]} колонок"
                            )

                            # Кнопка для скачивания CSV
                            csv_data = response.text
                            filename = artifact_url.split("/")[-1]
                            st.download_button(
                                label="Скачать CSV",
                                data=csv_data,
                                file_name=f"results_{filename}",
                                mime="text/csv",
                                key=f"download_{idx}_{artifact_idx}_{filename}",
                            )
                        else:
                            st.error(f"Не удалось загрузить CSV (код {response.status_code})")
                            logger.error(
                                f"CSV loading failed: {response.status_code} - {artifact_url}"
                            )
                    except Exception as e:
                        st.error(f"Ошибка при загрузке CSV: {str(e)}")
                        logger.error(f"Error loading CSV {artifact_url}: {e}")

# Форма ввода сообщения
with st.form(key="chat_form", clear_on_submit=True, border=False):
    # Используем HTML/CSS для создания единой формы с кнопкой внутри
    col1, col2 = st.columns([0.9, 0.1], gap="small", vertical_alignment="bottom")

    with col1:
        user_input = st.text_input(
            "Ваше сообщение:",
            placeholder="      Спросите что-нибудь...",
            label_visibility="collapsed",
            key="user_message_input"
        )

    with col2:
        submit_button = st.form_submit_button("↑", type="primary")

# Обработка отправки сообщения
if submit_button and user_input:
    logger.info(f"User submitted message: {user_input[:50]}...")

    # Добавляем сообщение пользователя
    st.session_state[SESSION_MESSAGES].append({"role": ROLE_USER, "content": user_input})
    logger.info(
        f"Added user message to session, total messages: {len(st.session_state[SESSION_MESSAGES])}"
    )

    # Перезагружаем страницу для немедленного отображения сообщения пользователя
    st.rerun()

# Обработка запроса к API (выполняется после rerun, если есть сообщение без ответа)
if st.session_state[SESSION_MESSAGES] and st.session_state[SESSION_MESSAGES][-1].get("role") == ROLE_USER:
    # Последнее сообщение от пользователя, нужно получить ответ
    user_query = st.session_state[SESSION_MESSAGES][-1].get("content")

    # Отправляем запрос к API
    with st.spinner("Ассистент думает..."):
        try:
            # Если нет активного чата, создаем новый
            if not st.session_state.get(SESSION_CHAT_ID):
                logger.info("No active chat, creating new one")
                chat_result = api_client.create_chat(title=user_query[:50])
                if chat_result:
                    st.session_state[SESSION_CHAT_ID] = chat_result.get("id")
                    logger.info(f"Created new chat: {st.session_state[SESSION_CHAT_ID]}")
                else:
                    logger.error("Failed to create chat")

            # Выполняем запрос с механизмом retry
            logger.info(f"Executing query for chat_id={st.session_state.get(SESSION_CHAT_ID)}")
            response = api_client.execute_query_with_retry(
                query=user_query,
                chat_id=st.session_state.get(SESSION_CHAT_ID),
            )
            logger.info(f"Received response: {response is not None}")

            if response:
                logger.info(f"Processing response: {list(response.keys())}")
                # Обновляем количество токенов (добавляем к текущему значению)
                input_tokens = response.get("input_tokens", 0)
                output_tokens = response.get("output_tokens", 0)
                st.session_state[SESSION_TOTAL_TOKENS] += input_tokens + output_tokens

                # Добавляем ответ ассистента (поле "result" из ExecuteResponse)
                result_content = response.get("result", "Извините, не удалось получить ответ.")
                logger.info(
                    f"Assistant response content: {result_content[:200] if result_content else 'EMPTY'}"
                )
                assistant_message = {"role": ROLE_ASSISTANT, "content": result_content}

                # Добавляем артефакты (графики и таблицы)
                artifacts = []
                if "charts" in response and response["charts"]:
                    for chart_path in response["charts"]:
                        artifacts.append(
                            {
                                "type": ARTIFACT_TYPE_CHART,
                                "url": f"{api_client.base_url}{ENDPOINT_CHARTS}/{chart_path}",
                            }
                        )
                if "tables" in response and response["tables"]:
                    for table_path in response["tables"]:
                        artifacts.append(
                            {
                                "type": ARTIFACT_TYPE_CSV,
                                "url": f"{api_client.base_url}{ENDPOINT_CHARTS}/{table_path}",
                            }
                        )

                if artifacts:
                    assistant_message["artifacts"] = artifacts
                    logger.info(f"Added {len(artifacts)} artifacts")

                st.session_state[SESSION_MESSAGES].append(assistant_message)
                logger.info(
                    f"Added assistant message, total messages: {len(st.session_state[SESSION_MESSAGES])}"
                )

                # Перезагружаем страницу для отображения ответа ассистента
                st.rerun()
            else:
                logger.error("No response from API after all retry attempts")
                from config import app_config
                st.error(MSG_API_ERROR.format(retries=app_config.max_retries))

        except Exception as e:
            logger.exception(f"Exception during query execution: {e}")
            st.error(f"❌ Произошла ошибка: {str(e)}")