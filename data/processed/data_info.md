diagnoses.csv
- diagnosis_code: str - Код диагноза по МКБ
- name: str - Название диагноза
- classification: str - Класс заболевания

medication.csv
- medication_code: int - Код лекарства
- dosage: str - Дозировка
- trade_name: str - Торговое название
- price: float - Цена
- info: str - Информация о лекарстве

patients.csv
- id_patient: int - Идентификатор пациента
- birth_date: str - Дата рождения DD/MM/YYYY
- gender: str - Пол
- residential_area: str - Место жительства
- region: str - Регион

recipes.csv
- date: str - Дата выписанного рецепта YYYY/MM/DD HH:MM:SS
- diagnosis_code: str - Код диагноза по МКБ
- medication_code: int - Код лекарства
- id_patient: int - Идентификатор пациента