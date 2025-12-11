-- ========================================
-- Migration: 002_add_users_table
-- Direction: UP
-- Description: Добавление таблицы пользователей для аутентификации
-- Date: 2025-12-11
-- ========================================

BEGIN;

-- Таблица пользователей
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

-- Индекс для быстрого поиска по email
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Комментарии
COMMENT ON TABLE users IS 'Пользователи системы';
COMMENT ON COLUMN users.id IS 'Уникальный идентификатор пользователя';
COMMENT ON COLUMN users.email IS 'Email пользователя (логин)';
COMMENT ON COLUMN users.hashed_password IS 'Хешированный пароль (bcrypt)';
COMMENT ON COLUMN users.created_at IS 'Дата и время регистрации';
COMMENT ON COLUMN users.updated_at IS 'Дата и время последнего обновления';
COMMENT ON COLUMN users.is_active IS 'Флаг активности пользователя';

COMMIT;