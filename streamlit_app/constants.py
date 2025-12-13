"""Константы приложения."""

from typing import Final

# ===== HTTP STATUS CODES =====
HTTP_OK: Final[int] = 200
HTTP_CREATED: Final[int] = 201
HTTP_NO_CONTENT: Final[int] = 204
HTTP_BAD_REQUEST: Final[int] = 400
HTTP_UNAUTHORIZED: Final[int] = 401
HTTP_FORBIDDEN: Final[int] = 403
HTTP_NOT_FOUND: Final[int] = 404
HTTP_INTERNAL_SERVER_ERROR: Final[int] = 500

# ===== SESSION STATE KEYS =====
SESSION_AUTHENTICATED: Final[str] = "authenticated"
SESSION_TOKEN: Final[str] = "token"
SESSION_USER_INFO: Final[str] = "user_info"
SESSION_MESSAGES: Final[str] = "messages"
SESSION_CHAT_ID: Final[str] = "chat_id"
SESSION_THREAD_ID: Final[str] = "thread_id"
SESSION_TOTAL_TOKENS: Final[str] = "total_tokens"
SESSION_CONTEXT_LIMIT: Final[str] = "context_limit"
SESSION_MESSAGES_LOADED: Final[str] = "messages_loaded"
SESSION_TOKEN_CHECKED: Final[str] = "token_checked"
SESSION_LS_TOKEN: Final[str] = "ls_token"
SESSION_LS_TOKEN_LOADED: Final[str] = "ls_token_loaded"
SESSION_TOKEN_CHECK_ATTEMPTS: Final[str] = "token_check_attempts"
SESSION_SIDEBAR_COLLAPSED: Final[str] = "sidebar_collapsed"
SESSION_SHOW_PROFILE_MODAL: Final[str] = "show_profile_modal"

# ===== LOCALSTORAGE KEYS =====
LOCALSTORAGE_AUTH_TOKEN_KEY: Final[str] = "auth_token"

# ===== PASSWORD VALIDATION =====
MIN_PASSWORD_LENGTH: Final[int] = 6
MAX_PASSWORD_LENGTH_BYTES: Final[int] = 72

# ===== RETRY CONFIGURATION =====
DEFAULT_MAX_RETRIES: Final[int] = 3
MAX_TOKEN_CHECK_ATTEMPTS: Final[int] = 3

# ===== CONTEXT LIMITS =====
DEFAULT_CONTEXT_LIMIT: Final[int] = 256000

# ===== PAGINATION =====
DEFAULT_CHATS_LIMIT: Final[int] = 100
DEFAULT_MESSAGES_LIMIT: Final[int] = 100

# ===== TIMEOUTS =====
DEFAULT_API_TIMEOUT: Final[int] = 60
HEALTH_CHECK_TIMEOUT: Final[int] = 5

# ===== TOKEN VALIDATION =====
MIN_TOKEN_LENGTH: Final[int] = 10

# ===== UI MESSAGES =====
MSG_LOGIN_SUCCESS: Final[str] = "✅ Добро пожаловать, {email}!"
MSG_LOGIN_ERROR: Final[str] = "❌ Неверный email или пароль"
MSG_REGISTER_SUCCESS: Final[str] = "✅ Аккаунт создан! Добро пожаловать, {email}!"
MSG_REGISTER_ERROR: Final[str] = "❌ Ошибка регистрации. Возможно, email уже используется"
MSG_EMPTY_FIELDS: Final[str] = "❌ Заполните все поля"
MSG_PASSWORDS_MISMATCH: Final[str] = "❌ Пароли не совпадают"
MSG_AUTH_REQUIRED: Final[str] = "⚠️ Пожалуйста, войдите в систему"
MSG_CHAT_CREATE_ERROR: Final[str] = "Не удалось создать чат"
MSG_CHATS_LOAD_ERROR: Final[str] = "Не удалось загрузить список чатов"
MSG_NO_CHATS_YET: Final[str] = "У вас пока нет чатов. Создайте новый!"
MSG_API_ERROR: Final[str] = "❌ Не удалось получить ответ от сервера после {retries} попыток. Попробуйте переформулировать вопрос или повторить запрос позже."

# ===== ROLES =====
ROLE_USER: Final[str] = "user"
ROLE_ASSISTANT: Final[str] = "assistant"

# ===== ARTIFACT TYPES =====
ARTIFACT_TYPE_CHART: Final[str] = "chart"
ARTIFACT_TYPE_CSV: Final[str] = "csv"

# ===== CONTEXT INDICATOR =====
CONTEXT_STATUS_EXCELLENT: Final[str] = "Отлично"
CONTEXT_STATUS_NORMAL: Final[str] = "Нормально"
CONTEXT_STATUS_FILLING: Final[str] = "Заполняется"
CONTEXT_STATUS_ALMOST_FULL: Final[str] = "Почти заполнен"

CONTEXT_COLOR_GREEN: Final[str] = "#4CAF50"
CONTEXT_COLOR_ORANGE: Final[str] = "#FF9800"
CONTEXT_COLOR_RED_ORANGE: Final[str] = "#FF5722"
CONTEXT_COLOR_RED: Final[str] = "#F44336"

# ===== UI SIZING =====
LOGO_WIDTH_PX: Final[int] = 240
LOGO_HEIGHT_PX: Final[int] = 240
SUBMIT_BUTTON_SIZE_PX: Final[int] = 40

# ===== DEFAULT CHAT TITLE =====
DEFAULT_CHAT_TITLE: Final[str] = "Новый чат"

# ===== API ENDPOINTS =====
ENDPOINT_HEALTH: Final[str] = "/health"
ENDPOINT_AUTH_REGISTER: Final[str] = "/auth/register"
ENDPOINT_AUTH_LOGIN: Final[str] = "/auth/login"
ENDPOINT_AUTH_ME: Final[str] = "/auth/me"
ENDPOINT_EXECUTE: Final[str] = "/execute"
ENDPOINT_CHATS: Final[str] = "/chats"
ENDPOINT_CHARTS: Final[str] = "/charts"

# ===== DELAYS =====
LOCALSTORAGE_INIT_DELAY_MS: Final[int] = 100
