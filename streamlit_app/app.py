"""Streamlit интерфейс для медицинского аналитического агента."""

import os
import requests
import streamlit as st
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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
if "suggestions" not in st.session_state:
    st.session_state.suggestions = None
if "processing" not in st.session_state:
    st.session_state.processing = False
if "selected_suggestion" not in st.session_state:
    st.session_state.selected_suggestion = None
if "pending_query" not in st.session_state:
    st.session_state.pending_query = None

# Sidebar с информацией
with st.sidebar:
    st.header("📊 Информация")
    
    if st.button("🔄 Очистить историю"):
        st.session_state.messages = []
        st.session_state.suggestions = None
        st.session_state.processing = False
        st.session_state.selected_suggestion = None
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
            elif s3_status == "not_configured":
                st.warning("⚠️ MinIO: Не настроен")
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
    
    st.markdown("""
    ### 💡 Примеры запросов
    
    - Топ-5 заболеваний в Санкт-Петербурге
    - Средняя стоимость лекарств по районам
    - Распределение пациентов по полу и возрасту
    - Какие препараты чаще всего назначают при гипертонии?
    """)


def clarify_query(query: str):
    """Проверка запроса через /clarify endpoint"""
    logger.info(f"[CLARIFY] Starting clarify for query: {query[:50]}...")
    try:
        response = requests.post(
            f"{API_URL}/clarify",
            json={"query": query},
            timeout=300  # 5 минут для уточнения запроса
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"[CLARIFY] Response: is_valid={result.get('is_request_valid')}, "
                       f"needs_clarification={result.get('needs_clarification')}, "
                       f"message='{result.get('message')}'")
            return result
        else:
            logger.error(f"[CLARIFY] API error: {response.status_code}")
            st.error(f"Ошибка API: {response.status_code}")
            return None
    except requests.exceptions.Timeout:
        logger.error("[CLARIFY] Timeout")
        st.error("❌ Превышено время ожидания ответа")
        return None
    except requests.exceptions.ConnectionError:
        logger.error("[CLARIFY] Connection error")
        st.error("❌ Не удалось подключиться к API")
        return None
    except Exception as e:
        logger.error(f"[CLARIFY] Exception: {e}")
        st.error(f"❌ Ошибка: {str(e)}")
        return None


def execute_query(query: str):
    """Выполнение анализа через /execute endpoint"""
    logger.info(f"[EXECUTE] Starting execute for query: {query[:50]}...")
    try:
        response = requests.post(
            f"{API_URL}/execute",
            json={"query": query},
            timeout=None  # Без ограничения по времени для выполнения анализа
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"[EXECUTE] Success: result_length={len(result.get('result', ''))}, "
                       f"charts_count={len(result.get('charts', []))}")
            return result
        else:
            logger.error(f"[EXECUTE] API error: {response.status_code}")
            st.error(f"Ошибка API: {response.status_code}")
            return None
    except requests.exceptions.Timeout:
        logger.error("[EXECUTE] Timeout")
        st.error("❌ Превышено время ожидания. Запрос слишком сложный.")
        return None
    except requests.exceptions.ConnectionError:
        logger.error("[EXECUTE] Connection error")
        st.error("❌ Не удалось подключиться к API")
        return None
    except Exception as e:
        logger.error(f"[EXECUTE] Exception: {e}")
        st.error(f"❌ Ошибка: {str(e)}")
        return None


# Отображение истории сообщений
st.header("💬 Чат")

chat_container = st.container()

with chat_container:
    for idx, msg in enumerate(st.session_state.messages):
        # Фильтруем служебные сообщения
        content = msg.get("content", "")
        
        logger.debug(f"[CHAT] Message {idx}: role={msg.get('role')}, content='{content[:80]}...'")
        
        # Пропускаем пустые сообщения и служебные
        if not content or content.strip() == "":
            logger.debug(f"[CHAT] Skipping empty message {idx}")
            continue
            
        # Пропускаем "Запрос принят к выполнению" - это служебное сообщение
        if "Запрос принят к выполнению" in content:
            logger.warning(f"[CHAT] FILTERED SERVICE MESSAGE {idx}: '{content}'")
            continue
        
        with st.chat_message(msg["role"]):
            st.markdown(content)
            
            # Отображаем графики если они есть
            if "charts" in msg and msg["charts"]:
                for chart_url in msg["charts"]:
                    try:
                        # chart_url уже полный URL от S3 или локальный путь
                        if chart_url.startswith("http"):
                            st.image(chart_url, width=700)
                        else:
                            # Локальный путь - добавляем API_URL
                            st.image(f"{API_URL}{chart_url}", width=700)
                    except Exception as e:
                        st.error(f"Не удалось загрузить график: {chart_url}")

# Обработка отложенного запроса (после rerun когда юзер уже видит свое сообщение)
if st.session_state.pending_query:
    query = st.session_state.pending_query
    st.session_state.pending_query = None
    logger.info(f"[PENDING] Processing pending query: {query[:50]}...")
    
    # Проверка запроса
    with st.spinner("🔍 Проверяю запрос..."):
        clarify_result = clarify_query(query)
    
    if clarify_result:
        logger.info(f"[PENDING] Clarify result received")
        
        if not clarify_result.get("is_request_valid", False):
            logger.info("[PENDING] SCENARIO 1: Request is NOT valid")
            message = clarify_result.get('message', 'Запрос не относится к медицинским данным').strip()
            
            if "принят к выполнению" in message.lower():
                logger.warning(f"[PENDING] FILTERED service message: '{message}'")
                message = "Запрос не может быть выполнен"
            
            if message:
                st.session_state.messages.append({"role": "assistant", "content": f"❌ {message}"})
            else:
                st.session_state.messages.append({"role": "assistant", "content": "❌ Запрос не может быть выполнен"})
            st.rerun()
        
        elif clarify_result.get("needs_clarification", False):
            logger.info("[PENDING] SCENARIO 2: Request needs clarification")
            suggestions = clarify_result.get("suggestions", [])
            if suggestions:
                st.session_state.suggestions = suggestions
                message = clarify_result.get("message", "Ваш запрос требует уточнения").strip()
                
                if "принят к выполнению" in message.lower():
                    logger.warning(f"[PENDING] FILTERED service message: '{message}'")
                    message = "Ваш запрос требует уточнения"
                
                st.session_state.messages.append({"role": "assistant", "content": f"🤔 {message}"})
            else:
                st.session_state.messages.append({"role": "assistant", "content": "❓ Пожалуйста, уточните ваш запрос."})
            st.rerun()
        
        else:
            logger.info("[PENDING] SCENARIO 3: Request is ready for execution")
            with st.spinner("⏳ Выполняю анализ..."):
                execute_result = execute_query(query)
            
            if execute_result:
                result_text = execute_result.get("result", "").strip()
                if result_text:
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": result_text,
                        "charts": execute_result.get("charts", [])
                    })
                else:
                    st.session_state.messages.append({"role": "assistant", "content": "⚠️ Анализ выполнен, но результат пустой."})
            else:
                st.session_state.messages.append({"role": "assistant", "content": "❌ Произошла ошибка при выполнении анализа."})
            
            st.session_state.suggestions = None
            st.rerun()
    else:
        logger.error("[PENDING] Clarify failed")
        st.session_state.messages.append({"role": "assistant", "content": "❌ Не удалось проверить запрос. Проверьте подключение к API."})
        st.rerun()

# Если есть варианты уточнений - показываем их
if st.session_state.suggestions and not st.session_state.processing:
    st.info("🤔 Ваш запрос требует уточнения. Выберите один из вариантов:")
    
    # Показываем сами варианты с кнопками
    for idx, suggestion in enumerate(st.session_state.suggestions):
        col1, col2 = st.columns([1, 9])
        with col1:
            if st.button(f"✅", key=f"suggestion_btn_{idx}", help="Выбрать этот вариант"):
                st.session_state.selected_suggestion = suggestion
                st.session_state.processing = True
                st.rerun()
        with col2:
            st.markdown(f"**{idx + 1}.** {suggestion}")
    
    st.divider()
    st.markdown("*Или введите свой уточненный запрос ниже*")

# Обработка выбранного варианта (вне кнопок, чтобы spinner работал корректно)
if st.session_state.processing and st.session_state.selected_suggestion:
    suggestion = st.session_state.selected_suggestion
    st.session_state.selected_suggestion = None
    
    logger.info(f"[SUGGESTION] Processing selected suggestion: {suggestion}")
    
    # Добавляем выбранный вариант в историю
    st.session_state.messages.append({
        "role": "user",
        "content": suggestion
    })
    logger.debug(f"[SUGGESTION] Added user message to history")
    
    # Выполняем анализ (варианты уже проверены, сразу execute)
    with st.spinner("⏳ Выполняю анализ выбранного варианта..."):
        execute_result = execute_query(suggestion)
    
    if execute_result:
        result_text = execute_result.get("result", "").strip()
        logger.info(f"[SUGGESTION] Execute result: {len(result_text)} chars")
        if result_text:
            st.session_state.messages.append({
                "role": "assistant",
                "content": result_text,
                "charts": execute_result.get("charts", [])
            })
            logger.debug(f"[SUGGESTION] Added assistant response to history")
        else:
            logger.warning("[SUGGESTION] Empty result text")
            st.session_state.messages.append({
                "role": "assistant",
                "content": "⚠️ Анализ выполнен, но результат пустой."
            })
    else:
        logger.error("[SUGGESTION] Execute failed")
        st.session_state.messages.append({
            "role": "assistant",
            "content": "❌ Произошла ошибка при выполнении анализа. Попробуйте еще раз."
        })
    
    st.session_state.suggestions = None
    st.session_state.processing = False
    logger.info("[SUGGESTION] Processing complete, rerunning...")
    st.rerun()

# Форма для ввода сообщения (только если не обрабатываем запрос)
if not st.session_state.processing:
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
            
            # Очищаем старые варианты
            st.session_state.suggestions = None
            
            # Добавляем сообщение пользователя в историю
            st.session_state.messages.append({
                "role": "user",
                "content": user_input.strip()
            })
            logger.debug(f"[FORM] Added user message, total: {len(st.session_state.messages)}")
            
            # Сохраняем запрос для обработки после rerun
            st.session_state.pending_query = user_input.strip()
            
            # Немедленно показываем сообщение пользователя
            st.rerun()


