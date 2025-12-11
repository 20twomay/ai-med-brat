"""
Константы приложения
"""

# Agent constants
DEFAULT_REACT_MAX_ITER = 10
DEFAULT_CONTEXT_LIMIT = 256000

# Chat constants
DEFAULT_CHAT_TITLE = "Новый чат"
DEFAULT_CHAT_LIST_LIMIT = 100

# File naming patterns
CSV_FILE_PATTERN = "df_{uuid}.csv"
PLOT_FILE_PATTERN = "plot_{uuid}.json"

# HTTP Status Messages
STATUS_HEALTHY = "healthy"
STATUS_DEGRADED = "degraded"
STATUS_DISCONNECTED = "disconnected"
STATUS_CONNECTED = "connected"

# Service names
SERVICE_NAME = "Medical Analytics Agent"
SERVICE_VERSION = "2.0.0"

# Resource types for exceptions
RESOURCE_USER = "User"
RESOURCE_CHAT = "Chat"