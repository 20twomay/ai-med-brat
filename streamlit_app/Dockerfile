FROM python:3.11-slim

WORKDIR /app

# Копируем requirements и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY . .

# Экспортируем порт
EXPOSE 8501

# Отключаем буферизацию для логов
ENV PYTHONUNBUFFERED=1

# Запускаем Streamlit с логированием
CMD ["streamlit", "run", "app.py", "--server.address", "0.0.0.0", "--server.port", "8501", "--logger.level", "debug"]