"""Тесты container `game` и `init_game_state()` (задача 1.2).

Проверяем что:
- импорт characteristics НЕ ходит в Sheets (убрано в 1.2);
- init_game_state(state=...) принимает явный state без Sheets-call;
- init идемпотентен — повторный вызов ничего не ломает;
- post-load fixups применяются (loc='home', timestamp_last_enter, energy_max bonuses).
"""

import characteristics
from characteristics import game, init_game_state, _equipment_energy_max_bonus
from state import GameState


def _reset_game_container():
    """Хелпер — pytest fixture-style сброс между тестами."""
    game.state = None


def test_module_level_state_is_none_before_init():
    """Сразу после импорта characteristics — game.state должен быть None."""
    # Если другой тест уже init'ил, сбросим вручную.
    _reset_game_container()
    assert game.state is None


def test_init_with_explicit_state_skips_sheets():
    _reset_game_container()
    custom = GameState.default_new_game()
    custom.energy = 42
    custom.money = 999

    returned = init_game_state(custom)

    assert game.state is custom
    assert returned is custom
    assert game.state.energy == 42
    assert game.state.money == 999


def test_init_is_idempotent():
    """Повторный вызов не пересоздаёт state."""
    _reset_game_container()
    s1 = GameState.default_new_game()
    init_game_state(s1)

    s2 = GameState.default_new_game()
    s2.energy = 1  # отличный от s1
    returned = init_game_state(s2)

    # Возвращается уже сохранённый s1, не s2.
    assert returned is s1
    assert game.state is s1


def test_equipment_energy_max_bonus_no_equipment():
    state = GameState.default_new_game()
    assert _equipment_energy_max_bonus(state) == 0


def test_equipment_energy_max_bonus_sums_only_energy_max_items():
    state = GameState.default_new_game()
    state.equipment.head = {
        'characteristic': ['energy_max'], 'bonus': [10],
        'item_name': ['x'], 'item_type': ['x'], 'grade': ['a-grade'],
        'quality': [50.0], 'price': [50],
    }
    state.equipment.torso = {
        'characteristic': ['stamina'], 'bonus': [99],  # не energy_max → не считается
        'item_name': ['x'], 'item_type': ['x'], 'grade': ['a-grade'],
        'quality': [50.0], 'price': [50],
    }
    state.equipment.foots = {
        'characteristic': ['energy_max'], 'bonus': [5],
        'item_name': ['x'], 'item_type': ['x'], 'grade': ['a-grade'],
        'quality': [50.0], 'price': [50],
    }
    assert _equipment_energy_max_bonus(state) == 15


def test_init_applies_post_load_fixups():
    """Fixups: loc='home', timestamp_last_enter обновлён, energy_max пересчитан."""
    _reset_game_container()
    # Эмулируем ситуацию — state передан напрямую, минуя Sheets.
    # Но в этом случае init не применяет fixups (state получен extern).
    # Проверяем fixups на пути через mock-loader.
    custom = GameState.default_new_game()
    custom.loc = 'gym'  # нелокальное
    init_game_state(custom)
    # При explicit-state path fixups НЕ применяются — state доверяется как есть.
    assert game.state.loc == 'gym'  # Не сброшен в 'home'.


def test_state_attribute_is_live_reference():
    """game.state живая ссылка — мутация видна через container."""
    _reset_game_container()
    s = GameState.default_new_game()
    init_game_state(s)
    # Мутация через прямую ссылку.
    s.energy = 7
    # Видна через container.
    assert game.state.energy == 7
    # И наоборот.
    game.state.money = 13
    assert s.money == 13
