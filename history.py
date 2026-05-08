"""История значимых игровых событий — append-only лог (4.6).

Архитектура: dual-write (local + Sheets). Local — primary, sync, никогда не
fails (защищено try/except, в worst case warning в stdout). Sheets — best-effort
sync через `HistoryLogRepo`, fail-silent на сетевых / API проблемах. Local
файл всегда содержит полную историю; Sheets копия может временно отставать
при offline / API quota — re-sync механизм планируется в 4.6.3.

Формат события (JSONL line):
    {
      "v": 1,                   # версия схемы (для будущей миграции)
      "ts": 1746124425.5,       # Unix timestamp (float)
      "date": "2026-05-08",     # человеко-читаемое
      "time": "14:30:25",
      "user_id": "alex",        # для multi-user (4.53)
      "game_version": "0.2.4",
      "type": "work_done",      # discrete enum
      "payload": {...}          # type-specific dict
    }

Использование (explicit calls в mutation-сайтах):
    from history import log_event
    log_event('work_done', salary=40, hours=4, vacancy='watchman')

Pruning / rotation — отдельная подзадача 4.6.1.
CLI viewer (`h. История`) — 4.6.2.
Re-sync after Sheets recovery — 4.6.3.
"""

import json
import time
from datetime import datetime
from typing import Any

from config import DEFAULT_USER_ID, HISTORY_FILE


# Версия схемы события. Если поменяем структуру (e.g. nested payload, разные
# типы для одного event_type) — bump'нуть и реализовать миграцию на чтении.
EVENT_SCHEMA_VERSION = 1


def _build_event(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Собирает event-dict с метаданными. Pure function (unit-testable)."""
    now = time.time()
    dt = datetime.fromtimestamp(now)
    # Lazy import чтобы избежать циклических зависимостей (version.py
    # импортируется отдельно, не тянет state / sheets).
    from version import VERSION
    return {
        'v': EVENT_SCHEMA_VERSION,
        'ts': now,
        'date': dt.strftime('%Y-%m-%d'),
        'time': dt.strftime('%H:%M:%S'),
        'user_id': DEFAULT_USER_ID,
        'game_version': VERSION,
        'type': event_type,
        'payload': payload,
    }


def _write_local(event: dict[str, Any]) -> None:
    """Append event в локальный JSONL. Sync, защита от падения игры при I/O ошибке."""
    try:
        with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    except OSError as e:
        # Не валим игру — печатаем warning. Sheets-часть всё ещё может
        # отработать (или нет, но это лучше чем crash).
        print(f'⚠️ history.jsonl write failed: {e}')


def _write_sheets(event: dict[str, Any]) -> None:
    """Append event в Sheets `history` лист. Best-effort, fail-silent.

    Local файл уже содержит событие — Sheets failure не теряет данные.
    Re-sync missed events на восстановление Sheets — 4.6.3.
    """
    try:
        from google_sheets_db import HistoryLogRepo
        HistoryLogRepo().append(event)
    except Exception:
        # Silent — игра продолжает, лог есть локально.
        pass


def log_event(event_type: str, **payload: Any) -> None:
    """Единая точка записи события. Local + Sheets dual-write.

    Args:
        event_type: discrete тип события ('work_done', 'skill_upgraded', ...).
        **payload: type-specific поля (kwargs становятся payload dict'ом).

    Example:
        log_event('work_done', salary=40, hours=4, vacancy='watchman')
    """
    event = _build_event(event_type, payload)
    _write_local(event)
    _write_sheets(event)
