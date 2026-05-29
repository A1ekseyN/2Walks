"""4.51 — Рюкзак: equipment-слот 'back', дроп 5%, грейд→слоты, износ/ремонт.

V1: только вместимость (characteristic='backpack_capacity'). Capacity от ГРЕЙДА.
"""

import pytest

from state import GameState
from bonus import (
    BASE_BACKPACK_CAPACITY,
    BACKPACK_GRADE_SLOTS,
    backpack_capacity,
    backpack_slots_bonus,
)
from drop import Drop_Item, BACKPACK_DROP_CHANCE


def _backpack(grade='a-grade', quality=80.0):
    return {
        'item_type': ['backpack'], 'item_name': ['backpack'], 'grade': [grade],
        'characteristic': ['backpack_capacity'], 'bonus': [BACKPACK_GRADE_SLOTS[grade]],
        'quality': [quality], 'price': [int(quality)],
    }


# ----- capacity -----

def test_no_backpack_capacity_is_base_plus_skill():
    s = GameState.default_new_game()
    assert backpack_capacity(s) == BASE_BACKPACK_CAPACITY
    s.gym.backpack_skill = 5
    assert backpack_capacity(s) == BASE_BACKPACK_CAPACITY + 5
    assert backpack_slots_bonus(s) == 0


@pytest.mark.parametrize('grade,slots', [
    ('c-grade', 2), ('b-grade', 4), ('a-grade', 6), ('s-grade', 8), ('s+grade', 10),
])
def test_backpack_grade_slots(grade, slots):
    s = GameState.default_new_game()
    s.equipment.back = _backpack(grade=grade)
    assert backpack_slots_bonus(s) == slots
    assert backpack_capacity(s) == BASE_BACKPACK_CAPACITY + slots


def test_backpack_stacks_with_skill():
    s = GameState.default_new_game()
    s.gym.backpack_skill = 7
    s.equipment.back = _backpack(grade='s-grade')  # +8
    assert backpack_capacity(s) == BASE_BACKPACK_CAPACITY + 7 + 8


def test_broken_backpack_gives_zero_slots():
    s = GameState.default_new_game()
    s.equipment.back = _backpack(grade='s+grade', quality=0.0)  # сломан
    assert backpack_slots_bonus(s) == 0
    assert backpack_capacity(s) == BASE_BACKPACK_CAPACITY


# ----- round-trip -----

def test_backpack_slot_round_trip():
    s = GameState.default_new_game()
    s.equipment.back = _backpack(grade='b-grade', quality=55.0)
    r = GameState.from_dict(s.to_dict())
    assert r.equipment.back is not None
    assert r.equipment.back['grade'][0] == 'b-grade'
    assert r.equipment.back['item_type'][0] == 'backpack'
    assert backpack_capacity(r) == BASE_BACKPACK_CAPACITY + 4


def test_default_state_has_empty_back_slot():
    s = GameState.default_new_game()
    assert s.equipment.back is None
    # legacy save без equipment_back → None
    assert GameState.from_dict({}).equipment.back is None


# ----- drop -----

def test_item_type_can_return_backpack(monkeypatch):
    # 4.65 — backpack теперь один из типов взвешенной выборки (не пре-гейт).
    s = GameState.default_new_game()
    d = Drop_Item()
    monkeypatch.setattr('drop.choices', lambda pop, weights=None: ['backpack'])
    assert d.item_type(s) == 'backpack'


def test_item_type_can_return_non_backpack(monkeypatch):
    s = GameState.default_new_game()
    d = Drop_Item()
    monkeypatch.setattr('drop.choices', lambda pop, weights=None: ['ring'])
    assert d.item_type(s) != 'backpack'


def test_backpack_drop_chance_value():
    assert BACKPACK_DROP_CHANCE == 0.05


def test_item_collect_backpack_has_capacity_characteristic(monkeypatch):
    """Выпавший рюкзак: characteristic='backpack_capacity', bonus=слоты по грейду."""
    s = GameState.default_new_game()
    d = Drop_Item()
    monkeypatch.setattr('drop.choices', lambda pop, weights=None: ['backpack'])
    monkeypatch.setattr(Drop_Item, 'one_item_random_grade',
                        lambda self, hard, state: 'a-grade')
    item = d.item_collect('walk_easy', s)
    assert item is not None
    assert item['item_type'][0] == 'backpack'
    assert item['characteristic'][0] == 'backpack_capacity'
    assert item['bonus'][0] == BACKPACK_GRADE_SLOTS['a-grade']  # 6
    # попал в инвентарь и даёт вместимость при надевании
    s.equipment.back = item
    assert backpack_capacity(s) == BASE_BACKPACK_CAPACITY + 6
