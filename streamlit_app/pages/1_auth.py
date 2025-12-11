"""Страница авторизации и регистрации."""

import logging

import streamlit as st

from api_client import APIClient
from utils import init_session_state, validate_password_length, save_token_to_cookies, check_token_from_cookies

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Авторизация - MEDBRAT.AI",
    page_icon="🔐",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Инициализация session state
init_session_state()

# Проверка токена из cookies
check_token_from_cookies()

# API клиент
api_client = APIClient()


# Скрываем sidebar и навигацию для неавторизованных пользователей
st.markdown(
    """
    <style>
        [data-testid="stSidebar"] {
            display: none;
        }
        [data-testid="stSidebarNav"] {
            display: none;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# Проверка уже авторизованного пользователя
if st.session_state.get("authenticated", False):
    st.switch_page("pages/2_chat.py")


# Логотип
col_logo1, col_logo2, col_logo3 = st.columns([1, 2, 1])
with col_logo2:
    st.image("src/logo.svg", width='stretch')
    st.markdown("### Добро пожаловать!")

col1, col2, col3 = st.columns([1, 2, 1])

with col2:    
    # Переключатель между входом и регистрацией
    tab1, tab2 = st.tabs(["Вход", "Регистрация"])
    
    with tab1:
        st.markdown("#### Вход в систему")
        
        with st.form(key="login_form"):
            login_email = st.text_input(
                "Email:",
                placeholder="your@email.com",
            )
            
            login_password = st.text_input(
                "Пароль:",
                type="password",
                placeholder="Введите пароль",
                max_chars=72,
            )
            
            submit_login = st.form_submit_button("Войти", width='stretch')
            
            if submit_login:
                if not login_email or not login_password:
                    st.error("❌ Заполните все поля")
                else:
                    with st.spinner("Выполняю вход..."):
                        result = api_client.login(login_email, login_password)
                        
                        if result:
                            token = result.get("access_token")
                            user = result.get("user")
                            
                            st.session_state.authenticated = True
                            st.session_state.token = token
                            st.session_state.user_info = user
                            save_token_to_cookies(token)  # Сохраняем токен в cookies
                            logger.info(f"User logged in: {user.get('email')}")
                            st.success(f"✅ Добро пожаловать, {user.get('email')}!")
                            st.switch_page("pages/2_chat.py")
                        else:
                            st.error("❌ Неверный email или пароль")
    
    with tab2:
        st.markdown("#### Создать новый аккаунт")
        st.info("💡 После регистрации вы автоматически войдёте в систему")
        
        with st.form(key="register_form"):
            register_email = st.text_input(
                "Email:",
                placeholder="your@email.com",
            )
            
            register_password = st.text_input(
                "Пароль:",
                type="password",
                placeholder="Минимум 6 символов, хотя бы одна заглавная буква",
                max_chars=72,
            )
            
            register_password_confirm = st.text_input(
                "Подтвердите пароль:",
                type="password",
                placeholder="Введите пароль ещё раз",
                max_chars=72,
            )
            
            submit_register = st.form_submit_button("Зарегистрироваться", width='stretch')
            
            if submit_register:
                if not register_email or not register_password:
                    st.error("❌ Заполните все поля")
                elif register_password != register_password_confirm:
                    st.error("❌ Пароли не совпадают")
                else:
                    # Валидация пароля
                    password_error = validate_password_length(register_password)
                    if password_error:
                        st.error(f"❌ {password_error}")
                    else:
                        with st.spinner("Создаю аккаунт..."):
                            result = api_client.register(register_email, register_password)
                            
                            if result:
                                token = result.get("access_token")
                                user = result.get("user")
                                
                                if not token or not user:
                                    st.error("❌ Ошибка: неверный формат ответа от сервера")
                                    logger.error(f"Invalid response format: {result}")
                                else:
                                    st.success(f"✅ Аккаунт создан! Добро пожаловать, {user.get('email')}!")
                                    
                                    # Автоматический вход
                                    st.session_state.authenticated = True
                                    st.session_state.token = token
                                    st.session_state.user_info = user
                                    save_token_to_cookies(token)  # Сохраняем токен в cookies
                                    
                                    st.info("🔄 Перезагружаю страницу...")
                                    st.rerun()
                            else:
                                st.error("❌ Ошибка регистрации. Возможно, email уже используется")

st.markdown("---")

# Проверка статуса API
with st.expander("🔌 Проверить статус API"):
    if st.button("Проверить соединение"):
        health_data = api_client.get_health()
        if health_data:
            st.success("✅ FastAPI доступен")
            
            col_a, col_b = st.columns(2)
            with col_a:
                db_status = health_data.get("database", "unknown")
                if db_status == "connected":
                    st.success("✅ PostgreSQL подключен")
                else:
                    st.error("❌ PostgreSQL отключен")
            
            with col_b:
                s3_status = health_data.get("s3", "unknown")
                if s3_status == "connected":
                    st.success("✅ MinIO подключен")
                else:
                    st.error("❌ MinIO отключен")
        else:
            st.error("❌ Не удалось подключиться к API")
