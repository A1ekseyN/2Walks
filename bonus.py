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
    adjusted = steps * (1 - state.gym.move_optimization_gym / 100)
    return int(adjusted)


def apply_move_optimization_work(steps: int, state: GameState) -> int:
    """Уменьшает требуемые шаги для Work на % прокачки соответствующего навыка."""
    adjusted = steps * (1 - state.gym.move_optimization_work / 100)
    return int(adjusted)


def apply_money_saving(cost: float, state: GameState) -> float:
    """4.20 — Скидка на денежные траты (Gym / Shop). Линейная: -1% за уровень
    `state.gym.money_saving`. Возвращает `round(..., 2)` чтобы цены имели
    максимум 2 знака после запятой и не плодили float-погрешности.

    Edge cases:
    - skill=0 → cost без изменений (round до 2 знаков для единообразия).
    - skill=100 → cost = 0 (бесплатно). Намеренный design choice — игрок выбрал
      линейную формулу несмотря на «риск 0».
    - skill > 100 → результат clamped до 0 (нет «отрицательной» цены).
    - НЕ применяется к: Work salary (доход), Bank deposit/withdraw, Bank loan.
    """
    discount = state.gym.money_saving / 100.0
    discounted = cost * (1.0 - discount)
    return round(max(0.0, discounted), 2)


# 4.50 — Базовая ёмкость инвентаря для нового персонажа.
# Прокачка: state.gym.backpack_skill (+1 слот за уровень).
BASE_BACKPACK_CAPACITY = 10


def backpack_capacity(state: GameState) -> int:
    """Текущая максимальная ёмкость инвентаря (4.50).

    `BASE_BACKPACK_CAPACITY + state.gym.backpack_skill`. Pure helper, без
    мутаций. Используется в:
    - `shop.py:_buy_item` — блокировка покупки при full.
    - `equipment.py:_unequip` — блокировка снятия при full.
    - `drop.py:item_collect` — будет в 4.50.1 (interactive sell-and-keep flow).
    - UI display: `inventory_view` (CLI), `_status_fragment.html` (web).

    Backwards-compat: если у игрока на момент введения capacity > base+skill —
    существующие предметы остаются (см. `inventory_full`), но новые не добавятся
    пока не освободится слот через продажу или Adventure-flow (4.50.1).
    """
    return BASE_BACKPACK_CAPACITY + state.gym.backpack_skill


def inventory_full(state: GameState) -> bool:
    """True если инвентарь заполнен (или переполнен — для legacy сейвов).

    `>=` а не `==` — чтобы игроки с большим существующим inventory не могли
    добавлять новые предметы (хрустящая backwards-compat, вариант A из 4.50).
    """
    return len(state.inventory) >= backpack_capacity(state)


def apply_earnings_boost(salary: float, state: GameState) -> float:
    """4.23 — Бонус к зарплате (только Work). Линейная: +1% за уровень
    `state.gym.earnings_boost`. Возвращает `round(..., 2)`. Симметричен
    `apply_money_saving` — обёрнут во ВСЕ display точки и при начислении
    в `work_check_done`, чтобы игрок видел итоговую зарплату с бонусом
    в preview меню работы.

    Edge cases:
    - skill=0 → salary без изменений (round до 2 знаков).
    - skill=100 → удвоение дохода. Без cap (намеренный design choice).
    - skill=200 → утроение и т.д. Линейно бесконечно.
    - state.work.salary остаётся **базовой** (без bonus) — все обёртки
      применяют bonus на лету. Это даёт recompute: прокачал во время
      смены → next render preview показывает новую сумму, при завершении
      применяется текущий уровень skill.
    """
    boost = state.gym.earnings_boost / 100.0
    return round(salary * (1.0 + boost), 2)
