"""Бонусы от экипировки. Все функции читают слоты из state.equipment.

4.61 (0.2.4x) — Поломка предметов. Item с `quality == 0` считается сломанным
и НЕ даёт bonus. Все 5 helper-функций ниже пропускают broken items через
`_is_broken(item)`. Legacy items без поля quality считаются «целыми»
(treated as non-broken — backwards-compat для очень старых сейвов).
"""

from typing import Optional

from state import GameState


def _equipment_slots(state: GameState) -> list[Optional[dict]]:
    """Список dict'ов экипировки (или None) из всех слотов state.equipment."""
    eq = state.equipment
    return [eq.head, eq.neck, eq.torso, eq.finger_01, eq.finger_02, eq.legs, eq.foots]


def _is_broken(item: dict) -> bool:
    """4.61 — Item сломан если quality == 0 (strict). Legacy items без поля
    quality → НЕ broken (backwards-compat). Items с quality > 0 → не broken.

    Используется во всех bonus-функциях ниже для skip broken items.
    """
    qual_list = item.get('quality')
    if not qual_list:
        return False  # legacy — нет поля → не broken
    return bool(qual_list[0] == 0)


def equipment_bonus(state: GameState) -> tuple[int, int, int, int]:
    """Сумма бонусов всей экипировки по 4 характеристикам.

    Возвращает кортеж (stamina, energy_max, speed_skill, luck).
    Broken items (quality=0) НЕ дают bonus — 4.61.
    """
    eq_stamina = 0
    eq_energy_max = 0
    eq_speed = 0
    eq_luck = 0
    for item in _equipment_slots(state):
        if item is None or _is_broken(item):
            continue
        char = item['characteristic'][0]
        bonus = item['bonus'][0]
        if char == 'stamina':
            eq_stamina += bonus
        elif char == 'energy_max':
            eq_energy_max += bonus
        elif char == 'speed_skill':
            eq_speed += bonus
        elif char == 'luck':
            eq_luck += bonus
    return eq_stamina, eq_energy_max, eq_speed, eq_luck


def equipment_stamina_bonus(state: GameState) -> int:
    total = 0
    for item in _equipment_slots(state):
        if (item is not None
                and not _is_broken(item)
                and item['characteristic'][0] == 'stamina'):
            total += item['bonus'][0]
    return total


def equipment_energy_max_bonus(state: GameState) -> int:
    total = 0
    for item in _equipment_slots(state):
        if (item is not None
                and not _is_broken(item)
                and item['characteristic'][0] == 'energy_max'):
            total += item['bonus'][0]
    return total


def equipment_speed_skill_bonus(state: GameState) -> int:
    total = 0
    for item in _equipment_slots(state):
        if (item is not None
                and not _is_broken(item)
                and item['characteristic'][0] == 'speed_skill'):
            total += item['bonus'][0]
    return total


def equipment_luck_bonus(state: GameState) -> int:
    total = 0
    for item in _equipment_slots(state):
        if (item is not None
                and not _is_broken(item)
                and item['characteristic'][0] == 'luck'):
            total += item['bonus'][0]
    return total


def low_quality_equipped_items(state: GameState, threshold: int = 20) -> list[dict]:
    """4.61 — Возвращает list equipped items с quality < threshold (default 20%).

    Используется для status_bar warning «⚠ Требует ремонта: N предметов».
    Broken (quality=0) включаются (0 < 20). Items без поля quality пропускаются
    (legacy).
    """
    result: list[dict] = []
    for item in _equipment_slots(state):
        if item is None:
            continue
        qual_list = item.get('quality')
        if not qual_list:
            continue
        if qual_list[0] < threshold:
            result.append(item)
    return result
