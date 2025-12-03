-- Создание таблиц для PostgreSQL

-- Таблица диагнозов (МКБ-10)
CREATE TABLE diagnoses (
    code VARCHAR(10) PRIMARY KEY,
    diagnosis VARCHAR(500) NOT NULL,
    disease_class VARCHAR(500) NOT NULL
);

-- Таблица пациентов
CREATE TABLE patients (
    id SERIAL PRIMARY KEY,
    birth_date DATE NOT NULL,
    gender CHAR(1) NOT NULL CHECK (gender IN ('м', 'ж')),
    district VARCHAR(100),
    region VARCHAR(100)
);

-- Таблица рецептов
CREATE TABLE prescriptions (
    id SERIAL PRIMARY KEY,
    prescription_date TIMESTAMP NOT NULL,
    diagnosis_code VARCHAR(10) NOT NULL,
    drug_code VARCHAR(20) NOT NULL,
    patient_id INTEGER NOT NULL,
    FOREIGN KEY (diagnosis_code) REFERENCES diagnoses(code),
    FOREIGN KEY (patient_id) REFERENCES patients(id)
);

-- Индексы для оптимизации
CREATE INDEX idx_prescriptions_patient ON prescriptions(patient_id);
CREATE INDEX idx_prescriptions_diagnosis ON prescriptions(diagnosis_code);
CREATE INDEX idx_prescriptions_date ON prescriptions(prescription_date);
