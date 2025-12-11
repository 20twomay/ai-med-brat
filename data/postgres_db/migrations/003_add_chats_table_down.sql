-- ========================================
-- Migration: 003_add_chats_table
-- Direction: DOWN
-- Description: Откат таблицы чатов
-- Date: 2025-12-11
-- ========================================

BEGIN;

DROP INDEX IF EXISTS idx_chats_updated_at;
DROP INDEX IF EXISTS idx_chats_thread_id;
DROP INDEX IF EXISTS idx_chats_user_id;
DROP TABLE IF EXISTS chats;

COMMIT;