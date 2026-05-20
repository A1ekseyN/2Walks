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


# ===========================================================================
# 4.61 — Поломка предметов: quality=0 → broken → НЕ даёт bonus
# ===========================================================================

from equipment_bonus import _is_broken, low_quality_equipped_items  # noqa: E402


def _item_with_quality(char, bonus, quality):
    """Item с полем quality (для broken-tests)."""
    return {'characteristic': [char], 'bonus': [bonus], 'quality': [quality]}


def test_is_broken_returns_true_for_quality_zero():
    assert _is_broken({'quality': [0]}) is True
    assert _is_broken({'quality': [0.0]}) is True


def test_is_broken_returns_false_for_positive_quality():
    assert _is_broken({'quality': [1]}) is False
    assert _is_broken({'quality': [50]}) is False
    assert _is_broken({'quality': [100]}) is False
    assert _is_broken({'quality': [0.1]}) is False  # 0.1 > 0 → не broken


def test_is_broken_returns_false_for_legacy_items_without_quality():
    """Backwards-compat: items без поля quality не считаются broken."""
    assert _is_broken({}) is False
    assert _is_broken({'characteristic': ['stamina'], 'bonus': [5]}) is False
    assert _is_broken({'quality': []}) is False  # пустой list


def test_broken_item_does_not_contribute_to_bonus():
    """quality=0 → бонус не учитывается в aggregator + всех individual helpers."""
    state = GameState.default_new_game()
    state.equipment.head = _item_with_quality('stamina', 10, quality=0)
    state.equipment.neck = _item_with_quality('luck', 5, quality=50)  # для контраста
    # Aggregator
    assert equipment_bonus(state) == (0, 0, 0, 5)  # only luck, stamina broken
    # Individual helpers
    assert equipment_stamina_bonus(state) == 0
    assert equipment_luck_bonus(state) == 5


def test_full_quality_item_gives_full_bonus():
    """quality > 0 (даже 0.1) → полный bonus, без partial (binary cliff)."""
    state = GameState.default_new_game()
    state.equipment.head = _item_with_quality('stamina', 10, quality=0.1)
    assert equipment_stamina_bonus(state) == 10  # 0.1 > 0 → полный 10


def test_legacy_item_without_quality_still_gives_bonus():
    """Backwards-compat: предмет без quality (старый формат) — даёт bonus."""
    state = GameState.default_new_game()
    state.equipment.head = _item('stamina', 7)  # без quality
    assert equipment_stamina_bonus(state) == 7


def test_all_four_chars_skip_broken_consistently():
    """4 individual helpers одинаково обрабатывают broken."""
    state = GameState.default_new_game()
    state.equipment.head = _item_with_quality('stamina', 10, quality=0)
    state.equipment.neck = _item_with_quality('energy_max', 15, quality=0)
    state.equipment.torso = _item_with_quality('speed_skill', 20, quality=0)
    state.equipment.foots = _item_with_quality('luck', 25, quality=0)
    assert equipment_stamina_bonus(state) == 0
    assert equipment_energy_max_bonus(state) == 0
    assert equipment_speed_skill_bonus(state) == 0
    assert equipment_luck_bonus(state) == 0
    assert equipment_bonus(state) == (0, 0, 0, 0)


def test_low_quality_helper_returns_items_below_threshold():
    """low_quality_equipped_items default threshold=20."""
    state = GameState.default_new_game()
    state.equipment.head = _item_with_quality('stamina', 10, quality=15)
    state.equipment.neck = _item_with_quality('luck', 5, quality=50)  # OK
    state.equipment.torso = _item_with_quality('energy_max', 5, quality=0)  # broken
    result = low_quality_equipped_items(state)
    # 2 items < 20%: head (15) + torso (0). Neck (50) OK.
    assert len(result) == 2


def test_low_quality_helper_custom_threshold():
    state = GameState.default_new_game()
    state.equipment.head = _item_with_quality('stamina', 10, quality=40)
    state.equipment.neck = _item_with_quality('luck', 5, quality=60)
    # threshold=50 → только head попадает.
    result = low_quality_equipped_items(state, threshold=50)
    assert len(result) == 1
    assert result[0]['characteristic'] == ['stamina']


def test_low_quality_helper_skips_legacy_items():
    """Items без поля quality не считаются low-quality."""
    state = GameState.default_new_game()
    state.equipment.head = _item('stamina', 10)  # legacy без quality
    state.equipment.neck = _item_with_quality('luck', 5, quality=10)  # low
    result = low_quality_equipped_items(state)
    assert len(result) == 1
    assert result[0]['characteristic'] == ['luck']
