"""Triumphs engine — core logic (task 4.62.0.2).

Pure helpers без UI. UI слой в `triumphs_menu.py` (4.62.0.3) + web (4.62.7).
Catalog в `triumphs_data.py`.

**Архитектура:**

1. **register_event(state, event_type, **payload)** — главный entry point.
   Вызывается из `history.log_event` после write. Делает 2 вещи:
   - **Event-based:** для триумфов с `event_hooks` matching event_type —
     инкрементирует counter (по умолчанию +1 или payload-driven).
   - **Metric-based:** для всех триумфов с `metric` — recheck current value
     против tier thresholds (любой event = perfect moment recheck).
   Возвращает list newly-unlocked tier dicts для UI notifications.

2. **State structure** (`state.triumphs[id]`):
   - `tier: int` — highest unlocked tier index (0 = nothing yet, 1 = first tier, ...)
   - `unlocked_at: dict[str, str]` — tier_index (str) → ISO datetime when unlocked
   - `count: int` — event-based accumulator (не используется для metric-based)

3. **Idempotency:** повторный event не двигает уже unlocked tier. Engine
   проверяет current_value >= threshold + tier > current_tier.

4. **Backfill** (см. Backfill design в TASKS.md 4.62): `backfill_from_history`
   сканит `history.jsonl` и аккумулирует event counters retroactively. Helper
   pure — caller (UI) решает когда вызывать.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Optional

from triumphs_data import CATEGORIES, POINTS_PER_TIER, TRIUMPHS


# --- Visual constants (parallelogram style per 4.62 visual design) ---

_FILLED = '▰'  # U+25B0 BLACK PARALLELOGRAM
_EMPTY = '▱'   # U+25B1 WHITE PARALLELOGRAM
_TIER_SEP = '│'  # Tier boundary separator


# --- Internal helpers ---

def _ensure_triumph_state(state, triumph_id: str) -> dict:
    """Lazy-init triumph state entry. Returns dict ref (in-place mutable)."""
    if triumph_id not in state.triumphs:
        state.triumphs[triumph_id] = {
            'tier': 0,
            'unlocked_at': {},
            'count': 0,
        }
    entry: dict = state.triumphs[triumph_id]
    return entry


def _read_current_value(state, spec: dict) -> int:
    """Возвращает current value для tier comparison.

    Metric-based — читает через `spec['metric'](state)`.
    Event-based — берёт `state.triumphs[id]['count']`.
    """
    if 'metric' in spec:
        try:
            value = spec['metric'](state)
        except Exception:  # noqa: BLE001 — defensive: metric может сломаться при partial state
            return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    # Event-based: count из state.
    triumph_id = spec.get('_id', '')
    if triumph_id in state.triumphs:
        return int(state.triumphs[triumph_id].get('count', 0))
    return 0


def _check_tier_unlocks(state, triumph_id: str, spec: dict, current_value: int) -> list[int]:
    """Идемпотентно проверяет и unlock'ает все tiers `tier_index > current_tier`
    которые threshold'у удовлетворяют.

    Returns list of newly unlocked tier indexes (1-based, как тиеры в catalog).
    Empty list если ничего нового.
    """
    triumph_state = _ensure_triumph_state(state, triumph_id)
    current_tier = int(triumph_state.get('tier', 0))
    tiers = spec.get('tiers', [])
    newly_unlocked = []
    now_iso = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    for i, threshold in enumerate(tiers, start=1):
        if i <= current_tier:
            continue  # уже unlocked
        if current_value >= threshold:
            triumph_state['tier'] = i
            triumph_state['unlocked_at'][str(i)] = now_iso
            newly_unlocked.append(i)
        else:
            break  # tiers упорядочены, дальше тоже не пройдут

    return newly_unlocked


# --- Public API ---

def register_event(state, event_type: str, **payload) -> list[dict]:
    """Главный entry point. Вызывается из `history.log_event` после write.

    Делает 2 вещи:
    1. Event-based counters increment для triumph'ов с matching `event_hooks`.
    2. Metric-based recheck для всех metric триумфов.

    Returns list of newly unlocked tier dicts: `[{'triumph_id', 'tier_index',
    'name', 'is_capstone'}, ...]` для UI notifications.

    Idempotent: повторный event не unlock'ает уже-unlocked tier. Safe to call
    с empty catalog (TRIUMPHS = {}).
    """
    if state is None:
        return []
    unlocked: list[dict] = []

    for triumph_id, spec in TRIUMPHS.items():
        spec_with_id = dict(spec)
        spec_with_id['_id'] = triumph_id  # для _read_current_value на event-based

        # 1. Event-based counter increment.
        hooks = spec.get('event_hooks', [])
        if event_type in hooks:
            # Optional filter (например 'drop' только S+ grade).
            event_filter = spec.get('event_filter')
            if event_filter is not None:
                try:
                    if not event_filter(payload):
                        continue
                except Exception:  # noqa: BLE001
                    continue
            # Optional delta function (например work_done +hours).
            delta_fn = spec.get('count_delta', lambda _p: 1)
            try:
                delta = int(delta_fn(payload))
            except Exception:  # noqa: BLE001
                delta = 1
            if delta > 0:
                triumph_state = _ensure_triumph_state(state, triumph_id)
                triumph_state['count'] = int(triumph_state.get('count', 0)) + delta

        # 2. Recheck tier unlocks (works for both metric и event-based).
        current_value = _read_current_value(state, spec_with_id)
        newly = _check_tier_unlocks(state, triumph_id, spec, current_value)
        for tier_idx in newly:
            unlocked.append({
                'triumph_id': triumph_id,
                'tier_index': tier_idx,
                'name': spec.get('name', triumph_id),
                'is_capstone': tier_idx == len(spec.get('tiers', [])),
            })

    return unlocked


def get_progress(state, triumph_id: str) -> Optional[dict]:
    """Returns progress dict для triumph_id или None если ID не в catalog'е.

    Dict structure:
    - `current_tier: int` — highest unlocked (0 если none)
    - `total_tiers: int` — len(spec['tiers'])
    - `current_value: int` — текущий metric/counter
    - `next_threshold: Optional[int]` — порог следующего tier (None если все unlocked)
    - `progress_pct: float` — % до next tier (или 100 если capstone reached)
    - `is_capstone: bool` — все tiers unlocked
    - `tiers: list[int]` — copy thresholds (для UI rendering)
    """
    spec = TRIUMPHS.get(triumph_id)
    if spec is None:
        return None
    spec_with_id = dict(spec)
    spec_with_id['_id'] = triumph_id

    triumph_state = state.triumphs.get(triumph_id, {})
    current_tier = int(triumph_state.get('tier', 0))
    tiers = spec.get('tiers', [])
    total_tiers = len(tiers)
    current_value = _read_current_value(state, spec_with_id)

    is_capstone = current_tier >= total_tiers
    if is_capstone:
        next_threshold = None
        progress_pct = 100.0
    else:
        next_threshold = tiers[current_tier]
        prev_threshold = tiers[current_tier - 1] if current_tier > 0 else 0
        if next_threshold > prev_threshold:
            progress_pct = (
                (current_value - prev_threshold) / (next_threshold - prev_threshold) * 100.0
            )
            progress_pct = max(0.0, min(100.0, progress_pct))
        else:
            progress_pct = 100.0

    return {
        'current_tier': current_tier,
        'total_tiers': total_tiers,
        'current_value': current_value,
        'next_threshold': next_threshold,
        'progress_pct': progress_pct,
        'is_capstone': is_capstone,
        'tiers': list(tiers),
        'name': spec.get('name', triumph_id),
        'category': spec.get('category', 'misc'),
    }


def init_metric_check(state) -> list[dict]:
    """4.62.1.1 fix (22.05.2026) — Metric-based recheck для всех metric triumph'ов.

    Вызывается из `init_game_state` после load — auto-unlock metric-based
    triumph'ов на старте игры (без необходимости ждать первого log_event).
    Решает UX-проблему: игрок открывает Triumphs menu и видит Marathoner
    unlocked сразу, а не «нужно потыкать чтобы триггернуть recheck».

    Event-based triumphs НЕ трогаются (их counters обновляются только при
    реальных event'ах через register_event).

    Returns list newly-unlocked dicts (для opcional notifications в caller'е).
    Идемпотентен — повторный вызов с тем же state не unlock'ает уже-unlocked.
    """
    if state is None:
        return []
    unlocked: list[dict] = []
    for triumph_id, spec in TRIUMPHS.items():
        if 'metric' not in spec:
            continue
        spec_with_id = dict(spec)
        spec_with_id['_id'] = triumph_id
        current = _read_current_value(state, spec_with_id)
        newly = _check_tier_unlocks(state, triumph_id, spec, current)
        for tier_idx in newly:
            unlocked.append({
                'triumph_id': triumph_id,
                'tier_index': tier_idx,
                'name': spec.get('name', triumph_id),
                'is_capstone': tier_idx == len(spec.get('tiers', [])),
            })
    return unlocked


def total_score(state) -> int:
    """Sum points по unlocked tiers всех triumph'ов в catalog'е."""
    total = 0
    for triumph_id, spec in TRIUMPHS.items():
        unlocked_tier = int(state.triumphs.get(triumph_id, {}).get('tier', 0))
        points_per = int(spec.get('points_per_tier', POINTS_PER_TIER))
        total += unlocked_tier * points_per
    return total


# --- 4.62.4 — Unclaimed unlocks (Destiny-2 claim mechanic) ---

import time as _time


def append_unclaimed(state, unlocks: list[dict]) -> None:
    """Добавляет newly-unlocked tier'ы в `state.unclaimed_unlocks` (dedupe).

    Каждый unlock `{triumph_id, tier_index, ..., [kind]}` мапится в unclaimed
    entry `{triumph_id, tier, unlocked_ts, kind}`. Dedupe по `(triumph_id, tier,
    kind)` — повторный register_event для уже-unclaimed tier'а no-op.

    Поле `kind` (4.62.3) — 'triumph' (default) или 'seal' для seal unlocks.
    Seal entries: triumph_id = category key, tier = 0 (unused для seals).

    Используется из `history.log_event` auto-hook (после register_event),
    из `init_metric_check` (startup auto-unlocks) и из `backfill_from_history`.
    """
    if state is None or not unlocks:
        return
    if not hasattr(state, 'unclaimed_unlocks') or state.unclaimed_unlocks is None:
        state.unclaimed_unlocks = []
    existing_keys = {
        (e.get('triumph_id'), int(e.get('tier', 0)), e.get('kind', 'triumph'))
        for e in state.unclaimed_unlocks
    }
    now_ts = _time.time()
    for u in unlocks:
        tid = u.get('triumph_id')
        tier = int(u.get('tier_index', 0))
        kind = u.get('kind', 'triumph')
        if not tid or (tid, tier, kind) in existing_keys:
            continue
        state.unclaimed_unlocks.append({
            'triumph_id': tid,
            'tier': tier,
            'unlocked_ts': now_ts,
            'kind': kind,
        })
        existing_keys.add((tid, tier, kind))


def get_unclaimed_for(state, triumph_id: str) -> list[dict]:
    """Возвращает список unclaimed entries для одного triumph'а (any tier).

    Empty list если нет unclaimed для этого triumph'а. Используется UI для
    показа ✨ marker'а + count в detail view.
    """
    if state is None or not state.unclaimed_unlocks:
        return []
    return [
        e for e in state.unclaimed_unlocks
        if e.get('triumph_id') == triumph_id
    ]


def claim_triumph(state, triumph_id: str, kind: str = 'triumph') -> int:
    """Помечает все unclaimed entries для triumph'а+kind как claimed (удаляет их).

    Returns count claimed tier'ов (для UI feedback).

    `kind` (4.62.3) — 'triumph' (default) для tier unlocks, или 'seal' для
    seal unlocks. Без фильтра по kind triumph 'foo' и seal cat_key 'foo'
    конфликтовали бы.

    Note (4.62.7.1, 25.05.2026): этот helper остался batch-API (clear все
    tier'ы для triumph'а). UI теперь использует `claim_one_tier` per-click
    для granular acknowledge (один tier = один claim).
    """
    if state is None or not state.unclaimed_unlocks:
        return 0
    before = len(state.unclaimed_unlocks)
    state.unclaimed_unlocks = [
        e for e in state.unclaimed_unlocks
        if not (e.get('triumph_id') == triumph_id and e.get('kind', 'triumph') == kind)
    ]
    return before - len(state.unclaimed_unlocks)


def claim_one_tier(state, triumph_id: str, kind: str = 'triumph') -> Optional[dict]:
    """4.62.7.1 (25.05.2026) — Claim **один** (oldest) unclaimed tier для
    triumph'а+kind. Per-tier acknowledge pattern (Destiny-2 style) — каждый
    tier = отдельный «приз», игрок прокликивает их по одному.

    Sort order: (unlocked_ts ASC, tier ASC) — oldest first. Если несколько
    tier'ов unlocked одним register_event (одинаковый unlocked_ts) — берётся
    с меньшим tier'ом (tier 1 раньше tier 2).

    Returns:
    - Удалённый entry dict (для UI feedback с tier number / name) или
    - None если нет matching entries в queue.
    """
    if state is None or not state.unclaimed_unlocks:
        return None
    # Find oldest matching entry.
    matching = [
        (i, e) for i, e in enumerate(state.unclaimed_unlocks)
        if e.get('triumph_id') == triumph_id
        and e.get('kind', 'triumph') == kind
    ]
    if not matching:
        return None
    # Sort by (unlocked_ts, tier) ASC.
    matching.sort(key=lambda pair: (
        float(pair[1].get('unlocked_ts', 0) or 0),
        int(pair[1].get('tier', 0)),
    ))
    idx, entry = matching[0]
    # Remove from queue (single pop by index).
    state.unclaimed_unlocks = (
        state.unclaimed_unlocks[:idx] + state.unclaimed_unlocks[idx + 1:]
    )
    result: dict = entry
    return result


def next_unclaimed_tier(state, triumph_id: str, kind: str = 'triumph') -> Optional[int]:
    """UI helper: tier number следующего unclaimed entry (для label кнопки
    «[✓ Собрать tier N]»). None если нет unclaimed для triumph'а.

    Same sort order как `claim_one_tier` (oldest first).
    """
    if state is None or not state.unclaimed_unlocks:
        return None
    matching = [
        e for e in state.unclaimed_unlocks
        if e.get('triumph_id') == triumph_id
        and e.get('kind', 'triumph') == kind
    ]
    if not matching:
        return None
    matching.sort(key=lambda e: (
        float(e.get('unlocked_ts', 0) or 0),
        int(e.get('tier', 0)),
    ))
    return int(matching[0].get('tier', 0))


def claim_all(state) -> int:
    """Claim все unclaimed entries за один раз.

    Returns count claimed entries (для UI feedback).
    """
    if state is None or not state.unclaimed_unlocks:
        return 0
    count = len(state.unclaimed_unlocks)
    state.unclaimed_unlocks = []
    return count


# --- 4.62.3 Seals & Titles ---

def is_seal_unlocked(state, cat_key: str) -> bool:
    """Seal unlocked если ВСЕ triumph'ы категории на capstone tier.

    Если в категории нет ни одного triumph'а → False (нет ничего
    capstone'нуть). Не зависит от наличия seal в SEALS — caller проверяет
    отдельно (некоторые категории могут не иметь seal).
    """
    if state is None:
        return False
    cat_triumph_ids = [
        tid for tid, spec in TRIUMPHS.items()
        if spec.get('category') == cat_key
    ]
    if not cat_triumph_ids:
        return False
    for tid in cat_triumph_ids:
        spec = TRIUMPHS[tid]
        total_tiers = len(spec.get('tiers', []))
        if total_tiers == 0:
            return False
        unlocked_tier = int(state.triumphs.get(tid, {}).get('tier', 0))
        if unlocked_tier < total_tiers:
            return False
    return True


def available_seals(state) -> list[str]:
    """Returns list category keys для которых seal unlocked И SEAL existует
    в SEALS catalog'е."""
    from triumphs_data import SEALS
    if state is None:
        return []
    return [
        cat_key for cat_key in SEALS.keys()
        if is_seal_unlocked(state, cat_key)
    ]


def available_titles(state) -> list[str]:
    """Returns list title strings из unlocked seals (для UI title selection)."""
    from triumphs_data import SEALS
    return [SEALS[cat_key]['name'] for cat_key in available_seals(state)]


def set_title(state, title: Optional[str]) -> None:
    """Set active title. None = снять title.

    Не валидирует что title в available_titles — caller ответственен
    (UI показывает только доступные).
    """
    if state is None:
        return
    state.title = title


def check_seal_unlocks(state) -> list[dict]:
    """4.62.3 — Detect newly unlocked seals (для unclaimed queue).

    Compares current `available_seals(state)` с уже claimed seals (tracked
    через `state.triumphs['__seal__'][cat_key]` marker dict). Returns list
    of dict'ов в формате compatible с `append_unclaimed`:
    `[{triumph_id: cat_key, tier_index: 0, name: SEAL_NAME, kind: 'seal'}, ...]`

    Idempotent: повторный call после claim не вернёт тот же seal.
    """
    from triumphs_data import SEALS
    if state is None:
        return []
    # Marker storage — особый «pseudo-triumph» __seal__ в state.triumphs
    # хранит уже-acknowledged seal keys (избегаем нового state-поля).
    seal_marker = state.triumphs.setdefault('__seal__', {'acknowledged': []})
    if not isinstance(seal_marker.get('acknowledged'), list):
        seal_marker['acknowledged'] = []
    already_ack = set(seal_marker['acknowledged'])

    new_unlocks: list[dict] = []
    for cat_key in available_seals(state):
        if cat_key in already_ack:
            continue
        seal_meta = SEALS.get(cat_key, {})
        new_unlocks.append({
            'triumph_id': cat_key,
            'tier_index': 0,
            'name': seal_meta.get('name', cat_key.title()),
            'is_capstone': True,
            'kind': 'seal',
        })
        seal_marker['acknowledged'].append(cat_key)
    return new_unlocks


def backfill_unclaimed_from_existing(state) -> int:
    """4.62.4 (one-shot для existing players): создаёт unclaimed entries для
    всех уже-unlocked tier'ов в `state.triumphs` которых ещё нет в queue.

    Используется при первом launch версии 4.62.4 для игроков у которых уже
    есть unlocked triumph'ы (например Marathoner tier 3, Skill Master tier 2).
    Без этого helper'а старые unlocks остались бы invisible — claim queue был
    бы пустой, игрок никогда не «acknowledged» прошлые достижения.

    Идемпотентен через dedupe в append_unclaimed (повторный вызов не создаёт
    duplicates). Возвращает count добавленных entries.
    """
    if state is None:
        return 0
    synthetic_unlocks: list[dict] = []
    for triumph_id, ts in (state.triumphs or {}).items():
        unlocked_tier = int(ts.get('tier', 0))
        if unlocked_tier <= 0:
            continue
        # Synthesize unlock entry для каждого tier'а 1..unlocked_tier.
        spec = TRIUMPHS.get(triumph_id)
        if spec is None:
            continue
        total_tiers = len(spec.get('tiers', []))
        for tier_idx in range(1, unlocked_tier + 1):
            synthetic_unlocks.append({
                'triumph_id': triumph_id,
                'tier_index': tier_idx,
                'name': spec.get('name', triumph_id),
                'is_capstone': tier_idx == total_tiers,
            })
    before = len(state.unclaimed_unlocks or [])
    append_unclaimed(state, synthetic_unlocks)
    return len(state.unclaimed_unlocks) - before


# --- Progress bar formatter ---

def _format_progress_bar(
    current: int,
    target: int,
    tier_thresholds: Optional[list[int]] = None,
    width: int = 10,
) -> str:
    """Формирует progress bar парallelogram'ами `▰▱` + tier separators `│`.

    Args:
        current: текущее значение.
        target: финальное значение (= max tier threshold).
        tier_thresholds: список intermediate tier boundaries (включая target).
            Если задан и > 1 tier — добавляем separators `│` между tier'ами.
        width: total cells (без separator'ов). По умолчанию 10.

    Examples:
        >>> _format_progress_bar(400_000, 1_000_000, width=10)
        '▰▰▰▰▱▱▱▱▱▱'
        >>> _format_progress_bar(30, 500, tier_thresholds=[10, 50, 100, 500])
        '▰▰▰│▱▱│▱▱│▱▱'

    Behavior:
        - Если current >= target → all filled, no separator.
        - Если current < 0 или target <= 0 → all empty.
        - Multi-tier с separators: cells распределяются proportionally по tiers,
          separator показывается между tier-segments.
    """
    if target <= 0 or width <= 0:
        return _EMPTY * max(0, width)
    current = max(0, min(current, target))

    # Single-tier (no separators) — простой fill.
    if not tier_thresholds or len(tier_thresholds) <= 1:
        filled = round(current / target * width)
        filled = max(0, min(filled, width))
        return _FILLED * filled + _EMPTY * (width - filled)

    # Multi-tier with separators: **equal-sized segments** (22.05.2026 UX fix).
    # Каждый tier = равное количество cells, независимо от threshold span.
    # Tier — это unit of progress; одинаковый visual weight для всех tier'ов
    # лучше отражает gameplay (закрыть все = одинаковая ценность). Раньше был
    # proportional (большие thresholds = больше cells) — мелкие tier'ы
    # терялись (для Marathoner 100k/500k/1M get 1 cell each due to round-down).
    tiers = sorted(tier_thresholds)
    if tiers[-1] <= 0:
        return _EMPTY * width
    n_tiers = len(tiers)
    # Distribute cells equally; первые `remainder` tier'ов получают +1 cell.
    base_cells = width // n_tiers
    remainder = width - base_cells * n_tiers
    cells_per_tier = [base_cells + (1 if i < remainder else 0) for i in range(n_tiers)]
    # Ensure min 1 cell per tier (когда width < n_tiers).
    cells_per_tier = [max(1, c) for c in cells_per_tier]

    # Заполняем каждый tier-segment + separators между.
    segments = []
    prev_threshold = 0
    for i, threshold in enumerate(tiers):
        tier_cells = cells_per_tier[i]
        tier_span = threshold - prev_threshold
        if current >= threshold:
            tier_filled = tier_cells
        elif current <= prev_threshold:
            tier_filled = 0
        elif tier_span > 0:
            tier_filled = round((current - prev_threshold) / tier_span * tier_cells)
            tier_filled = max(0, min(tier_filled, tier_cells))
        else:
            tier_filled = 0
        segments.append(_FILLED * tier_filled + _EMPTY * (tier_cells - tier_filled))
        prev_threshold = threshold

    return _TIER_SEP.join(segments)


# --- Backfill from history (jsonl file + Sheets) ---

def _replay_events_into_counters(state, events: list[dict]) -> dict[str, int]:
    """Internal: reset event-based counters → replay events → update max-trackers
    (Iron Worker `state.work.longest_shift_hours`) → recheck tier unlocks →
    push unclaimed.

    Shared logic для `backfill_from_history` (local jsonl) и
    `backfill_from_sheets_history` (cross-device через Sheets `history` лист).
    Caller отвечает за получение list events (file parsing / Sheets API).

    Returns `{triumph_id: count_delta}` feedback dict.
    """
    if state is None:
        return {}

    # 1. Reset event-based counters (для idempotency повторных backfill'ов).
    event_based_ids = [
        tid for tid, spec in TRIUMPHS.items() if 'event_hooks' in spec
    ]
    before_counts = {
        tid: int(state.triumphs.get(tid, {}).get('count', 0))
        for tid in event_based_ids
    }
    for tid in event_based_ids:
        ts = _ensure_triumph_state(state, tid)
        ts['count'] = 0

    # 2. Replay events.
    # 4.62.1.5.1 — Iron Worker max-tracker: scan work_done для max(hours).
    # Generic pattern — если в будущем появятся другие max-trackers (biggest
    # drop, longest streak), добавляются здесь же.
    max_shift = int(getattr(state.work, 'longest_shift_hours', 0))
    for event in events:
        event_type = event.get('type', '')
        payload = event.get('payload', {})
        if not event_type:
            continue

        # Iron Worker max-tracker.
        if event_type == 'work_done':
            hours = int(payload.get('hours', 0) or 0)
            if hours > max_shift:
                max_shift = hours

        # Event-based counters.
        for tid in event_based_ids:
            spec = TRIUMPHS[tid]
            if event_type not in spec.get('event_hooks', []):
                continue
            event_filter = spec.get('event_filter')
            if event_filter is not None:
                try:
                    if not event_filter(payload):
                        continue
                except Exception:  # noqa: BLE001
                    continue
            delta_fn = spec.get('count_delta', lambda _p: 1)
            try:
                delta = int(delta_fn(payload))
            except Exception:  # noqa: BLE001
                delta = 1
            if delta > 0:
                state.triumphs[tid]['count'] += delta

    # 3. Apply max-tracker updates.
    state.work.longest_shift_hours = max_shift

    # 4. Recheck все tier unlocks (event-based + metric-based) + collect
    # unlocks для unclaimed queue.
    feedback: dict[str, int] = {}
    all_new_unlocks: list[dict] = []
    for tid in event_based_ids:
        spec = TRIUMPHS[tid]
        spec_with_id = dict(spec)
        spec_with_id['_id'] = tid
        current = _read_current_value(state, spec_with_id)
        newly = _check_tier_unlocks(state, tid, spec, current)
        for tier_idx in newly:
            all_new_unlocks.append({
                'triumph_id': tid,
                'tier_index': tier_idx,
                'name': spec.get('name', tid),
                'is_capstone': tier_idx == len(spec.get('tiers', [])),
            })
        delta = state.triumphs[tid]['count'] - before_counts[tid]
        if delta != 0:
            feedback[tid] = delta

    for tid, spec in TRIUMPHS.items():
        if 'metric' not in spec:
            continue
        spec_with_id = dict(spec)
        spec_with_id['_id'] = tid
        current = _read_current_value(state, spec_with_id)
        newly = _check_tier_unlocks(state, tid, spec, current)
        for tier_idx in newly:
            all_new_unlocks.append({
                'triumph_id': tid,
                'tier_index': tier_idx,
                'name': spec.get('name', tid),
                'is_capstone': tier_idx == len(spec.get('tiers', [])),
            })

    append_unclaimed(state, all_new_unlocks)
    return feedback


def backfill_from_history(
    state,
    history_jsonl_path: str = 'history.jsonl',
) -> dict[str, int]:
    """Backfill через **local** `history.jsonl` (CLI machine only).

    Limitation: web events с сервера не учитываются — у server'а свой jsonl.
    Для cross-device backfill см. `backfill_from_sheets_history`.

    Идемпотентно: повторный вызов с тем же history не дублирует counters
    (логика — пересчитываем с нуля только для event-based, потом recheck tiers).

    Returns dict `{triumph_id: backfilled_count_delta}`. Silent-fail если файла
    нет / corrupted.
    """
    if state is None:
        return {}
    if not os.path.exists(history_jsonl_path):
        return {}

    try:
        events: list[dict] = []
        with open(history_jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return {}

    return _replay_events_into_counters(state, events)


def backfill_from_sheets_history(state) -> dict[str, int]:
    """4.62.6 (25.05.2026) — Backfill через **Sheets `history` лист**
    (cross-device).

    Pulls ALL events через `HistoryLogRepo.since(0)` — это включает события
    из CLI И web (server), в отличие от `backfill_from_history` который читает
    только local jsonl. Это позволяет existing player'у получить полный credit
    за прошлую активность даже когда часть событий записана с phone web на
    server и не присутствует в local jsonl.

    Идемпотентно (как и file-based backfill — reset → replay). Silent-fail
    если Sheets недоступен.
    """
    if state is None:
        return {}
    try:
        from google_sheets_db import HistoryLogRepo
        events = HistoryLogRepo().since(0)
    except Exception:  # noqa: BLE001 — Sheets unavailable / network error
        return {}
    if not events:
        return {}
    return _replay_events_into_counters(state, events)
