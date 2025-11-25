import pandas as pd
from sqlalchemy import create_engine

# Подключение к PostgreSQL
engine = create_engine("postgresql://user:user@localhost:5432/user_db")

# Загрузка CSV
patients = pd.read_csv("../data/processed/patients.csv")
recipes = pd.read_csv("../data/processed/recipes.csv")
diagnoses = pd.read_csv("../data/processed/diagnoses.csv")
medication = pd.read_csv("../data/processed/medication.csv")

# Загрузка в PostgreSQL
patients.to_sql("patients", engine, if_exists="replace", index=False)
recipes.to_sql("recipes", engine, if_exists="replace", index=False)
diagnoses.to_sql("diagnoses", engine, if_exists="replace", index=False)
medication.to_sql("medication", engine, if_exists="replace", index=False)

print("Данные успешно загружены в PostgreSQL!")
