"""
Тесты для проверки race conditions в LangGraph агенте

Этот файл содержит тесты для выявления гонок при параллельном выполнении
запросов к агенту. Проверяем:
1. Параллельные запросы с одним thread_id
2. Параллельные запросы с разными thread_id
3. Изоляцию состояния между разными сессиями
4. Корректность работы checkpoint
"""

import asyncio
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any

import pytest
from agent import build_agent_graph


# ==================== Fixtures ====================

@pytest.fixture(scope="module")
def agent_graph():
    """Создаёт граф агента для тестов"""
    compiled_graph, checkpointer = build_agent_graph()
    return compiled_graph, checkpointer


@pytest.fixture
def sample_queries():
    """Примеры запросов для тестирования"""
    return [
        "Сколько пациентов в базе данных?",
        "Какой средний возраст пациентов?",
        "Топ-5 самых частых диагнозов",
        "Распределение пациентов по полу",
        "Количество пациентов по районам",
    ]


# ==================== Helper Functions ====================

async def execute_single_query(graph, query: str, thread_id: str) -> Dict[str, Any]:
    """
    Выполняет один запрос к агенту
    
    Returns:
        dict: {
            'thread_id': str,
            'query': str,
            'result': str,
            'duration': float (seconds),
            'success': bool,
            'error': str or None
        }
    """
    start_time = time.time()
    config = {"configurable": {"thread_id": thread_id}}
    
    state = {
        "messages": [{"type": "human", "content": query}],
        "react_iter": 0,
        "react_max_iter": 10,
        "charts": [],
        "tables": [],
        "input_tokens": 0,
        "output_tokens": 0,
        "total_cost": 0.0,
    }
    
    try:
        result = None
        async for chunk in graph.astream(state, config, stream_mode="values"):
            result = chunk
        
        duration = time.time() - start_time
        last_message = result["messages"][-1]
        
        return {
            "thread_id": thread_id,
            "query": query,
            "result": last_message.content if hasattr(last_message, "content") else str(last_message),
            "duration": duration,
            "success": True,
            "error": None,
            "react_iter": result.get("react_iter", 0),
        }
    except Exception as e:
        duration = time.time() - start_time
        return {
            "thread_id": thread_id,
            "query": query,
            "result": None,
            "duration": duration,
            "success": False,
            "error": str(e),
        }


def execute_query_sync(graph, query: str, thread_id: str) -> Dict[str, Any]:
    """Синхронная обёртка для execute_single_query"""
    return asyncio.run(execute_single_query(graph, query, thread_id))


# ==================== Tests ====================

@pytest.mark.asyncio
async def test_sequential_execution(agent_graph, sample_queries):
    """
    Тест 1: Последовательное выполнение запросов
    
    Baseline тест - проверяем что агент работает корректно
    в простом последовательном режиме.
    """
    graph, checkpointer = agent_graph
    thread_id = str(uuid.uuid4())
    
    results = []
    for query in sample_queries[:3]:  # Берём первые 3 запроса
        result = await execute_single_query(graph, query, thread_id)
        results.append(result)
        
        assert result["success"], f"Query failed: {result['error']}"
        assert result["result"] is not None
        print(f"✓ Query: {query[:50]}... | Duration: {result['duration']:.2f}s")
    
    print(f"\n✅ Sequential test passed: {len(results)} queries executed")


@pytest.mark.asyncio
async def test_parallel_same_thread(agent_graph, sample_queries):
    """
    Тест 2: Параллельное выполнение с ОДНИМ thread_id
    
    КРИТИЧЕСКИЙ ТЕСТ для race conditions!
    
    Проверяем что происходит когда несколько запросов
    используют один и тот же thread_id одновременно.
    
    Ожидаемое поведение:
    - Checkpoint должен сериализовать доступ
    - Запросы должны выполняться последовательно
    - Все запросы должны завершиться успешно
    """
    graph, checkpointer = agent_graph
    thread_id = str(uuid.uuid4())
    
    print(f"\n🔥 Testing race condition with same thread_id: {thread_id}")
    
    # Запускаем 3 запроса параллельно с одним thread_id
    tasks = [
        execute_single_query(graph, query, thread_id)
        for query in sample_queries[:3]
    ]
    
    start_time = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    total_duration = time.time() - start_time
    
    # Анализ результатов
    successful = [r for r in results if not isinstance(r, Exception) and r["success"]]
    failed = [r for r in results if isinstance(r, Exception) or not r["success"]]
    
    print(f"\n📊 Results:")
    print(f"  Total time: {total_duration:.2f}s")
    print(f"  Successful: {len(successful)}")
    print(f"  Failed: {len(failed)}")
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"  ❌ Query {i+1}: EXCEPTION - {result}")
        elif result["success"]:
            print(f"  ✓ Query {i+1}: {result['duration']:.2f}s")
        else:
            print(f"  ❌ Query {i+1}: ERROR - {result['error']}")
    
    # Проверки
    assert len(failed) == 0, f"Some queries failed with same thread_id: {failed}"
    assert len(successful) == 3, "Not all queries succeeded"
    
    print(f"\n✅ Passed: All queries with same thread_id succeeded")


@pytest.mark.asyncio
async def test_parallel_different_threads(agent_graph, sample_queries):
    """
    Тест 3: Параллельное выполнение с РАЗНЫМИ thread_id
    
    Проверяем изоляцию состояния между разными сессиями.
    
    Ожидаемое поведение:
    - Все запросы должны выполняться параллельно
    - Состояние не должно смешиваться
    - Все запросы должны завершиться успешно
    """
    graph, checkpointer = agent_graph
    
    print(f"\n🔀 Testing parallel execution with different thread_ids")
    
    # Каждый запрос получает свой thread_id
    tasks = [
        execute_single_query(graph, query, str(uuid.uuid4()))
        for query in sample_queries[:3]
    ]
    
    start_time = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    total_duration = time.time() - start_time
    
    # Анализ
    successful = [r for r in results if not isinstance(r, Exception) and r["success"]]
    failed = [r for r in results if isinstance(r, Exception) or not r["success"]]
    
    print(f"\n📊 Results:")
    print(f"  Total time: {total_duration:.2f}s")
    print(f"  Successful: {len(successful)}")
    print(f"  Failed: {len(failed)}")
    
    # Проверяем что все thread_id уникальные
    thread_ids = [r["thread_id"] for r in successful]
    assert len(thread_ids) == len(set(thread_ids)), "Thread IDs are not unique!"
    
    for result in successful:
        print(f"  ✓ Thread {result['thread_id'][:8]}: {result['duration']:.2f}s")
    
    # Проверки
    assert len(failed) == 0, f"Some queries failed: {failed}"
    assert len(successful) == 3, "Not all queries succeeded"
    
    # Проверяем что выполнение было действительно параллельным
    # (общее время меньше суммы всех длительностей)
    sum_durations = sum(r["duration"] for r in successful)
    speedup = sum_durations / total_duration
    print(f"  Speedup: {speedup:.2f}x (parallel efficiency)")
    
    assert speedup > 1.5, f"Execution was not parallel enough (speedup: {speedup:.2f}x)"
    
    print(f"\n✅ Passed: Parallel execution with different threads works correctly")


@pytest.mark.asyncio
async def test_checkpoint_state_isolation(agent_graph):
    """
    Тест 4: Изоляция состояния checkpoint между thread_id
    
    Проверяем что состояние одного thread не влияет на другой.
    """
    graph, checkpointer = agent_graph
    
    thread_1 = str(uuid.uuid4())
    thread_2 = str(uuid.uuid4())
    
    print(f"\n🔒 Testing checkpoint state isolation")
    print(f"  Thread 1: {thread_1[:8]}")
    print(f"  Thread 2: {thread_2[:8]}")
    
    # Выполняем запрос в thread_1
    result_1 = await execute_single_query(
        graph, 
        "Сколько пациентов в базе?", 
        thread_1
    )
    assert result_1["success"]
    
    # Выполняем другой запрос в thread_2
    result_2 = await execute_single_query(
        graph,
        "Какой средний возраст пациентов?",
        thread_2
    )
    assert result_2["success"]
    
    # Проверяем что результаты разные (не смешались)
    assert result_1["result"] != result_2["result"], "Results are identical - state leaked!"
    
    # Выполняем ещё один запрос в thread_1
    # Он должен помнить контекст первого запроса
    result_3 = await execute_single_query(
        graph,
        "А сколько из них мужчин?",
        thread_1
    )
    assert result_3["success"]
    
    print(f"\n✅ Passed: Checkpoint state is properly isolated")


@pytest.mark.asyncio
async def test_stress_many_parallel_queries(agent_graph, sample_queries):
    """
    Тест 5: Стресс-тест с большим количеством параллельных запросов
    
    Запускаем 10+ параллельных запросов с разными thread_id.
    """
    graph, checkpointer = agent_graph
    
    num_queries = 10
    print(f"\n💥 Stress test: {num_queries} parallel queries")
    
    # Создаём задачи
    tasks = []
    for i in range(num_queries):
        query = sample_queries[i % len(sample_queries)]
        thread_id = str(uuid.uuid4())
        tasks.append(execute_single_query(graph, query, thread_id))
    
    start_time = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    total_duration = time.time() - start_time
    
    # Анализ
    successful = [r for r in results if not isinstance(r, Exception) and r["success"]]
    failed = [r for r in results if isinstance(r, Exception) or not r["success"]]
    
    print(f"\n📊 Stress test results:")
    print(f"  Total queries: {num_queries}")
    print(f"  Successful: {len(successful)}")
    print(f"  Failed: {len(failed)}")
    print(f"  Total time: {total_duration:.2f}s")
    print(f"  Avg time per query: {total_duration/num_queries:.2f}s")
    
    if failed:
        print(f"\n❌ Failed queries:")
        for r in failed[:5]:  # Показываем первые 5 ошибок
            if isinstance(r, Exception):
                print(f"  - Exception: {r}")
            else:
                print(f"  - Error: {r['error']}")
    
    # Допускаем небольшой процент ошибок под высокой нагрузкой
    success_rate = len(successful) / num_queries
    assert success_rate >= 0.8, f"Too many failures: {success_rate*100:.1f}% success rate"
    
    print(f"\n✅ Passed: {success_rate*100:.1f}% success rate under stress")


@pytest.mark.asyncio 
async def test_thread_pool_executor_race(agent_graph, sample_queries):
    """
    Тест 6: Race conditions через ThreadPoolExecutor
    
    Имитируем реальный FastAPI сценарий где запросы приходят
    от разных потоков.
    """
    graph, checkpointer = agent_graph
    
    print(f"\n🧵 Testing with ThreadPoolExecutor (real concurrency)")
    
    def run_query(query, thread_id):
        """Wrapper для ThreadPoolExecutor"""
        return execute_query_sync(graph, query, thread_id)
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for query in sample_queries[:5]:
            thread_id = str(uuid.uuid4())
            future = executor.submit(run_query, query, thread_id)
            futures.append(future)
        
        start_time = time.time()
        results = [f.result() for f in futures]
        total_duration = time.time() - start_time
    
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    
    print(f"\n📊 ThreadPool results:")
    print(f"  Total time: {total_duration:.2f}s")
    print(f"  Successful: {len(successful)}")
    print(f"  Failed: {len(failed)}")
    
    for result in results:
        status = "✓" if result["success"] else "❌"
        print(f"  {status} {result['query'][:40]}: {result['duration']:.2f}s")
    
    assert len(failed) == 0, f"Queries failed with ThreadPoolExecutor: {failed}"
    print(f"\n✅ Passed: ThreadPoolExecutor concurrency works correctly")


# ==================== Main Runner ====================

if __name__ == "__main__":
    """
    Для быстрого запуска без pytest:
    
    python test_agent_race_conditions.py
    """
    print("=" * 60)
    print("🏁 Agent Race Condition Tests")
    print("=" * 60)
    
    # Создаём граф
    print("\n📦 Building agent graph...")
    compiled_graph, checkpointer = build_agent_graph()
    agent_graph_fixture = (compiled_graph, checkpointer)
    
    sample_queries_fixture = [
        "Сколько пациентов в базе данных?",
        "Какой средний возраст пациентов?",
        "Топ-5 самых частых диагнозов",
        "Распределение пациентов по полу",
        "Количество пациентов по районам",
    ]
    
    # Запускаем тесты
    async def run_all_tests():
        print("\n" + "=" * 60)
        print("Test 1: Sequential Execution")
        print("=" * 60)
        await test_sequential_execution(agent_graph_fixture, sample_queries_fixture)
        
        print("\n" + "=" * 60)
        print("Test 2: Parallel - Same Thread ID (RACE CONDITION)")
        print("=" * 60)
        await test_parallel_same_thread(agent_graph_fixture, sample_queries_fixture)
        
        print("\n" + "=" * 60)
        print("Test 3: Parallel - Different Thread IDs")
        print("=" * 60)
        await test_parallel_different_threads(agent_graph_fixture, sample_queries_fixture)
        
        print("\n" + "=" * 60)
        print("Test 4: Checkpoint State Isolation")
        print("=" * 60)
        await test_checkpoint_state_isolation(agent_graph_fixture)
        
        print("\n" + "=" * 60)
        print("Test 5: Stress Test (10 queries)")
        print("=" * 60)
        await test_stress_many_parallel_queries(agent_graph_fixture, sample_queries_fixture)
        
        print("\n" + "=" * 60)
        print("Test 6: ThreadPoolExecutor Race")
        print("=" * 60)
        await test_thread_pool_executor_race(agent_graph_fixture, sample_queries_fixture)
        
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS COMPLETED")
        print("=" * 60)
    
    asyncio.run(run_all_tests())
