"""Тесты skill_training_data.py — таблица стоимости прокачки навыков (1.3.2).

Проверяют структуру таблицы (1..30 уровни, 4 ключа в каждом), формулу
экстраполяции для уровней > 30, и обёртку get_energy_training_data.
"""

from skill_training_data import (
    get_energy_training_data,
    get_skill_training,
    skill_training_table,
)


# ----- Структура таблицы -----

def test_skill_training_table_has_30_levels():
    """Таблица покрывает уровни 1..30."""
    assert set(skill_training_table.keys()) == set(range(1, 31))


def test_skill_training_table_each_level_has_four_keys():
    """Каждая запись содержит ровно 4 ключа: steps / energy / money / time."""
    expected_keys = {'steps', 'energy', 'money', 'time'}
    for level, cost in skill_training_table.items():
        assert set(cost.keys()) == expected_keys, f"Уровень {level}: {set(cost.keys())}"


def test_skill_training_table_level_1_baseline():
    """Уровень 1 — самая дешёвая запись (game-balance baseline)."""
    cost = skill_training_table[1]
    assert cost == {'steps': 1000, 'energy': 5, 'money': 10, 'time': 5}


def test_skill_training_table_level_30_baseline():
    """Уровень 30 — последний в таблице, формула > 30 экстраполируется от него."""
    cost = skill_training_table[30]
    assert cost == {'steps': 30000, 'energy': 150, 'money': 1300, 'time': 6000}


def test_skill_training_table_steps_monotonically_grows():
    """Steps монотонно растут от уровня к уровню (game-balance проверка)."""
    prev = 0
    for level in range(1, 31):
        current = skill_training_table[level]['steps']
        assert current > prev, f"Уровень {level}: {current} <= {prev}"
        prev = current


# ----- get_skill_training -----

def test_get_skill_training_returns_table_for_low_levels():
    """Для уровней 1..30 возвращается запись из таблицы (тот же объект)."""
    assert get_skill_training(1) is skill_training_table[1]
    assert get_skill_training(30) is skill_training_table[30]


def test_get_skill_training_extrapolates_above_30():
    """Уровни > 30 — формула: steps = level * 1000, energy/money/time от lvl 30 + delta."""
    cost = get_skill_training(31)
    assert cost == {
        'steps': 31000,
        'energy': 150 + 1 * 5,    # 155
        'money': 1300 + 1 * 50,   # 1350
        'time': 6000 + 1 * 240,   # 6240
    }


def test_get_skill_training_at_level_50():
    cost = get_skill_training(50)
    assert cost == {
        'steps': 50000,
        'energy': 150 + 20 * 5,   # 250
        'money': 1300 + 20 * 50,  # 2300
        'time': 6000 + 20 * 240,  # 10800
    }


# ----- get_energy_training_data -----

def test_get_energy_training_data_uses_table_for_low_levels():
    """Lvl 1..30 — берёт из таблицы напрямую (identity)."""
    assert get_energy_training_data(15) is skill_training_table[15]


def test_get_energy_training_data_falls_back_to_extrapolation():
    """Lvl > 30 — делегирует get_skill_training()."""
    assert get_energy_training_data(40) == get_skill_training(40)
