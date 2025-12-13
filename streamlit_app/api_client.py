"""Централизованный API клиент для взаимодействия с backend."""

import logging
from typing import Any, Dict, Optional

import requests

from config import app_config
from constants import (
    DEFAULT_API_TIMEOUT,
    DEFAULT_MAX_RETRIES,
    ENDPOINT_AUTH_LOGIN,
    ENDPOINT_AUTH_ME,
    ENDPOINT_AUTH_REGISTER,
    ENDPOINT_CHATS,
    ENDPOINT_EXECUTE,
    ENDPOINT_HEALTH,
    HEALTH_CHECK_TIMEOUT,
    HTTP_CREATED,
    HTTP_NO_CONTENT,
    HTTP_OK,
)

logger = logging.getLogger(__name__)


class APIClient:
    """Клиент для взаимодействия с FastAPI backend."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: int = DEFAULT_API_TIMEOUT,
    ) -> None:
        """
        Инициализация API клиента.
        
        Args:
            base_url: Базовый URL API (по умолчанию из конфигурации)
            timeout: Таймаут запросов в секундах
        """
        self.base_url = base_url or app_config.api_url
        self.timeout = timeout
        self.token: Optional[str] = None

    def set_token(self, token: str) -> None:
        """Установить токен авторизации"""
        self.token = token

    def clear_token(self) -> None:
        """Очистить токен авторизации"""
        self.token = None

    def _get_headers(self) -> Dict[str, str]:
        """Получить заголовки для запроса"""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _handle_response(
        self,
        response: requests.Response,
    ) -> Optional[Dict[str, Any]]:
        """
        Обработка ответа от сервера.
        
        Args:
            response: Ответ от сервера
            
        Returns:
            JSON данные или None в случае ошибки
        """
        if response.status_code in (HTTP_OK, HTTP_CREATED):
            try:
                return response.json()
            except ValueError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                return None
        
        logger.error(
            f"API request failed with status {response.status_code}: "
            f"{response.text[:200]}"
        )
        return None

    def register(
        self,
        email: str,
        password: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Регистрация нового пользователя.
        
        Args:
            email: Email пользователя
            password: Пароль
            
        Returns:
            Данные пользователя и токен или None в случае ошибки
        """
        try:
            response = requests.post(
                f"{self.base_url}{ENDPOINT_AUTH_REGISTER}",
                json={"email": email, "password": password},
                timeout=self.timeout,
            )
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            logger.error(f"Registration failed: {e}")
            return None

    def login(
        self,
        email: str,
        password: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Вход пользователя.
        
        Args:
            email: Email пользователя
            password: Пароль
            
        Returns:
            Данные пользователя и токен или None в случае ошибки
        """
        try:
            response = requests.post(
                f"{self.base_url}{ENDPOINT_AUTH_LOGIN}",
                json={"email": email, "password": password},
                timeout=self.timeout,
            )
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            logger.error(f"Login failed: {e}")
            return None

    def execute_query(
        self,
        query: str,
        chat_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Выполнение анализа данных.

        Args:
            query: Запрос пользователя
            chat_id: ID чата (опционально)

        Returns:
            Результат анализа или None в случае ошибки
        """
        try:
            payload: Dict[str, Any] = {"query": query}
            if chat_id:
                payload["chat_id"] = chat_id

            response = requests.post(
                f"{self.base_url}{ENDPOINT_EXECUTE}",
                json=payload,
                headers=self._get_headers(),
                timeout=None,  # Запросы могут быть долгими
            )
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            logger.error(f"Execute query failed: {e}")
            return None

    def execute_query_with_retry(
        self,
        query: str,
        chat_id: Optional[int] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> Optional[Dict[str, Any]]:
        """
        Выполнить запрос к API с механизмом повторных попыток при пустом ответе.

        Args:
            query: Запрос пользователя
            chat_id: ID чата (опционально)
            max_retries: Максимальное количество попыток

        Returns:
            Ответ от API или None в случае неудачи после всех попыток
        """
        for attempt in range(max_retries):
            logger.info(f"[RETRY] Attempt {attempt + 1}/{max_retries} for query execution")

            # Выполняем запрос
            response = self.execute_query(query=query, chat_id=chat_id)

            # Проверяем что ответ существует и не пустой
            if response:
                result_content = response.get("result", "")

                # Проверяем что result не пустой
                if result_content and result_content.strip():
                    logger.info(f"[RETRY] Successful response on attempt {attempt + 1}")
                    return response
                else:
                    logger.warning(f"[RETRY] Empty result content on attempt {attempt + 1}, response: {response}")
            else:
                logger.warning(f"[RETRY] No response on attempt {attempt + 1}")

            # Если это не последняя попытка, продолжаем
            if attempt < max_retries - 1:
                logger.info(f"[RETRY] Retrying... ({attempt + 2}/{max_retries})")

        # Все попытки исчерпаны
        logger.error(f"[RETRY] All {max_retries} attempts failed")
        return None

    def get_health(self) -> Optional[Dict[str, Any]]:
        """
        Проверка состояния API.
        
        Returns:
            Статус сервисов или None в случае ошибки
        """
        try:
            response = requests.get(
                f"{self.base_url}{ENDPOINT_HEALTH}",
                timeout=HEALTH_CHECK_TIMEOUT,
            )
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            logger.error(f"Health check failed: {e}")
            return None

    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """
        Получение информации о текущем пользователе.
        
        Returns:
            Информация о пользователе или None в случае ошибки
        """
        try:
            response = requests.get(
                f"{self.base_url}{ENDPOINT_AUTH_ME}",
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            logger.error(f"Get user info failed: {e}")
            return None

    def get_chats(
        self,
        skip: int = 0,
        limit: int = app_config.default_chats_limit,
    ) -> Optional[Dict[str, Any]]:
        """
        Получение списка чатов текущего пользователя.
        
        Args:
            skip: Количество чатов для пропуска
            limit: Максимальное количество чатов
            
        Returns:
            Список чатов или None в случае ошибки
        """
        try:
            response = requests.get(
                f"{self.base_url}{ENDPOINT_CHATS}",
                params={"skip": skip, "limit": limit},
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            logger.error(f"Get chats failed: {e}")
            return None

    def create_chat(self, title: str = "Новый чат") -> Optional[Dict[str, Any]]:
        """
        Создание нового чата.
        
        Args:
            title: Название чата
            
        Returns:
            Созданный чат или None в случае ошибки
        """
        try:
            response = requests.post(
                f"{self.base_url}{ENDPOINT_CHATS}",
                json={"title": title},
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            logger.error(f"Create chat failed: {e}")
            return None

    def delete_chat(self, chat_id: int) -> bool:
        """
        Удаление чата.
        
        Args:
            chat_id: ID чата для удаления
            
        Returns:
            True если успешно, иначе False
        """
        try:
            response = requests.delete(
                f"{self.base_url}{ENDPOINT_CHATS}/{chat_id}",
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            return response.status_code == HTTP_NO_CONTENT
        except requests.exceptions.RequestException as e:
            logger.error(f"Delete chat failed: {e}")
            return False

    def get_chat_messages(
        self,
        chat_id: int,
        skip: int = 0,
        limit: int = app_config.default_messages_limit,
    ) -> Optional[Dict[str, Any]]:
        """
        Получение истории сообщений чата.
        
        Args:
            chat_id: ID чата
            skip: Количество сообщений для пропуска
            limit: Максимальное количество сообщений
            
        Returns:
            Список сообщений или None в случае ошибки
        """
        try:
            response = requests.get(
                f"{self.base_url}{ENDPOINT_CHATS}/{chat_id}/messages",
                params={"skip": skip, "limit": limit},
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            logger.error(f"Get chat messages failed: {e}")
            return None
