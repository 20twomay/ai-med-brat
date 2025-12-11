#!/bin/sh
set -e

echo "========================================="
echo "Checking if data needs to be loaded..."
echo "========================================="

# Проверяем количество записей в таблице patients
PATIENT_COUNT=$(psql -h postgres -U ${POSTGRES_USER} -d ${POSTGRES_DB} -t -c "SELECT COUNT(*) FROM patients;" 2>/dev/null || echo "0")

# Убираем пробелы
PATIENT_COUNT=$(echo $PATIENT_COUNT | tr -d '[:space:]')

echo "Current patients count: $PATIENT_COUNT"

if [ "$PATIENT_COUNT" -eq "0" ]; then
    echo "========================================="
    echo "Database is empty. Loading data..."
    echo "========================================="
    
    psql -h postgres -U ${POSTGRES_USER} -d ${POSTGRES_DB} -f /load_data.sql
    
    echo ""
    echo "========================================="
    echo "Data loaded successfully!"
    echo "========================================="
else
    echo "========================================="
    echo "Database already contains data. Skipping load."
    echo "========================================="
fi

exit 0
