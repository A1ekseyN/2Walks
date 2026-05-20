"""Persistence layer — save/load state в Google Sheets + CSV fallback.

Выделено из `characteristics.py` в задаче 1.3.3 (0.2.4y, 20.05.2026). До этого
все функции жили в characteristics.py что делало его mixed-concern файлом
(state container + persistence I/O в одном). После выноса:

- `characteristics.py` — state container (`game` singleton + `init_game_state`).
- `persistence.py` — save/load I/O + STALE prompt UI.

**Unified parser (1.4.2 одним проходом с 1.3.3, 0.2.4y):**
Раньше CSV и Sheets парсились разными функциями (`load_characteristic` +
`google_sheets_db._rows_to_state_dict`) с дублированной логикой. Теперь
оба используют общий `_parse_value(v, key)` — `json.loads` → `ast.literal_eval`
→ manual int/float/bool/empty detection → datetime fallback для DATE_KEYS.
Удалена дублированная типизация. Format сейвов не изменён —
backwards-compat 100%.
"""

import ast
import csv
import json
import time
from datetime import datetime
from typing import Any, Literal, Optional

from characteristics import game
from settings import debug_mode
from state import GameState


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

def load_characteristic() -> dict:
    """Считать сохранение из CSV (offline fallback). Использует unified
    `_parse_value` для каждой ячейки."""
    char_characteristic: dict[str, Any] = {}

    with open("characteristic.csv", mode='r', encoding='utf-8') as file:
        csv_reader = csv.reader(file)
        headers = next(csv_reader)
        data_row = next(csv_reader)
        for key, value in zip(headers, data_row):
            char_characteristic[key] = _parse_value(value, key=key)

    return char_characteristic


def load_data_from_google_sheet_or_csv() -> dict:
    """Сначала пытается загрузить данные из Google Sheets, при неудаче — CSV."""
    from google_sheets_db import GameStateRepo  # lazy для тестов
    try:
        loaded = GameStateRepo().load()
        if loaded:
            return loaded
        print("Google Sheets пуст. Загружаем данные из CSV файла.")
        loaded = load_characteristic()
        print("Loaded Data from CSV.")
        return loaded
    except Exception as error:
        print(f"Ошибка при загрузке данных из Google Sheets: {error}. Загружаем данные из CSV файла.")
        loaded = load_characteristic()
        print("Loaded Data from CSV.")
        return loaded


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
    """Save state: Sheets save_safe + локальный CSV (offline fallback).

    4.54.4 — обёртка для optimistic concurrency. Sheets save выполняется через
    `GameStateRepo.save_safe()` с pre-check `state.last_modified` vs Sheets.

    Returns:
    - **"OK"** — Sheets save прошёл (или сетевая ошибка — fall back на CSV-only).
      В этом случае: (1) `state.last_modified` синкается к новому timestamp'у
      от Sheets, (2) `state.last_loaded_snapshot` обновляется через `take_snapshot()`,
      (3) CSV пишется с новым timestamp'ом.
    - **"STALE"** — Sheets имеет newer `last_modified` (someone else сохранил
      первым). State не мутируется, CSV не пишется. Caller (4.54.5 CLI prompt /
      4.54.6 web flash) должен показать игроку diff + Reload/Force/Cancel.

    Сетевая ошибка Sheets → treat as "OK" (CSV-only fallback): pre-4.54 поведение
    сохраняется для offline-mode, игрок продолжает играть локально.

    Формат сохранения (4.20.1, 0.2.3b): `state_dict = game.state.to_dict()`
    — flat-dict со всеми полями. dict / list-значения серилазуются как
    JSON-строки (через `json.dumps`). Datetime — через `__str__()`.

    Историческая заметка (1.4.1, 0.2.3c — 07.05.2026): раньше save также
    писал в `characteristic.txt` (JSON), который никогда не читался —
    write-only zombie файл. Удалён в той задаче.
    """
    if game.state is None:
        raise RuntimeError("game.state не инициализирован — вызови init_game_state() до save_characteristic().")
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
        print(f'[save] Sheets sync failed (CSV-only fallback): {e}')
        sheets_network_error = True
        sheets_status = "OK"

    # Step 2: STALE — rejection, NO CSV write, NO state mutation. Caller handles.
    if sheets_status == "STALE":
        return "STALE"

    # Step 3: OK — синкаем state с тем что записано в Sheets.
    game.state.last_modified = state_dict.get('last_modified', game.state.last_modified)

    # Step 4: CSV write.
    try:
        with open('characteristic.csv', 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=state_dict.keys())
            writer.writeheader()
            processed_char = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
                              for k, v in state_dict.items()}
            writer.writerow(processed_char)
    except PermissionError:
        print("\nОшибка записи в файл 'characteristic.csv'. "
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
