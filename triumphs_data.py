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


# 20 trainable Gym skill field names (источник правды — `_GYM_SKILL_DISPLAY`
# в web/main.py + state.GymSkills). Используется в (1) Skill Master aggregate
# metric (sum по всем 20) и (2) тестах catalog'а для validate всех per-skill.
# Mechanics / it_technologies из state.GymSkills намеренно исключены —
# legacy fields, не trainable через Gym menu.
_GYM_SKILL_FIELDS: tuple[str, ...] = (
    'stamina', 'energy_max_skill', 'energy_regen_skill', 'speed_skill', 'luck_skill',
    'move_optimization_adventure', 'move_optimization_gym', 'move_optimization_work',
    'energy_optimization_adventure', 'energy_optimization_gym', 'energy_optimization_work',
    'neatness_in_using_things', 'money_saving', 'earnings_boost', 'trader',
    'banking_interest_rate', 'loan_capacity', 'loan_interest_reduction',
    'inspiration', 'backpack_skill',
)


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

    # ----- 🗺 Adventures (4.62.1.2 + 4.62.1.3, 22.05.2026) -----
    # Metric-based — читает state.adventure.counters напрямую. Эти counters
    # уже обновляются в Adventure.adventure_check_done после каждой завершённой
    # прогулки за всё время игры (6+ месяцев у Oleksii) → мгновенный auto-unlock
    # через init_metric_check без backfill из history. Event-based подход не
    # нужен — counters это и есть persistent metric.
    #
    # Tiers одинаковые [10/50/100/500/1000] для всех 8 — симметрично с Energy
    # decision (simplicity over realism). Per-walk capstones (особенно
    # walk_30k = 1000 прохождений = 30M шагов) намеренно very-long-term
    # endgame goals.

    # Adventurer — sum across all 7 walk types. Mainstream триумф для активной
    # игры (общий показатель «сколько раз ходил гулять»).
    'adventurer': {
        'name': 'Adventurer',
        'category': 'adventures',
        'tiers': [10, 50, 100, 500, 1000],
        'metric': lambda state: sum(state.adventure.counters.values()),
    },

    # Per-walk (7 штук) — точечный счётчик для каждого walk type.
    # Тематическая прогрессия по сложности (Stroller easy → Conqueror endgame).
    'stroller': {
        'name': 'Stroller',
        'category': 'adventures',
        'tiers': [10, 50, 100, 500, 1000],
        'metric': lambda state: state.adventure.counters.get('walk_easy', 0),
    },
    'hiker': {
        'name': 'Hiker',
        'category': 'adventures',
        'tiers': [10, 50, 100, 500, 1000],
        'metric': lambda state: state.adventure.counters.get('walk_normal', 0),
    },
    'trekker': {
        'name': 'Trekker',
        'category': 'adventures',
        'tiers': [10, 50, 100, 500, 1000],
        'metric': lambda state: state.adventure.counters.get('walk_hard', 0),
    },
    'roamer': {
        'name': 'Roamer',
        'category': 'adventures',
        'tiers': [10, 50, 100, 500, 1000],
        'metric': lambda state: state.adventure.counters.get('walk_15k', 0),
    },
    'voyager': {
        'name': 'Voyager',
        'category': 'adventures',
        'tiers': [10, 50, 100, 500, 1000],
        'metric': lambda state: state.adventure.counters.get('walk_20k', 0),
    },
    'explorer': {
        'name': 'Explorer',
        'category': 'adventures',
        'tiers': [10, 50, 100, 500, 1000],
        'metric': lambda state: state.adventure.counters.get('walk_25k', 0),
    },
    'conqueror': {
        'name': 'Conqueror',
        'category': 'adventures',
        'tiers': [10, 50, 100, 500, 1000],
        'metric': lambda state: state.adventure.counters.get('walk_30k', 0),
    },

    # ----- 🏋 Gym / Skill Mastery (4.62.1.6, 22.05.2026) -----
    # 20 per-skill metric-based triumphs (tier зависит от level каждого skill'а)
    # + 1 aggregate "Skill Master" на sum всех 20.
    #
    # Per-skill tiers [10, 15, 20, 25, 30] (choice 22.05.2026 — tight pacing,
    # каждый next tier = +5 levels). Triumph ID = field name в state.GymSkills,
    # name = title из _GYM_SKILL_DISPLAY (web/main.py — единый источник UI).
    # Metric-based — auto-unlock через init_metric_check на старте без backfill.
    #
    # Aggregate Skill Master tiers [50, 100, 250, 500, 1000] (choice 22.05.2026).
    # Current player snapshot: sum=133, 14/20 prokachano → tiers 1-2 backfill
    # мгновенно. Capstone 1000 = avg 50/skill = deep endgame goal (sum 600 =
    # "все 20 to lvl 30" уже unlock'нет 4 tier'а — capstone стимулирует grind
    # за пределами этого).

    # ----- 20 per-skill (Tier = current skill level) -----
    'stamina': {
        'name': 'Stamina', 'category': 'gym',
        'tiers': [10, 15, 20, 25, 30],
        'metric': lambda s: s.gym.stamina,
    },
    'energy_max_skill': {
        'name': 'Energy Max', 'category': 'gym',
        'tiers': [10, 15, 20, 25, 30],
        'metric': lambda s: s.gym.energy_max_skill,
    },
    'energy_regen_skill': {
        'name': 'Регенерация энергии', 'category': 'gym',
        'tiers': [10, 15, 20, 25, 30],
        'metric': lambda s: s.gym.energy_regen_skill,
    },
    'speed_skill': {
        'name': 'Speed', 'category': 'gym',
        'tiers': [10, 15, 20, 25, 30],
        'metric': lambda s: s.gym.speed_skill,
    },
    'luck_skill': {
        'name': 'Luck', 'category': 'gym',
        'tiers': [10, 15, 20, 25, 30],
        'metric': lambda s: s.gym.luck_skill,
    },
    'move_optimization_adventure': {
        'name': 'Move Optimization (Adventure)', 'category': 'gym',
        'tiers': [10, 15, 20, 25, 30],
        'metric': lambda s: s.gym.move_optimization_adventure,
    },
    'move_optimization_gym': {
        'name': 'Move Optimization (Gym)', 'category': 'gym',
        'tiers': [10, 15, 20, 25, 30],
        'metric': lambda s: s.gym.move_optimization_gym,
    },
    'move_optimization_work': {
        'name': 'Move Optimization (Work)', 'category': 'gym',
        'tiers': [10, 15, 20, 25, 30],
        'metric': lambda s: s.gym.move_optimization_work,
    },
    'energy_optimization_adventure': {
        'name': 'Экономия энергии в Adventure', 'category': 'gym',
        'tiers': [10, 15, 20, 25, 30],
        'metric': lambda s: s.gym.energy_optimization_adventure,
    },
    'energy_optimization_gym': {
        'name': 'Экономия энергии в Gym', 'category': 'gym',
        'tiers': [10, 15, 20, 25, 30],
        'metric': lambda s: s.gym.energy_optimization_gym,
    },
    'energy_optimization_work': {
        'name': 'Экономия энергии в Work', 'category': 'gym',
        'tiers': [10, 15, 20, 25, 30],
        'metric': lambda s: s.gym.energy_optimization_work,
    },
    'neatness_in_using_things': {
        'name': 'Neatness', 'category': 'gym',
        'tiers': [10, 15, 20, 25, 30],
        'metric': lambda s: s.gym.neatness_in_using_things,
    },
    'money_saving': {
        'name': 'Экономия денег', 'category': 'gym',
        'tiers': [10, 15, 20, 25, 30],
        'metric': lambda s: s.gym.money_saving,
    },
    'earnings_boost': {
        'name': 'Бонус к зарплате', 'category': 'gym',
        'tiers': [10, 15, 20, 25, 30],
        'metric': lambda s: s.gym.earnings_boost,
    },
    'trader': {
        'name': 'Торговец', 'category': 'gym',
        'tiers': [10, 15, 20, 25, 30],
        'metric': lambda s: s.gym.trader,
    },
    'banking_interest_rate': {
        'name': 'Банковская ставка', 'category': 'gym',
        'tiers': [10, 15, 20, 25, 30],
        'metric': lambda s: s.gym.banking_interest_rate,
    },
    'loan_capacity': {
        'name': 'Кредитный лимит', 'category': 'gym',
        'tiers': [10, 15, 20, 25, 30],
        'metric': lambda s: s.gym.loan_capacity,
    },
    'loan_interest_reduction': {
        'name': 'Снижение ставки по кредиту', 'category': 'gym',
        'tiers': [10, 15, 20, 25, 30],
        'metric': lambda s: s.gym.loan_interest_reduction,
    },
    'inspiration': {
        'name': 'Обучение', 'category': 'gym',
        'tiers': [10, 15, 20, 25, 30],
        'metric': lambda s: s.gym.inspiration,
    },
    'backpack_skill': {
        'name': 'Размер инвентаря', 'category': 'gym',
        'tiers': [10, 15, 20, 25, 30],
        'metric': lambda s: s.gym.backpack_skill,
    },

    # ----- Aggregate (sum по всем 20 skills) -----
    'skill_master': {
        'name': 'Skill Master',
        'category': 'gym',
        'tiers': [50, 100, 250, 500, 1000],
        'metric': lambda s: sum(getattr(s.gym, f) for f in _GYM_SKILL_FIELDS),
    },

    # ----- 🏭 Work / Hard Worker (4.62.1.5, 22.05.2026) -----
    # Event-based через `work_done` payload (vacancy + hours + salary). Payload
    # стабилен с самого начала work_done логирования (4.6 / 0.2.4) → backfill
    # из Sheets history лист автоматически работает.
    #
    # Aggregate Hard Worker = sum hours по всем 4 вакансиям; per-vacancy =
    # filter по `payload['vacancy']`. Тiers `[100, 500, 1000, 5000, 10000]`
    # одинаковые для всех 5 triumph'ов (choice 22.05.2026 — simplicity over
    # difficulty scaling). Player snapshot CLI local jsonl: 637h watchman +
    # 472h pending = 1109h после finalize → Hard Worker tier 3 (1000) сразу
    # backfill, Watchman tier 3 backfill, capstone (10k) realistic при 6+
    # месяцев consistent grind. Server events добавят больше (CLI/web split).

    # Aggregate — total hours across all vacancies.
    'hard_worker': {
        'name': 'Hard Worker',
        'category': 'work',
        'tiers': [100, 500, 1000, 5000, 10000],
        'event_hooks': ['work_done'],
        'count_delta': lambda p: int(p.get('hours', 0) or 0),
    },

    # Per-vacancy — same tiers, filtered by payload['vacancy'].
    # Triumph id = vacancy key из work.py (work_requirements). Названия по-русски
    # симметрично UI в work.py:check_requirements (Сторож / Завод / Курьер /
    # Экспедитор).
    'watchman': {
        'name': 'Сторож',
        'category': 'work',
        'tiers': [100, 500, 1000, 5000, 10000],
        'event_hooks': ['work_done'],
        'event_filter': lambda p: p.get('vacancy') == 'watchman',
        'count_delta': lambda p: int(p.get('hours', 0) or 0),
    },
    'factory': {
        'name': 'Заводчанин',
        'category': 'work',
        'tiers': [100, 500, 1000, 5000, 10000],
        'event_hooks': ['work_done'],
        'event_filter': lambda p: p.get('vacancy') == 'factory',
        'count_delta': lambda p: int(p.get('hours', 0) or 0),
    },
    'courier_foot': {
        'name': 'Курьер',
        'category': 'work',
        'tiers': [100, 500, 1000, 5000, 10000],
        'event_hooks': ['work_done'],
        'event_filter': lambda p: p.get('vacancy') == 'courier_foot',
        'count_delta': lambda p: int(p.get('hours', 0) or 0),
    },
    'forwarder': {
        'name': 'Экспедитор',
        'category': 'work',
        'tiers': [100, 500, 1000, 5000, 10000],
        'event_hooks': ['work_done'],
        'event_filter': lambda p: p.get('vacancy') == 'forwarder',
        'count_delta': lambda p: int(p.get('hours', 0) or 0),
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
