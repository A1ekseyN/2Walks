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


# --- Backfill from history.jsonl ---

def backfill_from_history(
    state,
    history_jsonl_path: str = 'history.jsonl',
) -> dict[str, int]:
    """Сканит history.jsonl и накапливает event-based counters retroactively.

    Идемпотентно: повторный вызов с тем же history не дублирует counters
    (логика — пересчитываем с нуля только для event-based, потом recheck tiers).

    Returns dict `{triumph_id: backfilled_count_delta}` — сколько ДОБАВЛЕНО к
    counter в результате этого вызова (для UI feedback «backfill добавил +N»).

    Silent-fail если файла нет / corrupted: возвращает пустой dict, state не
    мутируется.

    Metric-based triumphs не нуждаются в backfill — `register_event` сам
    recheck'ает metrics. Этот helper только для event-based counters.
    """
    if state is None:
        return {}
    if not os.path.exists(history_jsonl_path):
        return {}

    # 1. Reset event-based counters (для idempotency повторных backfill'ов).
    # Метric-based триумфы не трогаем — у них нет counter.
    event_based_ids = [
        tid for tid, spec in TRIUMPHS.items() if 'event_hooks' in spec
    ]
    before_counts = {
        tid: int(state.triumphs.get(tid, {}).get('count', 0))
        for tid in event_based_ids
    }
    for tid in event_based_ids:
        ts = _ensure_triumph_state(state, tid)
        ts['count'] = 0  # reset для recompute

    # 2. Сканим history.jsonl, replay events через counter logic (без unlock
    # notifications — мы просто пересчитываем counters).
    try:
        with open(history_jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event_type = event.get('type', '')
                payload = event.get('payload', {})
                if not event_type:
                    continue

                # Replay event-based counter increments only (не recheck'аем
                # metrics — они auto-handle в register_event).
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
    except OSError:
        # Восстанавливаем counts если file read failed после reset.
        for tid, original in before_counts.items():
            state.triumphs[tid]['count'] = original
        return {}

    # 3. Recheck все tier unlocks (event-based и metric-based) после backfill.
    feedback = {}
    for tid in event_based_ids:
        spec_with_id = dict(TRIUMPHS[tid])
        spec_with_id['_id'] = tid
        current = _read_current_value(state, spec_with_id)
        _check_tier_unlocks(state, tid, TRIUMPHS[tid], current)
        delta = state.triumphs[tid]['count'] - before_counts[tid]
        if delta != 0:
            feedback[tid] = delta

    # Также recheck metric-based (на случай если они ещё не auto-unlock'нуты).
    for tid, spec in TRIUMPHS.items():
        if 'metric' not in spec:
            continue
        spec_with_id = dict(spec)
        spec_with_id['_id'] = tid
        current = _read_current_value(state, spec_with_id)
        _check_tier_unlocks(state, tid, spec, current)

    return feedback
