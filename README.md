# Medical Analytics Agent v2.0 - Масштабируемая архитектура

## Что изменилось

Сервис полностью переписан с нуля для решения проблем с масштабируемостью и управлением сессиями.

### Проблемы старой версии:
- ❌ Сессии хранились в памяти (MemorySaver) - терялись при перезапуске
- ❌ Граф агента создавался глобально - невозможно горизонтальное масштабирование
- ❌ Все процессы в одном месте - нельзя масштабировать отдельные части
- ❌ Синхронное выполнение - FastAPI блокировался на время работы агента

### Решение в новой версии:
- ✅ Redis для хранения сессий - данные переживают перезапуск
- ✅ Разделение на воркеры - роутинг и обработка в разных очередях
- ✅ Асинхронные очереди - можно запускать несколько экземпляров воркеров
- ✅ WebSocket поддержка - real-time обновления для фронтенда

## Новая архитектура

```
┌─────────────────────────────────────────────────────────┐
│                     FastAPI Backend                      │
│  - Управление сессиями (Redis)                           │
│  - REST API эндпоинты                                    │
│  - WebSocket для real-time обновлений                    │
│  - Публикация задач в очередь                            │
└────────────┬────────────────────────────┬────────────────┘
             │                            │
             ▼                            ▼
┌────────────────────────┐   ┌───────────────────────────┐
│  Router Workers (x2)   │   │  Query Workers (x3)       │
│  - Валидация запроса   │   │  - SQL выполнение         │
│  - Уточнения           │   │  - Визуализация           │
│  - Легковесный         │   │  - Тяжёлые операции       │
└────────────────────────┘   └───────────────────────────┘
             │                            │
             └────────────┬───────────────┘
                          ▼
                  ┌──────────────┐
                  │  asyncio     │
                  │  Queue       │
                  │  (in-memory) │
                  └──────────────┘
                          │
                          ▼
                  ┌──────────────┐
                  │    Redis     │
                  │  (sessions)  │
                  └──────────────┘
```

## Структура проекта

```
fastapi_app/
├── core/                   # Ядро системы
│   ├── session_store.py   # Redis хранилище сессий
│   └── task_queue.py      # Очереди задач (asyncio)
│
├── workers/               # Воркеры для обработки
│   ├── router_worker.py  # Валидация и роутинг
│   └── query_worker.py   # Обработка SQL запросов
│
├── models/                # Pydantic модели
│   ├── session.py        # Модели сессий и статусов
│   └── requests.py       # API request/response модели
│
├── agent/                 # LangGraph агент (legacy)
│   ├── graph.py
│   ├── prompts.py
│   ├── state.py
│   └── tools.py
│
└── main.py               # FastAPI приложение
```

## Установка и запуск

### 1. Установите зависимости

```bash
cd fastapi_app
pip install -r requirements.txt
```

### 2. Настройте окружение

Скопируйте `.env.example` в `.env` и заполните:

```bash
cp .env.example .env
```

Необходимые переменные:
- `OPENROUTER_API_KEY` - API ключ OpenRouter
- `DATABASE_URL` - URL PostgreSQL базы данных
- `REDIS_URL` - URL Redis (по умолчанию `redis://localhost:6379`)

### 3. Запустите Redis и PostgreSQL

```bash
docker-compose up -d
```

Это запустит:
- Redis на порту 6379
- PostgreSQL на порту 5432

### 4. Запустите FastAPI приложение

```bash
python main.py
```

Или через uvicorn:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### POST /query
Создаёт новый запрос или продолжает существующую сессию.

**Request:**
```json
{
  "query": "Топ-5 заболеваний в СПб?",
  "session_id": "optional-session-id"
}
```

**Response:**
```json
{
  "session_id": "uuid",
  "status": "router_processing",
  "message": "Query submitted for processing",
  "needs_feedback": false,
  "iteration": 0,
  "charts": []
}
```

### POST /feedback
Отправляет feedback пользователя на уточняющий вопрос.

**Request:**
```json
{
  "session_id": "uuid",
  "feedback": "Да, покажи по всем районам СПб"
}
```

### GET /status/{session_id}
Получает текущий статус сессии.

**Response:**
```json
{
  "session_id": "uuid",
  "status": "completed",
  "message": "Вот топ-5 заболеваний...",
  "needs_feedback": false,
  "iteration": 3,
  "charts": ["/charts/plot_123.png"]
}
```

### WebSocket /ws/{session_id}
Real-time обновления статуса сессии.

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/session-id');
ws.onmessage = (event) => {
  const status = JSON.parse(event.data);
  console.log('Status update:', status);
};
```

### GET /health
Проверка здоровья сервиса.

**Response:**
```json
{
  "status": "healthy",
  "service": "Medical Analytics Agent v2",
  "router_queue_size": 0,
  "query_queue_size": 2
}
```

## Статусы сессий

- `created` - Сессия создана
- `router_processing` - Идёт валидация запроса
- `waiting_feedback` - Ожидание уточнения от пользователя
- `query_processing` - Выполнение SQL и визуализация
- `completed` - Запрос завершён
- `error` - Произошла ошибка

## Масштабирование

### Горизонтальное масштабирование

Можно запустить несколько экземпляров FastAPI:

```bash
# Терминал 1
uvicorn main:app --host 0.0.0.0 --port 8000

# Терминал 2
uvicorn main:app --host 0.0.0.0 --port 8001

# Терминал 3
uvicorn main:app --host 0.0.0.0 --port 8002
```

Используйте nginx как load balancer:

```nginx
upstream fastapi_backend {
    server localhost:8000;
    server localhost:8001;
    server localhost:8002;
}

server {
    listen 80;
    location / {
        proxy_pass http://fastapi_backend;
    }
}
```

### Настройка количества воркеров

В [main.py](fastapi_app/main.py:64-69):

```python
await task_queue.start_workers(
    router_handler=router_worker.process_task,
    query_handler=query_worker.process_task,
    num_router_workers=2,  # ← увеличьте для большей пропускной способности
    num_query_workers=3,   # ← увеличьте для параллельной обработки
)
```

## Миграция с v1 на v2

Старая версия использовала LangGraph с MemorySaver. Новая версия несовместима - сессии из v1 не будут работать в v2.

**Рекомендации:**
1. Завершите все активные сессии в v1
2. Сделайте backup базы данных
3. Запустите v2 на новом порту для тестирования
4. После проверки переключите фронтенд на v2

## Мониторинг и отладка

### Логи
Все логи пишутся в stdout с уровнем INFO:

```bash
# Смотрим логи
tail -f fastapi.log

# Фильтр по воркерам
tail -f fastapi.log | grep "RouterWorker"
tail -f fastapi.log | grep "QueryWorker"
```

### Проверка Redis
```bash
# Подключитесь к Redis
redis-cli

# Посмотрите все сессии
KEYS session:*

# Посмотрите конкретную сессию
GET session:uuid-here

# TTL сессии
TTL session:uuid-here
```

### Метрики
Endpoint `/health` показывает текущее состояние очередей.

## Известные ограничения

1. **In-memory очереди** - при перезапуске задачи в очереди теряются
   - Решение: перейти на Celery + RabbitMQ/Redis в будущем

2. **WebSocket не масштабируется** - active_connections хранятся локально
   - Решение: использовать Redis Pub/Sub для WebSocket

3. **Нет retry логики** - если воркер падает, задача теряется
   - Решение: добавить retry через декораторы

## Дальнейшее развитие

- [ ] Заменить asyncio.Queue на Celery или Temporal
- [ ] Добавить Redis Pub/Sub для WebSocket
- [ ] Реализовать retry логику для воркеров
- [ ] Добавить Prometheus метрики
- [ ] Реализовать rate limiting
- [ ] Добавить аутентификацию и авторизацию
- [ ] Создать admin панель для мониторинга очередей

## Вопросы?

Если что-то непонятно или нужна помощь - создайте issue в репозитории.