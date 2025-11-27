-- Таблица пациентов
CREATE TABLE IF NOT EXISTS patients (
    id_patient INTEGER PRIMARY KEY, -- Идентификатор пациента
    birth_date DATE, -- Дата рождения пациента
    gender VARCHAR(10), -- Пол пациента
    residential_area VARCHAR(100), -- Район проживания пациента
    region VARCHAR(100) -- Регион проживания пациента
);

-- Таблица диагнозов
CREATE TABLE IF NOT EXISTS diagnoses (
    diagnosis_code VARCHAR(20) PRIMARY KEY, -- МКБ код диагноза
    name VARCHAR(100), -- Название диагноза
    classification VARCHAR(100) -- Классификация диагноза
);

-- Таблица медикаментов
CREATE TABLE IF NOT EXISTS medication (
    medication_code INTEGER PRIMARY KEY, -- Код препарата
    dosage VARCHAR(100), -- Дозировка препарата
    trade_name VARCHAR(100), -- Торговое наименование препарата
    price FLOAT, -- Цена препарата
    info VARCHAR(300) -- Дополнительная информация о препарате
);

-- Таблица рецептов
CREATE TABLE IF NOT EXISTS recipes (
    date DATE, -- Дата выписки рецепта
    diagnosis_code VARCHAR(20), -- МКБ код диагноза
    medication_code INTEGER, -- Код препарата
    id_patient INTEGER, -- Идентификатор пациента
    FOREIGN KEY (id_patient) REFERENCES patients(id_patient),
    FOREIGN KEY (diagnosis_code) REFERENCES diagnoses(diagnosis_code),
    FOREIGN KEY (medication_code) REFERENCES medication(medication_code)
);



-- Индексы для оптимизации запросов
CREATE INDEX IF NOT EXISTS idx_recipes_patient ON recipes(id_patient);
CREATE INDEX IF NOT EXISTS idx_recipes_diagnosis ON recipes(diagnosis_code);
CREATE INDEX IF NOT EXISTS idx_recipes_medication ON recipes(medication_code);