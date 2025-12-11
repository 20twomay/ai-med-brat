-- ========================================
-- Migration: 006_add_messages_table
-- Direction: DOWN
-- Description: Откат миграции - удаление таблицы сообщений
-- Date: 2025-12-11
-- ========================================

BEGIN;

DROP TABLE IF EXISTS messages CASCADE;

COMMIT;
