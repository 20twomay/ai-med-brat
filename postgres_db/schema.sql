DROP TABLE IF EXISTS recipes;
DROP TABLE IF EXISTS medication;
DROP TABLE IF EXISTS diagnoses;
DROP TABLE IF EXISTS patients;

-- Таблица пациентов
CREATE TABLE patients (
    "id" INTEGER PRIMARY KEY, -- Идентификатор пациента
    "дата_рождения" DATE, -- Дата рождения пациента
    "пол" VARCHAR(10), -- Пол пациента
    "район_проживания" VARCHAR(100), -- Район проживания пациента
    "регион" VARCHAR(100) -- Регион проживания пациента
);

-- Таблица диагнозов
CREATE TABLE diagnoses (
    "код_мкб" VARCHAR(20) PRIMARY KEY, -- МКБ код диагноза
    "название_диагноза" TEXT, -- Название диагноза
    "класс_заболевания" TEXT -- Классификация диагноза
);

-- Таблица медикаментов
CREATE TABLE medication (
    "код_препарата" INTEGER PRIMARY KEY, -- Код препарата
    "дозировка" VARCHAR(100), -- Дозировка препарата
    "торговое_название" VARCHAR(100), -- Торговое наименование препарата
    "стоимость" FLOAT, -- Цена препарата
    "мета_информация" VARCHAR(200) -- Дополнительная информация о препарате
);

-- Таблица рецептов
CREATE TABLE recipes (
    "дата_рецепта" DATE, -- Дата выписки рецепта
    "код_диагноза" VARCHAR(20), -- МКБ код диагноза
    "код_препарата" INTEGER, -- Код препарата
    "id_пациента" INTEGER, -- Идентификатор пациента
    FOREIGN KEY ("id_пациента") REFERENCES patients("id"),
    FOREIGN KEY ("код_диагноза") REFERENCES diagnoses("код_мкб"),
    FOREIGN KEY ("код_препарата") REFERENCES medication("код_препарата")
);