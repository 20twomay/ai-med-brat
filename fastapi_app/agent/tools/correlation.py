"""
Инструмент для вычисления корреляции между признаками в DataFrame
"""

import asyncio
import io
import logging

import pandas as pd
from config import get_settings
from core import get_storage_client
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CorrelationInput(BaseModel):
    """Входные параметры для инструмента корреляции"""

    df_filename: str = Field(description="Имя CSV файла с данными для анализа корреляции")
    method: str = Field(
        default="pearson",
        description="Метод вычисления корреляции: 'pearson', 'spearman' или 'kendall'",
    )
    threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Пороговое значение для отображения корреляции (от 0 до 1)",
    )


@tool(args_schema=CorrelationInput)
async def correlation_tool(
    df_filename: str,
    method: str = "pearson",
    threshold: float = 0.5,
    config: RunnableConfig = None,
) -> dict:
    """
    Загружает DataFrame и вычисляет корреляцию между числовыми признаками.
    Возвращает корреляционную матрицу и пары признаков с сильной корреляцией.

    Методы корреляции:
    - pearson: линейная корреляция (по умолчанию)
    - spearman: ранговая корреляция
    - kendall: корреляция Кендалла
    """
    try:
        chat_id = config["configurable"]["thread_id"]
        path_to_df = f"{chat_id}/{df_filename}"
        settings = get_settings()
        client = get_storage_client()

        # Загружаем DataFrame
        response = await asyncio.to_thread(client.get_object, settings.s3_bucket, path_to_df)
        df = pd.read_csv(io.BytesIO(response.read()))
        response.close()
        response.release_conn()

        logger.info(f"Загружен DataFrame: {df.shape[0]} строк, {df.shape[1]} столбцов")

        # Выбираем только числовые колонки
        numeric_cols = df.select_dtypes(include=["int64", "float64"]).columns.tolist()

        if len(numeric_cols) < 2:
            return {
                "error": f"Недостаточно числовых колонок для анализа корреляции. Найдено: {len(numeric_cols)}",
                "numeric_columns": numeric_cols,
            }

        # Вычисляем корреляцию
        df_numeric = df[numeric_cols]
        correlation_matrix = df_numeric.corr(method=method)

        # Находим пары с высокой корреляцией
        high_correlation_pairs = []
        for i in range(len(correlation_matrix.columns)):
            for j in range(i + 1, len(correlation_matrix.columns)):
                col1 = correlation_matrix.columns[i]
                col2 = correlation_matrix.columns[j]
                corr_value = correlation_matrix.iloc[i, j]

                if abs(corr_value) >= threshold:
                    high_correlation_pairs.append(
                        {
                            "feature_1": col1,
                            "feature_2": col2,
                            "correlation": round(float(corr_value), 4),
                        }
                    )

        # Сортируем по абсолютному значению корреляции
        high_correlation_pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)

        # Формируем результат
        result = {
            "method": method,
            "threshold": threshold,
            "total_numeric_features": len(numeric_cols),
            "numeric_features": numeric_cols,
            "high_correlation_pairs_count": len(high_correlation_pairs),
        }

        if len(high_correlation_pairs) > 0:
            # Если пар больше 20, показываем только топ-20
            if len(high_correlation_pairs) > 20:
                result["high_correlation_pairs_top20"] = high_correlation_pairs[:20]
                result["note"] = f"Показаны топ-20 пар из {len(high_correlation_pairs)} найденных"
            else:
                result["high_correlation_pairs"] = high_correlation_pairs
        else:
            result["message"] = f"Не найдено пар признаков с корреляцией >= {threshold}"

        # Добавляем статистику по корреляционной матрице
        result["correlation_matrix_stats"] = {
            "max_correlation": round(float(correlation_matrix.max().max()), 4),
            "min_correlation": round(float(correlation_matrix.min().min()), 4),
            "mean_correlation": round(float(correlation_matrix.mean().mean()), 4),
        }

        # Если колонок немного, добавляем полную матрицу
        if len(numeric_cols) <= 10:
            result["correlation_matrix"] = correlation_matrix.round(4).to_dict()

        logger.info(
            f"Корреляция вычислена: {len(high_correlation_pairs)} пар с |corr| >= {threshold}"
        )

        return result

    except Exception as e:
        logger.error(f"Ошибка в correlation tool: {e}", exc_info=True)
        return {
            "error": str(e),
            "error_type": type(e).__name__,
        }
