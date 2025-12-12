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

    df_filename: str = Field(description="Имя файла с DataFrame")
    chart_type: str = Field(description="Тип графика: barplot, lineplot, scatterplot")
    x: Optional[str | list[str]] = Field(description="Имя колонки для оси X")
    y: Optional[str | list[str]] = Field(description="Имя колонки для оси Y")
    hue: Optional[str] = Field(
        default=None, description="Имя колонки для цветовой дифференциации (опционально)"
    )
    size: Optional[str] = Field(
        default=None, description="Имя колонки для размера (опционально). Только для scatterplot)"
    )
    title: Optional[str] = Field(default=None, description="Заголовок графика (опционально)")
    xlabel: Optional[str] = Field(default=None, description="Подпись оси X (опционально)")
    ylabel: Optional[str] = Field(default=None, description="Подпись оси Y (опционально)")


class PlotChartOutput(BaseModel):
    """Выходные данные построения графика"""

    success: bool = Field(description="Флаг успешного выполнения запроса")
    result_meta: str = Field(description="Метаданные результата")
    result_filename: str = Field(description="Имя файла в S3 с полным результатом")


@tool(args_schema=PlotChartInput)
async def plot_chart_tool(
    df_filename: str,
    chart_type: str,
    x: Optional[str | list[str]] = None,
    y: Optional[str | list[str]] = None,
    hue: Optional[str] = None,
    size: Optional[str] = None,
    title: Optional[str] = None,
    xlabel: Optional[str] = None,
    ylabel: Optional[str] = None,
    config: RunnableConfig = None,
) -> str:
    """
    Строит интерактивный график с помощью plotly.express и сохраняет его как JSON.
    """
    chat_id = config["configurable"]["thread_id"]
    path_to_df = f"{chat_id}/{df_filename}"
    settings = get_settings()
    client = get_storage_client()

    try:
        response = await asyncio.to_thread(client.get_object, settings.s3_bucket, path_to_df)
        df = pd.read_csv(io.BytesIO(response.read()))
        response.close()
        response.release_conn()

        if chart_type == "barplot":
            fig = px.bar(df, x=x, y=y, color=hue, title=title, labels={x: xlabel, y: ylabel})
        elif chart_type == "lineplot":
            fig = px.line(df, x=x, y=y, color=hue, title=title, labels={x: xlabel, y: ylabel})
        elif chart_type == "scatterplot":
            fig = px.scatter(
                df, x=x, y=y, color=hue, title=title, labels={x: xlabel, y: ylabel}, size=size
            )
        else:
            result = PlotChartOutput(
                success=False,
                result_filename="",
                result_meta=f"Unsupported chart type: {chart_type}",
            )
            logger.info(f"Chart creation failed. Unsupported chart type: {chart_type}")
            return result.model_dump_json(indent=2)

        fig_json = fig.to_json()
        fig_bytes = fig_json.encode("utf-8")
        fig_filename = f"chart_{uuid.uuid4().hex[:8]}.json"
        full_path = f"{chat_id}/{fig_filename}"

        await asyncio.to_thread(
            client.put_object,
            bucket_name=settings.s3_bucket,
            object_name=full_path,
            data=io.BytesIO(fig_bytes),
            length=len(fig_bytes),
            content_type="application/json",
        )
        result = PlotChartOutput(
            success=True,
            result_filename=fig_filename,
            result_meta=f"Chart type: {chart_type}, Data points: {len(df)}",
        )
        logger.info(f"Chart created successfully. Saved as: {full_path}")
        return result.model_dump_json(indent=2)

    except Exception as e:
        result = PlotChartOutput(
            success=False,
            result_filename="",
            result_meta=str(e),
        )
        logger.error(f"Chart creation failed: {str(e)}", exc_info=True)
        return result.model_dump_json(indent=2)
