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
            ('s+grade', drop_percent_item_s_),
        ],
    },
    'walk_30k': {
        'steps': 30000,
        'energy': 70,
        'time': 360,
        'drops': [('s+grade', drop_percent_item_s_)],
    },
}