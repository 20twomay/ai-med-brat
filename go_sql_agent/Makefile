.PHONY: build run clean docker-up docker-down docker-clean test help

# Переменные
BINARY_NAME=go_sql_agent.exe
GO=go
DOCKER_COMPOSE=docker-compose

help: ## Показать справку
	@echo "Доступные команды:"
	@echo "  make build         - Собрать приложение"
	@echo "  make run          - Запустить приложение"
	@echo "  make clean        - Удалить бинарник и CSV файлы"
	@echo "  make docker-up-pg - Запустить PostgreSQL"
	@echo "  make docker-up-mysql - Запустить MySQL"
	@echo "  make docker-down  - Остановить все контейнеры"
	@echo "  make docker-clean - Остановить и удалить все данные"
	@echo "  make test-pg      - Протестировать подключение к PostgreSQL"
	@echo "  make test-mysql   - Протестировать подключение к MySQL"

build: ## Собрать приложение
	@echo "Сборка $(BINARY_NAME)..."
	$(GO) build -o $(BINARY_NAME) .\cmd\main.go
	@echo "✓ Сборка завершена"

run: build ## Запустить приложение
	@echo "Запуск $(BINARY_NAME)..."
	.\$(BINARY_NAME)

clean: ## Удалить бинарник и сгенерированные файлы
	@echo "Очистка..."
	@if exist $(BINARY_NAME) del $(BINARY_NAME)
	@if exist diagnoses.csv del diagnoses.csv
	@if exist patients.csv del patients.csv
	@if exist receips.csv del receips.csv
	@echo "✓ Очистка завершена"

docker-up-pg: ## Запустить PostgreSQL
	@echo "Запуск PostgreSQL..."
	$(DOCKER_COMPOSE) up -d postgres
	@echo "✓ PostgreSQL запущен на порту 5432"
	@echo "  Креды: meduser / medpass123"

docker-up-mysql: ## Запустить MySQL
	@echo "Запуск MySQL..."
	$(DOCKER_COMPOSE) up -d mysql
	@echo "✓ MySQL запущен на порту 3306"
	@echo "  Креды: meduser / medpass123"

docker-up: ## Запустить обе базы данных
	@echo "Запуск всех баз данных..."
	$(DOCKER_COMPOSE) up -d
	@echo "✓ Все базы данных запущены"

docker-down: ## Остановить все контейнеры
	@echo "Остановка контейнеров..."
	$(DOCKER_COMPOSE) down
	@echo "✓ Контейнеры остановлены"

docker-clean: ## Остановить и удалить все данные
	@echo "Удаление контейнеров и данных..."
	$(DOCKER_COMPOSE) down -v
	@echo "✓ Контейнеры и данные удалены"

test-pg: ## Протестировать подключение к PostgreSQL
	@echo "Тест PostgreSQL..."
	docker exec -it medical_db_postgres psql -U meduser -d medical_db -c "SELECT 'Диагнозов: ' || COUNT(*)::text FROM diagnoses; SELECT 'Пациентов: ' || COUNT(*)::text FROM patients; SELECT 'Рецептов: ' || COUNT(*)::text FROM prescriptions;"

test-mysql: ## Протестировать подключение к MySQL
	@echo "Тест MySQL..."
	docker exec -it medical_db_mysql mysql -u meduser -pmedpass123 medical_db -e "SELECT CONCAT('Диагнозов: ', COUNT(*)) FROM diagnoses; SELECT CONCAT('Пациентов: ', COUNT(*)) FROM patients; SELECT CONCAT('Рецептов: ', COUNT(*)) FROM prescriptions;"

setup-pg: docker-up-pg ## Полная настройка с PostgreSQL
	@echo "Создание конфига для PostgreSQL..."
	@copy .env.postgres .env
	@echo "✓ Готово! Укажите QWEN_API_KEY в .env и запустите 'make run'"

setup-mysql: docker-up-mysql ## Полная настройка с MySQL
	@echo "Создание конфига для MySQL..."
	@copy .env.mysql .env
	@echo "✓ Готово! Укажите QWEN_API_KEY в .env и запустите 'make run'"
