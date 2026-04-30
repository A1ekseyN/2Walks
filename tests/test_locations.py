"""Тесты locations.py после миграции на GameState (Phase 4 задачи 1.1, commit 4)."""

from state import GameState
from locations import (
    icon_loc,
    home_location,
    garage_location,
    auto_dialer_location,
    bank_location,
)


def test_icon_loc_known_locations():
    state = GameState.default_new_game()
    state.loc = 'home'
    assert icon_loc(state) == '🏠'

    state.loc = 'gym'
    assert icon_loc(state) == '🏋️'

    state.loc = 'shop'
    assert icon_loc(state) == '🛒'

    state.loc = 'work'
    assert icon_loc(state) == '🏭'

    state.loc = 'adventure'
    assert icon_loc(state) == '🗺️'

    state.loc = 'garage'
    assert icon_loc(state) == '🚗'

    state.loc = 'bank'
    assert icon_loc(state) == '🏛'


def test_icon_loc_auto_dialer_returns_none():
    state = GameState.default_new_game()
    state.loc = 'auto_dialer'
    assert icon_loc(state) is None


def test_icon_loc_unknown_location_returns_none():
    state = GameState.default_new_game()
    state.loc = 'mystery_zone'
    assert icon_loc(state) is None


# ----- *_location placeholder UI smoke -----

def test_home_location_prints_header(capsys):
    state = GameState.default_new_game()
    home_location(state)
    assert 'Home Location' in capsys.readouterr().out


def test_garage_location_prints_header(capsys):
    state = GameState.default_new_game()
    garage_location(state)
    assert 'Garage Location' in capsys.readouterr().out


def test_auto_dialer_location_prints_header(capsys):
    state = GameState.default_new_game()
    auto_dialer_location(state)
    assert 'Auto Dialer Location' in capsys.readouterr().out


def test_bank_location_prints_header(capsys):
    state = GameState.default_new_game()
    bank_location(state)
    assert 'Bank Location' in capsys.readouterr().out
