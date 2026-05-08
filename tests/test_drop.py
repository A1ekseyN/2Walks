"""Тесты drop.py после миграции на GameState (Phase 4 задачи 1.1, commit 4)."""

import random

import pytest

from state import GameState
from drop import Drop_Item, current_luck


# ----- current_luck -----

def test_current_luck_zero_default():
    state = GameState.default_new_game()
    assert current_luck(state) == 0


def test_current_luck_sums_skill_equipment_level():
    state = GameState.default_new_game()
    state.gym.luck_skill = 5
    state.char_level.skill_luck = 3
    state.equipment.head = {
        'characteristic': ['luck'], 'bonus': [2], 'item_name': ['x'],
        'item_type': ['x'], 'grade': ['a-grade'], 'quality': [50.0], 'price': [50],
    }
    assert current_luck(state) == 10


# ----- item_bonus_value (статический helper) -----

def test_item_bonus_value_per_grade():
    for grade, expected in [
        ('c-grade', 1), ('b-grade', 2), ('a-grade', 3),
        ('s-grade', 4), ('s+grade', 5),
    ]:
        assert Drop_Item.item_bonus_value(item=None, grade=[grade]) == expected


# ----- item_quality / item_price -----

def test_item_quality_in_expected_range():
    state = GameState.default_new_game()
    drop = Drop_Item()
    for _ in range(50):
        q = drop.item_quality(state)
        assert 20 <= q <= 100


def test_item_price_per_grade():
    drop = Drop_Item()
    assert drop.item_price(grade=['c-grade'], quality=[100]) == 50
    assert drop.item_price(grade=['b-grade'], quality=[100]) == 100
    assert drop.item_price(grade=['a-grade'], quality=[100]) == 150
    assert drop.item_price(grade=['s-grade'], quality=[100]) == 200
    assert drop.item_price(grade=['s+grade'], quality=[100]) == 250


# ----- one_item_random_grade -----

def test_one_item_random_grade_walk_easy_returns_c_or_none(monkeypatch):
    state = GameState.default_new_game()
    drop = Drop_Item()
    # Прогон Monte Carlo: только None или 'c-grade'.
    grades = {drop.one_item_random_grade('walk_easy', state) for _ in range(200)}
    assert grades.issubset({None, 'c-grade'})


def test_one_item_random_grade_walk_30k_returns_s_plus_or_none():
    state = GameState.default_new_game()
    drop = Drop_Item()
    grades = {drop.one_item_random_grade('walk_30k', state) for _ in range(500)}
    assert grades.issubset({None, 's+grade'})


def test_one_item_random_grade_unknown_difficulty_returns_none():
    state = GameState.default_new_game()
    drop = Drop_Item()
    assert drop.one_item_random_grade('walk_does_not_exist', state) is None


# ----- item_type / characteristic_type -----

def test_item_type_returns_known_or_none():
    state = GameState.default_new_game()
    drop = Drop_Item()
    valid = {None, 'ring', 'necklace', 'helmet', 'shoes', 't-shirt'}
    for _ in range(50):
        assert drop.item_type(state) in valid


def test_characteristic_type_returns_known_or_none():
    state = GameState.default_new_game()
    drop = Drop_Item()
    valid = {None, 'stamina', 'energy_max', 'speed_skill', 'luck'}
    for _ in range(50):
        assert drop.characteristic_type(state) in valid


# ----- item_collect -----

def test_item_collect_appends_to_inventory_when_drop_succeeds(monkeypatch, capsys):
    """Форсим успешный дроп через monkeypatch на randint."""
    state = GameState.default_new_game()
    state.inventory = []
    drop = Drop_Item()

    # Все вызовы randint вернут одинаковое маленькое число → дроп проходит.
    monkeypatch.setattr('drop.randint', lambda a, b: 1)

    result = drop.item_collect('walk_easy', state)
    # При randint всегда=1 у item_type будет дубликат max_value → может вернуть None.
    # Проверяем оба исхода: либо item записан в inventory, либо ничего.
    out = capsys.readouterr().out
    if result is not None:
        assert state.inventory == [result]
        assert 'Выпал предмет' in out
    else:
        assert state.inventory == []


def test_item_collect_no_drop_returns_none(monkeypatch, capsys):
    """Если randint всегда возвращает 99 — drop_percent_gl (80) не пройдёт."""
    state = GameState.default_new_game()
    state.inventory = []
    monkeypatch.setattr('drop.randint', lambda a, b: 99)

    result = Drop_Item().item_collect('walk_easy', state)
    assert result is None
    assert state.inventory == []
    assert 'Ничего не выпало' in capsys.readouterr().out


# ----- 4.50.1 — item_collect 3-branch: append / pending / forced sale -----

def _force_successful_drop(monkeypatch):
    """Заставляет item_collect вернуть валидный item — через подмену
    helpers Drop_Item, чтобы обойти randint-дубликат-проблему."""
    monkeypatch.setattr('drop.randint', lambda a, b: 1)
    monkeypatch.setattr(Drop_Item, 'item_type', lambda self, state: 'ring')
    monkeypatch.setattr(Drop_Item, 'characteristic_type', lambda self, state: 'luck')
    monkeypatch.setattr(Drop_Item, 'item_quality', lambda self, state: 80)
    monkeypatch.setattr(Drop_Item, 'one_item_random_grade',
                        lambda self, hard, state: 'a-grade')


def test_item_collect_branch_append_when_inventory_has_room(monkeypatch, capsys):
    """Branch (1): inventory не full → item кладётся в инвентарь."""
    state = GameState.default_new_game()
    state.inventory = []
    _force_successful_drop(monkeypatch)

    result = Drop_Item().item_collect('walk_easy', state)

    assert result is not None
    assert len(state.inventory) == 1
    assert state.pending_drop is None
    assert state.inventory[0] is result


def test_item_collect_branch_pending_when_full_no_pending(monkeypatch, capsys):
    """Branch (2): inventory full + pending=None → item уходит в pending,
    инвентарь не меняется, печатается info-сообщение."""
    state = GameState.default_new_game()
    state.inventory = [{} for _ in range(10)]  # full при cap=10
    state.pending_drop = None
    _force_successful_drop(monkeypatch)

    result = Drop_Item().item_collect('walk_easy', state)

    assert result is not None
    assert state.pending_drop is result
    assert len(state.inventory) == 10  # без мутации
    assert 'Инвентарь полон' in capsys.readouterr().out


def test_item_collect_branch_forced_sale_when_full_and_pending(monkeypatch, capsys):
    """Branch (3): inventory full + pending уже занят → новый item авто-продан
    за base price (money += price). Старый pending не трогается."""
    state = GameState.default_new_game()
    state.inventory = [{} for _ in range(10)]
    state.money = 50.0
    existing_pending = {
        'item_name': ['x'], 'item_type': ['ring'], 'grade': ['c-grade'],
        'characteristic': ['luck'], 'bonus': [1], 'quality': [50.0], 'price': [25],
    }
    state.pending_drop = existing_pending
    _force_successful_drop(monkeypatch)
    # новый item с price=80*1.5=120 (a-grade)

    result = Drop_Item().item_collect('walk_hard', state)

    assert result is not None
    new_price = result['price'][0]  # 120 для quality=80, a-grade
    assert state.money == 50.0 + new_price
    assert state.pending_drop is existing_pending  # не тронут
    assert len(state.inventory) == 10
    assert 'автоматически продана' in capsys.readouterr().out
