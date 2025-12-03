import ast
import os
import uuid
from typing import Any, Optional

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
DATABASE_URL = os.getenv("DATABASE_URL")


def get_db_engine():
    url = DATABASE_URL
    return create_engine(url)


class ExecuteSQLInput(BaseModel):
    query: str = Field(description="SQL query to execute")


@tool(args_schema=ExecuteSQLInput)
def execute_sql_tool(query: str) -> list[dict[str, Any]] | str:
    """Выполняет SQL запрос и возвращает результат как список словарей."""
    try:
        engine = get_db_engine()
        if "limit" not in query.lower():
            query = query.rstrip(";") + " LIMIT 25;"

        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn)

        if df.empty:
            return "Query executed successfully but returned no results."

        return df.to_dict(orient="records")
    except Exception as e:
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

        # Возвращаем только имя файла для API
        return f"CHART_GENERATED:{filename}"
    except Exception as e:
        return f"Plotting Error: {str(e)}"
