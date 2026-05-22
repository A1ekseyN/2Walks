"""Тесты triumphs_menu CLI (task 4.62.0.3)."""

import json

import pytest

import triumphs
from state import GameState
from triumphs_menu import (
    _check_first_launch_backfill_prompt,
    _render_triumph_line,
    open_triumphs_menu,
    render_pinned_status_bar,
)


# --- Helpers ---

def _mock_history_file(tmp_path, monkeypatch, events=None):
    """Создаёт history.jsonl в tmp_path + monkeypatch'ит HISTORY_FILE constant."""
    history_path = tmp_path / 'history.jsonl'
    if events:
        history_path.write_text('\n'.join(json.dumps(e) for e in events), encoding='utf-8')
    else:
        history_path.touch()
    # HISTORY_FILE используется в triumphs_menu через `from config import HISTORY_FILE`.
    # Monkeypatch'им const в самом triumphs_menu (не в config) — реально привязан там.
    import triumphs_menu
    monkeypatch.setattr(triumphs_menu, 'HISTORY_FILE', str(history_path))
    return history_path


# --- _check_first_launch_backfill_prompt ---

def test_prompt_skipped_when_dismissed_flag_true(tmp_path, monkeypatch, capsys):
    """state.triumphs_backfill_dismissed=True → no prompt."""
    state = GameState.default_new_game()
    state.triumphs_backfill_dismissed = True
    _mock_history_file(tmp_path, monkeypatch, events=[
        {'type': 'adventure_done', 'payload': {}}
    ])

    result = _check_first_launch_backfill_prompt(state)
    assert result is False
    out = capsys.readouterr().out
    assert 'Найдена существующая история' not in out


def test_prompt_skipped_when_history_file_missing(tmp_path, monkeypatch, capsys):
    """Нет history.jsonl → no prompt."""
    state = GameState.default_new_game()
    import triumphs_menu
    monkeypatch.setattr(triumphs_menu, 'HISTORY_FILE', str(tmp_path / 'nonexistent.jsonl'))

    result = _check_first_launch_backfill_prompt(state)
    assert result is False


def test_prompt_skipped_when_history_file_empty(tmp_path, monkeypatch, capsys):
    """Пустой history.jsonl → no prompt."""
    state = GameState.default_new_game()
    _mock_history_file(tmp_path, monkeypatch)  # empty file

    result = _check_first_launch_backfill_prompt(state)
    assert result is False


def test_prompt_shows_when_history_exists_and_not_dismissed(tmp_path, monkeypatch, capsys):
    """history.jsonl с events + dismissed=False → prompt появляется."""
    state = GameState.default_new_game()
    _mock_history_file(tmp_path, monkeypatch, events=[
        {'type': 'adventure_done', 'payload': {}},
        {'type': 'work_done', 'payload': {'hours': 4}},
    ])
    monkeypatch.setattr('builtins.input', lambda *a, **k: 'n')  # «Позже»

    result = _check_first_launch_backfill_prompt(state)
    assert result is True
    out = capsys.readouterr().out
    assert 'Найдена существующая история' in out
    assert '(2 events)' in out
    # dismissed flag НЕ установлен (player выбрал «n»).
    assert state.triumphs_backfill_dismissed is False


def test_prompt_skip_sets_dismissed_flag(tmp_path, monkeypatch, capsys):
    """Choice «s» → state.triumphs_backfill_dismissed = True."""
    state = GameState.default_new_game()
    _mock_history_file(tmp_path, monkeypatch, events=[{'type': 'adventure_done', 'payload': {}}])
    monkeypatch.setattr('builtins.input', lambda *a, **k: 's')
    # Mock save_characteristic чтобы не пытался писать в Sheets.
    import persistence
    monkeypatch.setattr(persistence, 'save_characteristic', lambda: "OK")

    _check_first_launch_backfill_prompt(state)
    assert state.triumphs_backfill_dismissed is True


def test_prompt_yes_triggers_backfill(tmp_path, monkeypatch, capsys):
    """Choice «y» → backfill вызывается. catalog mock с adventurer event-based."""
    state = GameState.default_new_game()
    _mock_history_file(tmp_path, monkeypatch, events=[
        {'type': 'adventure_done', 'payload': {}},
        {'type': 'adventure_done', 'payload': {}},
        {'type': 'adventure_done', 'payload': {}},
    ])
    monkeypatch.setattr('builtins.input', lambda *a, **k: 'y')
    # Mock save_characteristic.
    import persistence
    monkeypatch.setattr(persistence, 'save_characteristic', lambda: "OK")
    # Mock catalog с adventurer.
    monkeypatch.setattr(triumphs, 'TRIUMPHS', {
        'adventurer': {
            'name': 'Adventurer', 'category': 'adventures',
            'tiers': [10, 50], 'event_hooks': ['adventure_done'],
        },
    })
    # И в triumphs_menu (тот же ref).
    import triumphs_menu
    monkeypatch.setattr(triumphs_menu, 'TRIUMPHS', {
        'adventurer': {
            'name': 'Adventurer', 'category': 'adventures',
            'tiers': [10, 50], 'event_hooks': ['adventure_done'],
        },
    })

    _check_first_launch_backfill_prompt(state)
    assert state.triumphs['adventurer']['count'] == 3
    out = capsys.readouterr().out
    assert '✅ Backfill завершён' in out
    assert 'Adventurer: +3' in out


# --- open_triumphs_menu — empty catalog flow ---

def test_open_menu_empty_catalog_shows_empty_message(monkeypatch, capsys):
    """Пустой TRIUMPHS → empty message + commands. «0» закрывает."""
    state = GameState.default_new_game()
    state.triumphs_backfill_dismissed = True  # skip prompt
    monkeypatch.setattr('builtins.input', lambda *a, **k: '0')
    monkeypatch.setattr(triumphs, 'TRIUMPHS', {})
    import triumphs_menu
    monkeypatch.setattr(triumphs_menu, 'TRIUMPHS', {})

    open_triumphs_menu(state)
    out = capsys.readouterr().out
    assert '🏆' in out  # header
    # 'Score:' и '0' разделены ANSI escape — проверяем components отдельно.
    assert 'Score:' in out
    assert 'Каталог триумфов пуст' in out


def test_open_menu_unknown_command_shows_error(monkeypatch, capsys):
    """Unknown command → error message, loop продолжается."""
    state = GameState.default_new_game()
    state.triumphs_backfill_dismissed = True
    inputs = iter(['x', '0'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))
    monkeypatch.setattr(triumphs, 'TRIUMPHS', {})
    import triumphs_menu
    monkeypatch.setattr(triumphs_menu, 'TRIUMPHS', {})

    open_triumphs_menu(state)
    out = capsys.readouterr().out
    assert 'Неизвестная команда' in out


def test_open_menu_with_catalog_shows_categories(monkeypatch, capsys):
    """Catalog с 1 triumph → отображается в category секции."""
    state = GameState.default_new_game()
    state.triumphs_backfill_dismissed = True
    state.steps.total_used = 50_000
    monkeypatch.setattr('builtins.input', lambda *a, **k: '0')
    catalog = {
        'marathoner': {
            'name': 'Marathoner', 'category': 'steps',
            'tiers': [10_000, 100_000, 1_000_000],
            'metric': lambda s: s.steps.total_used,
        },
    }
    monkeypatch.setattr(triumphs, 'TRIUMPHS', catalog)
    import triumphs_menu
    monkeypatch.setattr(triumphs_menu, 'TRIUMPHS', catalog)

    open_triumphs_menu(state)
    out = capsys.readouterr().out
    assert '🏃 Шаги' in out
    assert 'Marathoner' in out


# --- _render_triumph_line ---

def test_render_triumph_line_in_progress(monkeypatch):
    state = GameState.default_new_game()
    state.steps.total_used = 5_000
    catalog = {
        'marathoner': {
            'name': 'Marathoner', 'category': 'steps',
            'tiers': [10_000, 100_000, 1_000_000],
            'metric': lambda s: s.steps.total_used,
        },
    }
    monkeypatch.setattr(triumphs, 'TRIUMPHS', catalog)

    line = _render_triumph_line(state, 'marathoner')
    assert 'Marathoner' in line
    assert 'Tier 0/3' in line
    assert '5,000' in line
    assert '▰' in line or '▱' in line  # progress bar present


def test_render_triumph_line_capstone(monkeypatch):
    state = GameState.default_new_game()
    state.steps.total_used = 5_000_000
    state.triumphs['marathoner'] = {'tier': 3, 'unlocked_at': {}, 'count': 0}
    catalog = {
        'marathoner': {
            'name': 'Marathoner', 'category': 'steps',
            'tiers': [10_000, 100_000, 1_000_000],
            'metric': lambda s: s.steps.total_used,
        },
    }
    monkeypatch.setattr(triumphs, 'TRIUMPHS', catalog)

    line = _render_triumph_line(state, 'marathoner')
    assert 'Capstone' in line


# --- render_pinned_status_bar ---

def test_pinned_status_bar_empty_when_no_pinned():
    state = GameState.default_new_game()
    assert render_pinned_status_bar(state) == ''


def test_pinned_status_bar_empty_when_catalog_empty(monkeypatch):
    state = GameState.default_new_game()
    state.pinned_triumphs = ['marathoner']
    monkeypatch.setattr(triumphs, 'TRIUMPHS', {})
    import triumphs_menu
    monkeypatch.setattr(triumphs_menu, 'TRIUMPHS', {})
    assert render_pinned_status_bar(state) == ''


def test_pinned_status_bar_renders_pinned(monkeypatch):
    state = GameState.default_new_game()
    state.steps.total_used = 50_000
    state.pinned_triumphs = ['marathoner']
    catalog = {
        'marathoner': {
            'name': 'Marathoner', 'category': 'steps',
            'tiers': [10_000, 100_000, 1_000_000],
            'metric': lambda s: s.steps.total_used,
        },
    }
    monkeypatch.setattr(triumphs, 'TRIUMPHS', catalog)
    import triumphs_menu
    monkeypatch.setattr(triumphs_menu, 'TRIUMPHS', catalog)

    output = render_pinned_status_bar(state)
    assert '🏆 Pinned' in output
    assert 'Marathoner' in output


def test_pinned_status_bar_caps_at_3(monkeypatch):
    """Если pinned > 3 — показываем только первые 3."""
    state = GameState.default_new_game()
    state.steps.total_used = 50_000
    state.pinned_triumphs = ['a', 'b', 'c', 'd', 'e']  # 5 IDs
    catalog = {
        x: {'name': x, 'category': 'steps', 'tiers': [10],
            'metric': lambda s: 5}
        for x in ['a', 'b', 'c', 'd', 'e']
    }
    monkeypatch.setattr(triumphs, 'TRIUMPHS', catalog)
    import triumphs_menu
    monkeypatch.setattr(triumphs_menu, 'TRIUMPHS', catalog)

    output = render_pinned_status_bar(state)
    # Считаем lines с triumph rows — должно быть 3 (плюс 1 заголовок «Pinned:»).
    # Используем количество '▰' / '▱' секций как proxy для количества triumph lines.
    progress_lines = sum(1 for line in output.split('\n') if '▰' in line or '▱' in line)
    assert progress_lines == 3
