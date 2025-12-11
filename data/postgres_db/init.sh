#!/bin/bash

# ========================================
# PostgreSQL Initialization Script
# ========================================
# Этот скрипт запускается при первом запуске контейнера PostgreSQL
# Применяет все миграции из папки migrations/
# ========================================

set -e

echo "========================================="
echo "Starting PostgreSQL initialization..."
echo "========================================="

# Ждем, пока PostgreSQL полностью запустится
sleep 2

# Запускаем скрипт миграций
if [ -f /docker-entrypoint-initdb.d/migrate.sh ]; then
    echo "Applying migrations..."
    bash /docker-entrypoint-initdb.d/migrate.sh up

    echo ""
    echo "Migration status:"
    bash /docker-entrypoint-initdb.d/migrate.sh status
else
    echo "ERROR: migrate.sh not found!"
    exit 1
fi

echo ""
echo "========================================="
echo "PostgreSQL initialization completed!"
echo "========================================="