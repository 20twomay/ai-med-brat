-- ========================================
-- Migration: 001_initial_schema
-- Direction: DOWN
-- Description: Откат начальной схемы для медицинских данных
-- Date: 2025-12-11
-- ========================================

BEGIN;

DROP TABLE IF EXISTS recipes;
DROP TABLE IF EXISTS medication;
DROP TABLE IF EXISTS diagnoses;
DROP TABLE IF EXISTS patients;

COMMIT;