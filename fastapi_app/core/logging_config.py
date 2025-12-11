"""
Конфигурация структурированного логирования
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """
    Форматтер для структурированных JSON логов.

    Преимущества:
    - Легко парсится автоматическими системами мониторинга
    - Содержит структурированную информацию
    - Поддерживает дополнительные поля через extra
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Форматирует лог запись в JSON.

        Args:
            record: Лог запись

        Returns:
            JSON строка
        """
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Добавляем дополнительные поля из extra
        if hasattr(record, "__dict__"):
            for key, value in record.__dict__.items():
                if key not in [
                    "name",
                    "msg",
                    "args",
                    "created",
                    "filename",
                    "funcName",
                    "levelname",
                    "levelno",
                    "lineno",
                    "module",
                    "msecs",
                    "message",
                    "pathname",
                    "process",
                    "processName",
                    "relativeCreated",
                    "thread",
                    "threadName",
                    "exc_info",
                    "exc_text",
                    "stack_info",
                ]:
                    log_data[key] = value

        # Добавляем информацию об исключении если есть
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Добавляем stack info если есть
        if record.stack_info:
            log_data["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(log_data, ensure_ascii=False, default=str)


class ColoredFormatter(logging.Formatter):
    """
    Форматтер с цветным выводом для консоли (для разработки).
    """

    # ANSI цветовые коды
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """
        Форматирует лог запись с цветами.

        Args:
            record: Лог запись

        Returns:
            Форматированная строка с цветами
        """
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logging(
    level: str = "INFO",
    json_logs: bool = False,
    log_file: str = None,
) -> None:
    """
    Настройка логирования для приложения.

    Args:
        level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: Использовать JSON формат (для production)
        log_file: Путь к файлу логов (опционально)

    Example:
        >>> setup_logging(level="DEBUG", json_logs=False)
        >>> logger = logging.getLogger(__name__)
        >>> logger.info("Test message", extra={"user_id": 123})
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Удаляем существующие handlers
    root_logger.handlers = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    if json_logs:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(
            ColoredFormatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root_logger.addHandler(console_handler)

    # File handler (опционально)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(JSONFormatter())  # Всегда JSON для файлов
        root_logger.addHandler(file_handler)

    # Настройка логирования для внешних библиотек
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    root_logger.info(
        "Logging configured",
        extra={
            "level": level,
            "json_logs": json_logs,
            "log_file": log_file,
        },
    )


def get_logger(name: str) -> logging.Logger:
    """
    Получает logger с заданным именем.

    Args:
        name: Имя logger (обычно __name__)

    Returns:
        Настроенный logger

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Hello", extra={"key": "value"})
    """
    return logging.getLogger(name)