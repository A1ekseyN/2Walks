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

import json
import time
from datetime import datetime
from typing import Literal, Optional

import gspread
from gspread.utils import ValueInputOption, ValueRenderOption
from oauth2client.service_account import ServiceAccountCredentials

from config import (
    CREDENTIALS_PATH,
    DEFAULT_USER_ID,
    GAME_STATE_SHEET_NAME,
    HISTORY_SHEET_NAME,
    SPREADSHEET_ID,
    STEPS_LOG_SHEET_NAME,
)


_SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
_DATETIME_FMT = '%Y-%m-%d %H:%M:%S.%f'

# Заголовок steps_log листа.
_STEPS_LOG_HEADER = ["ts", "user_id", "steps", "source"]

# Заголовок history листа (4.6).
_HISTORY_HEADER = ["ts", "datetime", "user_id", "game_version", "event_type", "payload_json"]

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

    **LEGACY format (до 1.4.3 / 0.2.5).** С 1.4.3 используется `_state_dict_to_blob_rows`
    (JSON-blob в одной ячейке + last_modified в A1). Этот helper оставлен для
    обратной совместимости и для тестов которые проверяют parsing старого формата.

    Первая строка — заголовок ['Key', 'Value']. Списки/словари сериализуются
    как JSON-строки. Datetime — через strftime в legacy-формате. Float —
    явно через `repr()` (а не как Python-объект), чтобы Sheets не интерпретировал
    его по системной локали (баг 07.05.2026: `state.money=2018.10` сохранялся
    как `'2018,1'` при locale=ru, на чтении `ast.literal_eval('2018,1')` →
    tuple `(2018, 1)` → crash в `from_dict`).
    """
    rows = [["Key", "Value"]]
    for key, value in data.items():
        if isinstance(value, (list, dict)):
            rows.append([key, json.dumps(value)])
        elif isinstance(value, datetime):
            rows.append([key, value.strftime(_DATETIME_FMT)])
        elif isinstance(value, float):
            # repr(2018.1) = '2018.1' — точка как разделитель, не локаль-зависимо.
            rows.append([key, repr(value)])
        else:
            rows.append([key, value])
    return rows


def _rows_to_state_dict(rows: list) -> dict:
    """rows из листа game_state (LEGACY Key/Value layout) → flat-dict.

    Принимает rows БЕЗ заголовка (первая строка с ключом отброшена caller'ом).
    Использует unified `persistence._parse_value` (1.4.2, 0.2.4y) — общий
    parser для CSV и Sheets.

    **С 1.4.3 (0.2.5)** используется только как fallback в `GameStateRepo.load`
    когда auto-detect видит старый Key/Value layout. Удалится в 1.4.3.1
    Legacy cleanup через 1-2 недели после bake-test'а.
    """
    from persistence import _parse_value  # lazy: persistence → characteristics → state
    data = {}
    for row in rows:
        if len(row) < 2:
            continue
        key, value = row[0], row[1]
        data[key] = _parse_value(value, key=key)
    return data


def _json_blob_default(obj: object) -> object:
    """Сериализация non-JSON типов для `json.dumps` в blob layout.

    Datetime → strftime в `_DATETIME_FMT` (тот же формат что использовался
    в legacy Key/Value layout). Это сохраняет совместимость с
    `persistence._parse_value` (`_DATETIME_KEYS` → strptime обратно).

    Future task 1.4.3.2 — переход на ISO-8601 (datetime.isoformat / fromisoformat).
    """
    if isinstance(obj, datetime):
        return obj.strftime(_DATETIME_FMT)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _state_dict_to_blob_rows(data: dict) -> list:
    """flat-dict → rows для blob layout (1.4.3 / 0.2.5).

    Возвращает одну строку с двумя ячейками:
    - A1: `last_modified` (float, для fast load_meta)
    - B1: JSON-blob всего state (включая дубликат last_modified — round-trip simplicity)

    Datetime сериализуется через `_json_blob_default` в legacy strftime формат
    (чтобы `from_dict` не пришлось менять — он принимает и datetime, и str
    через `_deser_datetime`).
    """
    last_mod = data.get('last_modified', 0.0)
    if not isinstance(last_mod, (int, float)):
        last_mod = 0.0
    blob = json.dumps(data, ensure_ascii=False, default=_json_blob_default)
    return [[float(last_mod), blob]]


def _blob_rows_to_state_dict(rows: list) -> dict:
    """rows blob layout → flat-dict.

    Ожидает row[0] = [last_modified, json_blob_string]. Datetime поля из
    `_DATETIME_KEYS` конвертируются обратно из str → datetime через strptime
    (legacy формат). Остальные поля приходят как native Python типы из JSON.

    Returns {} если row[0] пустой / blob невалидный — caller fallback на legacy.
    """
    if not rows or len(rows[0]) < 2:
        return {}
    blob = rows[0][1]
    if not isinstance(blob, str) or not blob:
        return {}
    try:
        data = json.loads(blob)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    # Datetime поля приходят как str (legacy strftime формат) — конвертируем обратно.
    for key in _DATETIME_KEYS:
        v = data.get(key)
        if isinstance(v, str) and v:
            try:
                data[key] = datetime.strptime(v, _DATETIME_FMT)
            except ValueError:
                pass  # оставим как есть, _deser_datetime в from_dict разрулит
    return data


def _is_legacy_kv_layout(rows: list) -> bool:
    """Auto-detect: первая строка — ['Key', 'Value'] header → legacy layout.

    Auto-detect нужен для миграции 1.4.3 → 0.2.5: первый load после deploy
    видит старый формат, парсит его, первый save переписывает в blob layout.
    """
    if not rows:
        return False
    first = rows[0]
    return len(first) >= 2 and first[0] == 'Key' and first[1] == 'Value'


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
        """Записать flat-dict на лист game_state в blob layout (1.4.3 / 0.2.5).

        Layout:
        - A1: `last_modified` (float) — для fast `load_meta` без parse JSON.
        - B1: JSON-blob всего state.

        Полная перезапись (`ws.clear()` перед update) — гарантирует что
        legacy Key/Value rows (если до этого был старый формат) удалены.
        Первый save после deploy 1.4.3 автоматически мигрирует layout.

        `ValueInputOption.raw` — same reason что и до 1.4.3: float без
        locale-парсинга. Для JSON-blob важно чтобы Sheets не интерпретировал
        строку как formula (если начинается с `=`).
        """
        ping = time.time()
        rows = _state_dict_to_blob_rows(state_dict)
        ws = self._worksheet()
        ws.clear()
        ws.update(rows, value_input_option=ValueInputOption.raw)
        print(f"Save Data to Google Sheets. [{time.time() - ping:,.2f} sec]")

    def load(self) -> dict:
        """Прочитать лист game_state → flat-dict для GameState.from_dict().

        Auto-detect (1.4.3 / 0.2.5): если первая строка — legacy header
        `['Key', 'Value']` → парсим старым `_rows_to_state_dict` и печатаем
        migration notice. Иначе — blob layout через `_blob_rows_to_state_dict`.
        Это позволяет первому load после deploy прочитать pre-migration данные;
        первый save автоматически перепишет в новый формат.
        """
        ping = time.time()
        print("Loading...")
        ws = self._worksheet()
        rows = ws.get_all_values()
        if _is_legacy_kv_layout(rows):
            print("[migration 1.4.3] Detected legacy Key/Value layout — "
                  "next save will convert to JSON-blob format.")
            data = _rows_to_state_dict(rows[1:])
        else:
            data = _blob_rows_to_state_dict(rows)
        print(f"Data Loaded from Google Sheets. [{time.time() - ping:,.2f} sec]")
        return data

    def load_meta(self) -> float:
        """4.54.2 — Облегчённый запрос только `last_modified` ячейки.

        Используется для optimistic concurrency check в `save_safe()`: нужен
        только timestamp, не полный state.

        1.4.3 (0.2.5) — fast-path через `acell('A1')`: одна cell read вместо
        scan всех rows. Auto-detect (1.4.3): если A1 не parsable как float
        (legacy Key/Value layout до миграции) → fallback на старый scan
        `last_modified` row.

        Returns 0.0 если ключ отсутствует (legacy save до 4.54) или формат
        невалидный. Default 0.0 + check `current > expected + epsilon` → legacy
        save без `last_modified` пройдёт первый save_safe (expected тоже 0.0).
        """
        ws = self._worksheet()
        # Fast-path: A1 в blob layout = last_modified (float).
        # 4.48.5.4 (0.2.5d) — UNFORMATTED_VALUE критично: cell A1 имеет дефолтное
        # форматирование "Number" (без decimals) → FORMATTED_VALUE возвращает
        # округлённый до integer string ('1779300151' вместо реального
        # 1779300150.71383). Это давало false-positive STALE: load_meta
        # возвращал rounded value > expected + 0.01 epsilon → каждый второй
        # save'ил STALE без реальной причины (диагноз 20.05.2026).
        try:
            cell = ws.acell('A1',
                            value_render_option=ValueRenderOption.unformatted).value
            if cell is not None and cell != 'Key':
                # UNFORMATTED для number cell возвращает int/float напрямую,
                # не string. float() работает на обоих.
                return float(cell)
        except (TypeError, ValueError):
            pass
        except Exception:  # noqa: BLE001 — network/api errors → fallback на scan
            pass
        # Legacy fallback: scan rows ища `last_modified` row.
        rows = ws.get_all_values()
        for row in rows:
            if len(row) >= 2 and row[0] == 'last_modified':
                try:
                    return float(row[1])
                except (TypeError, ValueError):
                    return 0.0
        return 0.0

    def save_safe(
        self,
        state_dict: dict,
        expected_last_modified: Optional[float],
    ) -> Literal["OK", "STALE"]:
        """4.54.2 — Optimistic concurrency save.

        Если `expected_last_modified is None` — bypass check (Force option в
        CLI STALE prompt, 4.54.5). Иначе сначала `load_meta()` сверить с
        Sheets: если Sheets newer чем expected → return `"STALE"` без записи.

        На `OK`: мутирует `state_dict['last_modified'] = time.time()`, делает
        полный save через `self.save()`, возвращает `"OK"`. Caller (4.54.4
        wrappers) рассчитывает на мутацию `state_dict` чтобы синкнуть
        `state.last_modified` после успеха.

        Epsilon `0.01` сек на float-сравнение — float-точность timestamp'ов
        Sheets / Python округляется в микросекундах, без epsilon идентичные
        saves могли бы давать false-positive STALE.
        """
        if expected_last_modified is not None:
            current = self.load_meta()
            if current > expected_last_modified + 0.01:
                return "STALE"
        state_dict['last_modified'] = time.time()
        self.save(state_dict)
        return "OK"


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
        """Добавляет одну запись в лог. Fail-fast при сетевой ошибке.

        `ValueInputOption.raw` — чтобы Sheets не парсил `ts` (float) по локали.
        Без этого `1714398000.123` мог бы сохраниться как `'1714398000,123'`
        и потом падать `float(...)` в `for_day()`. См. fix в `GameStateRepo.save`.
        """
        ws = self._ensure_sheet()
        entry = _format_steps_entry(ts, user_id, steps, source)
        ws.append_row(entry, value_input_option=ValueInputOption.raw)

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
# HistoryLogRepo — append-only лог значимых игровых событий (4.6)
# ----------------------------------------------------------------------------

class HistoryLogRepo:
    """Лог значимых событий игры: ts | datetime | user_id | game_version | event_type | payload_json.

    Используется как Sheets-копия параллельно с локальным `history.jsonl` —
    local primary, Sheets best-effort (см. `history.log_event`). Pruning /
    rotation — задача 4.6.1. Re-sync missed events — 4.6.3.

    `_ensure_sheet()` — auto-create листа с заголовком при отсутствии. Защитный
    код: если миграция `migrate_sheets.py` не была обновлена для нового листа,
    лист создаётся автоматически на первой записи.
    """

    def __init__(self,
                 spreadsheet_id: str = SPREADSHEET_ID,
                 sheet_name: str = HISTORY_SHEET_NAME):
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name

    def _spreadsheet(self) -> gspread.Spreadsheet:
        return _get_client().open_by_key(self.spreadsheet_id)

    def _ensure_sheet(self) -> gspread.Worksheet:
        spreadsheet = self._spreadsheet()
        try:
            return spreadsheet.worksheet(self.sheet_name)
        except gspread.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=self.sheet_name, rows=1000, cols=len(_HISTORY_HEADER))
            ws.update([_HISTORY_HEADER])
            return ws

    def append(self, event: dict) -> None:
        """Append event-dict (см. `history._build_event`) в Sheets `history` лист.

        `value_input_option=RAW` — критично, чтобы float `ts` и числовые
        payload-поля не парсились по локали (баг 2.13 / 0.2.3g). payload
        сериализуется в JSON-строку.
        """
        ws = self._ensure_sheet()
        dt_str = f"{event['date']} {event['time']}"
        payload_json = json.dumps(event.get('payload', {}), ensure_ascii=False)
        row = [
            event['ts'],
            dt_str,
            event['user_id'],
            event['game_version'],
            event['type'],
            payload_json,
        ]
        ws.append_row(row, value_input_option=ValueInputOption.raw)

    def since(self, ts: float) -> list[dict]:
        """4.2 (0.2.5e) — Возвращает все events с `ts >= since` для report
        «пока тебя не было». Используется на старте CLI / web init.

        Полный read всех rows (через `get_all_values`) + Python-filter. Для
        тысяч rows ~500-700 мс. UNFORMATTED для ts чтобы избежать precision
        loss (как с last_modified — см. 4.48.5.4 / 0.2.5d).

        Returns list of dicts: `{'ts': float, 'datetime': str, 'user_id': str,
        'game_version': str, 'type': str, 'payload': dict}`. На ошибке возвращает
        пустой список (silent-fail, report — не критичная фича).
        """
        try:
            ws = self._ensure_sheet()
            rows = ws.get_values(value_render_option=ValueRenderOption.unformatted)
        except Exception:  # noqa: BLE001
            return []
        events: list[dict] = []
        for row in rows[1:]:  # skip header
            if len(row) < 6:
                continue
            try:
                event_ts = float(row[0])
            except (TypeError, ValueError):
                continue
            if event_ts < ts:
                continue
            try:
                payload = json.loads(row[5]) if row[5] else {}
            except (json.JSONDecodeError, TypeError):
                payload = {}
            events.append({
                'ts': event_ts,
                'datetime': str(row[1]),
                'user_id': str(row[2]),
                'game_version': str(row[3]),
                'type': str(row[4]),
                'payload': payload,
            })
        return events


# ----------------------------------------------------------------------------
# Standalone smoke (запуск файла напрямую): show current state contents.
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    state_dict = GameStateRepo().load()
    print(f"Loaded {len(state_dict)} keys from {GAME_STATE_SHEET_NAME}")
