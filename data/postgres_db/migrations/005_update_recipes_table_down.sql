-- ========================================
-- Migration: 005_update_recipes_table
-- Direction: DOWN
-- Description: Откат изменений в таблице recipes
-- Date: 2025-12-11
-- ========================================

BEGIN;

-- Удаляем новые foreign keys
ALTER TABLE recipes DROP CONSTRAINT IF EXISTS recipes_patient_fkey;
ALTER TABLE recipes DROP CONSTRAINT IF EXISTS recipes_diagnosis_fkey;
ALTER TABLE recipes DROP CONSTRAINT IF EXISTS recipes_medication_fkey;

-- Удаляем колонку id
ALTER TABLE recipes DROP COLUMN IF EXISTS id;

-- Восстанавливаем старые foreign keys без CASCADE
ALTER TABLE recipes 
    ADD CONSTRAINT recipes_id_пациента_fkey 
    FOREIGN KEY ("id_пациента") 
    REFERENCES patients("id");
    
ALTER TABLE recipes 
    ADD CONSTRAINT recipes_код_диагноза_fkey 
    FOREIGN KEY ("код_диагноза") 
    REFERENCES diagnoses("код_мкб");
    
ALTER TABLE recipes 
    ADD CONSTRAINT recipes_код_препарата_fkey 
    FOREIGN KEY ("код_препарата") 
    REFERENCES medication("код_препарата");

COMMIT;
