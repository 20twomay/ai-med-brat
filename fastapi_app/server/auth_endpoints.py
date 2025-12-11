"""
Эндпоинты для авторизации и управления пользователями
"""

import logging

from core.auth import (
    authenticate_user,
    create_access_token,
    create_user,
    get_current_user,
    get_db_session,
)
from core.exceptions import InvalidCredentialsError, ResourceAlreadyExistsError
from fastapi import APIRouter, Depends, HTTPException, status
from models import User
from schemas.auth import (
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserRegister,
    db: Session = Depends(get_db_session),
):
    """
    Регистрирует нового пользователя и возвращает JWT токен.
    
    Args:
        user_data: Email и пароль для регистрации
        db: Сессия базы данных
        
    Returns:
        JWT токен и информация о пользователе
    """
    logger.info(f"Registration request for email: {user_data.email}")
    
    # Создаем пользователя (ResourceAlreadyExistsError будет обработан error handler)
    user = create_user(db, email=user_data.email, password=user_data.password)
    logger.info(f"User registered successfully: {user.email} (ID: {user.id})")
    
    # Создаем JWT токен
    access_token = create_access_token(user.id, user.email)
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.post("/login", response_model=TokenResponse)
async def login_user(
    user_data: UserLogin,
    db: Session = Depends(get_db_session),
):
    """
    Аутентифицирует пользователя и возвращает JWT токен.
    
    Args:
        user_data: Email и пароль для входа
        db: Сессия базы данных
        
    Returns:
        JWT токен и информация о пользователе
    """
    logger.info(f"Login request for email: {user_data.email}")
    
    # Аутентифицируем пользователя
    user = authenticate_user(db, email=user_data.email, password=user_data.password)
    
    if not user:
        logger.warning(f"Authentication failed for email: {user_data.email}")
        raise InvalidCredentialsError("Invalid email or password")
    
    logger.info(f"User logged in successfully: {user.email} (ID: {user.id})")
    
    # Создаем JWT токен
    access_token = create_access_token(user.id, user.email)
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """
    Получает информацию о текущем пользователе по JWT токену.
    
    Args:
        current_user: Текущий авторизованный пользователь
        
    Returns:
        Информация о пользователе
    """
    logger.info(f"[ME] User info requested: id={current_user.id}, email={current_user.email}")
    return UserResponse.model_validate(current_user)
