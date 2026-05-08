"""Тесты bonus после миграции на GameState (Phase 3 задачи 1.1)."""

from state import GameState
from bonus import (
    apply_money_saving,
    equipment_bonus_stamina_steps,
    daily_steps_bonus,
    level_steps_bonus,
    apply_move_optimization_adventure,
    apply_move_optimization_gym,
    apply_move_optimization_work,
    compute_energy_max,
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


def test_compute_energy_max_default():
    """Default state: 50 + 0 + 0 + 0 + 0 = 50."""
    state = GameState.default_new_game()
    assert compute_energy_max(state) == 50


def test_compute_energy_max_with_gym_skill():
    state = GameState.default_new_game()
    state.gym.energy_max_skill = 15
    assert compute_energy_max(state) == 65


def test_compute_energy_max_with_all_sources():
    """Полная комбинация: gym + equipment + daily + char_level skill."""
    state = GameState.default_new_game()
    state.gym.energy_max_skill = 10
    state.equipment.head = _item('energy_max', 5)  # equipment +5
    state.steps.daily_bonus = 3
    state.char_level.skill_energy_max = 2
    # 50 + 10 + 5 + 3 + 2 = 70
    assert compute_energy_max(state) == 70


def test_compute_energy_max_ignores_state_field():
    """state.energy_max как поле (legacy save cache) НЕ влияет на compute —
    всегда выводится из источников. Это и есть pure A: derived value."""
    state = GameState.default_new_game()
    state.energy_max = 999  # mock stale cache
    state.gym.energy_max_skill = 5
    # compute считает только из источников.
    assert compute_energy_max(state) == 55


# ---------------------------------------------------------------------------
# 4.20 — apply_money_saving: -1%/level скидка, линейная, round до 2 знаков.
# ---------------------------------------------------------------------------

def test_apply_money_saving_no_skill_keeps_cost():
    """skill=0 — цена не меняется, но возвращается как float (round до 2 знаков)."""
    state = GameState.default_new_game()
    assert apply_money_saving(100, state) == 100.00
    assert apply_money_saving(0, state) == 0.00


def test_apply_money_saving_linear_discount():
    """skill=10 → 10% скидка от 100 = 90.00."""
    state = GameState.default_new_game()
    state.gym.money_saving = 10
    assert apply_money_saving(100, state) == 90.00


def test_apply_money_saving_fractional_result():
    """750 × (1 - 7/100) = 697.50 — ровно 2 знака без флоат-погрешности."""
    state = GameState.default_new_game()
    state.gym.money_saving = 7
    assert apply_money_saving(750, state) == 697.50


def test_apply_money_saving_rounds_to_two_decimals():
    """Дробные результаты округляются ровно до 2 знаков."""
    state = GameState.default_new_game()
    state.gym.money_saving = 33  # cost * 0.67
    assert apply_money_saving(100, state) == 67.0
    assert apply_money_saving(1000, state) == 670.0
    # 17 * 0.67 = 11.39
    assert apply_money_saving(17, state) == 11.39


def test_apply_money_saving_at_skill_100_returns_zero():
    """skill=100 — цена становится 0.00 (намеренный design choice — линейная
    формула без cap, см. TASKS.md 4.20)."""
    state = GameState.default_new_game()
    state.gym.money_saving = 100
    assert apply_money_saving(500, state) == 0.00


def test_apply_money_saving_above_100_clamped_to_zero():
    """skill > 100 — clamp до 0, нет «отрицательной цены»."""
    state = GameState.default_new_game()
    state.gym.money_saving = 150
    assert apply_money_saving(500, state) == 0.00


def test_apply_money_saving_zero_cost_stays_zero():
    """cost=0 → результат 0.00 при любом skill."""
    state = GameState.default_new_game()
    state.gym.money_saving = 50
    assert apply_money_saving(0, state) == 0.00


def test_apply_money_saving_returns_float_type():
    """Тип всегда float — обеспечивает корректную работу try_spend(money: float)."""
    state = GameState.default_new_game()
    result = apply_money_saving(100, state)
    assert isinstance(result, float)


# ---------------------------------------------------------------------------
# 4.23 — apply_earnings_boost: +1%/level бонус к зарплате (только Work).
# Линейный без cap (симметрично money_saving).
# ---------------------------------------------------------------------------

from bonus import apply_earnings_boost


def test_apply_earnings_boost_no_skill_keeps_salary():
    """skill=0 — зарплата не меняется (round до 2 знаков для единообразия)."""
    state = GameState.default_new_game()
    assert apply_earnings_boost(50, state) == 50.00
    assert apply_earnings_boost(0, state) == 0.00


def test_apply_earnings_boost_linear():
    """skill=10 → 50 * 1.10 = 55.00."""
    state = GameState.default_new_game()
    state.gym.earnings_boost = 10
    assert apply_earnings_boost(50, state) == 55.00


def test_apply_earnings_boost_fractional_result():
    """Дробный результат — round до 2 знаков. 17 * 1.07 = 18.19."""
    state = GameState.default_new_game()
    state.gym.earnings_boost = 7
    assert apply_earnings_boost(17, state) == 18.19


def test_apply_earnings_boost_doubles_at_skill_100():
    """skill=100 — удвоение. Без cap (намеренный design choice — симметрия с money_saving)."""
    state = GameState.default_new_game()
    state.gym.earnings_boost = 100
    assert apply_earnings_boost(50, state) == 100.00


def test_apply_earnings_boost_grows_above_100():
    """skill=200 — утроение. Линейно без cap."""
    state = GameState.default_new_game()
    state.gym.earnings_boost = 200
    assert apply_earnings_boost(50, state) == 150.00


def test_apply_earnings_boost_zero_salary_stays_zero():
    """salary=0 → 0.00 при любом skill."""
    state = GameState.default_new_game()
    state.gym.earnings_boost = 50
    assert apply_earnings_boost(0, state) == 0.00


def test_apply_earnings_boost_returns_float_type():
    """Тип всегда float — для round-trip с state.money: float."""
    state = GameState.default_new_game()
    result = apply_earnings_boost(50, state)
    assert isinstance(result, float)


def test_apply_earnings_boost_typical_watchman():
    """Реалистичный пример: watchman base salary=2, skill=15 → 2.30 $/ч."""
    state = GameState.default_new_game()
    state.gym.earnings_boost = 15
    assert apply_earnings_boost(2, state) == 2.30


# ----- 4.50.0 — backpack_capacity / inventory_full -----

from bonus import BASE_BACKPACK_CAPACITY, backpack_capacity, inventory_full


def test_backpack_capacity_default_is_base():
    """skill=0 → base = 10."""
    state = GameState.default_new_game()
    assert backpack_capacity(state) == BASE_BACKPACK_CAPACITY == 10


def test_backpack_capacity_grows_linearly_with_skill():
    """+1 слот за уровень skill, без cap."""
    state = GameState.default_new_game()
    state.gym.backpack_skill = 5
    assert backpack_capacity(state) == 15
    state.gym.backpack_skill = 50
    assert backpack_capacity(state) == 60


def test_inventory_full_at_capacity():
    """len(inventory) == cap — full = True."""
    state = GameState.default_new_game()
    state.inventory = [{} for _ in range(10)]
    assert inventory_full(state) is True


def test_inventory_full_below_capacity():
    """len(inventory) < cap — full = False."""
    state = GameState.default_new_game()
    state.inventory = [{} for _ in range(9)]
    assert inventory_full(state) is False


def test_inventory_full_above_capacity_legacy():
    """Legacy save с inventory > cap — full остаётся True (нельзя добавить
    новые предметы пока не освободится слот). Backwards-compat вариант A."""
    state = GameState.default_new_game()
    state.inventory = [{} for _ in range(20)]  # был сейв с 20 предметами
    assert inventory_full(state) is True


# ----- 4.50.1 — auto_collect_pending_drop -----

from bonus import auto_collect_pending_drop


def _make_pending_item(grade='a-grade', price=120):
    return {
        'item_name': ['ring'], 'item_type': ['ring'], 'grade': [grade],
        'characteristic': ['luck'], 'bonus': [3], 'quality': [80.0],
        'price': [price],
    }


def test_auto_collect_no_pending_returns_none():
    """Helper no-op'ит когда pending=None."""
    state = GameState.default_new_game()
    assert auto_collect_pending_drop(state) is None
    assert state.pending_drop is None
    assert state.inventory == []


def test_auto_collect_with_full_inventory_returns_none():
    """pending есть, но места всё равно нет — no-op."""
    state = GameState.default_new_game()
    state.pending_drop = _make_pending_item()
    state.inventory = [{} for _ in range(10)]  # cap=10, full

    assert auto_collect_pending_drop(state) is None
    assert state.pending_drop is not None  # без мутации
    assert len(state.inventory) == 10


def test_auto_collect_with_free_slot_appends_and_clears():
    """pending есть, место освободилось — append, clear, return item."""
    item = _make_pending_item()
    state = GameState.default_new_game()
    state.pending_drop = item
    state.inventory = [{} for _ in range(5)]  # 5 < 10

    result = auto_collect_pending_drop(state)

    assert result is item
    assert state.pending_drop is None
    assert state.inventory[-1] is item
    assert len(state.inventory) == 6


def test_auto_collect_after_skill_upgrade_makes_room():
    """Симуляция B): cap был 10 (full), прокачали backpack_skill=1 — cap=11,
    auto-collect должен сработать."""
    item = _make_pending_item()
    state = GameState.default_new_game()
    state.pending_drop = item
    state.inventory = [{} for _ in range(10)]  # full при cap=10
    assert auto_collect_pending_drop(state) is None  # ещё full

    state.gym.backpack_skill = 1  # cap → 11

    result = auto_collect_pending_drop(state)
    assert result is item
    assert state.pending_drop is None
    assert len(state.inventory) == 11


def test_auto_collect_idempotent_after_success():
    """Второй вызов после успеха — no-op (pending=None)."""
    state = GameState.default_new_game()
    state.pending_drop = _make_pending_item()
    state.inventory = []

    auto_collect_pending_drop(state)
    assert auto_collect_pending_drop(state) is None
    assert state.pending_drop is None
