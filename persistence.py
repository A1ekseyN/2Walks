"""Persistence layer — save/load state в Google Sheets + локальный fallback.

Выделено из `characteristics.py` в задаче 1.3.3 (0.2.4y, 20.05.2026).

- `characteristics.py` — state container (`game` singleton + `init_game_state`).
- `persistence.py` — save/load I/O + STALE prompt UI.

**Unified parser (1.4.2, 0.2.4y):** общий `_parse_value(v, key)` для CSV и
Sheets — `json.loads` → `ast.literal_eval` → manual int/float/bool/empty
detection → datetime fallback для DATE_KEYS.

**state.json primary (1.4.3, 0.2.5):** offline-fallback теперь хранится в
`state.json` (полный JSON-blob через `state.to_dict()`), а не в плоском
`characteristic.csv`. Save пишет только state.json. Load пробует state.json
первым; если файла нет — fallback на CSV reader (legacy backwards-compat
для игроков на pre-0.2.5 сейвах). CSV reader + writer удалится в 1.4.3.1
Legacy cleanup через 1-2 недели после bake-test'а.
"""

import ast
import csv
import json
import os
import time
from datetime import datetime
from typing import Any, Literal, Optional

from characteristics import apply_steps_log_max_merge, game
from settings import debug_mode
from state import GameState

STATE_JSON_PATH = 'state.json'
CHARACTERISTIC_CSV_PATH = 'characteristic.csv'  # legacy fallback (1.4.3.1 удалит)


# --- Datetime parsing constants ---
# Хранится тут (был дублирован в google_sheets_db.py + characteristics.py).
# Sheets / CSV пишут datetime через str(datetime) (ISO-like с микросекундами).
_DATETIME_FMT = '%Y-%m-%d %H:%M:%S.%f'

# Keys которые мы пытаемся распарсить как datetime после общих type-checks.
# Только эти 3 — `date_last_enter` пишется как строка YYYY-MM-DD (хранится str),
# `energy_time_stamp` / `working_start` / `adventure_*_timestamp` — float Unix ts.
_DATETIME_KEYS = (
    'skill_training_time_end',
    'working_end',
    'adventure_end_timestamp',
)


# --- Unified parser ---

def _parse_value(value: Any, key: Optional[str] = None) -> Any:
    """Универсальный парсер cell-value из CSV или Sheets (1.4.2, 0.2.4y).

    Восстанавливает Python-значение по строке через priority chain:
    1. Non-string → return as-is (Sheets иногда отдаёт int/float напрямую).
    2. Empty string → None.
    3. `json.loads` — для int/float/bool/null/dict/list/quoted-string.
       JSON-string («"text"») fall-through на дальнейшие шаги.
    4. `ast.literal_eval` — Python repr с одинарными кавычками (legacy
       Sheets-format когда dict печатался через str()).
    5. Manual type detection — int (`isdigit`), float (`replace('.','',1).isdigit`),
       bool (`'true'/'false'` case-insensitive).
    6. Datetime — если `key in _DATETIME_KEYS`, попытка `strptime(_DATETIME_FMT)`.
    7. Plain string fallback.

    Заменяет дублированную логику в `load_characteristic` (CSV) и
    `_rows_to_state_dict` (Sheets). Format сейвов не изменён — backwards-compat
    100%. Edge cases прежнего поведения сохранены (например `'2018,1'` от
    локального броken-save до 0.2.3g RAW-fix → `ast.literal_eval` парсит как
    tuple — тот же баг как раньше, fixed на стороне записи через RAW в Sheets).
    """
    # 1. Non-string — return as-is.
    if not isinstance(value, str):
        return value

    # 2. Empty → None.
    if value == '':
        return None

    # 3. JSON.
    try:
        parsed = json.loads(value)
        if not isinstance(parsed, str):
            return parsed  # int/float/bool/None/dict/list
    except (json.JSONDecodeError, TypeError):
        pass

    # 4. Python-литерал (single-quoted dict/list).
    try:
        parsed = ast.literal_eval(value)
        if not isinstance(parsed, str):
            return parsed
    except (ValueError, SyntaxError):
        pass

    # 5. Manual type detection (legacy compat).
    if value.isdigit():
        return int(value)
    if value.replace('.', '', 1).isdigit():
        return float(value)
    if value.lower() == 'true':
        return True
    if value.lower() == 'false':
        return False

    # 6. Datetime для specific keys.
    if key in _DATETIME_KEYS:
        try:
            return datetime.strptime(value, _DATETIME_FMT)
        except ValueError:
            pass

    # 7. Plain string.
    return value


# --- Load ---

def _json_default(obj: object) -> object:
    """Сериализация non-JSON типов для `json.dumps` (state.json)."""
    if isinstance(obj, datetime):
        return obj.strftime(_DATETIME_FMT)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def load_state_json() -> dict:
    """Считать state из `state.json` (1.4.3 / 0.2.5).

    Datetime поля приходят из JSON как строки (`_DATETIME_FMT`); конвертируем
    обратно в datetime для совместимости с `GameState.from_dict` (`_deser_datetime`
    тоже примет str, но native datetime в blob тестах нагляднее).

    Raises `FileNotFoundError` если файла нет — caller (`load_data_from_*`)
    делает fallback на CSV reader.
    """
    with open(STATE_JSON_PATH, mode='r', encoding='utf-8') as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"{STATE_JSON_PATH}: expected dict, got {type(data).__name__}")
    for key in _DATETIME_KEYS:
        v = data.get(key)
        if isinstance(v, str) and v:
            try:
                data[key] = datetime.strptime(v, _DATETIME_FMT)
            except ValueError:
                pass
    return data


def load_characteristic() -> dict:
    """Считать сохранение из CSV (LEGACY fallback, удалится в 1.4.3.1).

    С 1.4.3 (0.2.5) primary offline-формат — `state.json`. Этот reader
    сохранён для backwards-compat: игроки на pre-0.2.5 сейвах могут
    автоматически мигрировать на первом save после обновления.
    """
    char_characteristic: dict[str, Any] = {}

    with open(CHARACTERISTIC_CSV_PATH, mode='r', encoding='utf-8') as file:
        csv_reader = csv.reader(file)
        headers = next(csv_reader)
        data_row = next(csv_reader)
        for key, value in zip(headers, data_row):
            char_characteristic[key] = _parse_value(value, key=key)

    return char_characteristic


def load_data_from_google_sheet_or_csv() -> dict:
    """Загружает state из Google Sheets, при неудаче — локальный fallback.

    Локальный fallback (1.4.3 / 0.2.5): сначала пробуем `state.json` (новый
    primary format), при отсутствии файла — legacy `characteristic.csv`.
    """
    from google_sheets_db import GameStateRepo  # lazy для тестов
    try:
        loaded = GameStateRepo().load()
        if loaded:
            return loaded
        print("Google Sheets пуст. Загружаем данные из локального файла.")
        return _load_local_fallback()
    except Exception as error:
        print(f"Ошибка при загрузке данных из Google Sheets: {error}. Загружаем данные из локального файла.")
        return _load_local_fallback()


def _load_local_fallback() -> dict:
    """1.4.3 / 0.2.5 — state.json primary, characteristic.csv legacy fallback."""
    if os.path.exists(STATE_JSON_PATH):
        loaded = load_state_json()
        print(f"Loaded Data from {STATE_JSON_PATH}.")
        return loaded
    if os.path.exists(CHARACTERISTIC_CSV_PATH):
        loaded = load_characteristic()
        print(f"Loaded Data from {CHARACTERISTIC_CSV_PATH} (legacy fallback).")
        return loaded
    print("Локальный файл не найден.")
    return {}


# --- STALE prompt (CLI UX) ---

def handle_stale_prompt() -> Literal["reload", "force", "cancel"]:
    """4.54.5 — Интерактивный STALE-prompt для CLI.

    Загружает fresh Sheets state, вычисляет diff vs `state.last_loaded_snapshot`
    (через `sync_diff.diff_states`), показывает detailed список изменений и
    предлагает 3 опции:

    - **r / reload** — `init_game_state(state=None)` re-init из Sheets,
      потеряешь свои несохранённые мутации. Snapshot обновится.
    - **f / force** — двойной confirm prompt, потом save_safe с
      expected=None — перепишет Sheets своими данными, потеряешь серверные.
    - **c / cancel** — продолжить без save, prompt появится снова при
      следующем save attempt.

    Логирует `log_event('sync_conflict', source='cli', diff, choice)`.

    Возвращает выбор игрока ('reload' / 'force' / 'cancel') — caller сам
    решает что делать после (steps_log append / exit / continue).

    Импортируется в `game.py:_sync_to_cloud` при `status == "STALE"`.
    """
    if game.state is None:
        return "cancel"  # safety guard

    # Load fresh для diff.
    from google_sheets_db import GameStateRepo
    from sync_diff import diff_states, format_diff_brief, format_diff_cli, has_changes

    try:
        fresh = GameStateRepo().load()
    except Exception as e:  # noqa: BLE001
        print(f'\n⚠️ Не удалось загрузить fresh state для diff: {e}')
        print('Sheets недоступен — повторите попытку save позже.')
        return "cancel"

    snapshot = game.state.last_loaded_snapshot or {}
    diff = diff_states(snapshot, fresh)

    print('\n' + '=' * 60)
    print('⚠️  STALE — состояние на Sheets изменилось извне (web сервер / другой CLI).')
    print('=' * 60)
    if has_changes(diff):
        print(format_diff_cli(diff))
    else:
        print('(diff пустой — возможно, race condition без явных изменений)')
    print('=' * 60)

    from history import log_event
    diff_summary = format_diff_brief(diff)

    # Loop retry на невалиде.
    while True:
        choice = input(
            '\n[r] Reload — потерять свои несохранённые изменения, подтянуть свежее\n'
            '[f] Force  — перезаписать сервер (потеряешь изменения выше)\n'
            '[c] Cancel — продолжить без save, prompt появится снова\n'
            '>>> '
        ).strip().lower()

        if choice in ('r', 'reload'):
            print('\n🔄 Reload...')
            # lazy import: characteristics → persistence → characteristics циркуляр
            # на module level, но lazy внутри функции безопасно.
            from characteristics import init_game_state
            game.state = None  # сброс container'а
            init_game_state()  # re-init из Sheets + snapshot
            log_event('sync_conflict', source='cli', diff=diff_summary, choice='reload')
            print('✅ State пересинхронизирован с Sheets.')
            return "reload"

        if choice in ('f', 'force'):
            confirm = input(
                '\n⚠️ Force overwrite перезапишет ВСЕ изменения с сервера выше своими данными.\n'
                'Уверен? Введи `yes` для подтверждения: '
            ).strip().lower()
            if confirm != 'yes':
                print('Force отменён, возврат к меню выбора.')
                continue
            from google_sheets_db import GameStateRepo as _Repo
            state_dict = game.state.to_dict()
            try:
                _Repo().save_safe(state_dict, expected_last_modified=None)
            except Exception as e:  # noqa: BLE001
                print(f'\n❌ Force save failed: {e}')
                log_event('sync_conflict', source='cli', diff=diff_summary,
                          choice='force', result='failed', error=str(e))
                return "cancel"
            game.state.last_modified = state_dict.get('last_modified', game.state.last_modified)
            game.state.take_snapshot()
            log_event('sync_conflict', source='cli', diff=diff_summary, choice='force')
            print('✅ Force save прошёл. Серверные изменения перезаписаны.')
            return "force"

        if choice in ('c', 'cancel', ''):
            log_event('sync_conflict', source='cli', diff=diff_summary, choice='cancel')
            print('Save отменён.')
            return "cancel"

        print('Неверный выбор. Введи r / f / c.')


# --- Save ---

def save_characteristic() -> Literal["OK", "STALE"]:
    """Save state: Sheets save_safe + локальный `state.json` (offline fallback).

    4.54.4 — обёртка для optimistic concurrency. Sheets save выполняется через
    `GameStateRepo.save_safe()` с pre-check `state.last_modified` vs Sheets.

    Returns:
    - **"OK"** — Sheets save прошёл (или сетевая ошибка — fall back на local-only).
      В этом случае: (1) `state.last_modified` синкается к новому timestamp'у
      от Sheets, (2) `state.last_loaded_snapshot` обновляется через `take_snapshot()`,
      (3) `state.json` пишется с новым timestamp'ом.
    - **"STALE"** — Sheets имеет newer `last_modified` (someone else сохранил
      первым). State не мутируется, локальный файл не пишется.

    Сетевая ошибка Sheets → treat as "OK" (state.json-only fallback): pre-4.54
    поведение сохраняется для offline-mode, игрок продолжает играть локально.

    **Формат локального сейва (1.4.3, 0.2.5):** `state.json` через `state.to_dict()`
    + `json.dumps` (с `_json_default` для datetime). Заменил плоский CSV формат
    (`characteristic.csv`) который писался до 0.2.5. CSV reader сохранён в
    `load_characteristic()` для обратной совместимости и автомиграции на
    первом save — он будет удалён в 1.4.3.1 Legacy cleanup.
    """
    if game.state is None:
        raise RuntimeError("game.state не инициализирован — вызови init_game_state() до save_characteristic().")

    # 4.48.5.3 (0.2.5c): defense против регрессии steps.today при save.
    # Web RAM мог устареть относительно steps_log (max-merge выполняется только
    # в try_reload_state на GET /, не на каждом mutation endpoint). Без этого
    # max-merge web mutation писала state.steps.today из устаревшего snapshot'а,
    # затирая bigger value в Sheets → реальная регрессия (диагноз 20.05.2026).
    # Silent-fail внутри если steps_log недоступен — не блокируем save.
    apply_steps_log_max_merge(game.state)

    state_dict = game.state.to_dict()
    if debug_mode:
        print(f'Сохраняем данные: {state_dict}')

    # Step 1: Sheets save_safe (optimistic concurrency check).
    sheets_status: str = "OK"
    sheets_network_error = False
    try:
        from google_sheets_db import GameStateRepo
        sheets_status = GameStateRepo().save_safe(
            state_dict, expected_last_modified=game.state.last_modified
        )
    except Exception as e:  # noqa: BLE001 — best-effort sync
        print(f'[save] Sheets sync failed (local-only fallback): {e}')
        sheets_network_error = True
        sheets_status = "OK"

    # Step 2: STALE — rejection, NO local write, NO state mutation.
    if sheets_status == "STALE":
        return "STALE"

    # Step 3: OK — синкаем state с тем что записано в Sheets.
    game.state.last_modified = state_dict.get('last_modified', game.state.last_modified)

    # Step 4: state.json write (1.4.3, 0.2.5).
    try:
        with open(STATE_JSON_PATH, mode='w', encoding='utf-8') as f:
            json.dump(state_dict, f, ensure_ascii=False, indent=2, default=_json_default)
    except PermissionError:
        print(f"\nОшибка записи в файл '{STATE_JSON_PATH}'. "
              "\nЗакройте файл и повторите попытку. Задержка 30 сек и повторный запуск.")
        time.sleep(30)
        return save_characteristic()  # retry

    # Step 5: Snapshot для следующего STALE check'а.
    game.state.take_snapshot()

    # 4.6 — log_event факта успешного save.
    from history import log_event
    log_event('save')
    if sheets_network_error:
        print('\n💾 Save Successfully (local only).')
    else:
        print('\n💾 Save Successfully.')
    return "OK"
