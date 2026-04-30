"""Тесты skill_bonus после миграции на GameState (Phase 3 задачи 1.1)."""

from state import GameState
from skill_bonus import stamina_skill_bonus_def, speed_skill_equipment_and_level_bonus


def _item(char, bonus):
    return {'characteristic': [char], 'bonus': [bonus]}


def test_stamina_skill_bonus_def_zero_default():
    state = GameState.default_new_game()
    assert stamina_skill_bonus_def(state) == 0


def test_stamina_skill_bonus_def_with_skill():
    state = GameState.default_new_game()
    state.steps.today = 5000
    state.gym.stamina = 4
    # round(5000/100) * 4 = 50 * 4 = 200
    assert stamina_skill_bonus_def(state) == 200


def test_speed_skill_equipment_and_level_bonus_no_speed():
    """Без speed-бонусов x возвращается без изменения."""
    state = GameState.default_new_game()
    assert speed_skill_equipment_and_level_bonus(60, state) == 60


def test_speed_skill_equipment_and_level_bonus_with_skill():
    state = GameState.default_new_game()
    state.gym.speed_skill = 10
    # 60 - (60/100)*10 = 60 - 6 = 54
    assert speed_skill_equipment_and_level_bonus(60, state) == 54


def test_speed_skill_combines_skill_equipment_and_level():
    state = GameState.default_new_game()
    state.gym.speed_skill = 5
    state.char_level.skill_speed = 3
    state.equipment.head = _item('speed_skill', 2)
    # total speed = 5 + 2 + 3 = 10
    # 60 - (60/100)*10 = 54
    assert speed_skill_equipment_and_level_bonus(60, state) == 54
