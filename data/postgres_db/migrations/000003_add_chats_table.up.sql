-- ========================================
-- Migration: 003_add_chats_table
-- Direction: UP
-- Description: Добавление таблицы чатов для хранения истории диалогов
-- Date: 2025-12-11
-- ========================================

BEGIN;

-- Таблица чатов
CREATE TABLE IF NOT EXISTS chats (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    title VARCHAR(255) NOT NULL DEFAULT 'Новый чат',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_chats_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Индексы для оптимизации запросов
CREATE INDEX IF NOT EXISTS idx_chats_user_id ON chats(user_id);
CREATE INDEX IF NOT EXISTS idx_chats_updated_at ON chats(updated_at DESC);

-- Комментарии
COMMENT ON TABLE chats IS 'Чаты пользователей с медицинским агентом';
COMMENT ON COLUMN chats.id IS 'Уникальный идентификатор чата (используется как thread_id для LangGraph)';
COMMENT ON COLUMN chats.user_id IS 'ID пользователя, владельца чата';
COMMENT ON COLUMN chats.title IS 'Название чата';
COMMENT ON COLUMN chats.created_at IS 'Дата и время создания чата';
COMMENT ON COLUMN chats.updated_at IS 'Дата и время последнего сообщения в чате';
COMMENT ON COLUMN chats.is_active IS 'Флаг активности чата (для мягкого удаления)';

COMMIT;