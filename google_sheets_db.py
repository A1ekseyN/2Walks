"""Google Sheets backend — два repo для двух листов (задача 4.14).

Архитектура:
- ``GameStateRepo`` — snapshot состояния игры. Лист `game_state` (key/value).
  Используется для save/load всего GameState через flat-dict (`state.to_dict()`).
- ``StepsLogRepo`` — append-only лог замеров шагов. Лист `steps_log` с колонками
  `ts | user_id | steps | source`. Используется для max-merge (4.15) и iPhone /
  Web ввода (4.13 / 4.48.2).

Lazy singleton клиент (`_get_client()`) — один re-use'имый gspread connection
на весь процесс, чтобы избежать ~0.5 сек авторизации при каждом save/load.
"""

import ast
import json
import time
from datetime import datetime
from typing import Optional

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from config import (
    CREDENTIALS_PATH,
    DEFAULT_USER_ID,
    GAME_STATE_SHEET_NAME,
    SPREADSHEET_ID,
    STEPS_LOG_SHEET_NAME,
)


_SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
_DATETIME_FMT = '%Y-%m-%d %H:%M:%S.%f'

# Заголовок steps_log листа.
_STEPS_LOG_HEADER = ["ts", "user_id", "steps", "source"]

# Ключи, для которых `to_dict()` отдаёт datetime — нужно специально парсить при load.
_DATETIME_KEYS = ('skill_training_time_end', 'working_end', 'adventure_end_timestamp')


# ----------------------------------------------------------------------------
# Lazy singleton client
# ----------------------------------------------------------------------------

_client: Optional[gspread.Client] = None


def _get_client() -> gspread.Client:
    """Возвращает gspread.Client. Авторизация происходит один раз за процесс."""
    global _client
    if _client is None:
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, _SCOPE)
        _client = gspread.authorize(creds)
    return _client


def _reset_client() -> None:
    """Сбрасывает кэшированный клиент. Используется в тестах."""
    global _client
    _client = None


# ----------------------------------------------------------------------------
# Pure helpers — тестируются напрямую без gspread
# ----------------------------------------------------------------------------

def _state_dict_to_rows(data: dict) -> list:
    """flat-dict (`state.to_dict()`) → rows для записи на лист game_state.

    Первая строка — заголовок ['Key', 'Value']. Списки/словари сериализуются
    как JSON-строки. Datetime — через strftime в legacy-формате."""
    rows = [["Key", "Value"]]
    for key, value in data.items():
        if isinstance(value, (list, dict)):
            rows.append([key, json.dumps(value)])
        elif isinstance(value, datetime):
            rows.append([key, value.strftime(_DATETIME_FMT)])
        else:
            rows.append([key, value])
    return rows


def _rows_to_state_dict(rows: list) -> dict:
    """rows из листа game_state → flat-dict (формат, который ест GameState.from_dict).

    Принимает rows БЕЗ заголовка (первая строка с ключом отброшена caller'ом).
    Восстанавливает int / float / bool / None / dict / list / datetime по форме строки.
    """
    data = {}
    for row in rows:
        if len(row) < 2:
            continue
        key, value = row[0], row[1]
        # Пытаемся как JSON — для list/dict.
        try:
            data[key] = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            data[key] = value if not (isinstance(value, str) and value.isdigit()) else int(value)

        # Разбираем как Python-литерал (list/dict с одинарными кавычками).
        if isinstance(data[key], str):
            v = data[key]
            try:
                data[key] = ast.literal_eval(v)
            except (ValueError, SyntaxError):
                pass

            if isinstance(data[key], str):
                if v.isdigit():
                    data[key] = int(v)
                elif v.replace('.', '', 1).isdigit():
                    data[key] = float(v)
                elif v.lower() in ('true', 'false'):
                    data[key] = v.lower() == 'true'
                elif v == '':
                    data[key] = None

            # Datetime поля — explicit парсинг.
            if key in _DATETIME_KEYS and isinstance(data[key], str):
                try:
                    data[key] = datetime.strptime(data[key], _DATETIME_FMT)
                except ValueError:
                    pass
    return data


def _format_steps_entry(ts: float, user_id: str, steps: int, source: str) -> list:
    """Готовит строку для append в steps_log. Pure, без I/O."""
    return [ts, user_id, int(steps), source]


# ----------------------------------------------------------------------------
# GameStateRepo — read/write game_state листа
# ----------------------------------------------------------------------------

class GameStateRepo:
    """Snapshot-сохранение и загрузка GameState (как flat-dict) в Google Sheets.

    Каждое `save()` полностью перезаписывает лист (clear + update).
    `load()` читает все строки и восстанавливает типы.
    """

    def __init__(self,
                 spreadsheet_id: str = SPREADSHEET_ID,
                 sheet_name: str = GAME_STATE_SHEET_NAME):
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name

    def _worksheet(self) -> gspread.Worksheet:
        return _get_client().open_by_key(self.spreadsheet_id).worksheet(self.sheet_name)

    def save(self, state_dict: dict) -> None:
        """Записать flat-dict на лист game_state (полная перезапись)."""
        ping = time.time()
        rows = _state_dict_to_rows(state_dict)
        ws = self._worksheet()
        ws.clear()
        ws.update(rows)
        print(f"Save Data to Google Sheets. [{time.time() - ping:,.2f} sec]")

    def load(self) -> dict:
        """Прочитать лист game_state → flat-dict для GameState.from_dict()."""
        ping = time.time()
        print("Loading...")
        ws = self._worksheet()
        rows = ws.get_all_values()[1:]  # Пропускаем заголовок.
        data = _rows_to_state_dict(rows)
        print(f"Data Loaded from Google Sheets. [{time.time() - ping:,.2f} sec]")
        return data


# ----------------------------------------------------------------------------
# StepsLogRepo — append-only лог замеров
# ----------------------------------------------------------------------------

class StepsLogRepo:
    """Append-only лог замеров шагов: ts | user_id | steps | source.

    Используется для max-merge (4.15) при определении актуальных шагов за день
    и для отображения истории ввода.

    `_ensure_sheet()` — auto-create листа с заголовком, если его нет. Защитный
    код (вариант B), который удалится после задачи 4.14.2 (когда миграция
    точно прошла на всех окружениях). Миграция же делается через скрипт
    `migrate_sheets.py`.
    """

    def __init__(self,
                 spreadsheet_id: str = SPREADSHEET_ID,
                 sheet_name: str = STEPS_LOG_SHEET_NAME):
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name

    def _spreadsheet(self) -> gspread.Spreadsheet:
        return _get_client().open_by_key(self.spreadsheet_id)

    def _ensure_sheet(self) -> gspread.Worksheet:
        """Возвращает worksheet steps_log. Создаёт + добавляет заголовок если нет.

        Удалить после 4.14.2 — когда миграция гарантирована на всех окружениях.
        """
        spreadsheet = self._spreadsheet()
        try:
            return spreadsheet.worksheet(self.sheet_name)
        except gspread.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=self.sheet_name, rows=1000, cols=len(_STEPS_LOG_HEADER))
            ws.update([_STEPS_LOG_HEADER])
            return ws

    def append(self, ts: float, steps: int, source: str,
               user_id: str = DEFAULT_USER_ID) -> None:
        """Добавляет одну запись в лог. Fail-fast при сетевой ошибке."""
        ws = self._ensure_sheet()
        entry = _format_steps_entry(ts, user_id, steps, source)
        ws.append_row(entry, value_input_option='USER_ENTERED')

    def for_day(self, date_str: str, user_id: str = DEFAULT_USER_ID) -> list:
        """Возвращает все записи лога за указанный день для пользователя.

        ``date_str`` — строка `YYYY-MM-DD`. ``ts`` в логе хранится как Unix
        timestamp (float), сравнение делается через `datetime.fromtimestamp`.
        """
        ws = self._ensure_sheet()
        rows = ws.get_all_values()[1:]  # Пропускаем заголовок.
        result = []
        for row in rows:
            if len(row) < 4:
                continue
            try:
                ts = float(row[0])
            except (ValueError, TypeError):
                continue
            if row[1] != user_id:
                continue
            entry_date = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
            if entry_date != date_str:
                continue
            try:
                steps_val = int(row[2])
            except (ValueError, TypeError):
                continue
            result.append({
                'ts': ts,
                'user_id': row[1],
                'steps': steps_val,
                'source': row[3],
            })
        return result


# ----------------------------------------------------------------------------
# Standalone smoke (запуск файла напрямую): show current state contents.
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    state_dict = GameStateRepo().load()
    print(f"Loaded {len(state_dict)} keys from {GAME_STATE_SHEET_NAME}")
