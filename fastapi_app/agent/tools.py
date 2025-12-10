import io
import logging
import os
import uuid
from typing import Any, Optional

import pandas as pd
import plotly.express as px
from dotenv import load_dotenv
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from minio import Minio
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text

# Инициализация логгера
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# PostgreSQL
DATABASE_ENDPOINT = os.getenv("DATABASE_ENDPOINT")

# S3/MinIO
S3_ENDPOINT = os.getenv("S3_ENDPOINT")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_BUCKET = os.getenv("S3_BUCKET")

# Убираем схему протокола из endpoint для minio клиента
if S3_ENDPOINT:
    S3_ENDPOINT = S3_ENDPOINT.replace("http://", "").replace("https://", "")

MINIO_CLIENT = Minio(
    S3_ENDPOINT,
    access_key=S3_ACCESS_KEY,
    secret_key=S3_SECRET_KEY,
    secure=False,
)

if not MINIO_CLIENT.bucket_exists(S3_BUCKET):
    MINIO_CLIENT.make_bucket(S3_BUCKET)


def get_db_engine():
    """Создает подключение к базе данных"""
    if not DATABASE_ENDPOINT:
        raise ValueError("DATABASE_ENDPOINT environment variable is not set")
    return create_engine(DATABASE_ENDPOINT)


class PlotChartInput(BaseModel):
    path_to_df: str = Field(description="Path to the DataFrame")
    chart_type: str = Field(description="Type of chart: barplot, lineplot, scatterplot")
    x: str = Field(description="Column name for x-axis")
    y: str = Field(description="Column name for y-axis")
    hue: Optional[str] = Field(default=None, description="Column name for hue (optional)")
    title: Optional[str] = Field(default=None, description="Custom title for the chart (optional)")
    xlabel: Optional[str] = Field(default=None, description="Label for the x-axis (optional)")
    ylabel: Optional[str] = Field(default=None, description="Label for the y-axis (optional)")


@tool(args_schema=PlotChartInput)
async def plot_chart_tool(
    path_to_df: str,
    chart_type: str,
    x: str,
    y: str,
    hue: str = None,
    title: str = None,
    xlabel: str = None,
    ylabel: str = None,
    config: RunnableConfig = None,
) -> str:
    """Строит интерактивный plotly-график и сохраняет fig.to_json() в S3."""
    import asyncio

    thread_id = config["configurable"]["thread_id"]
    try:
        # Async MinIO операции через to_thread
        response = await asyncio.to_thread(MINIO_CLIENT.get_object, S3_BUCKET, path_to_df)
        df = pd.read_csv(io.BytesIO(response.read()))
        response.close()
        response.release_conn()

        if chart_type == "barplot":
            fig = px.bar(df, x=x, y=y, color=hue, title=title, labels={x: xlabel, y: ylabel})
        elif chart_type == "lineplot":
            fig = px.line(df, x=x, y=y, color=hue, title=title, labels={x: xlabel, y: ylabel})
        elif chart_type == "scatterplot":
            fig = px.scatter(df, x=x, y=y, color=hue, title=title, labels={x: xlabel, y: ylabel})
        else:
            return f"Unsupported chart type: {chart_type}"

        fig_json = fig.to_json()
        fig_bytes = fig_json.encode("utf-8")
        object_name = f"{thread_id}/plot_{uuid.uuid4()}.json"

        await asyncio.to_thread(
            MINIO_CLIENT.put_object,
            bucket_name=S3_BUCKET,
            object_name=object_name,
            data=io.BytesIO(fig_bytes),
            length=len(fig_bytes),
            content_type="application/json",
        )
        return f"Plotly figure JSON saved to MinIO: {object_name}"
    except Exception as e:
        return f"Plotting Error: {str(e)}"


class ExecuteSQLInput(BaseModel):
    query: str = Field(description="SQL запрос для выполнения")


@tool(args_schema=ExecuteSQLInput)
async def execute_sql_tool(
    query: str,
    config: RunnableConfig = None,
) -> str:
    """Выполняет SQL запрос и сохраняет результат в S3."""
    import asyncio

    thread_id = config["configurable"]["thread_id"]
    try:
        engine = get_db_engine()

        # Async DB операция через to_thread
        def run_query():
            with engine.connect() as conn:
                return pd.read_sql(text(query), conn)

        df = await asyncio.to_thread(run_query)

        if df.empty:
            return "Query executed successfully but returned no results."

        csv_buffer = io.BytesIO()
        df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        object_name = f"{thread_id}/df_{uuid.uuid4()}.csv"

        await asyncio.to_thread(
            MINIO_CLIENT.put_object,
            bucket_name=S3_BUCKET,
            object_name=object_name,
            data=csv_buffer,
            length=csv_buffer.getbuffer().nbytes,
            content_type="text/csv",
        )
        return f"First 25 rows:\n{df.head(25)}\nShape: {df.shape}\nFile saved to MinIO at '{object_name}'"
    except Exception as e:
        return f"SQL Error: {str(e)}"
