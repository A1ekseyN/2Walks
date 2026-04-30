"""Тесты equipment.py после миграции на GameState (Phase 4 задачи 1.1)."""

from state import GameState
from equipment import _equip_from_inventory, _unequip, Equipment


def _make_item(item_name='ring', item_type='ring', grade='a-grade',
               characteristic='luck', bonus=3, quality=80.0, price=120):
    return {
        'item_name': [item_name],
        'item_type': [item_type],
        'grade': [grade],
        'characteristic': [characteristic],
        'bonus': [bonus],
        'quality': [quality],
        'price': [price],
    }


# ----- _equip_from_inventory -----

def test_equip_to_empty_slot_moves_item_out_of_inventory():
    state = GameState.default_new_game()
    item = _make_item(item_type='helmet')
    state.inventory = [item]
    state.equipment.head = None

    new_item, prev = _equip_from_inventory(state, 'head', 0)

    assert new_item is item
    assert prev is None
    assert state.equipment.head is item
    assert state.inventory == []


def test_equip_to_occupied_slot_swaps_via_inventory():
    state = GameState.default_new_game()
    new = _make_item(item_type='helmet', bonus=5)
    old = _make_item(item_type='helmet', bonus=2)
    state.inventory = [new]
    state.equipment.head = old

    new_item, prev = _equip_from_inventory(state, 'head', 0)

    assert new_item is new
    assert prev is old
    assert state.equipment.head is new
    # Старый предмет вернулся в инвентарь
    assert state.inventory == [old]


def test_equip_preserves_other_inventory_items():
    state = GameState.default_new_game()
    other = _make_item(item_type='necklace')
    target = _make_item(item_type='helmet')
    state.inventory = [other, target]

    _equip_from_inventory(state, 'head', 1)

    assert state.equipment.head is target
    assert state.inventory == [other]


# ----- _unequip -----

def test_unequip_moves_item_back_to_inventory():
    state = GameState.default_new_game()
    item = _make_item()
    state.equipment.head = item
    state.inventory = []

    removed = _unequip(state, 'head')

    assert removed is item
    assert state.equipment.head is None
    assert state.inventory == [item]


def test_unequip_empty_slot_returns_none_no_op():
    state = GameState.default_new_game()
    state.equipment.head = None
    state.inventory = []

    removed = _unequip(state, 'head')

    assert removed is None
    assert state.inventory == []


# ----- Equipment.equipment_view (UI smoke) -----

def test_equipment_view_empty_prints_no_items(capsys, monkeypatch):
    """С пустыми слотами и автоматическим '0' в input — выводит "нет вещей"."""
    monkeypatch.setattr('builtins.input', lambda *args, **kwargs: '0')
    state = GameState.default_new_game()
    Equipment.equipment_view(self=None, state=state)
    out = capsys.readouterr().out
    assert 'нет вещей' in out
    assert 'Голова:' in out
    assert 'Ступни:' in out


def test_equipment_view_with_item_prints_details(capsys, monkeypatch):
    monkeypatch.setattr('builtins.input', lambda *args, **kwargs: '0')
    state = GameState.default_new_game()
    state.equipment.head = _make_item(item_name='helmet', grade='s-grade',
                                       characteristic='stamina', bonus=4, quality=88.5)
    Equipment.equipment_view(self=None, state=state)
    out = capsys.readouterr().out
    assert 'Helmet' in out
    assert 'S-Grade' in out
    assert '4' in out
