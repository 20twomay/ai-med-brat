"""
Модуль для работы с авторизацией
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import jwt
from config import get_settings
from core.constants import MAX_PASSWORD_LENGTH_BYTES
from core.database import get_sync_engine
from core.exceptions import InvalidCredentialsError, ResourceAlreadyExistsError, UnauthorizedError
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from models import User
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Схема безопасности для Bearer токена
security = HTTPBearer()

# Контекст для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_db_session():
    """
    Dependency для получения сессии базы данных.
    Использует yield pattern для автоматического закрытия сессии.
    """
    engine = get_sync_engine()
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()


def hash_password(password: str) -> str:
    """
    Хеширует пароль с учетом ограничения bcrypt в 72 байта.
    
    Args:
        password: Пароль для хеширования
        
    Returns:
        Хешированный пароль
    """
    # Bcrypt имеет ограничение в 72 байта
    password_bytes = password.encode('utf-8')[:MAX_PASSWORD_LENGTH_BYTES]
    # Декодируем обратно в строку, игнорируя возможные ошибки на границе UTF-8 символов
    truncated_password = password_bytes.decode('utf-8', errors='ignore')
    return pwd_context.hash(truncated_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверяет пароль с учетом ограничения bcrypt в 72 байта.
    
    Args:
        plain_password: Пароль для проверки
        hashed_password: Хешированный пароль для сравнения
        
    Returns:
        True если пароль совпадает, иначе False
    """
    # Bcrypt имеет ограничение в 72 байта
    # Обрезаем пароль так же, как при хешировании
    password_bytes = plain_password.encode('utf-8')[:MAX_PASSWORD_LENGTH_BYTES]
    truncated_password = password_bytes.decode('utf-8', errors='ignore')
    return pwd_context.verify(truncated_password, hashed_password)


def create_access_token(user_id: int, email: str) -> str:
    """Создает JWT токен"""
    settings = get_settings()
    expire = datetime.utcnow() + timedelta(days=settings.auth_access_token_expire_days)
    to_encode = {
        "sub": str(user_id),
        "email": email,
        "exp": expire
    }
    encoded_jwt = jwt.encode(to_encode, settings.auth_secret_key, algorithm=settings.auth_algorithm)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Декодирует JWT токен"""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.auth_secret_key, algorithms=[settings.auth_algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        return None
    except jwt.JWTError as e:
        logger.warning(f"JWT decode error: {e}")
        return None


def create_user(db: Session, email: str, password: str) -> User:
    """
    Создает нового пользователя в базе данных.
    
    Args:
        db: Сессия базы данных
        email: Email пользователя
        password: Пароль пользователя
        
    Returns:
        Созданный пользователь
        
    Raises:
        ValueError: Если пользователь с таким email уже существует
    """
    # Проверяем, существует ли пользователь с таким email
    existing_user = db.execute(
        select(User).where(User.email == email)
    ).scalar_one_or_none()
    
    if existing_user:
        raise ResourceAlreadyExistsError("User", email)
    
    # Хешируем пароль и создаем пользователя
    hashed_password = hash_password(password)
    user = User(
        email=email,
        hashed_password=hashed_password,
        created_at=datetime.utcnow()
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    logger.info(f"Created user: {user.email} (ID: {user.id})")
    return user


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """
    Аутентифицирует пользователя по email и паролю.
    
    Args:
        db: Сессия базы данных
        email: Email пользователя
        password: Пароль пользователя
        
    Returns:
        Пользователь, если аутентификация успешна, иначе None
    """
    user = db.execute(
        select(User).where(User.email == email, User.is_active == True)
    ).scalar_one_or_none()
    
    if not user:
        return None
    
    if not verify_password(password, user.hashed_password):
        return None
    
    return user


def verify_token(token: str, db: Session) -> Optional[User]:
    """
    Проверяет JWT токен и возвращает пользователя.
    
    Args:
        token: JWT токен для проверки
        db: Сессия базы данных
        
    Returns:
        Пользователь, если токен валиден, иначе None
        
    Note:
        Функция безопасно обрабатывает ошибки декодирования и не выбрасывает исключения
    """
    try:
        payload = decode_access_token(token)
        if not payload:
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            logger.warning("Token payload missing 'sub' claim")
            return None
        
        # Получаем пользователя
        user = db.execute(
            select(User).where(
                User.id == int(user_id),
                User.is_active == True,
            )
        ).scalar_one_or_none()
        
        if not user:
            logger.warning(f"User with id {user_id} not found or inactive")
        
        return user
    except (ValueError, TypeError) as e:
        logger.error(f"Error verifying token: {e}")
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db_session),
) -> User:
    """
    Dependency для получения текущего пользователя из JWT токена.
    
    Args:
        credentials: Bearer токен из заголовка Authorization
        db: Сессия базы данных
        
    Returns:
        Текущий пользователь
        
    Raises:
        HTTPException: Если токен невалиден
    """
    token = credentials.credentials
    user = verify_token(token, db)
    
    if not user:
        raise UnauthorizedError("Invalid or expired token")
    
    return user
