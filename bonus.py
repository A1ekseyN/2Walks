"""Бонусы (шаги/энергия/скорость) — функции, читающие GameState."""

from equipment_bonus import equipment_energy_max_bonus, equipment_stamina_bonus
from state import GameState


# Базовый максимум энергии нового персонажа. Все бонусы добавляются поверх.
ENERGY_MAX_BASE = 50


def compute_energy_max(state: GameState) -> int:
    """Вычисляет актуальный максимум энергии из всех источников.

    `state.energy_max` (поле) НЕ читается — это derived value, всегда
    вычисляется на лету (вариант A — pure computed, см. задачу 4.48.4.1).
    Поле остаётся в dataclass для save-format совместимости (CSV/Sheets
    колонка `energy_max`), но в логике игры читается только эта функция.
    """
    return (
        ENERGY_MAX_BASE
        + state.gym.energy_max_skill
        + equipment_energy_max_bonus(state)
        + state.steps.daily_bonus
        + state.char_level.skill_energy_max
    )


def equipment_bonus_stamina_steps(state: GameState) -> int:
    # Бонус шагов через бонус экипировки.
    return round((state.steps.today / 100) * equipment_stamina_bonus(state))


def daily_steps_bonus(state: GameState) -> int:
    # Бонус за пройденное кол-во шагов, более 10к.
    return round((state.steps.today / 100) * state.steps.daily_bonus)


def level_steps_bonus(state: GameState) -> int:
    """Бонус к кол-ву шагов в зависимости от уровня прокачки навыка."""
    return round((state.steps.today / 100) * state.char_level.skill_stamina)


def apply_move_optimization_adventure(steps: dict, state: GameState) -> dict:
    """Уменьшает требуемые шаги для Adventure на % прокачки соответствующего навыка.

    Принимает dict-запись из adventure_data_table (`{'steps': int, ...}`),
    мутирует поле `steps` и возвращает тот же dict (in-place + return).
    """
    steps['steps'] *= (1 - state.gym.move_optimization_adventure / 100)
    steps['steps'] = int(steps['steps'])
    return steps


def apply_move_optimization_gym(steps: int, state: GameState) -> int:
    """Уменьшает требуемые шаги для Gym на % прокачки соответствующего навыка."""
    steps *= (1 - state.gym.move_optimization_gym / 100)
    return int(steps)


def apply_move_optimization_work(steps: int, state: GameState) -> int:
    """Уменьшает требуемые шаги для Work на % прокачки соответствующего навыка."""
    steps *= (1 - state.gym.move_optimization_work / 100)
    return int(steps)
