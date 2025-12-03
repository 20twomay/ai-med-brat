-- Создание таблиц для MySQL

-- Таблица диагнозов (МКБ-10)
CREATE TABLE diagnoses (
    code VARCHAR(10) PRIMARY KEY,
    diagnosis VARCHAR(500) NOT NULL,
    disease_class VARCHAR(500) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица пациентов
CREATE TABLE patients (
    id INT AUTO_INCREMENT PRIMARY KEY,
    birth_date DATE NOT NULL,
    gender CHAR(1) NOT NULL CHECK (gender IN ('м', 'ж')),
    district VARCHAR(100),
    region VARCHAR(100)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица рецептов
CREATE TABLE prescriptions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    prescription_date DATETIME NOT NULL,
    diagnosis_code VARCHAR(10) NOT NULL,
    drug_code VARCHAR(20) NOT NULL,
    patient_id INT NOT NULL,
    FOREIGN KEY (diagnosis_code) REFERENCES diagnoses(code),
    FOREIGN KEY (patient_id) REFERENCES patients(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Индексы для оптимизации
CREATE INDEX idx_prescriptions_patient ON prescriptions(patient_id);
CREATE INDEX idx_prescriptions_diagnosis ON prescriptions(diagnosis_code);
CREATE INDEX idx_prescriptions_date ON prescriptions(prescription_date);
