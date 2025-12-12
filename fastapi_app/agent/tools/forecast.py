import asyncio
import io
import logging
import os
import tempfile
import uuid
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from config import get_settings
from core import DatabaseError, get_storage_client, get_sync_engine
from dotenv import load_dotenv
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
from sklearn.metrics import mean_absolute_error

load_dotenv()

logger = logging.getLogger(__name__)


class TimeSeriesForecastInput(BaseModel):
    ts_df_filename: str = Field(
        description=(
            "Имя CSV файла с временным рядом. Должен содержать колонку с датой в формате YYYY-MM-DD,"
            "колонку с целевой переменной и колонки с признаками."
        )
    )
    target_column: str = Field(
        description="Имя колонки с целевой переменной.",
    )
    date_column: str = Field(
        description="Имя колонки с датой в формате YYYY-MM-DD.",
    )
    pred_days_length: int = Field(
        ge=1,
        le=90,
        description="Горизонт прогноза: на сколько дней вперёд делать прогноз.",
    )
    n_days_history: int = Field(
        ge=5,
        le=365,
        description="Сколько прошедших дней использовать для создания лагов.",
    )
    # rolling_windows: Optional[List[int]] = Field(
    #     default=[7],
    #     description="Список размеров окон для скользящих средних и стандартных отклонений.",
    # )


@tool(args_schema=TimeSeriesForecastInput)
async def forecast_tool(
    ts_df_filename: str,
    target_column: str,
    date_column: str,
    pred_days_length: int,
    n_days_history: int,
    config: RunnableConfig = None,
    # rolling_windows: Optional[List[int]] = None,
) -> dict:
    """
    Обучает CatBoost модель на прогноз на 1 день вперед,
    затем итеративно применяет её для получения прогноза на pred_days_length дней.
    ts_df_filename обязательно дожен содержать колонку с сырой датой, признаками и колонку с целевой переменной.
    """
    try:
        chat_id = config["configurable"]["thread_id"]
        path_to_df = f"{chat_id}/{ts_df_filename}"
        settings = get_settings()
        client = get_storage_client()

        response = await asyncio.to_thread(client.get_object, settings.s3_bucket, path_to_df)
        df = pd.read_csv(io.BytesIO(response.read()))
        response.close()
        response.release_conn()

        random_state = 42
        verbose = False
        rolling_windows = [10]

        # === 1. Валидация и подготовка даты ===
        if date_column not in df.columns:
            raise ValueError(f"Колонка '{date_column}' не найдена. Доступные: {list(df.columns)}")
        if target_column not in df.columns:
            raise ValueError(f"Колонка '{target_column}' не найдена. Доступные: {list(df.columns)}")

        df[date_column] = pd.to_datetime(df[date_column])
        df[date_column] = df[date_column].dt.strftime("%Y-%m-%d")
        df = df.sort_values(date_column).reset_index(drop=True)

        # === Обработка дубликатов дат ===
        # Определяем типы данных до агрегации
        X_cols_temp = [col for col in df.columns if col not in [date_column]]
        categorical_cols_temp = (
            df[X_cols_temp].select_dtypes(include=["object", "category"]).columns.tolist()
        )
        numerical_cols_temp = (
            df[X_cols_temp].select_dtypes(include=["int64", "float64"]).columns.tolist()
        )

        # Проверяем на наличие дубликатов дат
        if df[date_column].duplicated().any():
            logger.info("Обнаружены дубликаты дат. Выполняется агрегация...")

            # Создаем словарь агрегирующих функций
            agg_dict = {}

            # Для числовых признаков - среднее
            for col in numerical_cols_temp:
                agg_dict[col] = "mean"

            # Для категориальных признаков - мода (наиболее частое значение)
            def get_mode(series):
                mode_result = series.mode()
                return mode_result[0] if not mode_result.empty else series.iloc[0]

            for col in categorical_cols_temp:
                agg_dict[col] = get_mode

            # Группируем по дате и агрегируем
            df = df.groupby(date_column, as_index=False).agg(agg_dict)
            logger.info(f"После агрегации осталось {len(df)} уникальных дат")

        # === Заполнение пропущенных дат ===
        df[date_column] = pd.to_datetime(df[date_column])
        df = df.set_index(date_column)
        df = df.asfreq("D")  # Создаём пропуски для отсутствующих дней
        df = df.ffill()  # Заполняем пропуски предыдущим значением
        df = df.reset_index()
        df[date_column] = df[date_column].dt.strftime("%Y-%m-%d")
        logger.info(f"После заполнения пропусков: {len(df)} дней")

        X_cols = [col for col in df.columns if col not in [date_column, target_column]]
        y_col = target_column

        # Определяем категориальные и числовые признаки
        categorical_cols = df[X_cols].select_dtypes(include=["object", "category"]).columns.tolist()
        numerical_cols = df[X_cols].select_dtypes(include=["int64", "float64"]).columns.tolist()

        logger.info(f"Категориальные признаки: {categorical_cols}")
        logger.info(f"Числовые признаки: {numerical_cols}")

        # === 2. Создание лагов ===
        for i in range(1, n_days_history + 1):
            df[f"{y_col}_lag_{i}"] = df[y_col].shift(i)
            # Создаем лаги только для числовых признаков
            for x in numerical_cols:
                df[f"{x}_lag_{i}"] = df[x].shift(i)

        # === 3. Скользящие статистики ===
        for window in rolling_windows:
            df[f"{y_col}_rolling_mean_{window}"] = df[y_col].rolling(window).mean()
            df[f"{y_col}_rolling_std_{window}"] = df[y_col].rolling(window).std()
            # Скользящие статистики только для числовых признаков
            for x in numerical_cols:
                df[f"{x}_rolling_mean_{window}"] = df[x].rolling(window).mean()
                df[f"{x}_rolling_std_{window}"] = df[x].rolling(window).std()

        # === 4. Временные признаки ===
        df_temp = pd.DataFrame()
        df_temp[date_column] = pd.to_datetime(df[date_column])
        df["day_of_week"] = df_temp[date_column].dt.dayofweek
        df["month"] = df_temp[date_column].dt.month
        df["day_of_month"] = df_temp[date_column].dt.day
        df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

        # === 5. Создание целевой переменной (прогноз на 1 день) ===
        df["target_next"] = df[y_col].shift(-1)

        # === 6. Удаление NaN ===
        df_clean = df.dropna().reset_index(drop=True)
        if len(df_clean) == 0:
            raise ValueError("После создания признаков не осталось строк без NaN.")

        # === 7. Формирование признаков ===
        feature_cols = [
            col
            for col in df_clean.columns
            if col not in [date_column, target_column, "target_next"]
        ]
        if not feature_cols:
            raise ValueError("Не найдено признаков для обучения.")

        # Определяем индексы категориальных признаков для CatBoost
        cat_feature_indices = []
        for idx, col in enumerate(feature_cols):
            # Проверяем, является ли признак категориальным (оригинальный или производный от категориального)
            if col in categorical_cols:
                cat_feature_indices.append(idx)
            # Также проверяем лаги категориальных признаков
            for cat_col in categorical_cols:
                if col.startswith(f"{cat_col}_lag_"):
                    cat_feature_indices.append(idx)
                    break

        logger.info(f"Индексы категориальных признаков для CatBoost: {cat_feature_indices}")

        # === 8. Разделение на train/test ===
        split_idx = int(len(df_clean) * 0.8)
        if split_idx < 10:
            train = df_clean
            test = df_clean
        else:
            train = df_clean.iloc[:split_idx]
            test = df_clean.iloc[split_idx:]

        X_train, y_train = train[feature_cols], train["target_next"]
        X_test, y_test = test[feature_cols], test["target_next"]

        logger.info(f"Размер обучающей выборки: {len(X_train)}")
        logger.info(f"Размер тестовой выборки: {len(X_test)}")
        logger.info(f"Пример выборки:\n{train.head().to_string()}")

        # === 9. Обучение модели на 1 день вперёд ===
        model = CatBoostRegressor(
            iterations=1000,
            depth=6,
            learning_rate=0.1,
            loss_function="MAE",
            random_seed=random_state,
            verbose=False,
            cat_features=cat_feature_indices,  # Указываем категориальные признаки
        )

        model.fit(
            X_train,
            y_train,
            eval_set=(X_test, y_test),
            use_best_model=True,
            early_stopping_rounds=50,
            verbose=verbose,
        )

        # Оценка на тесте
        test_pred = model.predict(X_test)
        mae = mean_absolute_error(y_test, test_pred)
        logger.info(f"MAE на тестовой выборке: {mae:.4f}")

        # === 10. Итеративный прогноз на pred_days_length дней ===
        # Берем последние данные для начала прогноза
        last_row = df_clean.iloc[-1].copy()
        forecasts = []
        forecast_dates = []

        current_date = pd.to_datetime(df_clean[date_column].iloc[-1])

        # Инициализируем окна для rolling статистик
        rolling_windows_data = {}
        for window in rolling_windows:
            # Берём последние window значений целевой переменной
            rolling_windows_data[f"{y_col}_{window}"] = df_clean[y_col].iloc[-window:].tolist()
            # Для числовых признаков тоже
            for x in numerical_cols:
                rolling_windows_data[f"{x}_{window}"] = df_clean[x].iloc[-window:].tolist()

        for step in range(pred_days_length):
            # Подготовка признаков для прогноза
            X_pred = last_row[feature_cols].values.reshape(1, -1)

            # Предсказание на 1 день вперёд
            pred_value = model.predict(X_pred)[0]
            forecasts.append(pred_value)

            # Следующая дата
            current_date = current_date + pd.Timedelta(days=1)
            forecast_dates.append(current_date.strftime("%Y-%m-%d"))

            # Обновляем last_row для следующей итерации
            # Сдвигаем лаги
            for i in range(n_days_history, 1, -1):
                last_row[f"{y_col}_lag_{i}"] = last_row[f"{y_col}_lag_{i - 1}"]
            last_row[f"{y_col}_lag_1"] = pred_value

            # Обновляем лаги для дополнительных признаков
            # Для числовых признаков сдвигаем лаги, но НЕ обновляем lag_1,
            # так как мы не знаем будущих значений этих признаков
            for x in numerical_cols:
                for i in range(n_days_history, 1, -1):
                    if f"{x}_lag_{i}" in last_row.index:
                        last_row[f"{x}_lag_{i}"] = last_row[f"{x}_lag_{i - 1}"]
                # lag_1 остаётся последним известным значением (не обновляем)

            # Категориальные признаки не обновляем их лаги (оставляем последние известные значения)

            # Обновляем rolling статистики корректно
            for window in rolling_windows:
                # Обновляем окно для целевой переменной
                if f"{y_col}_{window}" in rolling_windows_data:
                    rolling_windows_data[f"{y_col}_{window}"].append(pred_value)
                    rolling_windows_data[f"{y_col}_{window}"] = rolling_windows_data[
                        f"{y_col}_{window}"
                    ][-window:]

                    if f"{y_col}_rolling_mean_{window}" in last_row.index:
                        last_row[f"{y_col}_rolling_mean_{window}"] = np.mean(
                            rolling_windows_data[f"{y_col}_{window}"]
                        )
                        last_row[f"{y_col}_rolling_std_{window}"] = np.std(
                            rolling_windows_data[f"{y_col}_{window}"]
                        )

                # Для числовых признаков оставляем последнее известное значение в окне
                for x in numerical_cols:
                    if f"{x}_{window}" in rolling_windows_data:
                        # Добавляем последнее известное значение (не обновляем, так как не знаем будущее)
                        if f"{x}_rolling_mean_{window}" in last_row.index:
                            last_row[f"{x}_rolling_mean_{window}"] = np.mean(
                                rolling_windows_data[f"{x}_{window}"]
                            )
                            last_row[f"{x}_rolling_std_{window}"] = np.std(
                                rolling_windows_data[f"{x}_{window}"]
                            )

            # Обновляем временные признаки
            last_row["day_of_week"] = current_date.dayofweek
            last_row["month"] = current_date.month
            last_row["day_of_month"] = current_date.day
            last_row["is_weekend"] = int(current_date.dayofweek >= 5)

        # === 11. Формирование результата ===
        forecast_df = pd.DataFrame({"date": forecast_dates, "raw_forecast": forecasts})

        # Добавляем сглаживание (скользящее среднее с окном 3)
        window_size = min(3, len(forecast_df))
        if window_size > 1:
            forecast_df["smoothed_forecast"] = (
                forecast_df["raw_forecast"]
                .rolling(window=window_size, center=True, min_periods=1)
                .mean()
            )
        else:
            forecast_df["smoothed_forecast"] = forecast_df["raw_forecast"]

        # Добавляем кумулятивный прогноз
        forecast_df["cumulative_forecast"] = forecast_df["smoothed_forecast"].cumsum()

        # Топ-5 признаков по важности
        feature_importance_full = dict(zip(feature_cols, model.feature_importances_))
        feature_importance = dict(
            sorted(feature_importance_full.items(), key=lambda x: x[1], reverse=True)[:5]
        )

        if mae > 150:
            logger.warning(
                f"Высокое MAE на тестовой выборке: {mae:.4f}. "
                "Возможные причины: недостаток данных, нерегулярный ряд, неподходящие признаки."
            )
            return {
                "test_mae": float(mae),
                "warning": (
                    "Высокое MAE на тестовой выборке. Модель с низкой точностью."
                    "Возможные причины: недостаток данных, нерегулярный ряд, неподходящие признаки."
                ),
            }

        csv_buffer = io.BytesIO()
        forecast_df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        filename = f"df_{uuid.uuid4().hex[:8]}.csv"
        full_path = f"{chat_id}/{filename}"

        await asyncio.to_thread(
            client.put_object,
            bucket_name=settings.s3_bucket,
            object_name=full_path,
            data=csv_buffer,
            length=csv_buffer.getbuffer().nbytes,
            content_type="text/csv",
        )

        if len(forecast_df) > 20:
            return {
                "forecast_df.head(5)": forecast_df.head(5).to_string(index=False),
                "forecast_df.tail(5)": forecast_df.tail(5).to_string(index=False),
                "feature_importance top-5": feature_importance,
                "result_filename": filename,
                "test_mae": float(mae),
            }
        else:
            return {
                "forecast_df": forecast_df.to_string(index=False),
                "feature_importance": feature_importance,
                "result_filename": filename,
                "test_mae": float(mae),
            }
    except Exception as e:
        logger.error(f"Ошибка в forecast tool: {e}", exc_info=True)
        raise e
