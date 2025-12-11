"""Общие компоненты для Streamlit приложения."""

import base64
from pathlib import Path

import streamlit as st

from utils import logout as utils_logout


def get_logo_base64():
    """Загружает логотип и конвертирует в base64."""
    logo_path = Path(__file__).parent / "src" / "logo.svg"
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None


def render_logo():
    """Отображает логотип приложения."""
    logo_base64 = get_logo_base64()

    if logo_base64:
        st.markdown(
            f"""
            <div style="text-align: center; padding: 1.5rem 0 2rem 0;">
                <img src="data:image/svg+xml;base64,{logo_base64}" style="width: 180px; height: 180px; margin-bottom: 1rem;" />
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        # Fallback на эмодзи если логотип не найден
        st.markdown(
            """
            <div style="text-align: center; padding: 1.5rem 0 2rem 0;">
                <h1 style="font-size: 5rem; margin: 0;">🏥</h1>
                <p style="margin: 0.5rem 0 0 0; color: #666; font-size: 1rem; font-weight: 500;">Медицинская аналитика</p>
            </div>
            """,
            unsafe_allow_html=True
        )


def render_chat_list(api_client, current_chat_id=None):
    """
    Отображает список чатов пользователя.

    Args:
        api_client: API клиент
        current_chat_id: ID текущего открытого чата
    """
    # Кнопка создания нового чата
    if st.button("Новый чат", use_container_width=True, type="primary"):
        result = api_client.create_chat()
        if result:
            st.session_state.chat_id = result.get("id")
            st.session_state.messages = []
            st.rerun()
        else:
            st.error("Не удалось создать чат")

    st.markdown("")  # Пробел

    st.markdown("### Ваши чаты")

    # Загрузка списка чатов
    chats_data = api_client.get_chats()
    if chats_data and "chats" in chats_data:
        chats = chats_data["chats"]
        
        if not chats:
            st.info("У вас пока нет чатов. Создайте новый!")
        else:
            for chat in chats:
                chat_id = chat["id"]
                title = chat["title"]
                created_at = chat.get("created_at", "")
                
                # Подсветка активного чата
                is_active = chat_id == current_chat_id
                
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    if st.button(
                        title,
                        key=f"chat_{chat_id}",
                        use_container_width=True,
                        type="primary" if is_active else "secondary"
                    ):
                        st.session_state.chat_id = chat_id
                        st.session_state.messages = []  # Очистим, будем загружать из истории
                        st.rerun()
                
                with col2:
                    if st.button("🗑️", key=f"delete_{chat_id}", help="Удалить чат"):
                        if api_client.delete_chat(chat_id):
                            if chat_id == current_chat_id:
                                st.session_state.chat_id = None
                                st.session_state.messages = []
                            st.rerun()
    else:
        st.warning("Не удалось загрузить список чатов")


def render_user_profile_button(api_client):
    """
    Отображает кнопку профиля пользователя с модальным окном настроек.
    
    Args:
        api_client: API клиент
    """
    user_info = st.session_state.get("user_info")
    
    if user_info:
        email = user_info.get("email", "Пользователь")
        
        # Кнопка профиля - переключает состояние
        if st.button(f"👤 {email}", use_container_width=True, type="secondary", key="profile_btn"):
            st.session_state.show_profile_modal = not st.session_state.get("show_profile_modal", False)
            st.rerun()
        
        # Модальное окно с профилем (только отображение, без кнопок)
        if st.session_state.get("show_profile_modal", False):
            with st.expander("⚙️ Настройки профиля", expanded=True):
                st.markdown("### 👤 Информация о пользователе")
                st.text_input("Email", value=email, disabled=True, key="profile_email")
                st.text_input("ID", value=str(user_info.get("id", "")), disabled=True, key="profile_id")
                
                created_at = user_info.get("created_at", "")
                if created_at:
                    st.text_input("Дата регистрации", value=created_at[:10], disabled=True, key="profile_date")
                
                st.markdown("---")
                st.markdown("### 🔒 Безопасность")
                st.info("Смена пароля будет доступна в следующей версии")
                st.caption("💡 Нажмите кнопку профиля снова, чтобы закрыть")


def render_context_indicator(total_tokens: int, context_limit: int = 256000):
    """
    Отображает индикатор использования контекста над чатом.
    
    Args:
        total_tokens: Текущее количество токенов
        context_limit: Лимит контекста
    """
    usage_percent = (total_tokens / context_limit) * 100 if context_limit > 0 else 0
    
    # Определяем цвет в зависимости от заполненности
    if usage_percent < 50:
        color = "#4CAF50"  # Зеленый
        status = "🟢 Отлично"
    elif usage_percent < 75:
        color = "#FF9800"  # Оранжевый
        status = "🟡 Нормально"
    elif usage_percent < 90:
        color = "#FF5722"  # Красно-оранжевый
        status = "🟠 Заполняется"
    else:
        color = "#F44336"  # Красный
        status = "🔴 Почти заполнен"
    
    st.markdown(
        f"""
        <div style="background: linear-gradient(90deg, {color} 0%, {color}44 100%); 
                    padding: 1rem; border-radius: 10px; margin-bottom: 1rem;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <div style="font-weight: bold; font-size: 1.1rem;">{status}</div>
                    <div style="font-size: 0.9rem; opacity: 0.9;">Контекст: {total_tokens:,} / {context_limit:,} токенов</div>
                </div>
                <div style="font-size: 2rem; font-weight: bold;">{usage_percent:.1f}%</div>
            </div>
            <div style="background: rgba(255,255,255,0.3); height: 8px; border-radius: 4px; margin-top: 0.5rem; overflow: hidden;">
                <div style="background: white; height: 100%; width: {min(usage_percent, 100)}%; transition: width 0.3s;"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_logout_button():
    """Отображает кнопку выхода."""
    if st.button("🚪 Выйти из системы", use_container_width=True, type="secondary"):
        utils_logout()
        st.switch_page("pages/1_auth.py")
