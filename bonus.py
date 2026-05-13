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


# ===== 4.22 (0.2.4j) — Energy Optimization per-activity =====
#
# Группа из трёх навыков, симметричных move_optimization_*, но для энергии.
# Линейная формула -1%/level, clamp `max(1, ...)` (никогда не бесплатно).
# Для Work применяется к TOTAL (per_hour × hours), не per-hour — это убирает
# плато в low-base активностях (watchman 4 эн/ч). Для Gym/Adventure base = total
# (одна транзакция, нет batching).

def apply_energy_optimization_adventure(adv_data: dict, state: GameState) -> dict:
    """Уменьшает энергозатраты Adventure на % прокачки. Мутирует `adv_data['energy']`
    in-place (как `apply_move_optimization_adventure` для `'steps'`). Clamp min=1.

    Вызывается в `Adventure.__init__` после `apply_move_optimization_adventure`.
    """
    adjusted = adv_data['energy'] * (1 - state.gym.energy_optimization_adventure / 100)
    adv_data['energy'] = max(1, int(adjusted))
    return adv_data


def apply_energy_optimization_gym(energy: int, state: GameState) -> int:
    """Уменьшает энергозатраты Gym training (одна транзакция = одно списание).
    Clamp min=1.
    """
    adjusted = energy * (1 - state.gym.energy_optimization_gym / 100)
    return max(1, int(adjusted))


def apply_energy_optimization_work(energy: int, state: GameState) -> int:
    """Уменьшает энергозатраты Work shift. **Применяется к TOTAL energy**
    (per_hour × hours), НЕ per-hour. Это даёт линейную экономию без плато,
    которое было бы при per-hour rounding на low-base активностях (watchman
    4 эн/ч). Clamp min=1.

    Caller (work.py) ДОЛЖЕН передавать уже умноженное `per_hour * hours` значение.
    """
    adjusted = energy * (1 - state.gym.energy_optimization_work / 100)
    return max(1, int(adjusted))


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


def auto_collect_pending_drop(state: GameState):
    """4.50.1 — Авто-перемещает `state.pending_drop` в инвентарь, если место
    освободилось (продал предмет / прокачал backpack_skill / снял экипировку
    куда-то ещё). Pure helper: возвращает item на момент перемещения (для
    логирования / печати), либо None — если нет pending или ещё нет места.

    Идемпотентен: повторный вызов после успешного auto-collect — no-op.

    Логирование `drop_auto_collected` event'а делается ВНУТРИ helper'а,
    чтобы все callsite (CLI tick / web render / unit-tests) единообразно
    оставляли след в history.
    """
    if state.pending_drop is None:
        return None
    if inventory_full(state):
        return None
    item = state.pending_drop
    state.inventory.append(item)
    state.pending_drop = None
    from history import log_event
    log_event('drop_auto_collected',
              item_type=(item.get('item_type') or [None])[0],
              grade=(item.get('grade') or [None])[0],
              characteristic=(item.get('characteristic') or [None])[0],
              bonus=(item.get('bonus') or [None])[0],
              quality=(item.get('quality') or [None])[0],
              price=(item.get('price') or [None])[0])
    return item


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


def apply_trader(price: float, state: GameState) -> float:
    """4.28 — Бонус к цене продажи (все предметы). Линейная: +1% за уровень
    `state.gym.trader`. Возвращает `round(..., 2)`. Третья нога
    экономической трилогии (4.20 money_saving / 4.23 earnings_boost /
    4.28 trader).

    Применяется во ВСЕХ 4 точках продажи (0.2.4h):
    - `inventory._sell_item_at_index` — обычная продажа из меню Inventory.
    - `inventory._resolve_pending_drop_sell_existing` — продажа предмета
      из инвентаря в pending-drop resolve (4.50.1).
    - `inventory._resolve_pending_drop_sell_new` — продажа самой находки
      (pending).
    - `drop.Drop_Item.item_collect` — forced sale новой находки когда
      full inventory + pending уже занят (4.50.1 ветка (3)).

    Edge cases:
    - skill=0 → price без изменений (round до 2 знаков).
    - skill=100 → удвоение цены продажи. Без cap (симметрично с earnings_boost).
    - skill=200 → утроение. Линейно бесконечно.
    - Применяется ко ВСЕМ предметам (включая еду / Shop-покупки): игрок изначально
      платит больше в Shop чем получает обратно — баланс остаётся положительным
      даже с большим trader. Не требует source-tracking item-формата.
    """
    boost = state.gym.trader / 100.0
    return round(price * (1.0 + boost), 2)


def energy_regen_interval(base_seconds: int, state: GameState) -> int:
    """4.21 (0.2.4i) — Интервал regen энергии в секундах. Pure helper.

    До 0.2.4i regen использовал `speed_skill_equipment_and_level_bonus` —
    тот же helper что и для длительности активностей. Это связывало
    несвязанные механики: прокачка Speed невольно ускоряла regen.

    После 0.2.4i regen зависит ТОЛЬКО от energy_regen-источников:
    - `state.gym.energy_regen_skill` (новый Gym-скилл)
    - `state.char_level.skill_energy_regen` (новая CharLevel allocation)
    - Equipment **не учитывается** в V1 (V2 / задача 4.57 добавит characteristic='energy_regen').

    Формула: base - (base / 100) * (gym_regen + char_level_regen).
    Возвращает целое (как и оригинальный speed_skill_equipment_and_level_bonus).

    Edge cases:
    - regen=0 (default) → interval = base (60 сек).
    - regen=100 → interval = 0 (мгновенный regen).
    - regen > 100 → отрицательный interval, но fmt сам clamp'нит к корректному
      поведению (regen фактически мгновенный).
    """
    total = state.gym.energy_regen_skill + state.char_level.skill_energy_regen
    return int(base_seconds - (base_seconds / 100) * total)
