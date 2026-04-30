"""Тесты adventure.py после миграции на GameState (Phase 4 задачи 1.1, commit 3)."""

from datetime import datetime

import pytest

from state import GameState
from adventure import Adventure
from adventure_data import adventure_data_table


# ----- Adventure.__init__ -----

def test_adventure_init_builds_seven_adventures():
    state = GameState.default_new_game()
    adv = Adventure(adventure_data_table, state=state)
    assert set(adv.adventures.keys()) == {'1', '2', '3', '4', '5', '6', '7'}
    assert adv.adventures['1']['name'] == 'walk_easy'
    assert adv.adventures['7']['name'] == 'walk_30k'


def test_adventure_init_does_not_mutate_static_table():
    """Phase 3-4 fix — раньше apply_move_optimization_adventure портил
    adventure_data_table при каждом создании Adventure."""
    state = GameState.default_new_game()
    state.gym.move_optimization_adventure = 50

    original_steps = adventure_data_table['walk_easy']['steps']
    Adventure(adventure_data_table, state=state)
    Adventure(adventure_data_table, state=state)
    Adventure(adventure_data_table, state=state)

    assert adventure_data_table['walk_easy']['steps'] == original_steps


def test_adventure_init_applies_move_optimization():
    state = GameState.default_new_game()
    state.gym.move_optimization_adventure = 50
    adv = Adventure(adventure_data_table, state=state)

    # walk_easy steps уменьшены на 50%.
    base = adventure_data_table['walk_easy']['steps']
    assert adv.adventures['1']['data']['steps'] == base // 2


# ----- Adventure.check_requirements -----

def test_check_requirements_pass_starts_adventure(capsys):
    state = GameState.default_new_game()
    state.steps.can_use = 100000
    state.energy = 100
    adv = Adventure(adventure_data_table, state=state)

    result = adv.check_requirements('walk_easy', adv_steps=1000, adv_energy=5, adv_time=10)

    assert result is True
    assert state.adventure.active is True
    assert state.adventure.name == 'walk_easy'
    assert state.adventure.end_ts is not None
    assert state.steps.can_use == 100000 - 1000
    assert state.energy == 95


def test_check_requirements_fail_insufficient_steps(capsys):
    state = GameState.default_new_game()
    state.steps.can_use = 100
    state.energy = 100
    adv = Adventure(adventure_data_table, state=state)

    result = adv.check_requirements('walk_easy', adv_steps=1000, adv_energy=5, adv_time=10)

    assert result is False
    assert state.adventure.active is False
    out = capsys.readouterr().out
    assert 'Не достаточно: 🏃' in out


def test_check_requirements_fail_insufficient_energy(capsys):
    state = GameState.default_new_game()
    state.steps.can_use = 100000
    state.energy = 1
    adv = Adventure(adventure_data_table, state=state)

    result = adv.check_requirements('walk_easy', adv_steps=1000, adv_energy=5, adv_time=10)

    assert result is False
    assert 'энергии' in capsys.readouterr().out


# ----- Adventure.adventure_check_done -----

def test_adventure_check_done_not_expired_prints_remaining(capsys):
    state = GameState.default_new_game()
    state.adventure.active = True
    state.adventure.name = 'walk_easy'
    state.adventure.end_ts = datetime.now().timestamp() + 600
    adv = Adventure(adventure_data_table, state=state)

    adv.adventure_check_done()

    assert state.adventure.active is True
    out = capsys.readouterr().out
    assert 'находится в Приключении' in out


def test_adventure_check_done_expired_drops_and_clears(monkeypatch, capsys):
    """По таймеру: дроп, инкремент counter, очистка сессии."""
    drops = []
    monkeypatch.setattr('adventure.Drop_Item.item_collect',
                        lambda self, hard, state: drops.append(hard))

    state = GameState.default_new_game()
    state.adventure.active = True
    state.adventure.name = 'walk_easy'
    state.adventure.end_ts = datetime.now().timestamp() - 1
    state.adventure.counters['walk_easy'] = 0

    adv = Adventure(adventure_data_table, state=state)
    adv.adventure_check_done()

    assert drops == ['walk_easy']
    assert state.adventure.counters['walk_easy'] == 1
    assert state.adventure.active is False
    assert state.adventure.name is None
    assert state.adventure.end_ts is None


def test_adventure_check_done_inactive_no_op():
    state = GameState.default_new_game()
    state.adventure.active = False
    adv = Adventure(adventure_data_table, state=state)
    adv.adventure_check_done()  # Should not crash.


def test_adventure_check_done_legacy_self_none_call(monkeypatch):
    """Legacy: Adventure.adventure_check_done(self=None, state=state) — должен работать."""
    state = GameState.default_new_game()
    state.adventure.active = False
    Adventure.adventure_check_done(self=None, state=state)


# ----- Adventure.get_adventure_requirement -----

def test_get_adventure_requirement_returns_string():
    state = GameState.default_new_game()
    adv = Adventure(adventure_data_table, state=state)
    req = adv.get_adventure_requirement('walk_easy')
    assert '🏃' in req
    assert '🔋' in req
    assert '🕑' in req
