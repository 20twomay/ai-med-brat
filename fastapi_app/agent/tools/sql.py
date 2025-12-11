"""
SQL инструмент для выполнения запросов к базе данных
"""

import asyncio
import io
import logging
import uuid

import pandas as pd
from config import get_settings
from core import DatabaseError, get_storage_client, get_sync_engine
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
from sqlalchemy import text

logger = logging.getLogger(__name__)


class ExecuteSQLInput(BaseModel):
    """Входные параметры для SQL инструмента"""

    query: str = Field(description="SQL запрос для выполнения")


@tool(args_schema=ExecuteSQLInput)
async def execute_sql_tool(query: str, config: RunnableConfig = None) -> str:
    """
    Выполняет SQL запрос к PostgreSQL и сохраняет результат в MinIO.

    Args:
        query: SQL запрос для выполнения
        config: Конфигурация с thread_id

    Returns:
        Строка с первыми 25 строками результата и путём к файлу в MinIO

    Raises:
        DatabaseError: При ошибке выполнения SQL запроса
    """
    chat_id = config["configurable"]["thread_id"]  # chat_id передается как thread_id
    settings = get_settings()

    try:
        engine = get_sync_engine()

        # Выполняем SQL запрос асинхронно
        def run_query():
            with engine.connect() as conn:
                return pd.read_sql(text(query), conn)

        df = await asyncio.to_thread(run_query)

        if df.empty:
            return "Query executed successfully but returned no results."

        # Сохраняем результат в MinIO
        csv_buffer = io.BytesIO()
        df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        object_name = f"{chat_id}/df_{uuid.uuid4()}.csv"

        client = get_storage_client()
        await asyncio.to_thread(
            client.put_object,
            bucket_name=settings.s3_bucket,
            object_name=object_name,
            data=csv_buffer,
            length=csv_buffer.getbuffer().nbytes,
            content_type="text/csv",
        )

        logger.info(f"SQL query executed successfully. Saved to: {object_name}")
        return f"First 25 rows:\n{df.head(25)}\n\nShape: {df.shape}\nFile saved to MinIO at '{object_name}'"

    except Exception as e:
        logger.error(f"SQL execution failed: {str(e)}", exc_info=True)
        raise DatabaseError(f"SQL execution failed: {str(e)}")
