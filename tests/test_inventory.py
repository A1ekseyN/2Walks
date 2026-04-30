"""Тесты inventory.py после миграции на GameState (Phase 4 задачи 1.1)."""

from state import GameState
from inventory import (
    _sort_inventory,
    _sell_item_at_index,
    inventory_view,
    Wear_Equipped_Items,
)


def _make_item(item_type='ring', grade='a-grade', characteristic='luck',
               bonus=3, quality=80.0, price=120, item_name='ring'):
    return {
        'item_name': [item_name],
        'item_type': [item_type],
        'grade': [grade],
        'characteristic': [characteristic],
        'bonus': [bonus],
        'quality': [quality],
        'price': [price],
    }


# ----- _sort_inventory -----

def test_sort_inventory_empty():
    assert _sort_inventory([]) == []


def test_sort_inventory_by_type_then_characteristic_then_bonus_desc():
    inventory = [
        _make_item(item_type='ring', characteristic='luck', bonus=2),
        _make_item(item_type='helmet', characteristic='stamina', bonus=3),
        _make_item(item_type='ring', characteristic='luck', bonus=5),
        _make_item(item_type='ring', characteristic='energy_max', bonus=4),
    ]
    sorted_inv = _sort_inventory(inventory)
    # helmet < ring (alphabetical) → helmet first.
    assert sorted_inv[0]['item_type'] == ['helmet']
    # Among rings: 'energy_max' < 'luck' → energy_max ring first.
    assert sorted_inv[1]['characteristic'] == ['energy_max']
    # Among luck rings: bonus DESC → 5 then 2.
    assert sorted_inv[2]['bonus'] == [5]
    assert sorted_inv[3]['bonus'] == [2]


def test_sort_inventory_does_not_mutate_input():
    inventory = [_make_item(bonus=1), _make_item(bonus=3), _make_item(bonus=2)]
    original_order = [i['bonus'][0] for i in inventory]
    _sort_inventory(inventory)
    assert [i['bonus'][0] for i in inventory] == original_order


# ----- _sell_item_at_index -----

def test_sell_item_increases_money_and_removes_from_inventory():
    state = GameState.default_new_game()
    state.inventory = [_make_item(price=100), _make_item(price=200)]
    state.money = 50

    item, refund = _sell_item_at_index(state, 1)

    assert refund == 200
    assert state.money == 250
    assert len(state.inventory) == 1
    assert state.inventory[0]['price'] == [100]


def test_sell_item_no_price_refunds_zero():
    state = GameState.default_new_game()
    state.inventory = [{'price': []}]  # отсутствует [0]
    state.money = 10

    item, refund = _sell_item_at_index(state, 0)

    assert refund == 0
    assert state.money == 10
    assert state.inventory == []


def test_sell_item_rounds_float_price():
    state = GameState.default_new_game()
    state.inventory = [_make_item(price=129.7)]
    state.money = 0

    _, refund = _sell_item_at_index(state, 0)
    assert refund == 130


# ----- inventory_view (UI) -----

def test_inventory_view_empty(capsys):
    state = GameState.default_new_game()
    inventory_view(state)
    out = capsys.readouterr().out
    assert 'Пусто' in out


def test_inventory_view_lists_items(capsys):
    state = GameState.default_new_game()
    state.inventory = [_make_item(item_name='ring', grade='s-grade', bonus=4)]
    inventory_view(state)
    out = capsys.readouterr().out
    assert 'Ring' in out
    assert 's-grade' in out


# ----- Wear_Equipped_Items -----

def test_wear_init_with_state():
    state = GameState.default_new_game()
    state.gym.neatness_in_using_things = 25
    w = Wear_Equipped_Items(state)
    assert w.neatness_factor == 0.75


def test_wear_decrease_durability_reduces_quality():
    state = GameState.default_new_game()
    state.gym.neatness_in_using_things = 0
    state.equipment.head = _make_item(item_type='helmet', quality=50.0,
                                       grade='a-grade', price=75)

    w = Wear_Equipped_Items(state)
    initial_quality = state.equipment.head['quality'][0]
    w.decrease_durability(steps=100000)

    final_quality = state.equipment.head['quality'][0]
    assert final_quality < initial_quality


def test_wear_decrease_durability_clamps_at_zero():
    state = GameState.default_new_game()
    state.gym.neatness_in_using_things = 0
    state.equipment.head = _make_item(quality=1.0, grade='a-grade', price=2)

    w = Wear_Equipped_Items(state)
    w.decrease_durability(steps=10**9)  # Сильно больше, чем выдержит предмет.

    assert state.equipment.head['quality'][0] == 0
    # Цена пересчитана: a-grade * 0 = 0.
    assert state.equipment.head['price'][0] == 0


def test_wear_decrease_durability_skips_empty_slots():
    """None-слоты не должны падать."""
    state = GameState.default_new_game()
    # Все слоты None по умолчанию.
    w = Wear_Equipped_Items(state)
    w.decrease_durability(steps=1000)  # Должно молча пройти.


def test_wear_neatness_reduces_wear():
    """С большим neatness прочность убывает медленнее."""
    state_no_skill = GameState.default_new_game()
    state_no_skill.gym.neatness_in_using_things = 0
    state_no_skill.equipment.head = _make_item(quality=80.0, grade='a-grade', price=120)

    state_with_skill = GameState.default_new_game()
    state_with_skill.gym.neatness_in_using_things = 50
    state_with_skill.equipment.head = _make_item(quality=80.0, grade='a-grade', price=120)

    Wear_Equipped_Items(state_no_skill).decrease_durability(steps=1_000_000)
    Wear_Equipped_Items(state_with_skill).decrease_durability(steps=1_000_000)

    assert state_with_skill.equipment.head['quality'][0] > state_no_skill.equipment.head['quality'][0]


def test_wear_recalc_prices_by_grade():
    """Цена = quality * grade-коэффициент."""
    state = GameState.default_new_game()
    state.equipment.head = _make_item(grade='a-grade', quality=60.0, price=999)
    state.equipment.neck = _make_item(grade='s+grade', quality=60.0, price=999)
    state.equipment.torso = _make_item(grade='c-grade', quality=60.0, price=999)

    w = Wear_Equipped_Items(state)
    w.recalc_item_prices()

    assert state.equipment.head['price'][0] == int(60 * 1.5)   # a-grade
    assert state.equipment.neck['price'][0] == int(60 * 2.5)   # s+grade
    assert state.equipment.torso['price'][0] == int(60 * 0.5)  # c-grade


def test_wear_reduce_wear_alias():
    """reduce_wear(steps) == decrease_durability(steps * (1 - neatness/100))."""
    state = GameState.default_new_game()
    state.gym.neatness_in_using_things = 30
    state.equipment.head = _make_item(quality=80.0, grade='a-grade', price=120)
    initial = state.equipment.head['quality'][0]

    Wear_Equipped_Items(state).reduce_wear(steps=10000)
    after_reduce = state.equipment.head['quality'][0]

    # Сбросим качество и сравним с decrease_durability на тех же reduced steps.
    state.equipment.head['quality'][0] = initial
    state.equipment.head['price'][0] = 120
    Wear_Equipped_Items(state).decrease_durability(steps=10000 * 0.7)
    after_decrease = state.equipment.head['quality'][0]

    assert abs(after_reduce - after_decrease) < 1e-6
