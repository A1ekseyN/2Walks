"""Тесты work.py после миграции на GameState (Phase 4 задачи 1.1, commit 3)."""

from datetime import datetime, timedelta

import pytest

from state import GameState
from work import Work, work_check_done, _speed_bonus_pct


# ----- _speed_bonus_pct -----

def test_speed_bonus_pct_sums_skill_equipment_level():
    state = GameState.default_new_game()
    state.gym.speed_skill = 5
    state.char_level.skill_speed = 3
    state.equipment.head = {
        'characteristic': ['speed_skill'], 'bonus': [2], 'item_name': ['x'],
        'item_type': ['x'], 'grade': ['a-grade'], 'quality': [50.0], 'price': [50],
    }
    assert _speed_bonus_pct(state) == 10


# ----- Work.__init__ -----

def test_work_init_uses_state_for_move_optimization():
    state = GameState.default_new_game()
    state.gym.move_optimization_work = 50  # 50% reduction
    w = Work(state)
    # watchman: base 200, reduced by 50% → 100
    assert w.work_requirements['watchman']['steps'] == 100
    assert w.work_requirements['factory']['steps'] == 250


def test_work_init_accepts_proxy_via_resolve():
    """Legacy locations.py:54 вызывает Work(char_characteristic) — proxy."""
    from state import CharCharacteristicProxy
    state = GameState.default_new_game()
    proxy = CharCharacteristicProxy(state)
    w = Work(proxy)
    assert w._state is state


# ----- Work.check_requirements -----

def test_check_requirements_starts_work_session():
    state = GameState.default_new_game()
    state.gym.move_optimization_work = 0
    state.steps.can_use = 1000
    state.energy = 50
    state.money = 0

    w = Work(state)
    result = w.check_requirements('watchman', working_hours=2)

    assert result is True
    # 2 часа × 200 шагов = 400, 2 × 4 энергии = 8
    assert state.steps.can_use == 1000 - 400
    assert state.energy == 50 - 8
    assert state.work.active is True
    assert state.work.work_type == 'watchman'
    assert state.work.hours == 2
    assert state.work.salary == 2
    assert state.work.end is not None


def test_check_requirements_insufficient_resources_no_session():
    state = GameState.default_new_game()
    state.gym.move_optimization_work = 0
    state.steps.can_use = 100  # Недостаточно для 1 часа watchman (200)
    state.energy = 50

    w = Work(state)
    result = w.check_requirements('watchman', working_hours=1)

    assert result is False
    assert state.work.active is False
    assert state.steps.can_use == 100  # Не списано


def test_check_requirements_zero_hours_returns_false():
    state = GameState.default_new_game()
    w = Work(state)
    assert w.check_requirements('watchman', working_hours=0) is False


def test_check_requirements_extends_existing_session():
    """Если уже работаем — добавляются часы к существующей сессии."""
    state = GameState.default_new_game()
    state.gym.move_optimization_work = 0
    state.steps.can_use = 5000
    state.energy = 50
    state.work.active = True
    state.work.work_type = 'watchman'
    state.work.hours = 3
    state.work.start = datetime.now()
    state.work.end = datetime.now() + timedelta(hours=1)
    state.work.salary = 2

    w = Work(state)
    w.check_requirements('watchman', working_hours=2)

    # Часы накапливаются: было 3, добавили 2 → 5.
    assert state.work.hours == 5


# ----- work_check_done -----

def test_work_check_done_timer_not_expired_no_op():
    state = GameState.default_new_game()
    state.work.active = True
    state.work.work_type = 'factory'
    state.work.salary = 5
    state.work.hours = 4
    state.work.end = datetime.now() + timedelta(hours=1)
    state.money = 100

    work_check_done(state)

    # Зарплата не выплачена, сессия активна.
    assert state.work.active is True
    assert state.money == 100


def test_work_check_done_timer_expired_pays_and_clears(monkeypatch, capsys):
    """По таймеру выплачивается зарплата, сессия очищается, save вызывается."""
    saves = []
    monkeypatch.setattr('work.save_characteristic', lambda: saves.append(True))

    state = GameState.default_new_game()
    state.work.active = True
    state.work.work_type = 'factory'
    state.work.salary = 5
    state.work.hours = 4
    state.work.start = datetime.now() - timedelta(hours=2)
    state.work.end = datetime.now() - timedelta(seconds=1)
    state.money = 100

    work_check_done(state)

    # 5 × 4 = 20 → +20 к money.
    assert state.money == 120
    assert state.work.active is False
    assert state.work.work_type is None
    assert state.work.hours == 0
    assert state.work.end is None
    assert state.work.start is None
    assert len(saves) == 1
    assert 'заработали' in capsys.readouterr().out.lower()


def test_work_check_done_no_session_no_op():
    state = GameState.default_new_game()
    state.work.end = None
    work_check_done(state)
    assert state.work.active is False
