"""
SQL инструмент для выполнения запросов к базе данных
"""

import asyncio
import io
import logging
import uuid
from typing import Optional

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


class ExecuteSQLOutput(BaseModel):
    """Выходные данные SQL инструмента"""

    success: bool = Field(description="Флаг успешного выполнения запроса")
    result_preview: str = Field(description="Предварительный просмотр первых 5 строк результата")
    result_meta: str = Field(description="Метаданные результата")
    result_filename: str = Field(description="Имя файла в S3 с полным результатом")


@tool(args_schema=ExecuteSQLInput)
async def execute_sql_tool(query: str, config: RunnableConfig = None) -> str:
    """
    Выполняет SQL запрос к PostgreSQL. Можно получить лишь 1 таблицу. Возваращет первые 5 строк результата и сохраняет df как csv.
    """
    chat_id = config["configurable"]["thread_id"]
    settings = get_settings()
    client = get_storage_client()

    try:
        engine = get_sync_engine()
        query = query.replace("CURRENT_DATE", "DATE '2025-02-18'")

        def run_query():
            with engine.connect() as conn:
                return pd.read_sql(text(query), conn)

        df = await asyncio.to_thread(run_query)

        if df.empty:
            result = ExecuteSQLOutput(
                success=True,
                result_preview="",
                result_meta="Empty result set",
                result_filename="",
            )
            logger.info("SQL query executed successfully")
            return result.model_dump_json(indent=2)

        # Сохраняем результат в S3
        csv_buffer = io.BytesIO()
        df.to_csv(csv_buffer, index=False)
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

        result = ExecuteSQLOutput(
            success=True,
            result_preview=df.head(5).to_string(),
            result_meta=str(df.shape),
            result_filename=filename,
        )
        logger.info(f"SQL query executed successfully. Result saved as {full_path}")
        return result.model_dump_json(indent=2)
    except Exception as e:
        result = ExecuteSQLOutput(
            success=False,
            result_preview="",
            result_meta=str(e),
            result_filename="",
        )
        logger.error(f"SQL execution failed: {str(e)}", exc_info=True)
        return result.model_dump_json(indent=2)
