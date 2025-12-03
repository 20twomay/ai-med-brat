# Тестовые базы данных в Docker

Этот каталог содержит SQL скрипты для инициализации тестовых баз данных PostgreSQL и MySQL с медицинскими данными.

## Структура базы данных

### Таблица `diagnoses` (Диагнозы МКБ-10)
- `code` - код МКБ-10 (PRIMARY KEY)
- `diagnosis` - название диагноза
- `disease_class` - класс заболевания

**15 записей**: от холеры (a00) до хронической почечной недостаточности (n18)

### Таблица `patients` (Пациенты)
- `id` - ID пациента (AUTO INCREMENT)
- `birth_date` - дата рождения
- `gender` - пол (м/ж)
- `district` - район проживания
- `region` - регион

**15 записей**: пациенты из разных районов Санкт-Петербурга и Москвы

### Таблица `prescriptions` (Рецепты)
- `id` - ID рецепта (AUTO INCREMENT)
- `prescription_date` - дата и время выписки рецепта
- `diagnosis_code` - код диагноза (FOREIGN KEY -> diagnoses.code)
- `drug_code` - код препарата
- `patient_id` - ID пациента (FOREIGN KEY -> patients.id)

**25 записей**: рецепты за период 2019-2024 годов

## Запуск через Docker Compose

### Запустить PostgreSQL

```bash
docker-compose up -d postgres
```

База будет доступна на `localhost:5432`

Проверка подключения:
```bash
docker exec -it medical_db_postgres psql -U meduser -d medical_db -c "SELECT COUNT(*) FROM patients;"
```

### Запустить MySQL

```bash
docker-compose up -d mysql
```

База будет доступна на `localhost:3306`

Проверка подключения:
```bash
docker exec -it medical_db_mysql mysql -u meduser -pmedpass123 medical_db -e "SELECT COUNT(*) FROM patients;"
```

### Запустить обе базы

```bash
docker-compose up -d
```

## Остановка и удаление

Остановить контейнеры:
```bash
docker-compose down
```

Остановить и удалить данные:
```bash
docker-compose down -v
```

## Подключение к базам

### PostgreSQL
- Host: `localhost`
- Port: `5432`
- User: `meduser`
- Password: `medpass123`
- Database: `medical_db`

### MySQL
- Host: `localhost`
- Port: `3306`
- User: `meduser`
- Password: `medpass123`
- Database: `medical_db`

## Примеры запросов

### Получить все диагнозы:
```sql
SELECT * FROM diagnoses ORDER BY code;
```

### Получить всех пациентов:
```sql
SELECT * FROM patients ORDER BY id;
```

### Получить рецепты с информацией о пациентах и диагнозах:
```sql
SELECT 
    p.prescription_date,
    d.diagnosis,
    p.drug_code,
    pat.birth_date,
    pat.gender,
    pat.district,
    pat.region
FROM prescriptions p
JOIN diagnoses d ON p.diagnosis_code = d.code
JOIN patients pat ON p.patient_id = pat.id
ORDER BY p.prescription_date DESC;
```

## Файлы

- `init-postgres.sql` - схема для PostgreSQL
- `init-mysql.sql` - схема для MySQL
- `seed-data.sql` - тестовые данные для PostgreSQL
- `seed-data-mysql.sql` - тестовые данные для MySQL

## Примечания

- Данные автоматически загружаются при первом запуске контейнера
- Скрипты выполняются в алфавитном порядке (01-init, 02-seed)
- Данные сохраняются в Docker volumes и не теряются при перезапуске контейнеров
- Для полной очистки используйте `docker-compose down -v`
