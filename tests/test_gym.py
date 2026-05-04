"""Тесты gym.py после миграции на GameState (Phase 4 задачи 1.1, commit 3)."""

from datetime import datetime, timedelta

import pytest

from state import GameState
from gym import (
    _next_skill_level,
    _training_cost,
    _apply_speed_bonus,
    format_lvl_up_info,
    Skill_Training,
    skill_training_check_done,
)


# ----- _next_skill_level -----
# В 0.2.1g (4.48.4.1) удалён off-by-one helper `_energy_max_skill_level` —
# теперь все 8 навыков читаются единообразно через `getattr(state.gym, key) + 1`.

def test_next_skill_level_for_stamina():
    state = GameState.default_new_game()
    state.gym.stamina = 4
    assert _next_skill_level(state, 'stamina') == 5


def test_next_skill_level_for_energy_max_skill():
    """После унификации в 0.2.1g — energy_max_skill через тот же путь."""
    state = GameState.default_new_game()
    state.gym.energy_max_skill = 15
    assert _next_skill_level(state, 'energy_max_skill') == 16


# ----- _training_cost -----

def test_training_cost_lookup():
    state = GameState.default_new_game()
    state.gym.stamina = 0  # Уровень 0 → next = 1
    cost = _training_cost(state, 'stamina')
    assert cost == {'steps': 1000, 'energy': 5, 'money': 10, 'time': 5}


# ----- _apply_speed_bonus -----

def test_apply_speed_bonus_zero():
    state = GameState.default_new_game()
    assert _apply_speed_bonus(60, state) == 60


def test_apply_speed_bonus_with_skill():
    state = GameState.default_new_game()
    state.gym.speed_skill = 10
    # 60 - (60/100)*10 = 54
    assert _apply_speed_bonus(60, state) == 54.0


# ----- format_lvl_up_info -----

def test_format_lvl_up_info_contains_cost_marks():
    state = GameState.default_new_game()
    state.gym.stamina = 0
    out = format_lvl_up_info(state, 'stamina')
    assert '🏃' in out
    assert '🔋' in out
    assert '💰' in out
    assert '🕑' in out
    assert '1,000' in out  # 1000 шагов на 1 уровень stamina


# ----- Skill_Training.check_requirements -----

def test_check_requirements_pass(capsys):
    state = GameState.default_new_game()
    state.gym.stamina = 0
    state.steps.can_use = 10000
    state.energy = 50
    state.money = 100

    st = Skill_Training(state=state, name='stamina')
    assert st.check_requirements() is True
    assert 'успешна' in capsys.readouterr().out


def test_check_requirements_fail_insufficient_steps(monkeypatch, capsys):
    """Недостаточно шагов → False, gym_menu вызывается (мокаем input)."""
    monkeypatch.setattr('builtins.input', lambda *a, **k: '0')
    state = GameState.default_new_game()
    state.gym.stamina = 0
    state.steps.can_use = 100  # < 1000 нужных
    state.energy = 50
    state.money = 100

    st = Skill_Training(state=state, name='stamina')
    assert st.check_requirements() is False
    assert 'не достаточно ресурсов' in capsys.readouterr().out.lower()


# ----- Skill_Training.start_skill_training -----

def test_start_skill_training_spends_resources_and_sets_timer(capsys):
    state = GameState.default_new_game()
    state.gym.stamina = 0
    state.steps.can_use = 10000
    state.steps.used = 0
    state.steps.total_used = 0
    state.energy = 50
    state.money = 100

    st = Skill_Training(state=state, name='stamina')
    st.start_skill_training()

    # Уровень stamina ещё не повышен (это финализатор делает), но ресурсы списаны.
    cost = {'steps': 1000, 'energy': 5, 'money': 10}
    assert state.steps.can_use == 10000 - cost['steps']
    assert state.steps.used == cost['steps']
    assert state.steps.total_used == cost['steps']
    assert state.energy == 50 - cost['energy']
    assert state.money == 100 - cost['money']
    assert state.training.active is True
    assert state.training.skill_name == 'stamina'
    assert state.training.time_end is not None


# ----- skill_training_check_done -----

def test_skill_training_check_done_timer_not_expired_no_op():
    state = GameState.default_new_game()
    state.training.active = True
    state.training.skill_name = 'stamina'
    state.training.time_end = datetime.now() + timedelta(minutes=10)
    state.gym.stamina = 3

    skill_training_check_done(state)

    # Уровень не повышен, сессия не очищена.
    assert state.training.active is True
    assert state.gym.stamina == 3


def test_skill_training_check_done_timer_expired_levels_up(monkeypatch, capsys):
    """По таймеру повышается уровень, чистится сессия, save_characteristic вызывается."""
    saves = []
    monkeypatch.setattr('gym.save_characteristic', lambda: saves.append(True))

    state = GameState.default_new_game()
    state.training.active = True
    state.training.skill_name = 'stamina'
    state.training.time_end = datetime.now() - timedelta(seconds=1)
    state.gym.stamina = 3

    skill_training_check_done(state)

    assert state.gym.stamina == 4
    assert state.training.active is False
    assert state.training.skill_name is None
    assert state.training.time_end is None
    assert len(saves) == 1
    assert 'улучшен до 4' in capsys.readouterr().out
