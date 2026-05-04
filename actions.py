"""Helper-функции для не-тривиальных мутаций GameState.

Phase 4 задачи 1.1: тонкий слой между геймплейными модулями (gym/work/adventure)
и state. Каждая функция инкапсулирует инвариант — например, `try_spend` атомарно
проверяет ресурсы и списывает их, чтобы не плодить `if energy >= cost: energy -= cost; ...`
по нескольким файлам.

В этом коммите создаётся минимальный набор. Расширяется по мере миграции
gym/work/adventure (Phase 4, commit 3).
"""

from datetime import datetime
from typing import Optional

from state import GameState


def try_spend(state: GameState, steps: int = 0, energy: int = 0, money: int = 0) -> bool:
    """Атомарно проверяет ресурсы и списывает их.

    Возвращает True, если все ресурсы покрывают запрошенную стоимость,
    и в этом случае выполняется списание. False — ничего не списывается.

    Списание шагов:
    - state.steps.can_use уменьшается на `steps`
    - state.steps.used и state.steps.total_used увеличиваются на `steps`

    Энергия (задача 2.2.3 — фикс "бесплатной энергии после максимума"):
    если перед тратой энергия была на максимуме (`state.energy == state.energy_max`),
    то после списания `state.energy_time_stamp` синкается к `now`. Это закрывает
    эксплоит, когда стамп ушёл далеко в прошлое (на full-энергии), потом игрок
    тратит — и при следующем тике `energy_time_charge()` начисляет "накопленную"
    энергию назад. При не-full состоянии стамп не двигается, чтобы не штрафовать
    игрока за частичный прогресс к +1.
    """
    if state.steps.can_use < steps:
        return False
    if state.energy < energy:
        return False
    if state.money < money:
        return False

    if steps:
        state.steps.can_use -= steps
        state.steps.used += steps
        state.steps.total_used += steps
    if energy:
        # Lazy import — bonus.py зависит от equipment_bonus, чтобы не тянуть
        # его при каждом импорте actions (используется hot-path).
        from bonus import compute_energy_max
        was_full = state.energy >= compute_energy_max(state)
        state.energy -= energy
        if was_full:
            state.energy_time_stamp = datetime.now().timestamp()
    if money:
        state.money -= money
    return True


def start_work(
    state: GameState,
    work_type: str,
    salary: int,
    hours: int,
    start: datetime,
    end: datetime,
) -> None:
    """Включает рабочую сессию — выставляет все поля state.work одним шагом."""
    state.work.work_type = work_type
    state.work.active = True
    state.work.salary = salary
    state.work.hours = hours
    state.work.start = start
    state.work.end = end


def start_training(
    state: GameState,
    skill_name: str,
    time_end: datetime,
    timestamp: Optional[float] = None,
) -> None:
    """Включает тренировку навыка — выставляет state.training."""
    state.training.active = True
    state.training.skill_name = skill_name
    state.training.timestamp = timestamp
    state.training.time_end = time_end


def start_adventure(
    state: GameState,
    name: str,
    start_ts: float,
    end_ts: datetime,
) -> None:
    """Включает приключение — выставляет state.adventure."""
    state.adventure.active = True
    state.adventure.name = name
    state.adventure.start_ts = start_ts
    state.adventure.end_ts = end_ts
