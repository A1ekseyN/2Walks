"""Тесты equipment_bonus после миграции на GameState (Phase 3 задачи 1.1)."""

from state import GameState
from equipment_bonus import (
    equipment_bonus,
    equipment_stamina_bonus,
    equipment_energy_max_bonus,
    equipment_speed_skill_bonus,
    equipment_luck_bonus,
)


def _item(char, bonus):
    """Минимальный shape предмета: dict с 'characteristic'/'bonus' как list."""
    return {'characteristic': [char], 'bonus': [bonus]}


def test_empty_equipment_returns_zero():
    state = GameState.default_new_game()
    assert equipment_bonus(state) == (0, 0, 0, 0)
    assert equipment_stamina_bonus(state) == 0
    assert equipment_energy_max_bonus(state) == 0
    assert equipment_speed_skill_bonus(state) == 0
    assert equipment_luck_bonus(state) == 0


def test_single_stamina_item():
    state = GameState.default_new_game()
    state.equipment.head = _item('stamina', 5)
    assert equipment_stamina_bonus(state) == 5
    assert equipment_bonus(state) == (5, 0, 0, 0)


def test_multiple_slots_summed():
    state = GameState.default_new_game()
    state.equipment.head = _item('stamina', 3)
    state.equipment.torso = _item('stamina', 7)
    state.equipment.foots = _item('energy_max', 10)
    state.equipment.finger_01 = _item('speed_skill', 4)
    state.equipment.finger_02 = _item('luck', 2)
    assert equipment_stamina_bonus(state) == 10
    assert equipment_energy_max_bonus(state) == 10
    assert equipment_speed_skill_bonus(state) == 4
    assert equipment_luck_bonus(state) == 2
    assert equipment_bonus(state) == (10, 10, 4, 2)


def test_none_slots_skipped():
    """None в любом слоте не должен ломать функции."""
    state = GameState.default_new_game()
    state.equipment.head = None
    state.equipment.torso = _item('stamina', 6)
    state.equipment.legs = None
    assert equipment_stamina_bonus(state) == 6


def test_unknown_characteristic_ignored():
    """Если у предмета характеристика не из 4 known — игнорируем."""
    state = GameState.default_new_game()
    state.equipment.head = _item('mystery_skill', 99)
    assert equipment_bonus(state) == (0, 0, 0, 0)
