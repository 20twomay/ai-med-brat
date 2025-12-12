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


class GetDataFrameHeadInput(BaseModel):
    df_filename: str = Field(description="Имя CSV файла с данными")
    n_rows: int = Field(description="Количество строк для отображения", default=5)


class GetDataFrameHeadInputOutput(BaseModel):
    success: bool = Field(description="Флаг успешного выполнения запроса")
    result: str = Field(description="Первые n_rows строк DataFrame в виде строки")


@tool(args_schema=GetDataFrameHeadInput)
async def get_dataframe_head(
    df_filename: str, n_rows: int = 5, config: RunnableConfig = None
) -> str:
    """
    Показывает первые n_rows строк содержимого CSV файла с данными.
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

        head_df = df.head(n_rows)
        result_str = head_df.to_string(index=False)
        output = GetDataFrameHeadInputOutput(
            success=True,
            result=result_str,
        )
        return output.model_dump_json(indent=2)
    except Exception:
        logger.exception("Failed to get DataFrame head")
        output = GetDataFrameHeadInputOutput(
            success=False,
            result="Error retrieving DataFrame head.",
        )
        return output.model_dump_json(indent=2)


class GetDataFrameTailInput(BaseModel):
    df_filename: str = Field(description="Имя CSV файла с данными")
    n_rows: int = Field(description="Количество строк для отображения", default=5)


class GetDataFrameTailInputOutput(BaseModel):
    success: bool = Field(description="Флаг успешного выполнения запроса")
    result: str = Field(description="Первые n_rows строк DataFrame в виде строки")


@tool(args_schema=GetDataFrameTailInput)
async def get_dataframe_tail(
    df_filename: str, n_rows: int = 5, config: RunnableConfig = None
) -> str:
    """
    Показывает последние n_rows строк содержимого CSV файла с данными.
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

        tail_df = df.tail(n_rows)
        result_str = tail_df.to_string(index=False)
        output = GetDataFrameTailInputOutput(
            success=True,
            result=result_str,
        )
        return output.model_dump_json(indent=2)
    except Exception:
        logger.exception("Failed to get DataFrame tail")
        output = GetDataFrameTailInputOutput(
            success=False,
            result="Error retrieving DataFrame tail.",
        )
        return output.model_dump_json(indent=2)


class CreateCustomDataFrameInput(BaseModel):
    df_filename: str = Field(description="Имя CSV файла с данными")
    df_as_dict: list[dict[str, str]] = Field(
        description="Данные для создания DataFrame в виде списка словарей"
    )


class CreateCustomDataFrameOutput(BaseModel):
    success: bool = Field(description="Флаг успешного выполнения запроса")
    result: str = Field(description="Результат создания DataFrame")
    result_filename: str = Field(description="Имя созданного CSV файла")


@tool(args_schema=CreateCustomDataFrameInput)
async def create_custom_dataframe(
    df_filename: str, df_as_dict: list[dict[str, str]], config: RunnableConfig = None
) -> str:
    """
    Создаёт новый CSV файл с данными на основе переданного списка словарей.
    Использует pandas для создания DataFrame и сохраняет его как df_filename.
    """
    chat_id = config["configurable"]["thread_id"]
    settings = get_settings()
    client = get_storage_client()

    try:
        df = pd.DataFrame(df_as_dict)
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

        output = CreateCustomDataFrameOutput(
            success=True,
            result=f"Custom DataFrame created successfully. Saved as {filename}",
        )
        return output.model_dump_json(indent=2)
    except Exception:
        logger.exception("Failed to create custom DataFrame")
        output = CreateCustomDataFrameOutput(
            success=False,
            result="Error creating custom DataFrame.",
        )
        return output.model_dump_json(indent=2)
