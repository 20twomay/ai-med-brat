import json
import re

import streamlit as st
from openai import OpenAI

# Настройка страницы
st.set_page_config(page_title="AI Чат", page_icon="🤖", layout="centered")

# Заголовок
st.title("🤖 AI Чат Ассистент")

# Инициализация клиента OpenAI
# Вы можете использовать OpenAI API или любой другой совместимый API
if "openai_api_key" not in st.session_state:
    st.session_state.openai_api_key = ""
if "api_provider" not in st.session_state:
    st.session_state.api_provider = "OpenAI"
if "custom_model" not in st.session_state:
    st.session_state.custom_model = ""

# Боковая панель для настроек
with st.sidebar:
    st.header("⚙️ Настройки")

    # Выбор провайдера API
    api_provider = st.selectbox(
        "API Провайдер",
        ["OpenAI", "OpenRouter"],
        index=0 if st.session_state.api_provider == "OpenAI" else 1,
        help="Выберите провайдера API",
    )
    st.session_state.api_provider = api_provider

    # Поле для API ключа с динамическим названием
    api_key_label = "OpenAI API Key" if api_provider == "OpenAI" else "OpenRouter API Key"
    api_key_help = (
        "Введите ваш OpenAI API ключ"
        if api_provider == "OpenAI"
        else "Введите ваш OpenRouter API ключ (получить на openrouter.ai)"
    )

    api_key = st.text_input(
        api_key_label,
        type="password",
        value=st.session_state.openai_api_key,
        help=api_key_help,
    )

    if api_key:
        st.session_state.openai_api_key = api_key

    # Выбор модели в зависимости от провайдера
    if api_provider == "OpenAI":
        model = st.selectbox(
            "Модель", ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"], index=1
        )
        st.session_state.custom_model = ""
    else:  # OpenRouter
        model_choice = st.radio(
            "Выбор модели", ["Популярные модели", "Своя модель"], horizontal=True
        )

        if model_choice == "Популярные модели":
            model = st.selectbox(
                "Модель",
                [
                    "anthropic/claude-3.5-sonnet",
                    "anthropic/claude-3-opus",
                    "anthropic/claude-3-haiku",
                    "google/gemini-pro-1.5",
                    "openai/gpt-4o",
                    "openai/gpt-4-turbo",
                    "meta-llama/llama-3.1-70b-instruct",
                    "mistralai/mistral-large",
                ],
                index=0,
            )
            st.session_state.custom_model = ""
        else:
            custom_model_input = st.text_input(
                "Название модели",
                value=st.session_state.custom_model,
                help="Введите полное название модели (например: anthropic/claude-3.5-sonnet)",
                placeholder="provider/model-name",
            )
            if custom_model_input:
                st.session_state.custom_model = custom_model_input
                model = custom_model_input
            else:
                model = "anthropic/claude-3.5-sonnet"  # По умолчанию

        st.caption("📖 Список всех моделей: [openrouter.ai/models](https://openrouter.ai/models)")

    temperature = st.slider(
        "Temperature",
        min_value=0.0,
        max_value=2.0,
        value=0.7,
        step=0.1,
        help="Контролирует случайность ответов",
    )

    max_tokens = st.slider(
        "Max Tokens",
        min_value=100,
        max_value=4000,
        value=1000,
        step=100,
        help="Максимальная длина ответа",
    )

    if st.button("🗑️ Очистить историю"):
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.caption("Создано с помощью Streamlit")


# Функция для создания одного графика из данных
def create_chart_from_data(chart_info):
    """Создает Plotly график из словаря с данными"""
    import plotly.graph_objects as go

    chart_type = chart_info.get("chart_type")
    chart_data = chart_info.get("data", {})
    layout = chart_info.get("layout", {})

    fig = None

    # Создаем график в зависимости от типа
    if chart_type == "bar":
        fig = go.Figure(
            data=[
                go.Bar(
                    x=chart_data.get("x", []),
                    y=chart_data.get("y", []),
                    name=chart_data.get("name", ""),
                    text=chart_data.get("text"),
                    textposition=chart_data.get("textposition", "auto"),
                )
            ]
        )

    elif chart_type == "line":
        fig = go.Figure(
            data=[
                go.Scatter(
                    x=chart_data.get("x", []),
                    y=chart_data.get("y", []),
                    mode=chart_data.get("mode", "lines+markers"),
                    name=chart_data.get("name", ""),
                    line=chart_data.get("line"),
                )
            ]
        )

    elif chart_type == "scatter":
        fig = go.Figure(
            data=[
                go.Scatter(
                    x=chart_data.get("x", []),
                    y=chart_data.get("y", []),
                    mode=chart_data.get("mode", "markers"),
                    name=chart_data.get("name", ""),
                    marker=chart_data.get("marker"),
                )
            ]
        )

    elif chart_type == "pie":
        fig = go.Figure(
            data=[
                go.Pie(
                    labels=chart_data.get("labels", []),
                    values=chart_data.get("values", []),
                    hole=chart_data.get("hole", 0),
                )
            ]
        )

    elif chart_type == "histogram":
        fig = go.Figure(
            data=[
                go.Histogram(
                    x=chart_data.get("x", []),
                    nbinsx=chart_data.get("nbins"),
                    name=chart_data.get("name", ""),
                )
            ]
        )

    elif chart_type == "box":
        fig = go.Figure(
            data=[
                go.Box(
                    y=chart_data.get("y", []),
                    name=chart_data.get("name", ""),
                    boxmean=chart_data.get("boxmean", True),
                )
            ]
        )

    elif chart_type == "heatmap":
        fig = go.Figure(
            data=[
                go.Heatmap(
                    z=chart_data.get("z", []),
                    x=chart_data.get("x"),
                    y=chart_data.get("y"),
                    colorscale=chart_data.get("colorscale", "Viridis"),
                )
            ]
        )

    # Применяем layout если есть
    if fig and layout:
        fig.update_layout(**layout)

    return fig


# Функция для извлечения и отображения графиков из JSON
def extract_and_render_plots(text):
    """Извлекает JSON блоки с данными для графиков и отображает их"""
    import plotly.express as px
    import plotly.graph_objects as go

    # Паттерн для поиска JSON блоков
    json_pattern = r"```json\n(.*?)```"
    json_blocks = re.findall(json_pattern, text, re.DOTALL)

    # Для скрытия JSON кода из отображаемого текста
    json_blocks_to_hide = []

    plots_rendered = []

    for json_str in json_blocks:
        try:
            data = json.loads(json_str)

            # Проверяем, что это дашборд с несколькими графиками
            if isinstance(data, dict) and "dashboard" in data:
                dashboard = data.get("dashboard", [])
                cols_count = data.get("columns", 2)

                # Создаем колонки для дашборда
                if dashboard:
                    st.markdown(f"### {data.get('title', 'Дашборд')}")
                    if data.get("description"):
                        st.markdown(data.get("description"))

                    # Разбиваем графики по рядам
                    for i in range(0, len(dashboard), cols_count):
                        cols = st.columns(cols_count)
                        for idx, chart_info in enumerate(dashboard[i : i + cols_count]):
                            with cols[idx]:
                                fig = create_chart_from_data(chart_info)
                                if fig:
                                    # Уникальный ключ для каждого графика
                                    chart_key = (
                                        f"dashboard_chart_{i}_{idx}_{hash(json_str) % 10000}"
                                    )
                                    st.plotly_chart(fig, width="stretch", key=chart_key)
                    plots_rendered.append(True)
                    json_blocks_to_hide.append(json_str)
                    continue

            # Проверяем, что это данные для одиночного графика
            if isinstance(data, dict) and "chart_type" in data:
                fig = create_chart_from_data(data)

                # Отображаем график
                if fig:
                    # Уникальный ключ для графика
                    chart_key = f"single_chart_{hash(json_str) % 10000}"
                    st.plotly_chart(fig, width="stretch", key=chart_key)
                    plots_rendered.append(True)
                    json_blocks_to_hide.append(json_str)

        except json.JSONDecodeError:
            continue
        except Exception as e:
            st.warning(f"Не удалось отобразить график: {str(e)}")

    return len(plots_rendered) > 0, json_blocks_to_hide


# Инициализация истории сообщений
if "messages" not in st.session_state:
    st.session_state.messages = []

# Отображение истории сообщений
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        # Скрываем JSON блоки графиков из текста
        display_content = message["content"]
        if message["role"] == "assistant":
            # Удаляем JSON блоки с графиками
            json_pattern = r"```json\n.*?```"
            temp_content = display_content
            json_blocks = re.findall(json_pattern, display_content, re.DOTALL)
            for json_block in json_blocks:
                try:
                    json_str = json_block.replace("```json\n", "").replace("```", "")
                    data = json.loads(json_str)
                    # Если это график или дашборд, удаляем
                    if isinstance(data, dict) and ("chart_type" in data or "dashboard" in data):
                        temp_content = temp_content.replace(json_block, "")
                except Exception:
                    pass
            display_content = temp_content.strip()

        if display_content:  # Отображаем только если есть текст
            st.markdown(display_content)

        # Отображение графиков если они есть
        if message["role"] == "assistant":
            extract_and_render_plots(message["content"])

# Поле ввода сообщения
if prompt := st.chat_input("Напишите ваше сообщение..."):
    # Проверка наличия API ключа
    if not st.session_state.openai_api_key:
        st.error("⚠️ Пожалуйста, введите OpenAI API ключ в боковой панели")
        st.stop()

    # Добавление сообщения пользователя в историю
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Отображение сообщения пользователя
    with st.chat_message("user"):
        st.markdown(prompt)

    # Получение ответа от AI
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""

        try:
            # Создание клиента с учетом провайдера
            if st.session_state.api_provider == "OpenRouter":
                client = OpenAI(
                    api_key=st.session_state.openai_api_key, base_url="https://openrouter.ai/api/v1"
                )
            else:
                client = OpenAI(api_key=st.session_state.openai_api_key)

            # Добавляем системный промпт для поддержки графиков
            system_message = {
                "role": "system",
                "content": """Ты полезный AI ассистент. Когда нужно показать данные визуально, 
создавай интерактивные графики, возвращая данные в JSON формате внутри блока ```json```.

Поддерживаемые типы графиков:
- bar: столбчатая диаграмма
- line: линейный график
- scatter: точечный график
- pie: круговая диаграмма
- histogram: гистограмма
- box: боксплот
- heatmap: тепловая карта

Пример столбчатой диаграммы:
```json
{
  "chart_type": "bar",
  "data": {
    "x": ["Январь", "Февраль", "Март"],
    "y": [100, 150, 120],
    "name": "Продажи"
  },
  "layout": {
    "title": "Продажи по месяцам",
    "xaxis": {"title": "Месяц"},
    "yaxis": {"title": "Количество"}
  }
}
```

Пример линейного графика:
```json
{
  "chart_type": "line",
  "data": {
    "x": [1, 2, 3, 4, 5],
    "y": [10, 15, 13, 17, 20],
    "mode": "lines+markers",
    "name": "Рост"
  },
  "layout": {
    "title": "График роста"
  }
}
```

Пример круговой диаграммы:
```json
{
  "chart_type": "pie",
  "data": {
    "labels": ["Категория A", "Категория B", "Категория C"],
    "values": [30, 45, 25]
  },
  "layout": {
    "title": "Распределение"
  }
}
```

Пример ДАШБОРДА с несколькими графиками:
```json
{
  "dashboard": [
    {
      "chart_type": "bar",
      "data": {
        "x": ["Январь", "Февраль", "Март"],
        "y": [100, 150, 120]
      },
      "layout": {
        "title": "Продажи"
      }
    },
    {
      "chart_type": "line",
      "data": {
        "x": [1, 2, 3, 4],
        "y": [10, 15, 13, 17]
      },
      "layout": {
        "title": "Рост"
      }
    },
    {
      "chart_type": "pie",
      "data": {
        "labels": ["A", "B", "C"],
        "values": [30, 45, 25]
      },
      "layout": {
        "title": "Распределение"
      }
    }
  ],
  "columns": 2,
  "title": "Общий дашборд",
  "description": "Анализ ключевых метрик"
}
```

Для дашборда используй поле "dashboard" со списком графиков, "columns" для количества колонок (по умолчанию 2), "title" и "description" для заголовка.
Всегда включай chart_type, data и layout. Графики автоматически отобразятся в интерфейсе.""",
            }

            # Формируем сообщения с системным промптом
            messages_with_system = [system_message] + [
                {"role": m["role"], "content": m["content"]} for m in st.session_state.messages
            ]

            # Получение ответа с потоковой передачей
            stream = client.chat.completions.create(
                model=model,
                messages=messages_with_system,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )

            # Отображение ответа по мере получения
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    full_response += chunk.choices[0].delta.content
                    # Скрываем JSON блоки при отображении (и завершенные, и незавершенные)
                    display_text = full_response

                    # Удаляем завершенные JSON блоки
                    json_pattern_complete = r"```json\n.*?```"
                    json_blocks_complete = re.findall(
                        json_pattern_complete, display_text, re.DOTALL
                    )
                    for json_block in json_blocks_complete:
                        try:
                            json_str = json_block.replace("```json\n", "").replace("```", "")
                            data = json.loads(json_str)
                            if isinstance(data, dict) and (
                                "chart_type" in data or "dashboard" in data
                            ):
                                display_text = display_text.replace(json_block, "")
                        except Exception:
                            pass

                    # Удаляем незавершенные JSON блоки (которые еще генерируются)
                    json_pattern_incomplete = r"```json\n(?:(?!```)[\s\S])*$"
                    if re.search(json_pattern_incomplete, display_text):
                        display_text = re.sub(json_pattern_incomplete, "", display_text)

                    if display_text.strip():
                        message_placeholder.markdown(display_text.strip() + "▆")
                    else:
                        message_placeholder.markdown("_Генерирую график..._")

            # Финальное отображение без JSON
            display_text = full_response
            json_pattern = r"```json\n.*?```"
            json_blocks = re.findall(json_pattern, display_text, re.DOTALL)
            for json_block in json_blocks:
                try:
                    json_str = json_block.replace("```json\n", "").replace("```", "")
                    data = json.loads(json_str)
                    if isinstance(data, dict) and ("chart_type" in data or "dashboard" in data):
                        display_text = display_text.replace(json_block, "")
                except Exception:
                    pass

            if display_text.strip():
                message_placeholder.markdown(display_text.strip())
            else:
                message_placeholder.empty()  # Убираем placeholder если только графики

            # Отображаем графики если они есть в ответе
            extract_and_render_plots(full_response)

        except Exception as e:
            st.error(f"❌ Ошибка: {str(e)}")
            full_response = f"Извините, произошла ошибка: {str(e)}"
            message_placeholder.markdown(full_response)

    # Добавление ответа ассистента в историю
    st.session_state.messages.append({"role": "assistant", "content": full_response})
