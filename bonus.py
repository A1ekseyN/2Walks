"""Бонусы (шаги/энергия/скорость) — функции, читающие GameState."""

from equipment_bonus import equipment_stamina_bonus
from state import GameState


def skill_bonus_energy_max(state: GameState):
    # Бонус Макс. Энергии от навыка (мутирующая, нигде не вызывается; см. 1.5).
    state.energy_max += state.gym.energy_max_skill
    return state.energy_max


def equipment_bonus_stamina_steps(state: GameState):
    # Бонус шагов через бонус экипировки.
    return round((state.steps.today / 100) * equipment_stamina_bonus(state))


def daily_steps_bonus(state: GameState):
    # Бонус за пройденное кол-во шагов, более 10к.
    return round((state.steps.today / 100) * state.steps.daily_bonus)


def level_steps_bonus(state: GameState):
    """Бонус к кол-ву шагов в зависимости от уровня прокачки навыка."""
    return round((state.steps.today / 100) * state.char_level.skill_stamina)


def apply_move_optimization_adventure(steps, state: GameState):
    """Уменьшает требуемые шаги для Adventure на % прокачки соответствующего навыка."""
    steps['steps'] *= (1 - state.gym.move_optimization_adventure / 100)
    steps['steps'] = int(steps['steps'])
    return steps


def apply_move_optimization_gym(steps, state: GameState):
    """Уменьшает требуемые шаги для Gym на % прокачки соответствующего навыка."""
    steps *= (1 - state.gym.move_optimization_gym / 100)
    return int(steps)


def apply_move_optimization_work(steps, state: GameState):
    """Уменьшает требуемые шаги для Work на % прокачки соответствующего навыка."""
    steps *= (1 - state.gym.move_optimization_work / 100)
    return int(steps)
