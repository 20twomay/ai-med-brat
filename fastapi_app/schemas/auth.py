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
    """
    Схема для регистрации нового пользователя.

    Attributes:
        email: Email пользователя (должен быть валидным)
        password: Пароль (минимум 8 символов, должен содержать заглавные, строчные буквы и цифры)
    """

    email: str = Field(
        ...,
        min_length=MIN_EMAIL_LENGTH,
        max_length=MAX_EMAIL_LENGTH,
        description="Email пользователя",
        examples=["doctor@medbrat.ai"],
    )
    password: str = Field(
        ...,
        min_length=MIN_PASSWORD_LENGTH,
        max_length=MAX_PASSWORD_LENGTH_CHARS,
        description="Пароль (минимум 8 символов, должен содержать заглавные, строчные буквы и цифры)",
        examples=["SecurePassword123!"],
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """
        Валидация email через регулярное выражение.

        Returns:
            Нормализованный email (lowercase, без пробелов)

        Raises:
            ValueError: Если email невалидный
        """
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, v):
            raise ValueError("Невалидный формат email")
        return v.lower().strip()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """
        Валидация надёжности пароля.

        Требования:
        - Минимум одна заглавная буква
        - Минимум одна строчная буква
        - Минимум одна цифра
        - Не более MAX_PASSWORD_LENGTH_BYTES байт (ограничение bcrypt)

        Returns:
            Валидированный пароль

        Raises:
            ValueError: Если пароль не соответствует требованиям
        """
        # Проверка на bcrypt ограничение
        password_bytes = v.encode("utf-8")
        if len(password_bytes) > MAX_PASSWORD_LENGTH_BYTES:
            raise ValueError(
                f"Пароль не может быть длиннее {MAX_PASSWORD_LENGTH_BYTES} байт"
            )

        # Проверка надёжности
        if not re.search(r"[A-Z]", v):
            raise ValueError("Пароль должен содержать хотя бы одну заглавную букву")
        if not re.search(r"[a-z]", v):
            raise ValueError("Пароль должен содержать хотя бы одну строчную букву")
        if not re.search(r"[0-9]", v):
            raise ValueError("Пароль должен содержать хотя бы одну цифру")

        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email": "doctor@medbrat.ai",
                    "password": "SecurePassword123!",
                }
            ]
        }
    }


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
