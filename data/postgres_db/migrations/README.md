# Database Migrations

Этот каталог содержит SQL миграции для базы данных PostgreSQL.

## Структура миграций

Каждая миграция состоит из двух файлов:
- `XXX_name_up.sql` - применение миграции (UP)
- `XXX_name_down.sql` - откат миграции (DOWN)

где `XXX` - порядковый номер миграции (001, 002, и т.д.)

## Как применить миграции

### Вручную (через psql)

```bash
# Применить миграцию
docker compose exec postgres psql -U postgres -d medbrat -f /docker-entrypoint-initdb.d/migrations/001_initial_schema_up.sql

# Откатить миграцию
docker compose exec postgres psql -U postgres -d medbrat -f /docker-entrypoint-initdb.d/migrations/001_initial_schema_down.sql
```

### Автоматически (через скрипт)

```bash
# Применить все миграции
docker compose exec postgres bash /docker-entrypoint-initdb.d/migrate.sh up

# Применить конкретную миграцию
docker compose exec postgres bash /docker-entrypoint-initdb.d/migrate.sh up 001

# Откатить последнюю миграцию
docker compose exec postgres bash /docker-entrypoint-initdb.d/migrate.sh down

# Откатить конкретную миграцию
docker compose exec postgres bash /docker-entrypoint-initdb.d/migrate.sh down 002
```

## История миграций

| Номер | Название | Описание | Дата |
|-------|----------|----------|------|
| 001   | initial_schema | Начальная схема: patients, diagnoses, medication, recipes | 2025-12-11 |
| 002   | add_users_table | Таблица пользователей для аутентификации | 2025-12-11 |
| 003   | add_chats_table | Таблица чатов для хранения истории диалогов | 2025-12-11 |

## Правила создания миграций

1. **Именование**: `XXX_descriptive_name_up.sql` и `XXX_descriptive_name_down.sql`
2. **Идемпотентность**: используйте `IF EXISTS` / `IF NOT EXISTS`
3. **Транзакции**: оборачивайте в `BEGIN` / `COMMIT`
4. **Комментарии**: добавляйте описание в начале файла
5. **Откат**: всегда создавайте DOWN миграцию