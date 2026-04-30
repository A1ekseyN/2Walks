"""Бонусы от навыков персонажа.

Phase 3 задачи 1.1: функции принимают `state: GameState`. Backward compat:
`state=None` → подтягивается `game_state` из characteristics. Удалить default
после Phase 5.

Module-level вызов `stamina_skill_bonus = stamina_skill_bonus_def()` убран —
он считал бонус один раз при импорте на ещё не прогретом состоянии. Импорт
этого имени из gym.py был мёртвым (значение никогда не использовалось).
"""

from equipment_bonus import equipment_speed_skill_bonus
from state import GameState


def _resolve_state(state):
    if state is None:
        from characteristics import game_state
        return game_state
    return state


def stamina_skill_bonus_def(state: GameState = None):
    # Бонус кол-ва шагов от навыка Stamina.
    state = _resolve_state(state)
    return round(state.steps.today / 100) * state.gym.stamina


def speed_skill_equipment_and_level_bonus(x, state: GameState = None):
    # Уменьшение длительности на сумму speed-бонусов (gym + equipment + level).
    state = _resolve_state(state)
    return int(x - (x / 100) * (
        state.gym.speed_skill
        + equipment_speed_skill_bonus(state)
        + state.char_level.skill_speed
    ))
