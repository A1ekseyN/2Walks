"""Triumphs catalog — static data (task 4.62.0.2).

Пустой при foundation phase (4.62.0.x). Catalog заполняется по одной категории
за раз в Phase 2 (4.62.1.1 Steps / 4.62.1.2 Adventures / etc).

**Структура TRIUMPHS entry:**
```python
TRIUMPHS = {
    'marathoner': {
        'name': 'Marathoner',                # Human-readable
        'category': 'steps',                  # Группировка в menu
        'tiers': [10_000, 100_000, 1_000_000, 10_000_000],  # Tier thresholds
        # Один из:
        'metric': lambda state: state.steps.total_used,     # Metric-based
        # ИЛИ:
        'event_hooks': ['adventure_done'],    # Event-based counter increment
        'count_delta': lambda payload: 1,     # По умолчанию +1 per event
        # ИЛИ для accumulators (work hours, energy):
        'count_delta': lambda payload: payload.get('hours', 0),
        # Опционально:
        'event_filter': lambda payload: payload.get('grade') == 's+grade',  # Filter
        'hidden': False,                      # 4.62.5 hidden until unlock
        'points_per_tier': 10,                # Override POINTS_PER_TIER если custom
    },
}
```

**Конвенции:**
- Используем строки grade ('s+grade' / 's-grade' / ...) консистентно с item['grade'][0].
- `metric` и `event_hooks` — взаимно-исключающие (один триумф — один тип).
- `event_filter` опционально для filter'а конкретных payload values (например 'drop' только S+).
"""

# Points за unlock одного tier'а (constant в MVP). Custom override через
# TRIUMPHS[id]['points_per_tier'].
POINTS_PER_TIER: int = 10


TRIUMPHS: dict[str, dict] = {
    # ----- 🏃 Steps (4.62.1.1, 22.05.2026) -----
    # Marathoner — metric-based, читает state.steps.total_used (ПОТРАЧЕННЫЕ
    # шаги, не walked). Поощряет активную игру: work / training / adventures.
    # Симметрично с другими активными metric'ами (Trader / Earnings Boost).
    #
    # Tiers chosen 22.05.2026:
    # - 100k: первый meaningful milestone (1-2 недели casual play). 10k был бы
    #   too easy (achievable за 1 день + 1 shift).
    # - 500k: intermediate gate в середине (3-4 месяца). Раньше gap 100k→1M
    #   был too big.
    # - 1M: solid mid-game milestone.
    # - 5M: late-game gate перед capstone. Split 1M→10M на 1M→5M→10M для
    #   pacing'а (старый 10x jump был too sparse).
    # - 10M: capstone (~5+ years для casual игрока).
    'marathoner': {
        'name': 'Marathoner',
        'category': 'steps',
        'tiers': [100_000, 500_000, 1_000_000, 5_000_000, 10_000_000],
        'metric': lambda state: state.steps.total_used,
    },

    # ----- 🔋 Energy (4.62.1.4, 22.05.2026) -----
    # Approach B: event-based через cost_energy в payload existing log_event'ов.
    # Backfill из history.jsonl автоматически работает (cost_energy уже в
    # payload work_start/extend/skill_train_start/adventure_start/item_repaired;
    # item_crafted получил cost_energy 22.05.2026 — patch в forge.py).
    #
    # Tiers [1k/5k/10k/50k] выбраны 22.05.2026: 1k = ~1-2 недели casual play
    # (first milestone), 5k = ~1.5 месяца mid-game, 10k = ~3 месяца solid,
    # 50k = ~1.5-2 года capstone. Симметрично pacing'у Marathoner.
    # Per-split (Workhorse/Disciplined/Pathfinder) используют те же tiers что
    # total (Endurance) — по выбору 22.05.2026, simplicity over realism.

    # Total energy spent — все 6 event types с cost_energy.
    'endurance': {
        'name': 'Endurance',
        'category': 'energy',
        'tiers': [1_000, 5_000, 10_000, 50_000],
        'event_hooks': [
            'work_start', 'work_extend',
            'skill_train_start',
            'adventure_start',
            'item_repaired', 'item_crafted',
        ],
        'count_delta': lambda p: int(p.get('cost_energy', 0) or 0),
    },

    # Per-source: только work events.
    'workhorse': {
        'name': 'Workhorse',
        'category': 'energy',
        'tiers': [1_000, 5_000, 10_000, 50_000],
        'event_hooks': ['work_start', 'work_extend'],
        'count_delta': lambda p: int(p.get('cost_energy', 0) or 0),
    },

    # Per-source: только gym training events.
    'disciplined': {
        'name': 'Disciplined',
        'category': 'energy',
        'tiers': [1_000, 5_000, 10_000, 50_000],
        'event_hooks': ['skill_train_start'],
        'count_delta': lambda p: int(p.get('cost_energy', 0) or 0),
    },

    # Per-source: только adventure events.
    'pathfinder': {
        'name': 'Pathfinder',
        'category': 'energy',
        'tiers': [1_000, 5_000, 10_000, 50_000],
        'event_hooks': ['adventure_start'],
        'count_delta': lambda p: int(p.get('cost_energy', 0) or 0),
    },
}


# Категории для меню grouping (упорядоченные). Расширяются по мере добавления
# триумфов в 4.62.1.x. Empty при foundation, заполнение через ADD в catalog tasks.
CATEGORIES: dict[str, dict] = {
    'steps': {'label': '🏃 Шаги', 'order': 1},
    'adventures': {'label': '🗺 Приключения', 'order': 2},
    'drops': {'label': '💎 Дропы', 'order': 3},
    'gym': {'label': '🏋 Тренировки', 'order': 4},
    'work': {'label': '🏭 Работа', 'order': 5},
    'energy': {'label': '🔋 Энергия', 'order': 6},
    'progression': {'label': '⭐ Уровень', 'order': 7},
    'streak': {'label': '🔥 Постоянство', 'order': 8},
    'bank': {'label': '🏦 Банк', 'order': 9},
    'forge': {'label': '🔨 Кузница', 'order': 10},
    'money': {'label': '💰 Деньги', 'order': 11},
    'lifestyle': {'label': '🕒 Образ жизни', 'order': 12},
    'collection': {'label': '🎒 Коллекция', 'order': 13},
}
