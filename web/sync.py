"""Минимальная синхронизация web ↔ Sheets (задача 4.54.0).

Задача: web-dashboard держит `game.state` в памяти uvicorn, и без явного
действия не подтягивает свежие данные из Sheets. Если параллельно играешь в
CLI и сохраняешься, web не видит изменений до рестарта.

Решение (variant D):
- `GET /` (заход на главную / F5 / pull-to-refresh) — `try_reload_state()`
  обновляет `game.state` через `GameStateRepo().load()`. Свежие данные на
  каждом заходе.
- `GET /status` (HTMX-полинг каждые 60 сек) — НЕ зовёт reload, рендерит из
  памяти. Не нагружает Sheets API.
- При ошибке Sheets во время reload: оставляем кэшированный state + сохраняем
  `ReloadStatus(ok=False, ...)`, чтобы UI мог показать badge "Cloud sync failed".

Полноценная двусторонняя sync с conflict detection — задача 4.54.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from characteristics import apply_steps_log_max_merge, game, save_characteristic
from functions import save_game_date_last_enter
from google_sheets_db import GameStateRepo


@dataclass
class ReloadStatus:
    """Результат последнего вызова `try_reload_state()`. Используется UI для
    показа badge при сбое."""
    ok: bool
    at: datetime
    error: Optional[str] = None


# Кэш последнего попытки reload — UI читает через get_last_reload().
_last_reload: Optional[ReloadStatus] = None


def get_last_reload() -> Optional[ReloadStatus]:
    """Последний `ReloadStatus` или None, если reload ещё не вызывался."""
    return _last_reload


def try_reload_state() -> ReloadStatus:
    """Обновляет `game.state` из Google Sheets in-place (через
    `state.update_from_dict`). Не падает при сетевой ошибке — сохраняет
    ReloadStatus с ok=False и оставляет кэшированный state без изменений.

    Возвращает ReloadStatus и сохраняет его как последний результат
    (доступен через get_last_reload()).

    Day rollover (4.54.0.2): после успешного reload вызываем
    `save_game_date_last_enter` — он сравнит `state.date_last_enter` с
    сегодняшней датой и при необходимости перенесёт `today → yesterday`,
    обнулит `today/used`, начислит daily_bonus за вчерашние 10k+. Если
    rollover фактически произошёл (`state.date_last_enter` изменился),
    persist'им свежий state в Sheets+CSV+JSON, чтобы CLI и web видели
    одинаковую картину. Активные сессии (work/training/adventure) при
    rollover не трогаем — таймер продолжает идти через midnight как в CLI.
    """
    global _last_reload
    if game.state is None:
        # init_game_state() ещё не отработал — это shouldn't happen в нормальном
        # потоке (lifespan вызывает его до первого запроса), но safety first.
        status = ReloadStatus(ok=False, at=datetime.now(), error="game.state not initialized")
    else:
        try:
            game.state.update_from_dict(GameStateRepo().load())
            # Max-merge со steps_log (4.15) — применяем свежий ввод из любого
            # канала (CLI / Web / iPhone), даже если game_state лист ещё не
            # обновлён. Silent-fail внутри если steps_log недоступен.
            apply_steps_log_max_merge(game.state)
            # Day rollover (4.54.0.2). save_game_date_last_enter idempotent —
            # на тот же день no-op, кроме пересчёта can_use.
            old_date = game.state.date_last_enter
            save_game_date_last_enter(game.state)
            if game.state.date_last_enter != old_date:
                # Фактический rollover произошёл — синкаем свежий state.
                persist_state_to_cloud()
            status = ReloadStatus(ok=True, at=datetime.now())
        except Exception as e:
            status = ReloadStatus(ok=False, at=datetime.now(), error=str(e))
    _last_reload = status
    return status


def persist_state_to_cloud() -> None:
    """Локальное сохранение (JSON+CSV) + push в Google Sheets.

    Локальное всегда первым (гарантия offline-mode). Sheets — best-effort:
    если упадёт сетевой, сообщение в лог uvicorn'а, но web-операция не
    отвалится. Применяется после каждой мутирующей web-операции
    (start/add_hours смены, day rollover).

    Жил исторически в web/main.py, перенесён сюда в 0.2.1b чтобы
    try_reload_state мог зайти после rollover-а без циркулярного импорта
    (web/sync ↔ web/main).
    """
    save_characteristic()
    try:
        GameStateRepo().save(game.state.to_dict())
    except Exception as e:  # noqa: BLE001 — best-effort sync
        print(f"[web] Sheets save failed (state cached locally): {e}")


def _reset_for_tests() -> None:
    """Сброс кэша last_reload между тестами. Не использовать в production."""
    global _last_reload
    _last_reload = None
