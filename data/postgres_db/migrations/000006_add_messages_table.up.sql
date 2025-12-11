-- ========================================
-- Migration: 006_add_messages_table
-- Direction: UP
-- Description: Добавление таблицы сообщений для хранения истории чатов
-- Date: 2025-12-11
-- ========================================

BEGIN;

-- Таблица сообщений
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id INTEGER NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    artifacts JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_messages_chat_id FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
);

-- Индексы для оптимизации запросов
CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_messages_chat_created ON messages(chat_id, created_at);

-- Комментарии
COMMENT ON TABLE messages IS 'Сообщения в чатах пользователей';
COMMENT ON COLUMN messages.id IS 'Уникальный идентификатор сообщения';
COMMENT ON COLUMN messages.chat_id IS 'ID чата, к которому относится сообщение';
COMMENT ON COLUMN messages.role IS 'Роль отправителя (user, assistant, system)';
COMMENT ON COLUMN messages.content IS 'Текст сообщения';
COMMENT ON COLUMN messages.artifacts IS 'JSON с артефактами (графики, таблицы)';
COMMENT ON COLUMN messages.created_at IS 'Дата и время создания сообщения';

COMMIT;
