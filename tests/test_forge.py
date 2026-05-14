"""Тесты forge.py — Кузница (4.59).

4.59.0 (0.2.5X) — skeleton-меню с 5 пунктами. Базовые UI-smoke тесты:
- меню рендерится без ошибок,
- '0' закрывает меню,
- невалидный ввод обрабатывается (continue цикла),
- stub-handler'ы 1-5 не падают.
"""

from state import GameState
from forge import forge_menu


def test_forge_menu_exit_by_zero(monkeypatch, capsys):
    """'0' выходит из меню сразу. Шапка отрисовалась."""
    state = GameState.default_new_game()
    monkeypatch.setattr('builtins.input', lambda *a, **k: '0')

    forge_menu(state)

    out = capsys.readouterr().out
    assert '🔨 Кузница' in out
    assert 'Отремонтировать предмет' in out
    assert 'Улучшить Grade предмета' in out
    assert 'Сделать дырку' in out
    assert 'Вставить камень' in out
    assert 'Объединить камни' in out


def test_forge_menu_shows_resources_in_header(monkeypatch, capsys):
    """Шапка показывает Steps / Energy / Money игрока."""
    state = GameState.default_new_game()
    state.money = 1234.56
    state.steps.can_use = 5000
    state.energy = 42
    monkeypatch.setattr('builtins.input', lambda *a, **k: '0')

    forge_menu(state)

    out = capsys.readouterr().out
    assert '5000' in out  # steps
    assert '42' in out  # energy
    assert '1,234.56' in out  # money с format_money


def test_forge_menu_invalid_input_loops_back(monkeypatch, capsys):
    """Невалидный ввод → '\\nНеверный выбор' → continue → '0' выходит."""
    state = GameState.default_new_game()
    inputs = iter(['xyz', '99', '0'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    forge_menu(state)

    out = capsys.readouterr().out
    assert out.count('Неверный выбор') >= 2  # xyz и 99


def test_forge_menu_repair_stub(monkeypatch, capsys):
    """Пункт 1 — stub в 4.59.0, не падает."""
    state = GameState.default_new_game()
    inputs = iter(['1', '0'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    forge_menu(state)

    out = capsys.readouterr().out
    assert 'разработке (4.59.1)' in out


def test_forge_menu_craft_stub(monkeypatch, capsys):
    """Пункт 2 — stub в 4.59.0, не падает."""
    state = GameState.default_new_game()
    inputs = iter(['2', '0'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    forge_menu(state)

    out = capsys.readouterr().out
    assert 'разработке (4.59.2)' in out


def test_forge_menu_gem_stubs_deferred(monkeypatch, capsys):
    """Пункты 3, 4, 5 — отложенные gem-stub'ы (4.59.3 deferred)."""
    state = GameState.default_new_game()
    inputs = iter(['3', '4', '5', '0'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    forge_menu(state)

    out = capsys.readouterr().out
    # Все 3 stub'а ссылаются на 4.59.3
    assert out.count('4.59.3') == 3
    assert 'Сделать дырку' in out or 'дырку' in out
    assert 'Вставить камень' in out or 'камень' in out
    assert 'Объединить камни' in out or 'камни' in out
