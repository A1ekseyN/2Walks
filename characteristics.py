import time
from datetime import datetime
from typing import Any, Literal, Optional
import csv
import json
import ast

from settings import debug_mode
from google_sheets_db import GameStateRepo
from state import GameState


# ----------------------------------------------------------------------------
# State container (задача 1.2 — убрать побочные эффекты импорта).
#
# Вместо module-level `game_state = ...` (который грузил Sheets при импорте)
# держим контейнер `game` с атрибутом `state`. Атрибут заполняется через
# `init_game_state()`, которую CLI вызывает в начале `__main__`, а FastAPI
# (когда появится) — в startup hook.
#
# Все callers получают живую ссылку через `from characteristics import game`
# и обращаются как `game.state.<field>` — без проблемы "from import None".
# ----------------------------------------------------------------------------


class _GameContainer:
    """Контейнер для активного `GameState`. Один игрок = один state.

    Расширение до multi-user (задача 4.53) — заменить `state` на `states[user_id]`.
    """
    state: Optional[GameState] = None


game = _GameContainer()


def init_game_state(state: Optional[GameState] = None) -> GameState:
    """Идемпотентная инициализация игрового состояния.

    Вызывается в начале `__main__` (CLI) или из FastAPI startup hook.
    Если state передан — используется как есть (для тестов/инжекта). Иначе
    подгружается из Google Sheets / CSV и применяются post-load fixups.

    Возвращает заполненный `game.state`.
    """
    if game.state is not None:
        return game.state

    if state is not None:
        game.state = state
        return game.state

    loaded = load_data_from_google_sheet_or_csv()
    s = GameState.from_dict(loaded)

    # Legacy fixups, которые делались на module-level до 1.2:
    # - timestamp_last_enter всегда обновляется до текущего момента при загрузке.
    # - loc всегда сбрасывается в 'home' (загруженное значение игнорируется).
    # - energy_max — обновляем кэш-поле через compute_energy_max (4.48.4.1 / 0.2.1g);
    #   логика игры читает значение через `bonus.compute_energy_max(state)`, поле
    #   `state.energy_max` остаётся в dataclass для save-format совместимости.
    # Day rollover detection — единственная точка в functions.save_game_date_last_enter()
    # на первом тике main loop, через state.date_last_enter (legacy save.txt
    # удалён в задаче 2.1, версия 0.2.0k).
    s.timestamp_last_enter = datetime.now().timestamp()
    s.loc = 'home'
    from bonus import compute_energy_max  # lazy — bonus импортирует equipment_bonus
    s.energy_max = compute_energy_max(s)

    # Max-merge с steps_log (задача 4.15) — поднимает state.steps.today до
    # максимума по записям лога за сегодня (web/iPhone/manual). Без этого CLI
    # не увидит ввод через web, если game_state лист ещё не обновлён.
    apply_steps_log_max_merge(s)

    # 4.54.1 — Snapshot для optimistic concurrency. Берётся ПОСЛЕ всех
    # post-load fixups (timestamp_last_enter / loc / energy_max / max-merge)
    # чтобы snapshot отражал точно тот state, который мы считаем «synced с
    # Sheets». Diff на STALE сравнит fresh Sheets vs этот snapshot.
    s.take_snapshot()

    game.state = s
    return game.state


def apply_steps_log_max_merge(state: GameState) -> None:
    """Поднимает `state.steps.today` до максимума по `steps_log` записям за
    сегодня. Также пересчитывает `state.steps.can_use` если today изменился.

    Используется после load (в init_game_state и web.sync.try_reload_state)
    чтобы свежий ввод через любой канал (CLI / Web / iPhone) применялся
    немедленно, независимо от того, обновлён ли `game_state` лист в Sheets.

    Silent-fail при сетевой ошибке: если steps_log недоступен — оставляем
    state как есть. Лучше показать чуть-старое значение, чем падать.
    """
    # Lazy imports — characteristics.py загружается до google_sheets_db в
    # некоторых сценариях, а functions.py имеет циклическую зависимость.
    from google_sheets_db import StepsLogRepo

    today_str = datetime.now().strftime('%Y-%m-%d')
    try:
        entries = StepsLogRepo().for_day(today_str)
    except Exception:
        return  # silent fail

    if not entries:
        return

    max_in_log = max(e['steps'] for e in entries)
    if max_in_log > state.steps.today:
        state.steps.today = max_in_log
        # Recompute can_use — lazy import чтобы избежать circular.
        from functions import total_bonus_steps
        state.steps.can_use = state.steps.today - state.steps.used + total_bonus_steps(state)


def load_characteristic() -> dict:
    """Функция для считывания сохранения из csv файла"""
    char_characteristic: dict[str, Any] = {}

    with open("characteristic.csv", mode='r', encoding='utf-8') as file:
        csv_reader = csv.reader(file)
        headers = next(csv_reader)
        data_row = next(csv_reader)

        for key, value in zip(headers, data_row):
            # Преобразование значений в соответствующие типы данных
            if value.isdigit():
                char_characteristic[key] = int(value)
            elif value.replace('.', '', 1).isdigit():
                char_characteristic[key] = float(value)
            elif value.lower() in ['true', 'false']:
                char_characteristic[key] = value.lower() == 'true'
            elif value == '':
                char_characteristic[key] = None
            else:
                # Преобразование строковых представлений словарей и списков обратно в объекты Python
                try:
                    char_characteristic[key] = ast.literal_eval(value)
                except (ValueError, SyntaxError):
                    char_characteristic[key] = value

            if key in ['skill_training_time_end', 'working_end', 'adventure_end_timestamp'] \
                and isinstance(char_characteristic[key], str):
                try:
                    char_characteristic[key] = datetime.strptime(
                        char_characteristic[key], '%Y-%m-%d %H:%M:%S.%f'
                    )
                except ValueError:
                    pass

    return char_characteristic


def load_data_from_google_sheet_or_csv() -> dict:
    """Сначала пытается загрузить данные из Google Sheets, при неудаче — CSV."""
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

# skill_training_table + get_skill_training + get_energy_training_data вынесены
# в `skill_training_data.py` (1.3.2, версия 0.2.3e). Hard break — старый импорт
# `from characteristics import skill_training_table` больше не работает.
# Импортёры (gym.py, web/main.py) обновлены на `from skill_training_data import ...`.

# Список ключей, для которых ожидается дата/время (настройте по необходимости)
DATE_KEYS = [
    "date_last_enter",
    "energy_time_stamp",
    "working_start",
    "working_end",
    "skill_training_time_end",
    "adventure_end_timestamp"
]


def handle_stale_prompt() -> Literal["reload", "force", "cancel"]:
    """4.54.5 — Интерактивный STALE-prompt для CLI.

    Загружает fresh Sheets state, вычисляет diff vs `state.last_loaded_snapshot`
    (через `sync_diff.diff_states`), показывает detailed список изменений и
    предлагает 3 опции:

    - **r / reload** — `init_game_state(state=None)` re-init из Sheets,
      потеряешь свои несохранённые мутации. Snapshot обновится.
    - **f / force** — двойной confirm prompt, потом `save_characteristic_force()`
      перепишет Sheets своими данными, потеряешь серверные изменения.
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
            # Force save_safe с expected=None — bypass check.
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
        # Сетевая ошибка / Sheets недоступен → CSV-only fallback (pre-4.54 поведение).
        print(f'[save] Sheets sync failed (CSV-only fallback): {e}')
        sheets_network_error = True
        sheets_status = "OK"

    # Step 2: STALE — rejection, NO CSV write, NO state mutation. Caller handles.
    if sheets_status == "STALE":
        return "STALE"

    # Step 3: OK (или network fallback) — синкаем state с тем что записано в Sheets.
    # save_safe мутирует state_dict['last_modified'] к time.time() на успехе;
    # при network error state_dict['last_modified'] остаётся прежним (CSV напишет
    # старый ts — это OK, на восстановлении сети save_safe пересинкает).
    game.state.last_modified = state_dict.get('last_modified', game.state.last_modified)

    # Step 4: CSV write (с новым ts от Sheets, или старым при network error).
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
        return save_characteristic()  # retry (могло поменяться состояние Sheets — снова save_safe)

    # Step 5: Snapshot для следующего STALE check'а — отражает «что сейчас в Sheets/CSV».
    game.state.take_snapshot()

    # 4.6 — log_event факта успешного save.
    from history import log_event
    log_event('save')
    if sheets_network_error:
        print('\n💾 Save Successfully (local only).')
    else:
        print('\n💾 Save Successfully.')
    return "OK"
