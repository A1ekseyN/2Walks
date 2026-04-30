"""Бонусы от навыков персонажа."""

from equipment_bonus import equipment_speed_skill_bonus
from state import GameState


def stamina_skill_bonus_def(state: GameState):
    # Бонус кол-ва шагов от навыка Stamina.
    return round(state.steps.today / 100) * state.gym.stamina


def speed_skill_equipment_and_level_bonus(x, state: GameState):
    # Уменьшение длительности на сумму speed-бонусов (gym + equipment + level).
    return int(x - (x / 100) * (
        state.gym.speed_skill
        + equipment_speed_skill_bonus(state)
        + state.char_level.skill_speed
    ))
