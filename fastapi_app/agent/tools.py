import ast
import logging
import os
import uuid
from typing import Any, Optional

import boto3
from botocore.client import Config
import matplotlib

matplotlib.use("Agg")  # Неинтерактивный бэкенд для серверного использования
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from dotenv import load_dotenv
from langchain.tools import tool
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text

load_dotenv()

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

# S3/MinIO configuration
S3_ENDPOINT = os.getenv("S3_ENDPOINT")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_BUCKET = os.getenv("S3_BUCKET", "charts")
S3_PUBLIC_URL = os.getenv("S3_PUBLIC_URL", "http://localhost:9000")


def get_db_engine():
    """Создает подключение к базе данных"""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable is not set")
    return create_engine(DATABASE_URL)


def get_s3_client():
    """Создает S3 клиент для MinIO"""
    if not all([S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY]):
        logger.warning("S3 configuration incomplete, charts will be saved locally only")
        return None
    
    try:
        s3_client = boto3.client(
            's3',
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
            config=Config(signature_version='s3v4'),
            region_name='us-east-1'
        )
        
        # Создаем bucket если не существует
        try:
            s3_client.head_bucket(Bucket=S3_BUCKET)
        except:
            s3_client.create_bucket(Bucket=S3_BUCKET)
            logger.info(f"Created S3 bucket: {S3_BUCKET}")
            
            # Устанавливаем политику публичного чтения
            bucket_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "PublicRead",
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{S3_BUCKET}/*"]
                    }
                ]
            }
            import json
            s3_client.put_bucket_policy(Bucket=S3_BUCKET, Policy=json.dumps(bucket_policy))
        
        return s3_client
    except Exception as e:
        logger.error(f"Failed to initialize S3 client: {e}")
        return None


def upload_to_s3(filepath: str, filename: str) -> Optional[str]:
    """Загружает файл в S3 и возвращает публичный URL"""
    s3_client = get_s3_client()
    if not s3_client:
        return None
    
    try:
        s3_client.upload_file(
            filepath,
            S3_BUCKET,
            filename,
            ExtraArgs={'ContentType': 'image/png'}
        )
        
        # Формируем публичный URL
        public_url = f"{S3_PUBLIC_URL}/{S3_BUCKET}/{filename}"
        logger.info(f"Uploaded chart to S3: {public_url}")
        return public_url
    except Exception as e:
        logger.error(f"Failed to upload to S3: {e}")
        return None


class ExecuteSQLInput(BaseModel):
    query: str = Field(description="SQL query to execute")


@tool(args_schema=ExecuteSQLInput)
def execute_sql_tool(query: str) -> list[dict[str, Any]] | str:
    """Выполняет SQL запрос и возвращает результат как список словарей."""
    try:
        logger.info(f"Executing SQL query: {query[:100]}...")
        engine = get_db_engine()
        if "limit" not in query.lower():
            query = query.rstrip(";") + " LIMIT 25;"

        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn)

        if df.empty:
            logger.info("Query returned no results")
            return "Query executed successfully but returned no results."

        logger.info(f"Query returned {len(df)} rows")
        return df.to_dict(orient="records")
    except Exception as e:
        logger.error(f"SQL Error: {str(e)}", exc_info=True)
        return f"SQL Error: {str(e)}"


class PlotChartInput(BaseModel):
    df: list[dict] | str = Field(description="DataFrame data as list of dicts")
    chart_type: str = Field(description="Type of chart: barplot, lineplot, scatterplot")
    x: str = Field(description="Column name for x-axis")
    y: str = Field(description="Column name for y-axis")
    hue: Optional[str] = Field(default=None, description="Column name for hue (optional)")
    title: Optional[str] = Field(default=None, description="Custom title for the chart (optional)")
    xlabel: Optional[str] = Field(default=None, description="Label for the x-axis (optional)")
    ylabel: Optional[str] = Field(default=None, description="Label for the y-axis (optional)")


@tool(args_schema=PlotChartInput)
def plot_chart_tool(
    df: list[dict],
    chart_type: str,
    x: str,
    y: str,
    hue: str = None,
    title: str = None,
    xlabel: str = None,
    ylabel: str = None,
) -> str:
    """Строит график и возвращает путь к файлу."""
    try:
        logger.info(f"Creating {chart_type} chart: x={x}, y={y}")
        if not df:
            return "No data to plot."

        df = pd.DataFrame(ast.literal_eval(df)) if isinstance(df, str) else pd.DataFrame(df)

        plt.figure(figsize=(10, 6))

        if chart_type == "barplot":
            sns.barplot(data=df, x=x, y=y, hue=hue)
        elif chart_type == "lineplot":
            sns.lineplot(data=df, x=x, y=y, hue=hue)
        elif chart_type == "scatterplot":
            sns.scatterplot(data=df, x=x, y=y, hue=hue)
        else:
            return f"Unsupported chart type: {chart_type}"

        title = title if title is not None else f"{chart_type}_{x}_by_{y}"
        plt.title(title)

        if xlabel:
            plt.xlabel(xlabel)
        if ylabel:
            plt.ylabel(ylabel)

        plt.xticks(rotation=45, ha="right")

        ax = plt.gca()
        xlabels = ax.get_xticklabels()
        new_labels = [
            label.get_text()[:30] + "..." if len(label.get_text()) > 30 else label.get_text()
            for label in xlabels
        ]
        ax.set_xticks(ax.get_xticks())
        ax.set_xticklabels(new_labels, rotation=45, ha="right")

        plt.tight_layout()

        # Создаем папку для графиков если её нет
        charts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "charts")
        os.makedirs(charts_dir, exist_ok=True)

        filename = f"plot_{uuid.uuid4()}.png"
        filepath = os.path.join(charts_dir, filename)
        plt.savefig(filepath)
        plt.close()

        logger.info(f"Chart saved locally: {filename}")
        
        # Пытаемся загрузить в S3
        s3_url = upload_to_s3(filepath, filename)
        if s3_url:
            # Возвращаем S3 URL
            return f"CHART_GENERATED:{filename}|{s3_url}"
        else:
            # Fallback на локальный путь
            return f"CHART_GENERATED:{filename}"
    except Exception as e:
        logger.error(f"Plotting Error: {str(e)}", exc_info=True)
        return f"Plotting Error: {str(e)}"
