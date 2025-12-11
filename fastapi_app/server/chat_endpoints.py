"""
Эндпоинты для работы с чатами
"""

import logging
from datetime import datetime

from core.auth import get_current_user, get_db_session
from core.exceptions import ResourceNotFoundError
from fastapi import APIRouter, Depends, HTTPException, status
from models import Chat, User
from schemas.chat import ChatCreate, ChatListResponse, ChatResponse, ChatUpdate
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chats", tags=["Chats"])


@router.post("/", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def create_chat(
    chat_data: ChatCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """
    Создать новый чат для текущего пользователя.

    Args:
        chat_data: Данные для создания чата
        current_user: Текущий пользователь
        db: Сессия базы данных

    Returns:
        Созданный чат
    """
    logger.info(f"[CHAT] Creating new chat for user_id={current_user.id}, title='{chat_data.title}'")

    chat = Chat(
        user_id=current_user.id,
        title=chat_data.title or "Новый чат",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(chat)
    db.commit()
    db.refresh(chat)

    logger.info(f"[CHAT] Chat created: id={chat.id}")
    return ChatResponse.model_validate(chat)


@router.get("/", response_model=ChatListResponse)
async def get_chats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    skip: int = 0,
    limit: int = 100,
):
    """
    Получить список чатов текущего пользователя.

    Args:
        current_user: Текущий пользователь
        db: Сессия базы данных
        skip: Количество чатов для пропуска
        limit: Максимальное количество чатов

    Returns:
        Список чатов пользователя
    """
    logger.info(f"[CHAT] Getting chats for user_id={current_user.id}, skip={skip}, limit={limit}")

    # Получаем чаты пользователя, отсортированные по дате обновления
    query = (
        select(Chat)
        .where(Chat.user_id == current_user.id, Chat.is_active == True)
        .order_by(desc(Chat.updated_at))
        .offset(skip)
        .limit(limit)
    )
    chats = db.execute(query).scalars().all()

    # Считаем общее количество чатов
    total_query = select(Chat).where(Chat.user_id == current_user.id, Chat.is_active == True)
    total = len(db.execute(total_query).scalars().all())

    logger.info(f"[CHAT] Found {len(chats)} chats (total: {total})")
    return ChatListResponse(
        chats=[ChatResponse.model_validate(chat) for chat in chats],
        total=total,
    )


@router.get("/{chat_id}", response_model=ChatResponse)
async def get_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """
    Получить чат по ID.

    Args:
        chat_id: ID чата
        current_user: Текущий пользователь
        db: Сессия базы данных

    Returns:
        Информация о чате
    """
    logger.info(f"[CHAT] Getting chat id={chat_id} for user_id={current_user.id}")

    chat = db.execute(
        select(Chat).where(Chat.id == chat_id, Chat.user_id == current_user.id)
    ).scalar_one_or_none()

    if not chat:
        logger.error(f"[CHAT] Chat not found: id={chat_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found",
        )

    return ChatResponse.model_validate(chat)


@router.patch("/{chat_id}", response_model=ChatResponse)
async def update_chat(
    chat_id: int,
    chat_data: ChatUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """
    Обновить чат.

    Args:
        chat_id: ID чата
        chat_data: Данные для обновления
        current_user: Текущий пользователь
        db: Сессия базы данных

    Returns:
        Обновленный чат
    """
    logger.info(f"[CHAT] Updating chat id={chat_id} for user_id={current_user.id}")

    chat = db.execute(
        select(Chat).where(Chat.id == chat_id, Chat.user_id == current_user.id)
    ).scalar_one_or_none()

    if not chat:
        logger.error(f"[CHAT] Chat not found: id={chat_id}")
        raise ResourceNotFoundError("Chat", chat_id)

    # Обновляем поля
    if chat_data.title is not None:
        chat.title = chat_data.title
    if chat_data.is_active is not None:
        chat.is_active = chat_data.is_active

    chat.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(chat)

    logger.info(f"[CHAT] Chat updated: id={chat.id}")
    return ChatResponse.model_validate(chat)


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """
    Удалить чат (мягкое удаление).

    Args:
        chat_id: ID чата
        current_user: Текущий пользователь
        db: Сессия базы данных
    """
    logger.info(f"[CHAT] Deleting chat id={chat_id} for user_id={current_user.id}")

    chat = db.execute(
        select(Chat).where(Chat.id == chat_id, Chat.user_id == current_user.id)
    ).scalar_one_or_none()

    if not chat:
        logger.error(f"[CHAT] Chat not found: id={chat_id}")
        raise ResourceNotFoundError("Chat", chat_id)

    # Мягкое удаление
    chat.is_active = False
    chat.updated_at = datetime.utcnow()
    db.commit()

    logger.info(f"[CHAT] Chat deleted: id={chat.id}")