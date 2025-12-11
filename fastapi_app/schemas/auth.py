"""
Схемы для авторизации и работы с пользователями
"""

import re
from datetime import datetime
from typing import Optional

from core.constants import (
    MAX_EMAIL_LENGTH,
    MAX_PASSWORD_LENGTH_BYTES,
    MAX_PASSWORD_LENGTH_CHARS,
    MIN_EMAIL_LENGTH,
    MIN_PASSWORD_LENGTH,
)
from pydantic import BaseModel, Field, field_validator


class UserRegister(BaseModel):
    """Схема для регистрации нового пользователя"""

    email: str = Field(
        ...,
        min_length=MIN_EMAIL_LENGTH,
        max_length=MAX_EMAIL_LENGTH,
        description="Email пользователя"
    )
    password: str = Field(
        ...,
        min_length=MIN_PASSWORD_LENGTH,
        max_length=MAX_PASSWORD_LENGTH_CHARS,
        description="Пароль"
    )

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Простая валидация email через регулярное выражение"""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError('Invalid email format')
        return v.lower().strip()

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Валидация пароля с учетом ограничения bcrypt"""
        password_bytes = v.encode('utf-8')
        if len(password_bytes) > MAX_PASSWORD_LENGTH_BYTES:
            raise ValueError(f'Password cannot be longer than {MAX_PASSWORD_LENGTH_BYTES} bytes')
        return v


class UserLogin(BaseModel):
    """Схема для входа пользователя"""

    email: str = Field(
        ...,
        min_length=MIN_EMAIL_LENGTH,
        max_length=MAX_EMAIL_LENGTH,
        description="Email пользователя"
    )
    password: str = Field(
        ...,
        min_length=MIN_PASSWORD_LENGTH,
        max_length=MAX_PASSWORD_LENGTH_CHARS,
        description="Пароль"
    )

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Простая валидация email через регулярное выражение"""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError('Invalid email format')
        return v.lower().strip()


class UserResponse(BaseModel):
    """Схема ответа с информацией о пользователе"""

    id: int
    email: str
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Схема ответа с JWT токеном"""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse
