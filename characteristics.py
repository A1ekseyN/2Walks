"""State container + initialization orchestration.

После 1.3.3 (0.2.4y, 20.05.2026) persistence I/O (save/load/STALE prompt) вынесены
в `persistence.py`. Этот файл оставлен как «state lifecycle» helper:

- `_GameContainer` / `game` — singleton, к которому обращаются все модули через
  `from characteristics import game`. Заполняется через `init_game_state()`.
- `init_game_state(state=None)` — entry point: подгружает state из Sheets/CSV
  (через `persistence.load_data_from_google_sheet_or_csv`) либо принимает явный
  state (для тестов). Применяет post-load fixups.
- `apply_steps_log_max_merge(state)` — max-merge `state.steps.today` с записями
  `steps_log` за сегодня. Вызывается из init и `web.sync.try_reload_state`.

Persistence (save_characteristic / load_characteristic / handle_stale_prompt) —
**в `persistence.py`**. Импортёры используют `from persistence import ...`.
"""

from datetime import datetime
from typing import Any, Optional

from state import GameState


# ----------------------------------------------------------------------------
# State container (задача 1.2 — убрать побочные эффекты импорта).
#
# Вместо module-level `game_state = ...` (который грузил Sheets при импорте)
# держим контейнер `game` с атрибутом `state`. Атрибут заполняется через
# `init_game_state()`, которую CLI вызывает в начале `__main__`, а FastAPI
# — в startup hook.
#
# Все callers получают живую ссылку через `from characteristics import game`
# и обращаются как `game.state.<field>` — без проблемы "from import None".
# ----------------------------------------------------------------------------


class _GameContainer:
    """Wrapper-объект чтобы импортёры держали стабильную ссылку, а
    атрибут `state` мог быть переприсвоен после init."""
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

    # Lazy import: persistence импортирует `game` из этого модуля → circular
    # на module level, lazy внутри функции безопасно.
    from persistence import load_data_from_google_sheet_or_csv
    loaded = load_data_from_google_sheet_or_csv()
    s = GameState.from_dict(loaded)

    # 4.2 — Capture prior_timestamp_last_enter (= last save time). Используется
    # для report «пока тебя не было» (events from Sheets history с
    # `ts >= prior_ts`). С 4.2.1 / 0.2.5r (22.05.2026) overwrite на now() убран —
    # `timestamp_last_enter` теперь обновляется ТОЛЬКО в save_characteristic,
    # что correctly отражает web-активность (которая раньше не сдвигала marker).
    prior_ts = s.timestamp_last_enter

    # Legacy fixups, которые делались на module-level до 1.2:
    # - loc всегда сбрасывается в 'home' (загруженное значение игнорируется).
    # - energy_max — обновляем кэш-поле через compute_energy_max (4.48.4.1 / 0.2.1g);
    #   логика игры читает значение через `bonus.compute_energy_max(state)`, поле
    #   `state.energy_max` остаётся в dataclass для save-format совместимости.
    # Day rollover detection — единственная точка в functions.save_game_date_last_enter()
    # на первом тике main loop, через state.date_last_enter (legacy save.txt
    # удалён в задаче 2.1, версия 0.2.0k).
    s.loc = 'home'
    from bonus import compute_energy_max  # lazy — bonus импортирует equipment_bonus
    s.energy_max = compute_energy_max(s)

    # Max-merge с steps_log (задача 4.15) — поднимает state.steps.today до
    # максимума по записям лога за сегодня (web/iPhone/manual). Без этого CLI
    # не увидит ввод через web, если game_state лист ещё не обновлён.
    apply_steps_log_max_merge(s)

    # 4.62.1.1 fix (22.05.2026) — auto-unlock metric-based triumphs на старте
    # (без необходимости ждать первого register_event через log_event).
    # Решает UX: открыл Triumphs menu → видишь unlock'и сразу, не «потыкай».
    # Silent-fail — triumphs не критичный feature.
    # 4.62.4 (25.05.2026) — Newly unlocked tier'ы попадают в `unclaimed_unlocks`
    # claim queue (нужно явно [c] прокликать в menu). + One-shot backfill
    # uncliaimed для существующих pre-4.62.4 unlocks (synthesize entries для
    # уже-unlocked tier'ов в state.triumphs, чтобы старые достижения тоже
    # требовали acknowledge).
    try:
        from triumphs import init_metric_check, append_unclaimed, backfill_unclaimed_from_existing
        # Сначала synth-backfill для старых unlocked tier'ов (только если
        # queue пустой — это one-shot per save, после первого launch с 4.62.4
        # queue будет non-empty или claim'нут).
        if not s.unclaimed_unlocks:
            backfill_unclaimed_from_existing(s)
        # Теперь recheck metrics — может добавить новые unlocks которых ещё нет.
        new_unlocks = init_metric_check(s)
        if new_unlocks:
            append_unclaimed(s, new_unlocks)
    except Exception:  # noqa: BLE001
        pass

    # 4.2 — Build «пока тебя не было» report. Silent-fail если Sheets history
    # недоступен. Caller (CLI play / web _dashboard_context) рендерит и
    # очищает list. Lazy import — report → google_sheets_db → может тянуть
    # gspread, не нужен в тестах.
    s.startup_report_since_ts = prior_ts
    try:
        from report import build_away_report
        s.startup_report = build_away_report(prior_ts)
    except Exception:  # noqa: BLE001 — report не критичен
        s.startup_report = []

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
    # Lazy imports — google_sheets_db тянет gspread, не нужен в большинстве
    # тестов, плюс circular с persistence.
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
