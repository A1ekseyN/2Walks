"""Тесты actions.py — helper-функции для не-тривиальных мутаций GameState
(Phase 4 задачи 1.1)."""

from datetime import datetime

from state import GameState
from actions import try_spend, start_work, start_training, start_adventure


# ----- try_spend -----

def test_try_spend_success_all_resources():
    state = GameState.default_new_game()
    state.steps.can_use = 1000
    state.steps.used = 50
    state.steps.total_used = 100
    state.energy = 30
    state.money = 200

    assert try_spend(state, steps=300, energy=10, money=50) is True
    assert state.steps.can_use == 700
    assert state.steps.used == 350
    assert state.steps.total_used == 400
    assert state.energy == 20
    assert state.money == 150


def test_try_spend_insufficient_steps_no_mutation():
    state = GameState.default_new_game()
    state.steps.can_use = 100
    state.steps.used = 0
    state.energy = 50
    state.money = 100

    assert try_spend(state, steps=200, energy=10, money=10) is False
    assert state.steps.can_use == 100
    assert state.steps.used == 0
    assert state.energy == 50
    assert state.money == 100


def test_try_spend_insufficient_energy_no_mutation():
    state = GameState.default_new_game()
    state.steps.can_use = 1000
    state.energy = 5
    state.money = 100

    assert try_spend(state, steps=100, energy=10, money=10) is False
    assert state.steps.can_use == 1000
    assert state.energy == 5
    assert state.money == 100


def test_try_spend_insufficient_money_no_mutation():
    state = GameState.default_new_game()
    state.steps.can_use = 1000
    state.energy = 50
    state.money = 5

    assert try_spend(state, steps=100, energy=10, money=10) is False
    assert state.steps.can_use == 1000
    assert state.energy == 50
    assert state.money == 5


def test_try_spend_zero_costs_succeeds_no_mutation():
    """Бесплатное действие — try_spend возвращает True и ничего не списывает."""
    state = GameState.default_new_game()
    state.steps.can_use = 100
    state.energy = 10
    state.money = 5

    assert try_spend(state) is True
    assert state.steps.can_use == 100
    assert state.energy == 10
    assert state.money == 5


def test_try_spend_exact_balance():
    """Списание ровно на оставшуюся сумму — должно пройти."""
    state = GameState.default_new_game()
    state.steps.can_use = 100
    state.energy = 10
    state.money = 5

    assert try_spend(state, steps=100, energy=10, money=5) is True
    assert state.steps.can_use == 0
    assert state.energy == 0
    assert state.money == 0


# ----- try_spend energy stamp sync (task 2.2.3) -----

def test_try_spend_energy_when_full_resets_stamp_to_now():
    """Был на max → после траты state.energy_time_stamp = now (фикс эксплоита
    "бесплатная энергия после максимума")."""
    state = GameState.default_new_game()
    state.energy = 50  # full (energy_max=50 default)
    state.energy_max = 50
    # Стамп далеко в прошлом (имитирует ситуацию "10 минут назад был на max").
    state.energy_time_stamp = datetime.now().timestamp() - 1000

    before = datetime.now().timestamp()
    assert try_spend(state, energy=10) is True
    after = datetime.now().timestamp()

    assert state.energy == 40
    # Стамп синкнут к now (с допуском в 1 секунду на jitter).
    assert before - 0.1 <= state.energy_time_stamp <= after + 0.1


def test_try_spend_energy_when_not_full_keeps_stamp():
    """Не на max → стамп не двигается (не штрафуем за частичный прогресс к +1)."""
    state = GameState.default_new_game()
    state.energy = 30  # не full
    state.energy_max = 50
    original_stamp = datetime.now().timestamp() - 30  # 30 сек назад
    state.energy_time_stamp = original_stamp

    assert try_spend(state, energy=10) is True

    assert state.energy == 20
    # Стамп НЕ изменился.
    assert state.energy_time_stamp == original_stamp


def test_try_spend_zero_energy_does_not_touch_stamp():
    """`try_spend(state, energy=0)` — даже если на max, стамп не двигается
    (нет реальной траты)."""
    state = GameState.default_new_game()
    state.energy = 50
    state.energy_max = 50
    original_stamp = datetime.now().timestamp() - 100
    state.energy_time_stamp = original_stamp

    assert try_spend(state, steps=0, energy=0, money=0) is True

    assert state.energy_time_stamp == original_stamp


def test_try_spend_failed_does_not_touch_stamp():
    """Недостаточно ресурсов — state не меняется, включая стамп."""
    state = GameState.default_new_game()
    state.energy = 5  # меньше чем требуется → fail
    state.energy_max = 50
    original_stamp = datetime.now().timestamp() - 100
    state.energy_time_stamp = original_stamp

    assert try_spend(state, energy=10) is False

    assert state.energy == 5  # не изменился
    assert state.energy_time_stamp == original_stamp  # не сдвинулся


# ----- start_work -----

def test_start_work_sets_all_fields():
    state = GameState.default_new_game()
    start = datetime(2026, 4, 30, 10, 0, 0)
    end = datetime(2026, 4, 30, 14, 0, 0)

    start_work(state, work_type='factory', salary=5, hours=4, start=start, end=end)

    assert state.work.work_type == 'factory'
    assert state.work.active is True
    assert state.work.salary == 5
    assert state.work.hours == 4
    assert state.work.start == start
    assert state.work.end == end


# ----- start_training -----

def test_start_training_sets_all_fields():
    state = GameState.default_new_game()
    end = datetime(2026, 4, 30, 12, 0, 0)

    start_training(state, skill_name='stamina', time_end=end, timestamp=1234567890.0)

    assert state.training.active is True
    assert state.training.skill_name == 'stamina'
    assert state.training.time_end == end
    assert state.training.timestamp == 1234567890.0


def test_start_training_timestamp_optional():
    state = GameState.default_new_game()
    end = datetime(2026, 4, 30, 12, 0, 0)

    start_training(state, skill_name='speed_skill', time_end=end)

    assert state.training.active is True
    assert state.training.skill_name == 'speed_skill'
    assert state.training.timestamp is None


# ----- start_adventure -----

def test_start_adventure_sets_all_fields():
    state = GameState.default_new_game()
    end = datetime(2026, 4, 30, 13, 0, 0)

    start_adventure(state, name='walk_15k', start_ts=1234567890.0, end_ts=end)

    assert state.adventure.active is True
    assert state.adventure.name == 'walk_15k'
    assert state.adventure.start_ts == 1234567890.0
    assert state.adventure.end_ts == end
