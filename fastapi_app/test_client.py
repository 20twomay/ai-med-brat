"""Простой клиент для тестирования API."""

import time

import requests

BASE_URL = "http://localhost:8000"


def test_agent():
    """Тестирование работы агента с human-in-the-loop."""

    # 1. Отправляем запрос
    print("=" * 60)
    print("📤 Отправляем запрос агенту...")
    query = "Чем болеют в городе?"

    response = requests.post(f"{BASE_URL}/query", json={"query": query})

    if response.status_code != 200:
        print(f"❌ Ошибка: {response.json()}")
        return

    data = response.json()
    session_id = data["session_id"]
    print(f"✅ Сессия создана: {session_id}")
    print(f"📊 Статус: {data['status']}")
    print(f"💬 Ответ: {data['message']}")

    # 2. Проверяем, нужна ли обратная связь
    while data["needs_feedback"]:
        print("\n" + "=" * 60)
        print("🔔 Агент просит уточнение!")
        print(f"💬 {data['message']}")
        print()

        # Получаем ответ от пользователя
        user_input = input("Ваш ответ (или 'q' для выхода): ").strip()

        if user_input.lower() == "q":
            print("Выход...")
            return

        # Отправляем обратную связь
        print("\n📤 Отправляем ответ агенту...")
        feedback_response = requests.post(
            f"{BASE_URL}/feedback", json={"session_id": session_id, "feedback": user_input}
        )

        if feedback_response.status_code != 200:
            print(f"❌ Ошибка: {feedback_response.json()}")
            return

        data = feedback_response.json()
        print(f"📊 Статус: {data['status']}")

        # Если агент продолжает работать
        if data["status"] == "running":
            print("⏳ Агент обрабатывает запрос...")

            # Опрашиваем статус
            while data["status"] == "running":
                time.sleep(2)
                status_response = requests.get(f"{BASE_URL}/status/{session_id}")
                data = status_response.json()
                print(f"   ... итерация {data.get('iteration', 0)}")

    # 3. Финальный результат
    print("\n" + "=" * 60)
    print("✅ АГЕНТ ЗАВЕРШИЛ РАБОТУ")
    print(f"📊 Итерации: {data.get('iteration', 0)}")
    print("💬 Финальный ответ:")
    print("-" * 60)
    print(data["message"])
    print("=" * 60)


def test_health():
    """Проверка работоспособности API."""
    response = requests.get(f"{BASE_URL}/health")
    print(f"Health check: {response.json()}")


if __name__ == "__main__":
    print("🚀 Тестирование Medical Analytics Agent API\n")

    # Проверяем здоровье API
    try:
        test_health()
        print()
    except requests.exceptions.ConnectionError:
        print("❌ API не запущен! Запустите сервер: uvicorn main:app --reload")
        exit(1)

    # Запускаем тест
    test_agent()
