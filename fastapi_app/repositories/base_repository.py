"""
Базовый репозиторий с общими операциями
"""

import logging
from typing import Generic, List, Optional, Type, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Type variable для Generic репозитория
T = TypeVar("T")


class BaseRepository(Generic[T]):
    """
    Базовый репозиторий с общими CRUD операциями.

    Использует Generic для типизации и переиспользования кода.

    Example:
        >>> class UserRepository(BaseRepository[User]):
        ...     def __init__(self, db: Session):
        ...         super().__init__(db, User)
    """

    def __init__(self, db: Session, model: Type[T]):
        """
        Args:
            db: SQLAlchemy сессия
            model: Класс модели SQLAlchemy
        """
        self.db = db
        self.model = model

    def get_by_id(self, id: int) -> Optional[T]:
        """
        Получить объект по ID.

        Args:
            id: Идентификатор объекта

        Returns:
            Объект модели или None если не найден
        """
        return self.db.execute(
            select(self.model).where(self.model.id == id)
        ).scalar_one_or_none()

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[dict] = None,
    ) -> List[T]:
        """
        Получить все объекты с пагинацией и фильтрами.

        Args:
            skip: Количество пропускаемых записей
            limit: Максимальное количество записей
            filters: Словарь фильтров {column_name: value}

        Returns:
            Список объектов модели
        """
        query = select(self.model)

        # Применяем фильтры
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.where(getattr(self.model, key) == value)
                else:
                    logger.warning(
                        f"Filter key '{key}' not found in model {self.model.__name__}"
                    )

        # Применяем пагинацию
        query = query.offset(skip).limit(limit)

        return self.db.execute(query).scalars().all()

    def count(self, filters: Optional[dict] = None) -> int:
        """
        Подсчитать количество объектов с фильтрами.

        Args:
            filters: Словарь фильтров {column_name: value}

        Returns:
            Количество объектов
        """
        query = select(func.count()).select_from(self.model)

        # Применяем фильтры
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.where(getattr(self.model, key) == value)

        return self.db.execute(query).scalar()

    def create(self, **kwargs) -> T:
        """
        Создать новый объект.

        Args:
            **kwargs: Параметры для создания объекта

        Returns:
            Созданный объект

        Note:
            Использует flush() вместо commit() для гибкости транзакций
        """
        obj = self.model(**kwargs)
        self.db.add(obj)
        self.db.flush()
        self.db.refresh(obj)

        logger.debug(
            f"Created {self.model.__name__}",
            extra={"model": self.model.__name__, "id": obj.id if hasattr(obj, "id") else None},
        )
        return obj

    def update(self, obj: T, **kwargs) -> T:
        """
        Обновить объект.

        Args:
            obj: Объект для обновления
            **kwargs: Поля для обновления

        Returns:
            Обновлённый объект

        Note:
            Использует flush() вместо commit() для гибкости транзакций
        """
        for key, value in kwargs.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
            else:
                logger.warning(
                    f"Update key '{key}' not found in model {self.model.__name__}"
                )

        self.db.flush()
        self.db.refresh(obj)

        logger.debug(
            f"Updated {self.model.__name__}",
            extra={"model": self.model.__name__, "id": obj.id if hasattr(obj, "id") else None},
        )
        return obj

    def delete(self, obj: T) -> None:
        """
        Удалить объект (hard delete).

        Args:
            obj: Объект для удаления

        Note:
            Использует flush() вместо commit() для гибкости транзакций
        """
        self.db.delete(obj)
        self.db.flush()

        logger.debug(
            f"Deleted {self.model.__name__}",
            extra={"model": self.model.__name__},
        )

    def soft_delete(self, obj: T) -> T:
        """
        Мягкое удаление объекта (установка is_active=False).

        Args:
            obj: Объект для удаления

        Returns:
            Обновлённый объект

        Raises:
            AttributeError: Если модель не имеет поля is_active

        Note:
            Использует flush() вместо commit() для гибкости транзакций
        """
        if not hasattr(obj, "is_active"):
            raise AttributeError(
                f"Model {self.model.__name__} does not have 'is_active' field"
            )

        obj.is_active = False
        self.db.flush()
        self.db.refresh(obj)

        logger.debug(
            f"Soft deleted {self.model.__name__}",
            extra={"model": self.model.__name__, "id": obj.id if hasattr(obj, "id") else None},
        )
        return obj

    def exists(self, id: int) -> bool:
        """
        Проверить существование объекта по ID.

        Args:
            id: Идентификатор объекта

        Returns:
            True если объект существует, иначе False
        """
        return self.db.execute(
            select(func.count()).select_from(self.model).where(self.model.id == id)
        ).scalar() > 0