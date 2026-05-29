"""4.65 — Drop-modifier: буст шанса нужного ТИПА по luck (completion-incentive).

Тестируем pure-helpers выбора типа (`_type_gap`, `_type_weights`) + распределение
`item_type` через Monte-Carlo на двух worked-examples из дизайна задачи.
"""

import random

import pytest

from state import GameState
from drop import (
    Drop_Item,
    _BASE_TYPE_WEIGHTS,
    _DROP_TYPES,
    _best_owned_tier,
    _item_grade_tier,
    _type_gap,
    _type_weights,
)


def mk(item_type: str, grade: str, characteristic: str = 'stamina') -> dict:
    """Минимальный item-dict нужного типа/грейда (characteristic≠luck — не влияет
    на current_luck)."""
    return {
        'item_name': [item_type], 'item_type': [item_type], 'grade': [grade],
        'characteristic': [characteristic], 'bonus': [10],
        'quality': [50.0], 'price': [50],
    }


# ----- _item_grade_tier / _best_owned_tier -----

def test_item_grade_tier_none_and_grades():
    assert _item_grade_tier(None) == 0
    assert _item_grade_tier(mk('ring', 'c-grade')) == 1
    assert _item_grade_tier(mk('ring', 'b-grade')) == 2
    assert _item_grade_tier(mk('ring', 'a-grade')) == 3
    assert _item_grade_tier(mk('ring', 's-grade')) == 4
    assert _item_grade_tier(mk('ring', 's+grade')) == 5


def test_item_grade_tier_empty_grade_list():
    # food/water — grade пустой → тир 0
    item = mk('helmet', 'a-grade')
    item['grade'] = []
    assert _item_grade_tier(item) == 0


def test_best_owned_tier_across_equipment_and_inventory():
    s = GameState.default_new_game()
    s.equipment.head = mk('helmet', 'c-grade')   # equipped c (1)
    s.inventory = [mk('helmet', 'a-grade')]      # inv a (3) — лучше
    assert _best_owned_tier(s, 'helmet') == 3
    assert _best_owned_tier(s, 'shoes') == 0     # ничего нет


# ----- _type_gap -----

def test_gap_empty_everything_is_max():
    s = GameState.default_new_game()
    for t in _DROP_TYPES:
        assert _type_gap(s, t) == 5  # 5 - 0


def test_gap_by_best_owned_grade():
    s = GameState.default_new_game()
    s.equipment.head = mk('helmet', 'a-grade')   # tier 3
    assert _type_gap(s, 'helmet') == 2           # 5 - 3
    s.inventory = [mk('helmet', 's+grade')]      # tier 5 в инвентаре
    assert _type_gap(s, 'helmet') == 0           # 5 - 5


def test_ring_gap_uses_worst_finger_r2():
    s = GameState.default_new_game()
    # один палец s+, другой пустой → худший = 0 → gap 5
    s.equipment.finger_01 = mk('ring', 's+grade')
    s.equipment.finger_02 = None
    assert _type_gap(s, 'ring') == 5
    # оба s+ → gap 0
    s.equipment.finger_02 = mk('ring', 's+grade')
    assert _type_gap(s, 'ring') == 0
    # a-grade(3) + c-grade(1) → худший 1 → gap 4
    s.equipment.finger_01 = mk('ring', 'a-grade')
    s.equipment.finger_02 = mk('ring', 'c-grade')
    assert _type_gap(s, 'ring') == 4


def test_ring_gap_ignores_inventory_rings():
    # R2: учитываются ТОЛЬКО надетые пальцы, не инвентарь.
    s = GameState.default_new_game()
    s.inventory = [mk('ring', 's+grade'), mk('ring', 's+grade')]
    assert _type_gap(s, 'ring') == 5  # пальцы пустые → gap 5


# ----- _type_weights -----

def test_weights_luck_zero_is_base():
    s = GameState.default_new_game()  # luck 0
    assert _type_weights(s) == _BASE_TYPE_WEIGHTS


def test_weights_max_gap_zero_is_base():
    # всё S+ (включая оба пальца и рюкзак) → max_gap 0 → буста нет даже при luck.
    s = GameState.default_new_game()
    s.gym.luck_skill = 50
    s.equipment.head = mk('helmet', 's+grade')
    s.equipment.neck = mk('necklace', 's+grade')
    s.equipment.torso = mk('t-shirt', 's+grade')
    s.equipment.foots = mk('shoes', 's+grade')
    s.equipment.finger_01 = mk('ring', 's+grade')
    s.equipment.finger_02 = mk('ring', 's+grade')
    s.equipment.back = mk('backpack', 's+grade')
    assert _type_weights(s) == _BASE_TYPE_WEIGHTS


def _example1_state() -> GameState:
    """Worked example 1: рюкзак пуст (gap5), helmet a-grade (gap2), остальное S+.
    luck=30 → max_gap=5."""
    s = GameState.default_new_game()
    s.gym.luck_skill = 30
    s.equipment.head = mk('helmet', 'a-grade')        # gap 2
    s.equipment.neck = mk('necklace', 's+grade')      # gap 0
    s.equipment.torso = mk('t-shirt', 's+grade')      # gap 0
    s.equipment.foots = mk('shoes', 's+grade')        # gap 0
    s.equipment.finger_01 = mk('ring', 's+grade')     # gap 0 (оба пальца s+)
    s.equipment.finger_02 = mk('ring', 's+grade')
    # back = None → backpack gap 5
    return s


def test_weights_example1_relative_boost():
    s = _example1_state()
    w = _type_weights(s)
    # max_gap=5; boost = luck * gap / 5
    assert w['backpack'] == pytest.approx(5 + 30)        # gap5 → +30 = 35
    assert w['helmet'] == pytest.approx(19 + 30 * 2 / 5)  # gap2 → +12 = 31
    assert w['ring'] == pytest.approx(19)                # gap0
    assert w['necklace'] == pytest.approx(19)
    assert w['shoes'] == pytest.approx(19)
    assert w['t-shirt'] == pytest.approx(19)


def _example2_state() -> GameState:
    """Worked example 2: helmet a-grade — единственный не-S+; рюкзак S+, всё S+.
    luck=30 → max_gap = gap(helmet) = 2 → helmet получает ПОЛНЫЙ буст."""
    s = _example1_state()
    s.equipment.back = mk('backpack', 's+grade')  # gap 0 теперь
    return s


def test_weights_example2_single_needy_gets_full():
    s = _example2_state()
    w = _type_weights(s)
    # max_gap=2 (helmet). boost helmet = 30*2/2 = 30 → 49; остальные gap0.
    assert w['helmet'] == pytest.approx(19 + 30)  # 49
    assert w['backpack'] == pytest.approx(5)
    for t in ('ring', 'necklace', 'shoes', 't-shirt'):
        assert w[t] == pytest.approx(19)


# ----- Monte-Carlo: распределение item_type под весами -----

def _mc_distribution(state: GameState, n: int = 40000) -> dict[str, float]:
    random.seed(20465)  # детерминизм
    d = Drop_Item()
    counts: dict[str, int] = {t: 0 for t in _DROP_TYPES}
    for _ in range(n):
        counts[d.item_type(state)] += 1
    return {t: counts[t] / n for t in _DROP_TYPES}


def test_mc_example1_matches_expected_percentages():
    # weights sum = 142: backpack 35/142=24.6%, helmet 31/142=21.8%, прочие 19/142=13.4%
    mc = _mc_distribution(_example1_state())
    assert mc['backpack'] == pytest.approx(35 / 142, abs=0.02)
    assert mc['helmet'] == pytest.approx(31 / 142, abs=0.02)
    for t in ('ring', 'necklace', 'shoes', 't-shirt'):
        assert mc[t] == pytest.approx(19 / 142, abs=0.02)


def test_mc_example2_matches_expected_percentages():
    # weights sum = 130: helmet 49/130=37.7%, прочие 19/130=14.6%, backpack 5/130=3.8%
    mc = _mc_distribution(_example2_state())
    assert mc['helmet'] == pytest.approx(49 / 130, abs=0.02)
    assert mc['backpack'] == pytest.approx(5 / 130, abs=0.02)
    for t in ('ring', 'necklace', 'shoes', 't-shirt'):
        assert mc[t] == pytest.approx(19 / 130, abs=0.02)


def test_mc_base_distribution_no_luck():
    # luck=0 → базовое: backpack 5/100=5%, прочие 19/100=19%
    mc = _mc_distribution(GameState.default_new_game())
    assert mc['backpack'] == pytest.approx(0.05, abs=0.015)
    for t in ('ring', 'necklace', 'helmet', 'shoes', 't-shirt'):
        assert mc[t] == pytest.approx(0.19, abs=0.02)
