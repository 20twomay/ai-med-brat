"""Streamlit интерфейс для медицинского аналитического агента."""

import logging
import os
from io import StringIO

import pandas as pd
import plotly.io as pio
import requests
import streamlit as st

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Настройки API
API_URL = os.getenv("API_URL", "http://localhost:8000")
logger.info(f"API_URL: {API_URL}")

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
if "messages" not in st.session_state:
    st.session_state.messages = []
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None
if "total_tokens" not in st.session_state:
    st.session_state.total_tokens = 0
if "context_limit" not in st.session_state:
    st.session_state.context_limit = 256000  # Лимит для ministral-14b-2512

# Sidebar с информацией
with st.sidebar:
    st.header("📊 Информация")

    if st.button("🔄 Очистить историю"):
        st.session_state.messages = []
        st.session_state.thread_id = None
        st.session_state.total_tokens = 0
        st.rerun()

    st.divider()

    # Проверка соединения с API
    st.header("🔌 Статус сервисов")
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            st.success("✅ FastAPI: Доступен")

            # Показываем статус БД
            db_status = health_data.get("database", "unknown")
            if db_status == "connected":
                st.success("✅ PostgreSQL: Подключен")
            else:
                st.error("❌ PostgreSQL: Отключен")

            # Показываем статус S3
            s3_status = health_data.get("s3", "unknown")
            if s3_status == "connected":
                st.success("✅ MinIO: Подключен")
            else:
                st.error("❌ MinIO: Отключен")
        else:
            st.error("❌ FastAPI: Недоступен")
    except requests.exceptions.ConnectionError:
        st.error("❌ Нет соединения с API")
    except requests.exceptions.Timeout:
        st.warning("⏳ API не отвечает")
    except Exception as e:
        st.error(f"❌ Ошибка: {str(e)[:50]}")

    st.divider()

    # Отображение использования токенов
    st.header("📊 Использование контекста")
    total_tokens = st.session_state.total_tokens
    context_limit = st.session_state.context_limit

    if total_tokens > 0:
        usage_percent = (total_tokens / context_limit) * 100
        st.metric(
            label="Токены",
            value=f"{total_tokens / 1000:.1f}k / {context_limit / 1000:.0f}k",
            delta=f"{usage_percent:.1f}% использовано",
        )
        st.progress(min(usage_percent / 100, 1.0))
    else:
        st.info("Ожидаются данные...")

    st.divider()


def execute_query(query: str, thread_id: str = None):
    """Выполнение анализа через /execute endpoint"""
    logger.info(f"[EXECUTE] Starting execute for query: {query[:50]}...")
    try:
        payload = {"query": query}
        if thread_id:
            payload["thread_id"] = thread_id

        response = requests.post(
            f"{API_URL}/execute",
            json=payload,
            timeout=None,
        )

        if response.status_code == 200:
            result = response.json()
            logger.info(
                f"[EXECUTE] Success: result_length={len(result.get('result', ''))}, "
                f"thread_id={result.get('thread_id')}"
            )
            return result
        else:
            logger.error(f"[EXECUTE] API error: {response.status_code}")
            st.error(f"Ошибка API: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"[EXECUTE] Exception: {e}")
        st.error(f"❌ Ошибка: {str(e)}")
        return None


# Отображение истории сообщений
st.header("💬 Чат")

for idx, msg in enumerate(st.session_state.messages):
    content = msg.get("content", "")

    if not content or content.strip() == "":
        continue

    with st.chat_message(msg["role"]):
        st.markdown(content)

        # Отображаем графики если они есть
        if "charts" in msg and msg["charts"]:
            for chart_idx, chart_path in enumerate(msg["charts"]):
                try:
                    response = requests.get(f"{API_URL}/charts/{chart_path}")
                    if response.status_code == 200:
                        fig = pio.from_json(response.text)
                        st.plotly_chart(
                            fig, width="stretch", key=f"chart_{idx}_{chart_idx}_{chart_path}"
                        )
                    else:
                        st.error("Не удалось загрузить график")
                except Exception as e:
                    st.error("Не удалось загрузить график")
                    logger.error(f"[CHART] Error loading chart {chart_path}: {e}")

        # Отображаем таблицы если они есть
        if "tables" in msg and msg["tables"]:
            for table_idx, table_path in enumerate(msg["tables"]):
                try:
                    response = requests.get(f"{API_URL}/charts/{table_path}")
                    if response.status_code == 200:
                        df = pd.read_csv(StringIO(response.text))
                        st.caption(
                            f"📊 Таблица результатов: {df.shape[0]} строк, {df.shape[1]} колонок"
                        )

                        # Кнопка для скачивания CSV
                        csv_data = response.text
                        st.download_button(
                            label="📥 Скачать CSV",
                            data=csv_data,
                            file_name=f"results_{table_path.split('/')[-1]}",
                            mime="text/csv",
                            key=f"download_{idx}_{table_idx}_{table_path}",
                        )
                    else:
                        st.error("Не удалось загрузить таблицу")
                except Exception as e:
                    st.error("Не удалось загрузить таблицу")
                    logger.error(f"[TABLE] Error loading table {table_path}: {e}")

# Форма для ввода сообщения
with st.form(key="query_form", clear_on_submit=True):
    user_input = st.text_area(
        "Ваш вопрос:",
        placeholder="Например: Топ-5 заболеваний в Санкт-Петербурге",
        height=100,
        key="user_input",
    )

    col1, col2 = st.columns([1, 5])
    with col1:
        submit_query = st.form_submit_button("📤 Отправить", use_container_width=True)
    with col2:
        st.caption("*Нажмите Ctrl+Enter для быстрой отправки*")

    if submit_query and user_input.strip():
        logger.info(f"[FORM] User submitted: {user_input.strip()[:50]}...")

        # Добавляем сообщение пользователя в историю
        st.session_state.messages.append({"role": "user", "content": user_input.strip()})

        # Немедленно отображаем сообщение пользователя
        st.rerun()

    # Выполняем запрос после rerun (если есть последнее сообщение без ответа)
    if (
        st.session_state.messages
        and st.session_state.messages[-1]["role"] == "user"
        and (len(st.session_state.messages) == 1 or st.session_state.messages[-2]["role"] != "user")
    ):
        user_query = st.session_state.messages[-1]["content"]

        # Выполняем запрос
        with st.spinner("⏳ Выполняю анализ..."):
            execute_result = execute_query(user_query, st.session_state.thread_id)

        if execute_result:
            # Сохраняем thread_id для продолжения диалога
            st.session_state.thread_id = execute_result.get("thread_id")

            # Обновляем информацию о токенах
            input_tokens = execute_result.get("input_tokens", 0)
            output_tokens = execute_result.get("output_tokens", 0)
            st.session_state.total_tokens += input_tokens + output_tokens

            result_text = execute_result.get("result", "").strip()
            if result_text:
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": result_text,
                        "charts": execute_result.get("charts", []),
                        "tables": execute_result.get("tables", []),
                    }
                )
            else:
                st.session_state.messages.append(
                    {"role": "assistant", "content": "⚠️ Анализ выполнен, но результат пустой."}
                )
        else:
            st.session_state.messages.append(
                {"role": "assistant", "content": "❌ Произошла ошибка при выполнении анализа."}
            )

        st.rerun()
