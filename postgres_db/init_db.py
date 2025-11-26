import time

import pandas as pd
from sqlalchemy import Column, Date, Float, Integer, MetaData, String, Table, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Подключение к PostgreSQL
engine = create_engine("postgresql://user:user@localhost:5432/user_db")

# Ожидание готовности БД
print("Ожидание подключения к БД...")
time.sleep(2)

# Дроп существующих таблиц
print("Удаление существующих таблиц...")
with engine.connect() as conn:
    try:
        conn.execute(text("DROP TABLE IF EXISTS recipes CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS medication CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS diagnoses CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS patients CASCADE;"))
        conn.commit()
        print("Существующие таблицы удалены.")
    except SQLAlchemyError as e:
        print(f"Ошибка при удалении таблиц: {e}")
        exit(1)


# Функция для выполнения SQL-скрипта
def execute_sql_file(file_path):
    with open(file_path, "r") as file:
        sql_script = file.read()
    with engine.connect() as conn:
        conn.execute(text(sql_script))
        conn.commit()


# Создание таблиц по схеме
print("Создание таблиц по схеме...")
try:
    execute_sql_file("postgres_db/schema.sql")
    print("Таблицы созданы успешно.")
except SQLAlchemyError as e:
    print(f"Ошибка при создании таблиц: {e}")
    exit(1)

# Загрузка CSV с проверкой типов
print("Загрузка данных из CSV...")

# Определите типы данных для каждого CSV (чтобы pandas правильно прочитал)
patients_dtypes = {
    "id_patient": "int64",
    "birth_date": "str",  # Будет преобразовано в дату позже
    "gender": "str",
    "residential_area": "str",
    "region": "str",
}
diagnoses_dtypes = {"diagnosis_code": "str", "name": "str", "classification": "str"}
medication_dtypes = {
    "medication_code": "int64",
    "dosage": "str",
    "trade_name": "str",
    "price": "float64",
    "info": "str",
}
recipes_dtypes = {
    "date": "str",  # Будет преобразовано в дату позже
    "diagnosis_code": "str",
    "medication_code": "int64",
    "id_patient": "int64",
}

try:
    patients = pd.read_csv("./data/processed/patients.csv", dtype=patients_dtypes)
    patients["birth_date"] = pd.to_datetime(
        patients["birth_date"], format="%d.%m.%Y", errors="coerce"
    ).dt.date  # Преобразование в дату

    diagnoses = pd.read_csv("./data/processed/diagnoses.csv", dtype=diagnoses_dtypes)

    medication = pd.read_csv("./data/processed/medication.csv", dtype=medication_dtypes)

    recipes = pd.read_csv("./data/processed/recipes.csv", dtype=recipes_dtypes)
    recipes["date"] = pd.to_datetime(
        recipes["date"], format="%d.%m.%Y", errors="coerce"
    ).dt.date  # Преобразование в дату

    print("CSV загружены и обработаны.")
except Exception as e:
    print(f"Ошибка при загрузке CSV: {e}")
    exit(1)

# Загрузка в PostgreSQL с транзакциями
print("Загрузка данных в таблицы...")

# Определение типов столбцов для каждой таблицы
patients_dtype = {
    "id_patient": Integer,
    "birth_date": Date,
    "gender": String(10),
    "residential_area": String(100),
    "region": String(100),
}
diagnoses_dtype = {
    "diagnosis_code": String(20),
    "name": String(100),
    "classification": String(100),
}
medication_dtype = {
    "medication_code": Integer,
    "dosage": String(100),
    "trade_name": String(100),
    "price": Float,
    "info": String(300),
}
recipes_dtype = {
    "date": Date,
    "diagnosis_code": String(20),
    "medication_code": Integer,
    "id_patient": Integer,
}

tables_data = [
    ("patients", patients, patients_dtype),
    ("diagnoses", diagnoses, diagnoses_dtype),
    ("medication", medication, medication_dtype),
    ("recipes", recipes, recipes_dtype),
]

with engine.begin() as conn:  # Транзакция для всех операций
    try:
        for table_name, df, dtype_dict in tables_data:
            print(f"Загрузка {table_name}...")
            df.to_sql(
                table_name, conn, if_exists="append", index=False, dtype=dtype_dict, chunksize=1000
            )
        print("Все данные успешно загружены!")
    except SQLAlchemyError as e:
        print(f"Ошибка при загрузке данных: {e}")
        conn.rollback()  # Откат транзакции при ошибке
        exit(1)
