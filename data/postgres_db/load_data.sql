-- Загрузка данных из CSV файлов

-- Загрузка пациентов
\COPY patients FROM '/docker-entrypoint-initdb.d/data/patients.csv' WITH (FORMAT csv, HEADER true, DELIMITER ',');

-- Загрузка диагнозов
\COPY diagnoses FROM '/docker-entrypoint-initdb.d/data/diagnoses.csv' WITH (FORMAT csv, HEADER true, DELIMITER ',');

-- Загрузка медикаментов
\COPY medication FROM '/docker-entrypoint-initdb.d/data/medication.csv' WITH (FORMAT csv, HEADER true, DELIMITER ',');

-- Загрузка рецептов
\COPY recipes FROM '/docker-entrypoint-initdb.d/data/recipes.csv' WITH (FORMAT csv, HEADER true, DELIMITER ',');

-- Проверка загруженных данных
SELECT 'patients' as table_name, COUNT(*) as row_count FROM patients
UNION ALL
SELECT 'diagnoses', COUNT(*) FROM diagnoses
UNION ALL
SELECT 'medication', COUNT(*) FROM medication
UNION ALL
SELECT 'recipes', COUNT(*) FROM recipes;
