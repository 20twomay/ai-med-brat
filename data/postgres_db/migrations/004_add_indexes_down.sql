-- Rollback migration: Remove indexes
-- Description: Удаляет индексы, добавленные в миграции 004

DROP INDEX IF EXISTS idx_chats_user_active_updated;
DROP INDEX IF EXISTS idx_chats_user_id;
DROP INDEX IF EXISTS idx_chats_thread_id;
DROP INDEX IF EXISTS idx_users_is_active;
DROP INDEX IF EXISTS idx_users_email;