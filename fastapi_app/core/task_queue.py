import asyncio
import logging
from typing import Dict, Callable, Awaitable
from dataclasses import dataclass
from models.session import TaskType

logger = logging.getLogger(__name__)


@dataclass
class Task:
    """Задача для обработки"""
    session_id: str
    task_type: TaskType
    data: Dict


class TaskQueue:
    """Очередь задач на базе asyncio.Queue"""

    def __init__(self):
        self.router_queue: asyncio.Queue = asyncio.Queue()
        self.query_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._workers: list[asyncio.Task] = []

    async def start_workers(
        self,
        router_handler: Callable[[Task], Awaitable[None]],
        query_handler: Callable[[Task], Awaitable[None]],
        num_router_workers: int = 2,
        num_query_workers: int = 3,
    ):
        """
        Запускает воркеры для обработки задач

        Args:
            router_handler: Функция для обработки router задач
            query_handler: Функция для обработки query задач
            num_router_workers: Количество router воркеров
            num_query_workers: Количество query воркеров
        """
        if self._running:
            logger.warning("Workers already running")
            return

        self._running = True
        logger.info(
            f"Starting {num_router_workers} router workers and {num_query_workers} query workers"
        )

        # Запускаем router воркеры
        for i in range(num_router_workers):
            worker = asyncio.create_task(
                self._worker(f"router-{i}", self.router_queue, router_handler)
            )
            self._workers.append(worker)

        # Запускаем query воркеры
        for i in range(num_query_workers):
            worker = asyncio.create_task(
                self._worker(f"query-{i}", self.query_queue, query_handler)
            )
            self._workers.append(worker)

        logger.info(f"Started {len(self._workers)} workers")

    async def _worker(
        self,
        name: str,
        queue: asyncio.Queue,
        handler: Callable[[Task], Awaitable[None]],
    ):
        """Воркер для обработки задач из очереди"""
        logger.info(f"Worker {name} started")

        while self._running:
            try:
                # Ждём задачу с таймаутом, чтобы можно было проверить _running
                try:
                    task = await asyncio.wait_for(queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                logger.info(
                    f"Worker {name} processing task for session {task.session_id}"
                )

                try:
                    await handler(task)
                    logger.info(
                        f"Worker {name} completed task for session {task.session_id}"
                    )
                except Exception as e:
                    logger.error(
                        f"Worker {name} error processing task {task.session_id}: {e}",
                        exc_info=True,
                    )
                finally:
                    queue.task_done()

            except Exception as e:
                logger.error(f"Worker {name} unexpected error: {e}", exc_info=True)

        logger.info(f"Worker {name} stopped")

    async def submit_task(self, task: Task):
        """Добавляет задачу в очередь"""
        if task.task_type == TaskType.ROUTER:
            await self.router_queue.put(task)
            logger.info(
                f"Submitted router task for session {task.session_id} (queue size: {self.router_queue.qsize()})"
            )
        elif task.task_type == TaskType.QUERY:
            await self.query_queue.put(task)
            logger.info(
                f"Submitted query task for session {task.session_id} (queue size: {self.query_queue.qsize()})"
            )
        else:
            raise ValueError(f"Unknown task type: {task.task_type}")

    async def stop_workers(self):
        """Останавливает всех воркеров"""
        if not self._running:
            return

        logger.info("Stopping workers...")
        self._running = False

        # Ждём завершения всех воркеров
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
            self._workers.clear()

        logger.info("All workers stopped")

    def get_queue_size(self, task_type: TaskType) -> int:
        """Возвращает размер очереди"""
        if task_type == TaskType.ROUTER:
            return self.router_queue.qsize()
        elif task_type == TaskType.QUERY:
            return self.query_queue.qsize()
        return 0