"""Тесты locations.py после миграции на GameState (Phase 4 задачи 1.1, commit 4)."""

from state import GameState
from locations import (
    icon_loc,
    home_location,
    garage_location,
    auto_dialer_location,
    bank_location,
    forge_location,
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

    state.loc = 'forge'
    assert icon_loc(state) == '🔨'


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


def test_bank_location_opens_menu(monkeypatch, capsys):
    """С 0.2.2 / 4.49.0.1 bank_location вызывает интерактивное меню банка.
    Передаём '0' (Назад) — меню должно отрисоваться и сразу вернуться."""
    state = GameState.default_new_game()
    monkeypatch.setattr('builtins.input', lambda *args, **kwargs: '0')
    bank_location(state)
    out = capsys.readouterr().out
    assert 'Bank Location' in out
    assert 'Депозит' in out


def test_forge_location_opens_menu(monkeypatch, capsys):
    """4.59.0 — forge_location вызывает интерактивное меню Кузницы.
    Передаём '0' (Назад) — меню должно отрисоваться и сразу вернуться.
    4.60 — нужен прокачанный forge-навык (иначе локация заблокирована)."""
    state = GameState.default_new_game()
    state.gym.forge_repair_quality = 1  # разблокирует Кузницу
    monkeypatch.setattr('builtins.input', lambda *args, **kwargs: '0')
    forge_location(state)
    out = capsys.readouterr().out
    assert '🔨 Кузница' in out
    assert 'Отремонтировать предмет' in out
    assert 'Улучшить Grade предмета' in out


def test_forge_location_locked_without_skill(monkeypatch, capsys):
    """4.60 — без прокачанного forge-навыка Кузница заблокирована:
    печатает сообщение о блокировке и НЕ открывает меню (input не вызывается)."""
    state = GameState.default_new_game()
    assert state.gym.forge_steps_saving == 0
    assert state.gym.forge_money_saving == 0
    assert state.gym.forge_repair_quality == 0

    def _fail_input(*args, **kwargs):
        raise AssertionError('меню не должно запрашивать ввод при блокировке')

    monkeypatch.setattr('builtins.input', _fail_input)
    forge_location(state)
    out = capsys.readouterr().out
    assert '🔒' in out
    assert 'заблокирована' in out
    assert 'Отремонтировать предмет' not in out


def test_forge_location_unlocks_with_any_forge_skill(monkeypatch, capsys):
    """4.60 — достаточно одного из трёх forge-навыков ≥1 для разблокировки."""
    for skill in ('forge_steps_saving', 'forge_money_saving', 'forge_repair_quality'):
        state = GameState.default_new_game()
        setattr(state.gym, skill, 1)
        monkeypatch.setattr('builtins.input', lambda *args, **kwargs: '0')
        forge_location(state)
        out = capsys.readouterr().out
        assert '🔨 Кузница' in out, f'{skill} должен разблокировать Кузницу'
