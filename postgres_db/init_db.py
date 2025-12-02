import time

import pandas as pd
from sqlalchemy import Column, Date, Float, Integer, MetaData, String, Table, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Подключение к PostgreSQL
engine = create_engine("postgresql://user:user@localhost:5432/user_db")

# ...existing code...

# Пути к обработанным данным
processed_path = "data/processed"

# Выполнение схемы базы данных
try:
    with open("postgres_db/schema.sql", "r") as f:
        schema_sql = f.read()
    with engine.connect() as conn:
        conn.execute(text(schema_sql))
        conn.commit()
    print("Схема базы данных создана.")
except SQLAlchemyError as e:
    print(f"Ошибка при создании схемы: {e}")

# Загрузка данных в таблицы в правильном порядке (учитывая foreign keys)
try:
    # Загрузка пациентов
    patients_df = pd.read_csv(f"{processed_path}/patients.csv")
    patients_df["дата_рождения"] = pd.to_datetime(
        patients_df["дата_рождения"]
    ).dt.date  # Конвертация в date для PostgreSQL
    patients_df.to_sql("patients", engine, if_exists="append", index=False)
    print("Таблица patients загружена.")

    # Загрузка диагнозов
    diagnoses_df = pd.read_csv(f"{processed_path}/diagnoses.csv")
    diagnoses_df.to_sql("diagnoses", engine, if_exists="append", index=False)
    print("Таблица diagnoses загружена.")

    # Загрузка медикаментов
    medication_df = pd.read_csv(f"{processed_path}/medication.csv")
    medication_df.to_sql("medication", engine, if_exists="append", index=False)
    print("Таблица medication загружена.")

    # Загрузка рецептов
    recipes_df = pd.read_csv(f"{processed_path}/recipes.csv")
    recipes_df["дата_рецепта"] = pd.to_datetime(
        recipes_df["дата_рецепта"]
    ).dt.date  # Конвертация в date для PostgreSQL
    recipes_df.to_sql("recipes", engine, if_exists="append", index=False)
    print("Таблица recipes загружена.")

    print("Все данные успешно загружены в базу данных.")

except SQLAlchemyError as e:
    print(f"Ошибка при загрузке данных: {e}")
