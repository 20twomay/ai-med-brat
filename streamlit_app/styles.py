"""Централизованные стили для Streamlit приложения."""

from typing import Final

# ===== COLORS =====
PRIMARY_COLOR: Final[str] = "#16A8B1"
PRIMARY_COLOR_DARK: Final[str] = "#1497A0"
PRIMARY_COLOR_LIGHT: Final[str] = "#2EA9AC"
PRIMARY_COLOR_LIGHTER: Final[str] = "#26989B"

# ===== GRADIENT STYLES =====
PRIMARY_GRADIENT: Final[str] = "linear-gradient(135deg, #16A8B1 0%, #2EA9AC 100%)"
PRIMARY_GRADIENT_HOVER: Final[str] = "linear-gradient(135deg, #1497A0 0%, #26989B 100%)"

# ===== SIDEBAR STYLES =====
SIDEBAR_HIDE_STYLE: Final[str] = """
<style>
    [data-testid="stSidebar"] {
        display: none;
    }
    [data-testid="stSidebarNav"] {
        display: none;
    }
</style>
"""

SIDEBAR_BUTTON_STYLE: Final[str] = """
<style>
/* Кастомная кнопка "Новый чат" */
div[data-testid="stSidebar"] button[kind="primary"] {
    background: linear-gradient(135deg, #16A8B1 0%, #2EA9AC 100%) !important;
    color: white !important;
    border: none !important;
    font-weight: 600 !important;
    text-align: left !important;
    padding-left: 1rem !important;
}

div[data-testid="stSidebar"] button[kind="primary"]:hover {
    background: linear-gradient(135deg, #1497A0 0%, #26989B 100%) !important;
    box-shadow: 0 2px 8px rgba(22, 168, 177, 0.3) !important;
}

/* Выравнивание текста по левому краю для всех кнопок в сайдбаре */
div[data-testid="stSidebar"] .stButton button {
    text-align: left !important;
    justify-content: flex-start !important;
}

/* Стиль для кнопок чатов в сайдбаре */
[data-testid="stSidebar"] .stButton button {
    text-align: left !important;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
</style>
"""

# ===== CHAT FORM STYLES =====
CHAT_FORM_STYLE: Final[str] = """
<style>
/* Скрыть стандартный sidebar toggle */
[data-testid="collapsedControl"] {
    display: none;
}

/* Скрыть стандартную навигацию Streamlit */
[data-testid="stSidebarNav"] {
    display: none;
}

/* Форма ввода - обертка */
[data-testid="stForm"] {
    width: 100% !important;
    max-width: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
}

/* Главный контейнер формы - убираем все границы и фоны */
[data-testid="stForm"] > div:first-child {
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    padding: 0 !important;
    display: flex !important;
    align-items: center !important;
    gap: 8px !important;
    transition: none !important;
    box-shadow: none !important;
}

[data-testid="stForm"] > div:first-child:focus-within {
    background: transparent !important;
    box-shadow: none !important;
}

/* Колонки внутри формы */
[data-testid="stForm"] [data-testid="column"] {
    padding: 0 !important;
    margin: 0 !important;
}

/* Первая колонка - растягиваем на доступное место */
[data-testid="stForm"] [data-testid="column"]:first-child {
    flex: 1 !important;
    min-width: 0 !important;
}

/* Вторая колонка - фиксированная ширина под кнопку */
[data-testid="stForm"] [data-testid="column"]:last-child {
    flex: 0 0 auto !important;
    width: auto !important;
}

/* Убираем все врапперы и отступы у input */
[data-testid="stForm"] [data-testid="column"] > div {
    padding: 0 !important;
    margin: 0 !important;
}

/* Поле ввода текста */
[data-testid="stForm"] input[type="text"] {
    width: 100% !important;
    border: none !important;
    border-bottom: 2px solid #e0e0e0 !important;
    border-radius: 0 !important;
    background: transparent !important;
    padding: 12px 0 !important;
    font-size: 1rem !important;
    outline: none !important;
    box-shadow: none !important;
    transition: border-color 0.2s ease !important;
}

[data-testid="stForm"] input[type="text"]:focus {
    border-bottom: 2px solid #16A8B1 !important;
    box-shadow: none !important;
    outline: none !important;
}

/* Кнопка отправки - идеально круглая */
[data-testid="stForm"] button[kind="primary"],
[data-testid="stForm"] button[type="submit"] {
    background: linear-gradient(135deg, #16A8B1 0%, #2EA9AC 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 50% !important;
    width: 40px !important;
    height: 40px !important;
    min-width: 40px !important;
    min-height: 40px !important;
    max-width: 40px !important;
    max-height: 40px !important;
    padding: 0 !important;
    margin: 0 !important;
    font-size: 1.3rem !important;
    line-height: 1 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    transition: all 0.2s ease !important;
    cursor: pointer !important;
    flex-shrink: 0 !important;
}

[data-testid="stForm"] button[kind="primary"]:hover,
[data-testid="stForm"] button[type="submit"]:hover {
    background: linear-gradient(135deg, #1497A0 0%, #26989B 100%) !important;
    box-shadow: 0 2px 8px rgba(22, 168, 177, 0.3) !important;
    transform: scale(1.05) !important;
}
</style>
"""


def get_context_indicator_style(
    total_tokens: int,
    context_limit: int = 256000,
) -> tuple[str, str, str]:
    """
    Получить стили для индикатора контекста.
    
    Args:
        total_tokens: Текущее количество токенов
        context_limit: Лимит контекста
        
    Returns:
        Кортеж (цвет, статус, процент)
    """
    usage_percent = (total_tokens / context_limit) * 100 if context_limit > 0 else 0
    
    if usage_percent < 50:
        return "#4CAF50", "Отлично", usage_percent
    elif usage_percent < 75:
        return "#FF9800", "Нормально", usage_percent
    elif usage_percent < 90:
        return "#FF5722", "Заполняется", usage_percent
    else:
        return "#F44336", "Почти заполнен", usage_percent


def get_context_indicator_html(total_tokens: int, context_limit: int = 256000) -> str:
    """
    Генерирует HTML для индикатора контекста.
    
    Args:
        total_tokens: Текущее количество токенов
        context_limit: Лимит контекста
        
    Returns:
        HTML строка с индикатором контекста
    """
    color, status, usage_percent = get_context_indicator_style(total_tokens, context_limit)
    
    return f"""
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
    """


def get_logo_html(logo_base64: str | None, size: int = 240) -> str:
    """
    Генерирует HTML для отображения логотипа.
    
    Args:
        logo_base64: Base64-закодированное изображение логотипа
        size: Размер логотипа в пикселях
        
    Returns:
        HTML строка с логотипом
    """
    if logo_base64:
        return f"""
        <div style="text-align: center; padding: 1rem 0 1.5rem 0;">
            <img src="data:image/svg+xml;base64,{logo_base64}" 
                 style="width: {size}px; height: {size}px; margin-bottom: 0.5rem;" />
        </div>
        """
    else:
        return """
        <div style="text-align: center; padding: 1rem 0 1.5rem 0;">
            <h1 style="font-size: 6rem; margin: 0;">🏥</h1>
            <p style="margin: 0.5rem 0 0 0; color: #666; font-size: 1rem; font-weight: 500;">Медицинская аналитика</p>
        </div>
        """
