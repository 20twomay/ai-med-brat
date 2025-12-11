-- Migration: Add indexes for performance optimization
-- Description: Добавляет дополнительные индексы для оптимизации производительности
-- Note: Базовые индексы для users и chats уже созданы в миграциях 002 и 003

-- Partial индекс на users.is_active для фильтрации активных пользователей
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active) WHERE is_active = true;

-- Составной индекс на chats (user_id, is_active, updated_at) для оптимизации списка чатов
CREATE INDEX IF NOT EXISTS idx_chats_user_active_updated
ON chats(user_id, is_active, updated_at DESC)
WHERE is_active = true;

-- Комментарии для документирования
COMMENT ON INDEX idx_users_is_active IS 'Partial index для фильтрации только активных пользователей';
COMMENT ON INDEX idx_chats_user_active_updated IS 'Composite index для оптимизации пагинации списка чатов пользователя';