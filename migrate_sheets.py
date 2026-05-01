"""Миграция Google Sheets для задачи 4.14.

Что делает (idempotent):
1. Если лист `Sheet1` существует и `game_state` — нет → переименовывает `Sheet1` → `game_state`.
2. Если лист `steps_log` отсутствует → создаёт + добавляет заголовок `ts | user_id | steps | source`.
3. Повторный запуск — no-op (всё уже на месте).

Запуск (один раз вручную после деплоя):
    python migrate_sheets.py
"""

import gspread

from config import GAME_STATE_SHEET_NAME, SPREADSHEET_ID, STEPS_LOG_SHEET_NAME
from google_sheets_db import _STEPS_LOG_HEADER, _get_client


_LEGACY_GAME_STATE_NAME = "Sheet1"


def migrate() -> None:
    spreadsheet = _get_client().open_by_key(SPREADSHEET_ID)
    sheet_titles = {ws.title for ws in spreadsheet.worksheets()}
    print(f"Existing sheets: {sorted(sheet_titles)}")

    # 1. Переименование Sheet1 → game_state.
    if GAME_STATE_SHEET_NAME in sheet_titles:
        print(f"  ✓ Sheet '{GAME_STATE_SHEET_NAME}' already exists — skip rename.")
    elif _LEGACY_GAME_STATE_NAME in sheet_titles:
        legacy_ws = spreadsheet.worksheet(_LEGACY_GAME_STATE_NAME)
        legacy_ws.update_title(GAME_STATE_SHEET_NAME)
        print(f"  ✓ Renamed '{_LEGACY_GAME_STATE_NAME}' → '{GAME_STATE_SHEET_NAME}'.")
    else:
        print(f"  ! Neither '{_LEGACY_GAME_STATE_NAME}' nor '{GAME_STATE_SHEET_NAME}' found —"
              f" сейв ещё не существует. Это OK для нового deployment.")

    # 2. Создание steps_log с заголовком.
    if STEPS_LOG_SHEET_NAME in sheet_titles:
        print(f"  ✓ Sheet '{STEPS_LOG_SHEET_NAME}' already exists — skip create.")
        ws = spreadsheet.worksheet(STEPS_LOG_SHEET_NAME)
        # Проверим заголовок — если первая строка пустая, дозальём.
        first_row = ws.row_values(1) if ws.row_count > 0 else []
        if first_row[:len(_STEPS_LOG_HEADER)] != _STEPS_LOG_HEADER:
            ws.update([_STEPS_LOG_HEADER])
            print(f"  ✓ Restored header on '{STEPS_LOG_SHEET_NAME}'.")
    else:
        ws = spreadsheet.add_worksheet(title=STEPS_LOG_SHEET_NAME, rows=1000,
                                       cols=len(_STEPS_LOG_HEADER))
        ws.update([_STEPS_LOG_HEADER])
        print(f"  ✓ Created '{STEPS_LOG_SHEET_NAME}' with header {_STEPS_LOG_HEADER}.")

    print("Migration done.")


if __name__ == "__main__":
    migrate()
