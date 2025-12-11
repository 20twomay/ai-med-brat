#!/bin/bash

# ========================================
# PostgreSQL Migration Script
# ========================================
# Скрипт для применения и отката миграций
# Использование:
#   ./migrate.sh up [number]      - Применить миграции
#   ./migrate.sh down [number]    - Откатить миграции
#   ./migrate.sh status           - Показать статус миграций
# ========================================

set -e

# Конфигурация
DB_NAME="${POSTGRES_DB:-medbrat}"
DB_USER="${POSTGRES_USER:-postgres}"
MIGRATIONS_DIR="/docker-entrypoint-initdb.d/migrations"
MIGRATION_TABLE="schema_migrations"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция для логирования
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Создание таблицы для отслеживания миграций
init_migration_table() {
    log_info "Initializing migration tracking table..."
    psql -U "$DB_USER" -d "$DB_NAME" <<EOF
CREATE TABLE IF NOT EXISTS $MIGRATION_TABLE (
    version VARCHAR(10) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
EOF
    log_success "Migration table initialized"
}

# Получить список примененных миграций
get_applied_migrations() {
    psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT version FROM $MIGRATION_TABLE ORDER BY version;" 2>/dev/null || echo ""
}

# Проверить, применена ли миграция
is_migration_applied() {
    local version=$1
    local applied=$(psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM $MIGRATION_TABLE WHERE version='$version';" 2>/dev/null || echo "0")
    [ "$applied" -gt 0 ]
}

# Применить миграцию UP
apply_migration_up() {
    local version=$1
    local migration_file=$(ls "$MIGRATIONS_DIR"/${version}_*_up.sql 2>/dev/null | head -n1)

    if [ -z "$migration_file" ]; then
        log_error "Migration file not found for version $version"
        return 1
    fi

    local migration_name=$(basename "$migration_file" | sed 's/_up\.sql$//' | sed "s/^${version}_//")

    if is_migration_applied "$version"; then
        log_warning "Migration $version ($migration_name) is already applied"
        return 0
    fi

    log_info "Applying migration $version: $migration_name"

    if psql -U "$DB_USER" -d "$DB_NAME" -f "$migration_file"; then
        psql -U "$DB_USER" -d "$DB_NAME" -c "INSERT INTO $MIGRATION_TABLE (version, name) VALUES ('$version', '$migration_name');"
        log_success "Migration $version applied successfully"
        return 0
    else
        log_error "Failed to apply migration $version"
        return 1
    fi
}

# Откатить миграцию DOWN
apply_migration_down() {
    local version=$1
    local migration_file=$(ls "$MIGRATIONS_DIR"/${version}_*_down.sql 2>/dev/null | head -n1)

    if [ -z "$migration_file" ]; then
        log_error "Migration file not found for version $version"
        return 1
    fi

    local migration_name=$(basename "$migration_file" | sed 's/_down\.sql$//' | sed "s/^${version}_//")

    if ! is_migration_applied "$version"; then
        log_warning "Migration $version ($migration_name) is not applied"
        return 0
    fi

    log_info "Rolling back migration $version: $migration_name"

    if psql -U "$DB_USER" -d "$DB_NAME" -f "$migration_file"; then
        psql -U "$DB_USER" -d "$DB_NAME" -c "DELETE FROM $MIGRATION_TABLE WHERE version='$version';"
        log_success "Migration $version rolled back successfully"
        return 0
    else
        log_error "Failed to rollback migration $version"
        return 1
    fi
}

# Показать статус миграций
show_status() {
    log_info "Migration Status:"
    echo ""

    # Получаем все файлы миграций
    local all_migrations=$(ls "$MIGRATIONS_DIR"/*_up.sql 2>/dev/null | sed 's/_up\.sql$//' | sed 's/.*\///' | sort)

    if [ -z "$all_migrations" ]; then
        log_warning "No migrations found"
        return
    fi

    printf "%-10s %-30s %-10s %-20s\n" "VERSION" "NAME" "STATUS" "APPLIED AT"
    printf "%-10s %-30s %-10s %-20s\n" "-------" "----" "------" "----------"

    for migration in $all_migrations; do
        local version=$(echo "$migration" | cut -d'_' -f1)
        local name=$(echo "$migration" | sed "s/^${version}_//")

        if is_migration_applied "$version"; then
            local applied_at=$(psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT applied_at FROM $MIGRATION_TABLE WHERE version='$version';" | xargs)
            printf "%-10s %-30s ${GREEN}%-10s${NC} %-20s\n" "$version" "$name" "APPLIED" "$applied_at"
        else
            printf "%-10s %-30s ${YELLOW}%-10s${NC} %-20s\n" "$version" "$name" "PENDING" "-"
        fi
    done
}

# Применить все миграции или конкретную
migrate_up() {
    local target_version=$1

    init_migration_table

    # Получаем все доступные миграции
    local all_migrations=$(ls "$MIGRATIONS_DIR"/*_up.sql 2>/dev/null | sed 's/_up\.sql$//' | sed 's/.*\///' | cut -d'_' -f1 | sort)

    if [ -z "$all_migrations" ]; then
        log_warning "No migrations found"
        return
    fi

    if [ -n "$target_version" ]; then
        # Применяем только указанную миграцию
        apply_migration_up "$target_version"
    else
        # Применяем все неприменённые миграции
        for version in $all_migrations; do
            apply_migration_up "$version" || true
        done
    fi
}

# Откатить последнюю миграцию или конкретную
migrate_down() {
    local target_version=$1

    init_migration_table

    if [ -n "$target_version" ]; then
        # Откатываем конкретную миграцию
        apply_migration_down "$target_version"
    else
        # Откатываем последнюю примененную миграцию
        local last_version=$(psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT version FROM $MIGRATION_TABLE ORDER BY version DESC LIMIT 1;" | xargs)

        if [ -z "$last_version" ]; then
            log_warning "No applied migrations to rollback"
            return
        fi

        apply_migration_down "$last_version"
    fi
}

# Главная функция
main() {
    local command=$1
    local version=$2

    case "$command" in
        up)
            migrate_up "$version"
            ;;
        down)
            migrate_down "$version"
            ;;
        status)
            init_migration_table
            show_status
            ;;
        *)
            echo "Usage: $0 {up|down|status} [version]"
            echo ""
            echo "Commands:"
            echo "  up [version]     - Apply all pending migrations or specific version"
            echo "  down [version]   - Rollback last migration or specific version"
            echo "  status           - Show migration status"
            exit 1
            ;;
    esac
}

main "$@"