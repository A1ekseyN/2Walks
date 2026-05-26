# Таблица с приключениями, и параметрами.
#
# `drops` (since 0.2.4f / task 4.29-replacement) — упорядоченный список тиеров
# (grade, threshold) для каждого приключения. Единый источник правды для
# `drop.py:one_item_random_grade()` и `compute_grade_probabilities()` (расчёт
# % выпадения для меню Adventure). Порядок ВАЖЕН — соответствует порядку
# roll'ов в drop.py. Threshold — это `drop_percent_item_*` из drop.py
# (импортируется явно ниже).
#
# Раньше существовали мёртвые поля `drop_items` (всегда `{ring, necklace}`,
# на самом деле сэмплится 5 типов в drop.py:item_type) и `drop_grade` (set
# без порогов) — удалены в 0.2.4f т.к. нигде не читались.
from drop import (
    drop_percent_item_c,
    drop_percent_item_b,
    drop_percent_item_a,
    drop_percent_item_s,
    drop_percent_item_s_,
    # 0.2.4g — per-adventure overrides для S+ threshold (walk_25k / walk_30k).
    drop_percent_item_s_walk_25k,
    drop_percent_item_s_walk_30k,
)


adventure_data_table = {
    'walk_easy': {
        'steps': 2500,
        'energy': 10,
        'time': 30,
        'drops': [('c-grade', drop_percent_item_c)],
    },
    'walk_normal': {
        'steps': 5000,
        'energy': 20,
        'time': 60,
        'drops': [
            ('c-grade', drop_percent_item_c),
            ('b-grade', drop_percent_item_b),
        ],
    },
    'walk_hard': {
        'steps': 10000,
        'energy': 30,
        'time': 120,
        'drops': [
            ('c-grade', drop_percent_item_c),
            ('b-grade', drop_percent_item_b),
            ('a-grade', drop_percent_item_a),
        ],
    },
    'walk_15k': {
        'steps': 15000,
        'energy': 40,
        'time': 180,
        'drops': [
            ('b-grade', drop_percent_item_b),
            ('a-grade', drop_percent_item_a),
            ('s-grade', drop_percent_item_s),
        ],
    },
    'walk_20k': {
        'steps': 20000,
        'energy': 50,
        'time': 240,
        'drops': [
            ('a-grade', drop_percent_item_a),
            ('s-grade', drop_percent_item_s),
            ('s+grade', drop_percent_item_s_),
        ],
    },
    'walk_25k': {
        'steps': 25000,
        'energy': 60,
        'time': 300,
        'drops': [
            ('s-grade', drop_percent_item_s),
            # 0.2.4g — S+ threshold 15 → 20 (см. drop.py:drop_percent_item_s_walk_25k).
            ('s+grade', drop_percent_item_s_walk_25k),
        ],
    },
    'walk_30k': {
        'steps': 30000,
        'energy': 70,
        'time': 360,
        # 0.2.4g — S+ threshold 15 → 35 (endgame bonus; см. drop.py).
        'drops': [('s+grade', drop_percent_item_s_walk_30k)],
    },
}


# --- Unlock chain (task 4.34) — единый источник правды для CLI и web ---
# Прогулка открывается, когда предыдущая в цепочке пройдена ≥ THRESHOLD раз.
# walk_easy всегда открыта (нет prereq → нет записи в ADVENTURE_PREREQ).
# Раньше порог дублировался: литерал 3 в 7 местах adventure.py + dict в web/main.py.
ADVENTURE_UNLOCK_THRESHOLD = 3

# adv_name → prereq adv_name.
ADVENTURE_PREREQ: dict[str, str] = {
    'walk_normal': 'walk_easy',
    'walk_hard':   'walk_normal',
    'walk_15k':    'walk_hard',
    'walk_20k':    'walk_15k',
    'walk_25k':    'walk_20k',
    'walk_30k':    'walk_25k',
}

# Human-readable RU-лейблы прогулок (для UI разблокировки + меню).
ADVENTURE_RU_LABELS: dict[str, str] = {
    'walk_easy':   'Прогулка вокруг озера',
    'walk_normal': 'Прогулка по району',
    'walk_hard':   'Прогулка в лес',
    'walk_15k':    'Прогулка 15к шагов',
    'walk_20k':    'Прогулка 20к шагов',
    'walk_25k':    'Прогулка 25к шагов',
    'walk_30k':    'Прогулка 30к шагов',
}