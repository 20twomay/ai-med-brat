-- ========================================
-- Migration: 005_update_recipes_table
-- Direction: UP
-- Description: Добавление PRIMARY KEY для recipes и обновление foreign keys
-- Date: 2025-12-11
-- ========================================

BEGIN;

-- Для существующих БД: добавляем колонку id если её нет
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'recipes' AND column_name = 'id'
    ) THEN
        -- Удаляем старые foreign keys если они есть
        ALTER TABLE recipes DROP CONSTRAINT IF EXISTS recipes_id_пациента_fkey;
        ALTER TABLE recipes DROP CONSTRAINT IF EXISTS recipes_код_диагноза_fkey;
        ALTER TABLE recipes DROP CONSTRAINT IF EXISTS recipes_код_препарата_fkey;
        
        -- Добавляем новую колонку id
        ALTER TABLE recipes ADD COLUMN id SERIAL PRIMARY KEY;
        
        -- Добавляем foreign keys с CASCADE/SET NULL
        ALTER TABLE recipes 
            ADD CONSTRAINT recipes_patient_fkey 
            FOREIGN KEY ("id_пациента") 
            REFERENCES patients("id") 
            ON DELETE CASCADE;
            
        ALTER TABLE recipes 
            ADD CONSTRAINT recipes_diagnosis_fkey 
            FOREIGN KEY ("код_диагноза") 
            REFERENCES diagnoses("код_мкб") 
            ON DELETE SET NULL;
            
        ALTER TABLE recipes 
            ADD CONSTRAINT recipes_medication_fkey 
            FOREIGN KEY ("код_препарата") 
            REFERENCES medication("код_препарата") 
            ON DELETE SET NULL;
        
        -- Добавляем комментарий для новой колонки
        COMMENT ON COLUMN recipes."id" IS 'Уникальный идентификатор рецепта';
        
        RAISE NOTICE 'Migration 005: recipes table updated successfully';
    ELSE
        RAISE NOTICE 'Migration 005: recipes table already has id column, skipping';
    END IF;
END $$;

COMMIT;
