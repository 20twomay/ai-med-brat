"""Общие компоненты для Streamlit приложения."""

import base64
from pathlib import Path
from typing import Optional

import streamlit as st

from api_client import APIClient
from config import app_config
from constants import (
    DEFAULT_CHAT_TITLE,
    LOGO_HEIGHT_PX,
    LOGO_WIDTH_PX,
    MSG_CHAT_CREATE_ERROR,
    MSG_CHATS_LOAD_ERROR,
    MSG_NO_CHATS_YET,
    SESSION_CHAT_ID,
    SESSION_MESSAGES,
    SESSION_MESSAGES_LOADED,
    SESSION_SHOW_PROFILE_MODAL,
    SESSION_TOTAL_TOKENS,
    SESSION_USER_INFO,
)
from core.auth import logout
from styles import (
    SIDEBAR_BUTTON_STYLE,
    get_context_indicator_html,
    get_logo_html,
)


def get_logo_base64() -> Optional[str]:
    """
    Загружает логотип и конвертирует в base64.
    
    Returns:
        Base64-закодированное изображение или None если файл не найден
    """
    logo_path = Path(__file__).parent / "src" / "logo.svg"
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None


def render_logo() -> None:
    """Отображает логотип приложения."""
    logo_base64 = get_logo_base64()
    html = get_logo_html(logo_base64, size=LOGO_WIDTH_PX)
    st.markdown(html, unsafe_allow_html=True)


def render_chat_list(
    api_client: APIClient,
    current_chat_id: Optional[int] = None,
) -> None:
    """
    Отображает список чатов пользователя.

    Args:
        api_client: API клиент
        current_chat_id: ID текущего открытого чата
    """
    # Стили для кастомной кнопки "Новый чат"
    st.markdown(SIDEBAR_BUTTON_STYLE, unsafe_allow_html=True)

    # Кнопка создания нового чата
    if st.button(
        f"+ {DEFAULT_CHAT_TITLE}",
        use_container_width=True,
        type="primary",
        key="new_chat_btn",
    ):
        result = api_client.create_chat()
        if result:
            st.session_state[SESSION_CHAT_ID] = result.get("id")
            st.session_state[SESSION_MESSAGES] = []
            st.session_state[SESSION_TOTAL_TOKENS] = result.get("total_tokens", 0)
            st.session_state[SESSION_MESSAGES_LOADED] = True  # Новый чат, история пустая
            st.rerun()
        else:
            st.error(MSG_CHAT_CREATE_ERROR)

    st.markdown("")  # Пробел

    st.markdown("#### Ваши чаты")

    # Загрузка списка чатов
    chats_data = api_client.get_chats()
    if chats_data and "chats" in chats_data:
        chats = chats_data["chats"]
        
        if not chats:
            st.info(MSG_NO_CHATS_YET)
        else:
            for chat in chats:
                chat_id = chat["id"]
                title = chat["title"]
                
                # Подсветка активного чата
                is_active = chat_id == current_chat_id
                
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    if st.button(
                        title,
                        key=f"chat_{chat_id}",
                        use_container_width=True,
                        type="primary" if is_active else "secondary",
                    ):
                        # При смене чата очищаем состояние и загружаем историю
                        st.session_state[SESSION_CHAT_ID] = chat_id
                        st.session_state[SESSION_MESSAGES] = []
                        st.session_state[SESSION_TOTAL_TOKENS] = chat.get("total_tokens", 0)
                        st.session_state[SESSION_MESSAGES_LOADED] = False
                        st.rerun()
                
                with col2:
                    if st.button("⨯", key=f"delete_{chat_id}", help="Удалить чат"):
                        if api_client.delete_chat(chat_id):
                            if chat_id == current_chat_id:
                                st.session_state[SESSION_CHAT_ID] = None
                                st.session_state[SESSION_MESSAGES] = []
                            st.rerun()
    else:
        st.warning(MSG_CHATS_LOAD_ERROR)


def render_user_profile_button(api_client: APIClient) -> None:
    """
    Отображает кнопку профиля пользователя с модальным окном настроек.
    
    Args:
        api_client: API клиент
    """
    user_info = st.session_state.get(SESSION_USER_INFO)
    
    if user_info:
        email = user_info.get("email", "Пользователь")
        
        # Кнопка профиля - переключает состояние
        if st.button(
            email,
            use_container_width=True,
            type="secondary",
            key="profile_btn",
        ):
            st.session_state[SESSION_SHOW_PROFILE_MODAL] = not st.session_state.get(
                SESSION_SHOW_PROFILE_MODAL,
                False,
            )
            st.rerun()
        
        # Модальное окно с профилем (только отображение, без кнопок)
        if st.session_state.get(SESSION_SHOW_PROFILE_MODAL, False):
            with st.expander("Настройки профиля", expanded=True):
                st.markdown("### Информация о пользователе")
                st.text_input(
                    "Email",
                    value=email,
                    disabled=True,
                    key="profile_email",
                )
                st.text_input(
                    "ID",
                    value=str(user_info.get("id", "")),
                    disabled=True,
                    key="profile_id",
                )
                
                created_at = user_info.get("created_at", "")
                if created_at:
                    st.text_input(
                        "Дата регистрации",
                        value=created_at[:10],
                        disabled=True,
                        key="profile_date",
                    )
                
                st.markdown("---")
                st.markdown("### Безопасность")
                st.info("Смена пароля будет доступна в следующей версии")
                st.caption("💡 Нажмите кнопку профиля снова, чтобы закрыть")


def render_context_indicator(
    total_tokens: int,
    context_limit: int = app_config.context_limit,
) -> None:
    """
    Отображает индикатор использования контекста над чатом.
    
    Args:
        total_tokens: Текущее количество токенов
        context_limit: Лимит контекста
    """
    html = get_context_indicator_html(total_tokens, context_limit)
    st.markdown(html, unsafe_allow_html=True)


def render_logout_button() -> None:
    """Отображает кнопку выхода."""
    if st.button("Выйти из системы", use_container_width=True, type="secondary"):
        logout()
        st.switch_page("pages/1_auth.py")
