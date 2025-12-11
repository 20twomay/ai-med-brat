"""
Константы приложения
"""

# Authentication
MAX_PASSWORD_LENGTH_BYTES = 72  # Ограничение bcrypt
MIN_PASSWORD_LENGTH = 6
MAX_PASSWORD_LENGTH_CHARS = 100
MIN_EMAIL_LENGTH = 3
MAX_EMAIL_LENGTH = 255

# JWT
TOKEN_TYPE_BEARER = "bearer"

# Database
DEFAULT_POOL_SIZE = 5
DEFAULT_MAX_OVERFLOW = 10

# Agent
DEFAULT_MAX_REACT_ITERATIONS = 10
DEFAULT_CONTEXT_LIMIT = 256000

# HTTP
HTTP_TIMEOUT_SECONDS = 60
HEALTH_CHECK_TIMEOUT_SECONDS = 5

# File types
SUPPORTED_CHART_FORMATS = {".png", ".jpg", ".jpeg", ".svg"}
SUPPORTED_TABLE_FORMATS = {".csv", ".json"}
SUPPORTED_MEDIA_TYPES = {
    ".json": "application/json",
    ".csv": "text/csv",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
}
