"""
Тестовый клиент для новой версии API (v2)
Демонстрирует работу с двумя независимыми эндпоинтами
"""

import requests
import json
import time


BASE_URL = "http://localhost:8000"


def test_clarify_needs_clarification():
    """Тест: запрос требует уточнения"""
    print("\n" + "="*80)
    print("ТЕСТ 1: Запрос требует уточнения")
    print("="*80)
    
    query = "Чем болеют в городе?"
    print(f"\nЗапрос: {query}")
    
    response = requests.post(
        f"{BASE_URL}/clarify",
        json={"query": query}
    )
    
    print(f"\nСтатус: {response.status_code}")
    data = response.json()
    print(f"\nОтвет:")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    
    assert data["need_feedback"] == True, "Должен требовать уточнения"
    assert data["suggestions"] is not None, "Должны быть варианты уточнения"
    assert len(data["suggestions"]) > 0, "Должен быть хотя бы один вариант"
    
    print("\n✅ Тест пройден: запрос требует уточнения")
    return data["suggestions"][0] if data["suggestions"] else None


def test_clarify_ready_to_execute():
    """Тест: запрос готов к выполнению"""
    print("\n" + "="*80)
    print("ТЕСТ 2: Запрос готов к выполнению")
    print("="*80)
    
    query = "Топ-5 заболеваний в Санкт-Петербурге за последний год"
    print(f"\nЗапрос: {query}")
    
    response = requests.post(
        f"{BASE_URL}/clarify",
        json={"query": query}
    )
    
    print(f"\nСтатус: {response.status_code}")
    data = response.json()
    print(f"\nОтвет:")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    
    assert data["need_feedback"] == False, "Не должен требовать уточнения"
    assert data["suggestions"] is None, "Не должно быть вариантов"
    
    print("\n✅ Тест пройден: запрос готов к выполнению")


def test_clarify_invalid_request():
    """Тест: невалидный запрос"""
    print("\n" + "="*80)
    print("ТЕСТ 3: Невалидный запрос")
    print("="*80)
    
    query = "Какая погода будет завтра?"
    print(f"\nЗапрос: {query}")
    
    response = requests.post(
        f"{BASE_URL}/clarify",
        json={"query": query}
    )
    
    print(f"\nСтатус: {response.status_code}")
    data = response.json()
    print(f"\nОтвет:")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    
    assert data["need_feedback"] == True, "Должен требовать feedback (показать ошибку)"
    assert "медицин" in data["message"].lower() or "данн" in data["message"].lower(), \
        "Должно быть пояснение о том, что запрос не относится к медданным"
    
    print("\n✅ Тест пройден: невалидный запрос корректно обработан")


def test_execute_simple_query():
    """Тест: выполнение простого запроса"""
    print("\n" + "="*80)
    print("ТЕСТ 4: Выполнение простого запроса")
    print("="*80)
    
    query = "Сколько всего пациентов в базе данных?"
    print(f"\nЗапрос: {query}")
    print("\nВыполняется... (это может занять 10-30 секунд)")
    
    start_time = time.time()
    
    response = requests.post(
        f"{BASE_URL}/execute",
        json={"query": query},
        timeout=60
    )
    
    elapsed = time.time() - start_time
    
    print(f"\nСтатус: {response.status_code}")
    data = response.json()
    
    print(f"\nРезультат ({elapsed:.2f} сек):")
    print("-" * 80)
    print(data["result"])
    print("-" * 80)
    
    if data["charts"]:
        print(f"\nГрафики: {data['charts']}")
    else:
        print("\nГрафики не построены")
    
    assert len(data["result"]) > 0, "Результат не должен быть пустым"
    
    print("\n✅ Тест пройден: запрос выполнен")


def test_execute_with_charts():
    """Тест: выполнение запроса с графиками"""
    print("\n" + "="*80)
    print("ТЕСТ 5: Выполнение запроса с графиками")
    print("="*80)
    
    query = "Топ-5 самых дорогих препаратов с визуализацией"
    print(f"\nЗапрос: {query}")
    print("\nВыполняется... (это может занять 20-40 секунд)")
    
    start_time = time.time()
    
    response = requests.post(
        f"{BASE_URL}/execute",
        json={"query": query},
        timeout=90
    )
    
    elapsed = time.time() - start_time
    
    print(f"\nСтатус: {response.status_code}")
    data = response.json()
    
    print(f"\nРезультат ({elapsed:.2f} сек):")
    print("-" * 80)
    print(data["result"])
    print("-" * 80)
    
    if data["charts"]:
        print(f"\nГрафики построены: {len(data['charts'])} шт.")
        for i, chart in enumerate(data['charts'], 1):
            print(f"  {i}. {chart}")
    else:
        print("\n⚠️  Графики не построены (возможно, агент не посчитал нужным)")
    
    assert len(data["result"]) > 0, "Результат не должен быть пустым"
    
    print("\n✅ Тест пройден: запрос выполнен")


def test_full_flow():
    """Тест: полный флоу с уточнением"""
    print("\n" + "="*80)
    print("ТЕСТ 6: Полный флоу (clarify → execute)")
    print("="*80)
    
    # Шаг 1: Отправляем неточный запрос
    vague_query = "Покажи статистику по заболеваниям"
    print(f"\nШаг 1: Отправляем неточный запрос")
    print(f"Запрос: {vague_query}")
    
    clarify_response = requests.post(
        f"{BASE_URL}/clarify",
        json={"query": vague_query}
    )
    
    clarify_data = clarify_response.json()
    print(f"\nОтвет /clarify:")
    print(json.dumps(clarify_data, indent=2, ensure_ascii=False))
    
    # Шаг 2: Берем один из вариантов уточнения
    if clarify_data["need_feedback"] and clarify_data["suggestions"]:
        clarified_query = clarify_data["suggestions"][0]
        print(f"\nШаг 2: Используем уточненный запрос")
        print(f"Запрос: {clarified_query}")
        
        # Шаг 3: Выполняем уточненный запрос
        print("\nШаг 3: Выполняем запрос...")
        
        execute_response = requests.post(
            f"{BASE_URL}/execute",
            json={"query": clarified_query},
            timeout=90
        )
        
        execute_data = execute_response.json()
        print(f"\nРезультат:")
        print("-" * 80)
        print(execute_data["result"][:500] + "..." if len(execute_data["result"]) > 500 else execute_data["result"])
        print("-" * 80)
        
        if execute_data["charts"]:
            print(f"\nГрафики: {len(execute_data['charts'])} шт.")
        
        print("\n✅ Тест пройден: полный флоу выполнен")
    else:
        print("\n⚠️  Запрос не требовал уточнения, пропускаем тест")


def test_health():
    """Тест: проверка health endpoint"""
    print("\n" + "="*80)
    print("ТЕСТ: Health Check")
    print("="*80)
    
    response = requests.get(f"{BASE_URL}/health")
    data = response.json()
    
    print(json.dumps(data, indent=2, ensure_ascii=False))
    
    assert response.status_code == 200
    assert data["status"] == "healthy"
    
    print("\n✅ Сервис работает")


def main():
    """Запускает все тесты"""
    print("\n" + "█"*80)
    print(" "*20 + "ТЕСТИРОВАНИЕ API v2")
    print("█"*80)
    
    try:
        # Проверка доступности API
        test_health()
        
        # Базовые тесты
        test_clarify_needs_clarification()
        test_clarify_ready_to_execute()
        test_clarify_invalid_request()
        
        # Тесты выполнения
        test_execute_simple_query()
        test_execute_with_charts()
        
        # Полный флоу
        test_full_flow()
        
        print("\n" + "█"*80)
        print(" "*25 + "✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
        print("█"*80 + "\n")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ ОШИБКА: Не удается подключиться к API")
        print("Убедитесь, что сервер запущен: python main_v2.py")
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
