"""
Инструмент для построения графиков
"""

import asyncio
import io
import logging
import uuid
from typing import Optional

import pandas as pd
import plotly.express as px
from config import get_settings
from core import StorageError, get_storage_client
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PlotChartInput(BaseModel):
    """Входные параметры для построения графика"""

    path_to_df: str = Field(description="Path to the DataFrame in MinIO")
    chart_type: str = Field(description="Type of chart: barplot, lineplot, scatterplot")
    x: str = Field(description="Column name for x-axis")
    y: str = Field(description="Column name for y-axis")
    hue: Optional[str] = Field(default=None, description="Column name for hue (optional)")
    size: Optional[str] = Field(
        default=None, description="Column name for size (optional). Only for scatterplot)"
    )
    title: Optional[str] = Field(default=None, description="Chart title (optional)")
    xlabel: Optional[str] = Field(default=None, description="X-axis label (optional)")
    ylabel: Optional[str] = Field(default=None, description="Y-axis label (optional)")


@tool(args_schema=PlotChartInput)
async def plot_chart_tool(
    path_to_df: str,
    chart_type: str,
    x: str,
    y: str,
    hue: str = None,
    size: str = None,
    title: str = None,
    xlabel: str = None,
    ylabel: str = None,
    config: RunnableConfig = None,
) -> str:
    """
    Строит интерактивный plotly-график и сохраняет его в MinIO как JSON.

    Args:
        path_to_df: Путь к DataFrame в MinIO
        chart_type: Тип графика (barplot, lineplot, scatterplot)
        x: Колонка для оси X
        y: Колонка для оси Y
        hue: Колонка для цветовой дифференциации (опционально)
        title: Заголовок графика (опционально)
        xlabel: Подпись оси X (опционально)
        ylabel: Подпись оси Y (опционально)
        config: Конфигурация с thread_id

    Returns:
        Путь к сохранённому графику в MinIO

    Raises:
        StorageError: При ошибке работы с MinIO или построения графика
    """
    thread_id = config["configurable"]["thread_id"]
    settings = get_settings()
    client = get_storage_client()

    try:
        # Загружаем DataFrame из MinIO
        response = await asyncio.to_thread(client.get_object, settings.s3_bucket, path_to_df)
        df = pd.read_csv(io.BytesIO(response.read()))
        response.close()
        response.release_conn()

        # Создаём график в зависимости от типа
        if chart_type == "barplot":
            fig = px.bar(df, x=x, y=y, color=hue, title=title, labels={x: xlabel, y: ylabel})
        elif chart_type == "lineplot":
            fig = px.line(df, x=x, y=y, color=hue, title=title, labels={x: xlabel, y: ylabel})
        elif chart_type == "scatterplot":
            fig = px.scatter(
                df, x=x, y=y, color=hue, title=title, labels={x: xlabel, y: ylabel}, size=size
            )
        else:
            return (
                f"Unsupported chart type: {chart_type}. Supported: barplot, lineplot, scatterplot"
            )

        # Сохраняем график как JSON в MinIO
        fig_json = fig.to_json()
        fig_bytes = fig_json.encode("utf-8")
        object_name = f"{thread_id}/plot_{uuid.uuid4()}.json"

        await asyncio.to_thread(
            client.put_object,
            bucket_name=settings.s3_bucket,
            object_name=object_name,
            data=io.BytesIO(fig_bytes),
            length=len(fig_bytes),
            content_type="application/json",
        )

        logger.info(f"Chart created successfully. Saved to: {object_name}")
        return f"Plotly figure JSON saved to MinIO: {object_name}"

    except Exception as e:
        logger.error(f"Chart creation failed: {str(e)}", exc_info=True)
        raise StorageError(f"Chart creation failed: {str(e)}")
