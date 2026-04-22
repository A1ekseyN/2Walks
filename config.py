"""Настройки проекта 2Walks. Общие пути и идентификаторы.

Здесь нет секретов — сервисный аккаунт хранится отдельно в credentials/
(gitignored), а ID Google-таблицы по сути публичен (виден в URL документа).
"""

# Google Sheets
SPREADSHEET_ID = "1l1SfzodtHAAIVsmsQjZPK2YEltilVzu5psv0_2p4MLM"
GAME_STATE_SHEET_NAME = "Sheet1"
# STEPS_LOG_SHEET_NAME = "steps_log"  # добавим в задаче 4.14
CREDENTIALS_PATH = "credentials/2walks_service_account.json"
