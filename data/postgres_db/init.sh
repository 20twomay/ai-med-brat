#!/bin/bash
set -e

echo "Initializing database..."

# Создание схемы
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/schema.sql

echo "Schema created successfully"

# Загрузка данных
if [ -f /docker-entrypoint-initdb.d/load_data.sql ]; then
    echo "Loading data..."
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/load_data.sql
    echo "Data loaded successfully"
else
    echo "No data file found, skipping data load"
fi

echo "Database initialization complete"
