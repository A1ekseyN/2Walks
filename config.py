"""Настройки проекта 2Walks. Общие пути и идентификаторы.

Здесь нет секретов — сервисный аккаунт хранится отдельно в credentials/
(gitignored), а ID Google-таблицы по сути публичен (виден в URL документа).
"""

import os


# Google Sheets
SPREADSHEET_ID = "1l1SfzodtHAAIVsmsQjZPK2YEltilVzu5psv0_2p4MLM"
GAME_STATE_SHEET_NAME = "game_state"          # переименован из Sheet1 в задаче 4.14
STEPS_LOG_SHEET_NAME = "steps_log"             # новый лист, заголовки: ts | user_id | steps | source
CREDENTIALS_PATH = "credentials/2walks_service_account.json"

# User identity (single-player). Переход на multi-user — задача 4.53.
DEFAULT_USER_ID = "alex"

# Web interface (FastAPI, задача 4.48). Локально — 127.0.0.1, на VPS будет 0.0.0.0
# через переменную окружения WEB_HOST.
WEB_HOST = os.getenv("WEB_HOST", "127.0.0.1")
WEB_PORT = int(os.getenv("WEB_PORT", "8008"))
