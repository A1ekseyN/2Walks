"""Бонусы (шаги/энергия/скорость) — функции, читающие GameState.

Phase 3 задачи 1.1: функции принимают `state: GameState`. Backward compat:
`state=None` → подтягивается `game_state` из characteristics. Удалить default
после Phase 5.
"""

from equipment_bonus import equipment_stamina_bonus
from state import GameState


def _resolve_state(state):
    if state is None:
        from characteristics import game_state
        return game_state
    return state


def skill_bonus_energy_max(state: GameState = None):
    # Бонус Макс. Энергии от навыка (мутирующая, нигде не вызывается; см. 1.5).
    state = _resolve_state(state)
    state.energy_max += state.gym.energy_max_skill
    return state.energy_max


def equipment_bonus_stamina_steps(state: GameState = None):
    # Бонус шагов через бонус экипировки.
    state = _resolve_state(state)
    return round((state.steps.today / 100) * equipment_stamina_bonus(state))


def daily_steps_bonus(state: GameState = None):
    # Бонус за пройденное кол-во шагов, более 10к.
    state = _resolve_state(state)
    return round((state.steps.today / 100) * state.steps.daily_bonus)


def level_steps_bonus(state: GameState = None):
    """Бонус к кол-ву шагов в зависимости от уровня прокачки навыка."""
    state = _resolve_state(state)
    return round((state.steps.today / 100) * state.char_level.skill_stamina)


def apply_move_optimization_adventure(steps, state: GameState = None):
    """Уменьшает требуемые шаги для Adventure на % прокачки соответствующего навыка."""
    state = _resolve_state(state)
    steps['steps'] *= (1 - state.gym.move_optimization_adventure / 100)
    steps['steps'] = int(steps['steps'])
    return steps


def apply_move_optimization_gym(steps, state: GameState = None):
    """Уменьшает требуемые шаги для Gym на % прокачки соответствующего навыка."""
    state = _resolve_state(state)
    steps *= (1 - state.gym.move_optimization_gym / 100)
    return int(steps)


def apply_move_optimization_work(steps, state: GameState = None):
    """Уменьшает требуемые шаги для Work на % прокачки соответствующего навыка."""
    state = _resolve_state(state)
    steps *= (1 - state.gym.move_optimization_work / 100)
    return int(steps)
