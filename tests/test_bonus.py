"""Тесты bonus после миграции на GameState (Phase 3 задачи 1.1)."""

from state import GameState
from bonus import (
    equipment_bonus_stamina_steps,
    daily_steps_bonus,
    level_steps_bonus,
    apply_move_optimization_adventure,
    apply_move_optimization_gym,
    apply_move_optimization_work,
    skill_bonus_energy_max,
)


def _item(char, bonus):
    return {'characteristic': [char], 'bonus': [bonus]}


def test_equipment_bonus_stamina_steps_zero_when_no_equipment():
    state = GameState.default_new_game()
    state.steps.today = 10000
    assert equipment_bonus_stamina_steps(state) == 0


def test_equipment_bonus_stamina_steps_uses_equipment():
    """Бонус = round((steps_today / 100) * equipment_stamina_bonus)."""
    state = GameState.default_new_game()
    state.steps.today = 5000
    state.equipment.head = _item('stamina', 10)
    # 5000 / 100 * 10 = 500
    assert equipment_bonus_stamina_steps(state) == 500


def test_daily_steps_bonus():
    state = GameState.default_new_game()
    state.steps.today = 10000
    state.steps.daily_bonus = 5
    # 10000 / 100 * 5 = 500
    assert daily_steps_bonus(state) == 500


def test_daily_steps_bonus_zero_below_10k():
    state = GameState.default_new_game()
    state.steps.today = 5000
    state.steps.daily_bonus = 0
    assert daily_steps_bonus(state) == 0


def test_level_steps_bonus():
    state = GameState.default_new_game()
    state.steps.today = 8000
    state.char_level.skill_stamina = 3
    # 8000 / 100 * 3 = 240
    assert level_steps_bonus(state) == 240


def test_apply_move_optimization_adventure_no_skill():
    state = GameState.default_new_game()
    steps = {'steps': 1000}
    result = apply_move_optimization_adventure(steps, state)
    assert result['steps'] == 1000


def test_apply_move_optimization_adventure_with_skill():
    state = GameState.default_new_game()
    state.gym.move_optimization_adventure = 20
    steps = {'steps': 1000}
    result = apply_move_optimization_adventure(steps, state)
    # 1000 * (1 - 20/100) = 800
    assert result['steps'] == 800


def test_apply_move_optimization_gym():
    state = GameState.default_new_game()
    state.gym.move_optimization_gym = 25
    # 2000 * 0.75 = 1500
    assert apply_move_optimization_gym(2000, state) == 1500


def test_apply_move_optimization_work():
    state = GameState.default_new_game()
    state.gym.move_optimization_work = 10
    # 500 * 0.9 = 450
    assert apply_move_optimization_work(500, state) == 450


def test_skill_bonus_energy_max_mutates_state():
    """Sanity: функция сейчас не используется в коде, но миграция сохранила её поведение."""
    state = GameState.default_new_game()
    state.energy_max = 50
    state.gym.energy_max_skill = 7
    result = skill_bonus_energy_max(state)
    assert result == 57
    assert state.energy_max == 57
