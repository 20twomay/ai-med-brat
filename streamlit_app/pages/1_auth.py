"""Страница авторизации и регистрации."""

import logging

import streamlit as st

from api_client import APIClient
from config import PAGE_CONFIGS
from constants import (
    MAX_PASSWORD_LENGTH_BYTES,
    MSG_EMPTY_FIELDS,
    MSG_LOGIN_ERROR,
    MSG_LOGIN_SUCCESS,
    MSG_PASSWORDS_MISMATCH,
    MSG_REGISTER_ERROR,
    MSG_REGISTER_SUCCESS,
    SESSION_AUTHENTICATED,
    SESSION_TOKEN,
    SESSION_USER_INFO,
)
from core import (
    check_token_from_localstorage,
    init_session_state,
    save_token_to_localstorage,
    validate_password_length,
)
from styles import SIDEBAR_HIDE_STYLE

logger = logging.getLogger(__name__)

# Настройка страницы
page_config = PAGE_CONFIGS["auth"]
st.set_page_config(
    page_title=page_config.title,
    page_icon=page_config.icon,
    layout=page_config.layout,
    initial_sidebar_state=page_config.initial_sidebar_state,
)

# Инициализация session state
init_session_state()

# Проверка токена из localStorage
check_token_from_localstorage()

# API клиент
api_client = APIClient()

# Скрываем sidebar и навигацию для неавторизованных пользователей
st.markdown(SIDEBAR_HIDE_STYLE, unsafe_allow_html=True)

# Проверка уже авторизованного пользователя
if st.session_state.get(SESSION_AUTHENTICATED, False):
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
                    st.error(MSG_EMPTY_FIELDS)
                else:
                    with st.spinner("Выполняю вход..."):
                        result = api_client.login(login_email, login_password)
                        
                        if result:
                            token = result.get("access_token")
                            user = result.get("user")
                            
                            st.session_state[SESSION_AUTHENTICATED] = True
                            st.session_state[SESSION_TOKEN] = token
                            st.session_state[SESSION_USER_INFO] = user
                            save_token_to_localstorage(token)
                            logger.info(f"User logged in: {user.get('email')}")
                            st.success(MSG_LOGIN_SUCCESS.format(email=user.get('email')))
                            st.switch_page("pages/2_chat.py")
                        else:
                            st.error(MSG_LOGIN_ERROR)
    
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
                max_chars=MAX_PASSWORD_LENGTH_BYTES,
            )
            
            register_password_confirm = st.text_input(
                "Подтвердите пароль:",
                type="password",
                placeholder="Введите пароль ещё раз",
                max_chars=MAX_PASSWORD_LENGTH_BYTES,
            )
            
            submit_register = st.form_submit_button("Зарегистрироваться", width='stretch')
            
            if submit_register:
                if not register_email or not register_password:
                    st.error(MSG_EMPTY_FIELDS)
                elif register_password != register_password_confirm:
                    st.error(MSG_PASSWORDS_MISMATCH)
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
                                    st.success(
                                        MSG_REGISTER_SUCCESS.format(email=user.get('email'))
                                    )
                                    
                                    # Автоматический вход
                                    st.session_state[SESSION_AUTHENTICATED] = True
                                    st.session_state[SESSION_TOKEN] = token
                                    st.session_state[SESSION_USER_INFO] = user
                                    save_token_to_localstorage(token)
                                    
                                    st.info("🔄 Перезагружаю страницу...")
                                    st.rerun()
                            else:
                                st.error(MSG_REGISTER_ERROR)

# st.markdown("---")

# # Проверка статуса API
# with st.expander("Проверить статус API"):
#     if st.button("Проверить соединение"):
#         health_data = api_client.get_health()
#         if health_data:
#             st.success("✅ FastAPI доступен")
            
#             col_a, col_b = st.columns(2)
#             with col_a:
#                 db_status = health_data.get("database", "unknown")
#                 if db_status == "connected":
#                     st.success("✅ PostgreSQL подключен")
#                 else:
#                     st.error("❌ PostgreSQL отключен")
            
#             with col_b:
#                 s3_status = health_data.get("s3", "unknown")
#                 if s3_status == "connected":
#                     st.success("✅ MinIO подключен")
#                 else:
#                     st.error("❌ MinIO отключен")
#         else:
#             st.error("❌ Не удалось подключиться к API")
