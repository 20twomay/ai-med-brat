-- ========================================
-- Migration: 001_initial_schema
-- Direction: UP
-- Description: Создание начальной схемы для медицинских данных
-- Date: 2025-12-11
-- ========================================

BEGIN;

-- Таблица пациентов
CREATE TABLE IF NOT EXISTS patients (
    "id" INTEGER PRIMARY KEY,
    "дата_рождения" DATE,
    "пол" VARCHAR(10),
    "район_проживания" VARCHAR(100),
    "регион" VARCHAR(100)
);

COMMENT ON TABLE patients IS 'Информация о пациентах';
COMMENT ON COLUMN patients."id" IS 'Идентификатор пациента';
COMMENT ON COLUMN patients."дата_рождения" IS 'Дата рождения пациента';
COMMENT ON COLUMN patients."пол" IS 'Пол пациента';
COMMENT ON COLUMN patients."район_проживания" IS 'Район проживания пациента';
COMMENT ON COLUMN patients."регион" IS 'Регион проживания пациента';

-- Таблица диагнозов
CREATE TABLE IF NOT EXISTS diagnoses (
    "код_мкб" VARCHAR(20) PRIMARY KEY,
    "название_диагноза" TEXT,
    "класс_заболевания" TEXT
);

COMMENT ON TABLE diagnoses IS 'Справочник диагнозов по МКБ';
COMMENT ON COLUMN diagnoses."код_мкб" IS 'МКБ код диагноза';
COMMENT ON COLUMN diagnoses."название_диагноза" IS 'Название диагноза';
COMMENT ON COLUMN diagnoses."класс_заболевания" IS 'Классификация диагноза';

-- Таблица медикаментов
CREATE TABLE IF NOT EXISTS medication (
    "код_препарата" INTEGER PRIMARY KEY,
    "дозировка" VARCHAR(100),
    "торговое_название" VARCHAR(100),
    "стоимость" FLOAT,
    "мета_информация" VARCHAR(200)
);

COMMENT ON TABLE medication IS 'Справочник медикаментов';
COMMENT ON COLUMN medication."код_препарата" IS 'Код препарата';
COMMENT ON COLUMN medication."дозировка" IS 'Дозировка препарата';
COMMENT ON COLUMN medication."торговое_название" IS 'Торговое наименование препарата';
COMMENT ON COLUMN medication."стоимость" IS 'Цена препарата';
COMMENT ON COLUMN medication."мета_информация" IS 'Дополнительная информация о препарате';

-- Таблица рецептов
CREATE TABLE IF NOT EXISTS recipes (
    "id" SERIAL PRIMARY KEY,
    "дата_рецепта" DATE,
    "код_диагноза" VARCHAR(20),
    "код_препарата" INTEGER,
    "id_пациента" INTEGER,
    FOREIGN KEY ("id_пациента") REFERENCES patients("id") ON DELETE CASCADE,
    FOREIGN KEY ("код_диагноза") REFERENCES diagnoses("код_мкб") ON DELETE SET NULL,
    FOREIGN KEY ("код_препарата") REFERENCES medication("код_препарата") ON DELETE SET NULL
);

COMMENT ON TABLE recipes IS 'Рецепты, выписанные пациентам';
COMMENT ON COLUMN recipes."id" IS 'Уникальный идентификатор рецепта';
COMMENT ON COLUMN recipes."дата_рецепта" IS 'Дата выписки рецепта';
COMMENT ON COLUMN recipes."код_диагноза" IS 'МКБ код диагноза';
COMMENT ON COLUMN recipes."код_препарата" IS 'Код препарата';
COMMENT ON COLUMN recipes."id_пациента" IS 'Идентификатор пациента';

-- Индексы для оптимизации запросов к медицинским данным
CREATE INDEX IF NOT EXISTS idx_recipes_patient_id ON recipes("id_пациента");
CREATE INDEX IF NOT EXISTS idx_recipes_diagnosis ON recipes("код_диагноза");
CREATE INDEX IF NOT EXISTS idx_recipes_medication ON recipes("код_препарата");
CREATE INDEX IF NOT EXISTS idx_recipes_date ON recipes("дата_рецепта" DESC);

CREATE INDEX IF NOT EXISTS idx_patients_region ON patients("регион");
CREATE INDEX IF NOT EXISTS idx_patients_district ON patients("район_проживания");
CREATE INDEX IF NOT EXISTS idx_patients_gender ON patients("пол");
CREATE INDEX IF NOT EXISTS idx_patients_birth_date ON patients("дата_рождения");

CREATE INDEX IF NOT EXISTS idx_diagnoses_class ON diagnoses("класс_заболевания");

CREATE INDEX IF NOT EXISTS idx_medication_cost ON medication("стоимость");

COMMIT;