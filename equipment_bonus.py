"""Бонусы от экипировки. Все функции читают слоты из state.equipment."""

from state import GameState


def _equipment_slots(state: GameState):
    """Список dict'ов экипировки (или None) из всех слотов state.equipment."""
    eq = state.equipment
    return [eq.head, eq.neck, eq.torso, eq.finger_01, eq.finger_02, eq.legs, eq.foots]


def equipment_bonus(state: GameState):
    """Сумма бонусов всей экипировки по 4 характеристикам.

    Возвращает кортеж (stamina, energy_max, speed_skill, luck).
    """
    eq_stamina = 0
    eq_energy_max = 0
    eq_speed = 0
    eq_luck = 0
    for item in _equipment_slots(state):
        if item is None:
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


def equipment_stamina_bonus(state: GameState):
    total = 0
    for item in _equipment_slots(state):
        if item is not None and item['characteristic'][0] == 'stamina':
            total += item['bonus'][0]
    return total


def equipment_energy_max_bonus(state: GameState):
    total = 0
    for item in _equipment_slots(state):
        if item is not None and item['characteristic'][0] == 'energy_max':
            total += item['bonus'][0]
    return total


def equipment_speed_skill_bonus(state: GameState):
    total = 0
    for item in _equipment_slots(state):
        if item is not None and item['characteristic'][0] == 'speed_skill':
            total += item['bonus'][0]
    return total


def equipment_luck_bonus(state: GameState):
    total = 0
    for item in _equipment_slots(state):
        if item is not None and item['characteristic'][0] == 'luck':
            total += item['bonus'][0]
    return total
