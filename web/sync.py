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

from characteristics import game
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
    """
    global _last_reload
    if game.state is None:
        # init_game_state() ещё не отработал — это shouldn't happen в нормальном
        # потоке (lifespan вызывает его до первого запроса), но safety first.
        status = ReloadStatus(ok=False, at=datetime.now(), error="game.state not initialized")
    else:
        try:
            game.state.update_from_dict(GameStateRepo().load())
            status = ReloadStatus(ok=True, at=datetime.now())
        except Exception as e:
            status = ReloadStatus(ok=False, at=datetime.now(), error=str(e))
    _last_reload = status
    return status


def _reset_for_tests() -> None:
    """Сброс кэша last_reload между тестами. Не использовать в production."""
    global _last_reload
    _last_reload = None
