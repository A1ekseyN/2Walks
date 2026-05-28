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

    # Wayfarer (4.62.1.1.1, 27.05.2026) — metric-based на state.steps.total_walked
    # (РЕАЛЬНО пройденные шаги, сумма дневных показаний браслета). В отличие от
    # Marathoner (потрачено, раздуто бонусами) — честная фитнес-метрика. Те же
    # тиры что Marathoner (по запросу). Forward-only: total_walked стартует с 0
    # (история реально-пройденных не трекалась). Категория steps → seal
    # «Marathoner» теперь требует capstone обоих (Marathoner + Wayfarer).
    'wayfarer': {
        'name': 'Wayfarer',
        'category': 'steps',
        'tiers': [100_000, 500_000, 1_000_000, 5_000_000, 10_000_000],
        'metric': lambda state: state.steps.total_walked,
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

    # 🏭 Iron Worker (4.62.1.5.1, 25.05.2026) — самая длинная одиночная смена.
    # Metric-based через state.work.longest_shift_hours (новое поле).
    # Hook в work.py:work_check_done обновляет field перед log_event.
    # Backfill для existing players в init_game_state через scan history.jsonl.
    # Tiers [24, 72, 168, 336, 720]: 1сут → 3дня → 1нед → 2нед → 1мес (capstone).
    'iron_worker': {
        'name': 'Iron Worker',
        'category': 'work',
        'tiers': [24, 72, 168, 336, 720],
        'metric': lambda s: s.work.longest_shift_hours,
    },

    # ----- ⭐ Progression (4.62.1.8, 27.05.2026) -----
    # Veteran — metric-based на state.char_level.level. Tiers по уровням
    # 5/10/15/20/25/30. ВАЖНО: текущий потолок уровня = 12 (level.py
    # LEVEL_THRESHOLDS, ключи 0..11). Тиры 15-30 пока недостижимы — задел на
    # будущее расширение градации уровней (TASKS 4.64, отложено). До
    # расширения capstone (L30) не закрывается → seal 'Veteran' остаётся locked.
    # init_metric_check / register_event(level_up) авто-анлокают достигнутые (≤12).
    'veteran': {
        'name': 'Veteran',
        'category': 'progression',
        'tiers': [5, 10, 15, 20, 25, 30],
        'metric': lambda state: state.char_level.level,
    },

    # ----- 💎 Drops (4.62.1.7, 27.05.2026) -----
    # Event-based. Считаем каждый ФАКТ дропа в приключении — три взаимоисключающих
    # generation-события: 'drop' (в инвентарь), 'drop_pending' (рюкзак полон →
    # pending), 'drop_force_sold' (инвентарь+pending заняты → авто-продан). Все три
    # несут плоский payload с 'grade'. drop_auto_collected / drop_resolved_* НЕ
    # считаем — это разрешение уже посчитанного pending-дропа (двойной счёт).
    # Collector — общий счётчик (любой grade); 5 per-grade — тот же хук + фильтр
    # по grade. Один дроп → Collector +1 и matching grade +1. Тиры одинаковы для
    # всех (по запросу 27.05.2026): [10, 50, 100, 250, 500, 1000].
    'collector': {
        'name': 'Collector',
        'category': 'drops',
        'tiers': [10, 50, 100, 250, 500, 1000],
        'event_hooks': ['drop', 'drop_pending', 'drop_force_sold'],
    },
    'drops_c': {
        'name': 'C-Grade Collector',
        'category': 'drops',
        'tiers': [10, 50, 100, 250, 500, 1000],
        'event_hooks': ['drop', 'drop_pending', 'drop_force_sold'],
        'event_filter': lambda p: p.get('grade') == 'c-grade',
    },
    'drops_b': {
        'name': 'B-Grade Collector',
        'category': 'drops',
        'tiers': [10, 50, 100, 250, 500, 1000],
        'event_hooks': ['drop', 'drop_pending', 'drop_force_sold'],
        'event_filter': lambda p: p.get('grade') == 'b-grade',
    },
    'drops_a': {
        'name': 'A-Grade Collector',
        'category': 'drops',
        'tiers': [10, 50, 100, 250, 500, 1000],
        'event_hooks': ['drop', 'drop_pending', 'drop_force_sold'],
        'event_filter': lambda p: p.get('grade') == 'a-grade',
    },
    'drops_s': {
        'name': 'S-Grade Collector',
        'category': 'drops',
        'tiers': [10, 50, 100, 250, 500, 1000],
        'event_hooks': ['drop', 'drop_pending', 'drop_force_sold'],
        'event_filter': lambda p: p.get('grade') == 's-grade',
    },
    'drops_s_plus': {
        'name': 'S+ Grade Collector',
        'category': 'drops',
        'tiers': [10, 50, 100, 250, 500, 1000],
        'event_hooks': ['drop', 'drop_pending', 'drop_force_sold'],
        'event_filter': lambda p: p.get('grade') == 's+grade',
    },

    # ----- 💰 Money (4.62.1.12, 27.05.2026) -----
    # Investor — event-based accumulator: суммирует cost_money из skill_train_start
    # (gym.py уже пишет cost_money в payload — новый event не нужен). cost_money =
    # реально уплаченная сумма (после money_saving скидки). Backfill из history
    # автоматический. ОДИН агрегатный триумф (не per-skill — per-skill дублировал
    # бы 20 существующих gym-level триумфов; см. обсуждение 27.05.2026).
    # Capstone-бонус (+5% money_saving из 4.62.1.12) отложен в 4.62.2.1.
    'investor': {
        'name': 'Investor',
        'category': 'money',
        'tiers': [1_000, 10_000, 50_000, 250_000, 1_000_000],
        'event_hooks': ['skill_train_start'],
        # int() — деньги счётчиком целым (движок с 4.60 не int-кастит сам).
        'count_delta': lambda p: int(p.get('cost_money', 0)),
    },

    # ----- 🔥 Streak (4.62.1.9 part: Total days played, 27.05.2026) -----
    # Dedicated — metric-based на state.days_played: уникальные дни с активностью
    # (НЕ подряд — это отдельный consecutive Daily streak record, остаток 4.62.1.9).
    # days_played инкрементится на rollover'е если день имел ≥1 шаг (functions.py).
    # Forward-only. Тиры: 1 день / неделя / месяц / полгода / год.
    'dedicated': {
        'name': 'Dedicated',
        'category': 'streak',
        'tiers': [1, 7, 31, 184, 365],
        'metric': lambda state: state.days_played,
    },

    # On Fire (4.62.1.9 part: Daily streak record, 27.05.2026) — metric-based на
    # state.steps.daily_streak_record (макс стрик ПОДРЯД дней с 10k+ за всё время).
    # daily_bonus = текущий стрик; record = его max (monotonic, не откатывается).
    # Freeze-item (4.36) меняет только сброс daily_bonus → триумф учтёт сам.
    'on_fire': {
        'name': 'On Fire',
        'category': 'streak',
        'tiers': [3, 7, 14, 21, 31],
        'metric': lambda state: state.steps.daily_streak_record,
    },

    # ----- 🔨 Forge (4.62.1.11 part: Repair, 28.05.2026) -----
    # Restorer — event-based accumulator восстановленного quality. count_delta =
    # to_quality − from_quality (очки качества за ремонт), НЕ число кликов: клик
    # зависит от ресурсов (можно чинить порциями). Tier 1000 = 10 полных ремонтов
    # 0→100. Один общий счётчик (тип предмета не ось сложности — per-type не нужен;
    # обсуждено 28.05.2026). item_repaired (forge.py) уже пишет from/to_quality →
    # backfill из history автоматический.
    'restorer': {
        'name': 'Restorer',
        'category': 'forge',
        'tiers': [25, 50, 100, 500, 1000],
        'event_hooks': ['item_repaired'],
        # 4.60 — БЕЗ round: копим дробное quality точно (forge_repair_quality
        # даёт дробный буст). Движок не int-кастит (см. triumphs.register_event).
        'count_delta': lambda p: max(0.0, p.get('to_quality', 0) - p.get('from_quality', 0)),
    },
    # Crafter (4.62.1.11 part: Crafting, 28.05.2026) — счётчик скрафченных
    # предметов. Каждый крафт = +1 (даёт ровно 1 предмет). item_crafted
    # (forge.py craft_item + forge_check_done) уже логируется → backfill авто.
    # Без seal у категории forge (решено 28.05.2026). First-S+ триумф отменён.
    'crafter': {
        'name': 'Crafter',
        'category': 'forge',
        'tiers': [5, 10, 25, 50, 100],
        'event_hooks': ['item_crafted'],
        'count_delta': lambda p: 1,
    },

    # ----- 🏦 Bank (4.62.1.10 part: Capitalist, 28.05.2026) -----
    # Capitalist — metric-based на forward-only аккумуляторе всего заработанного
    # процента по вкладу (`bank.total_interest_earned`, += в bank.accrue_deposit).
    # Непрерывный (растёт по мере капитализации), не сбрасывается на снятии.
    # int() для tier-сравнения — копится дробно. Backfill нет (forward-only с 0).
    # Без seal у категории bank (решено 28.05.2026). Остаток 4.62.1.10 — Saver.
    'capitalist': {
        'name': 'Capitalist',
        'category': 'bank',
        'tiers': [100, 500, 1000, 5000, 10000],
        'metric': lambda state: int(state.bank.total_interest_earned),
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


# 4.62.3 — Seals & Titles. Один seal per category. Unlock'ается когда ВСЕ
# triumph'ы в категории на capstone tier. Игрок может «надеть» title (один за
# раз) — отображается в status_bar над локацией. Чисто косметика на этом
# этапе (gameplay bonuses — отдельная task 4.62.2.1).
#
# Key = category key (matches CATEGORIES). Не все CATEGORIES обязаны иметь
# SEAL — defined только для категорий с triumph'ами в catalog'е.
SEALS: dict[str, dict] = {
    'steps': {'name': 'Marathoner', 'icon': '🏃'},
    'energy': {'name': 'Indefatigable', 'icon': '🔋'},
    'adventures': {'name': 'Globetrotter', 'icon': '🗺'},
    'gym': {'name': 'Polymath', 'icon': '🏋'},
    'work': {'name': 'Workaholic', 'icon': '🏭'},
    # 4.62.1.8 — capstone Veteran (level 30). До расширения level-кэпа (>12)
    # seal остаётся locked. Title «Veteran».
    'progression': {'name': 'Veteran', 'icon': '⭐'},
    # 4.62.1.7 — capstone всех 6 drop-триумфов (Collector + 5 per-grade на 1000).
    # Endgame seal. Title «Treasure Hunter».
    'drops': {'name': 'Treasure Hunter', 'icon': '💎'},
}
