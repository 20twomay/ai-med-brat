-- ========================================
-- Migration: 002_add_users_table
-- Direction: DOWN
-- Description: Откат таблицы пользователей
-- Date: 2025-12-11
-- ========================================

BEGIN;

DROP INDEX IF EXISTS idx_users_email;
DROP TABLE IF EXISTS users;

COMMIT;