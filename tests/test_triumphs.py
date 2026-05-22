"""Тесты triumphs engine (task 4.62.0.2).

Catalog (TRIUMPHS) пустой в foundation phase — тесты используют **monkeypatch'
ную** version с inline-определением fixtures для simulation.

Note: тесты в этом файле НЕ затронуты `_disable_triumphs_register_event_for_non_triumphs_tests`
fixture (skip по basename) — здесь register_event работает по-настоящему.
"""

import json

import pytest

import triumphs
from state import GameState
from triumphs import (
    _format_progress_bar,
    backfill_from_history,
    get_progress,
    register_event,
    total_score,
)


# --- Fixture: mock catalog для тестов ---

@pytest.fixture
def mock_catalog(monkeypatch):
    """Заменяет TRIUMPHS на тестовый catalog с 3 triumph'ами.

    - 'marathoner' — metric-based (state.steps.total_used)
    - 'adventurer' — event-based (count adventure_done)
    - 'worker' — event-based с accumulator (sum hours from work_done)
    """
    test_catalog = {
        'marathoner': {
            'name': 'Marathoner',
            'category': 'steps',
            'tiers': [10_000, 100_000, 1_000_000],
            'metric': lambda state: state.steps.total_used,
        },
        'adventurer': {
            'name': 'Adventurer',
            'category': 'adventures',
            'tiers': [10, 50, 100],
            'event_hooks': ['adventure_done'],
        },
        'worker': {
            'name': 'Hard Worker',
            'category': 'work',
            'tiers': [10, 100, 1000],
            'event_hooks': ['work_done'],
            'count_delta': lambda payload: payload.get('hours', 0),
        },
    }
    monkeypatch.setattr(triumphs, 'TRIUMPHS', test_catalog)
    return test_catalog


# --- register_event ---

def test_register_event_no_op_with_empty_catalog(monkeypatch):
    """Empty TRIUMPHS = {} → register_event no-op, no exception."""
    monkeypatch.setattr(triumphs, 'TRIUMPHS', {})
    state = GameState.default_new_game()
    result = register_event(state, 'work_done', hours=4)
    assert result == []
    assert state.triumphs == {}


def test_register_event_none_state():
    """None state → no-op (defensive)."""
    result = register_event(None, 'work_done', hours=4)
    assert result == []


def test_register_event_metric_based_auto_unlock(mock_catalog):
    """Metric-based: state.steps.total_used = 500k → Marathoner tier 2 unlock."""
    state = GameState.default_new_game()
    state.steps.total_used = 500_000

    unlocked = register_event(state, 'work_done', hours=1)  # любой event = recheck

    assert len(unlocked) == 2  # tier 1 (10k) + tier 2 (100k)
    unlocked_ids = {u['triumph_id'] for u in unlocked}
    assert 'marathoner' in unlocked_ids
    assert state.triumphs['marathoner']['tier'] == 2


def test_register_event_event_based_counter(mock_catalog):
    """Event-based: adventure_done увеличивает counter, unlock после порога."""
    state = GameState.default_new_game()

    # 9 событий — не unlock (порог 10).
    for _ in range(9):
        register_event(state, 'adventure_done')
    assert state.triumphs['adventurer']['count'] == 9
    assert state.triumphs['adventurer']['tier'] == 0

    # 10-е событие — unlock tier 1.
    unlocked = register_event(state, 'adventure_done')
    assert state.triumphs['adventurer']['count'] == 10
    assert state.triumphs['adventurer']['tier'] == 1
    assert any(u['triumph_id'] == 'adventurer' and u['tier_index'] == 1 for u in unlocked)


def test_register_event_count_delta_from_payload(mock_catalog):
    """work_done с hours=N — counter += hours, не +1."""
    state = GameState.default_new_game()

    register_event(state, 'work_done', hours=5)
    assert state.triumphs['worker']['count'] == 5

    register_event(state, 'work_done', hours=7)
    assert state.triumphs['worker']['count'] == 12

    # 100h — unlock tier 2.
    unlocked = register_event(state, 'work_done', hours=88)
    assert state.triumphs['worker']['count'] == 100
    assert state.triumphs['worker']['tier'] == 2
    assert any(u['triumph_id'] == 'worker' and u['tier_index'] == 2 for u in unlocked)


def test_register_event_idempotent_no_double_unlock(mock_catalog):
    """Повторный event при уже unlocked tier — не вызывает повторного unlock."""
    state = GameState.default_new_game()
    state.steps.total_used = 50_000

    # Первый раз — unlock tier 1.
    unlocked1 = register_event(state, 'work_done', hours=1)
    assert len(unlocked1) == 1
    assert state.triumphs['marathoner']['tier'] == 1

    # Второй раз — tier тот же, ничего нового.
    unlocked2 = register_event(state, 'work_done', hours=1)
    assert unlocked2 == []  # никакого Marathoner повторно
    assert state.triumphs['marathoner']['tier'] == 1


def test_register_event_multi_tier_unlock_at_once(mock_catalog):
    """Один event пересекает несколько tier'ов сразу (3 unlock'а)."""
    state = GameState.default_new_game()
    state.steps.total_used = 2_000_000  # сразу выше всех 3 tier'ов

    unlocked = register_event(state, 'work_done', hours=1)

    marathoner_unlocks = [u for u in unlocked if u['triumph_id'] == 'marathoner']
    assert len(marathoner_unlocks) == 3
    assert state.triumphs['marathoner']['tier'] == 3
    # Capstone (last tier) flag.
    assert any(u['is_capstone'] for u in marathoner_unlocks)


def test_register_event_unrelated_event_no_counter_increment(mock_catalog):
    """work_done event не должен инкрементировать adventurer counter."""
    state = GameState.default_new_game()

    register_event(state, 'work_done', hours=5)
    # adventurer counter не трогается (его hook — 'adventure_done', не 'work_done').
    # state.triumphs['adventurer'] может ещё не существовать.
    assert state.triumphs.get('adventurer', {}).get('count', 0) == 0


# --- get_progress ---

def test_get_progress_unknown_triumph_returns_none(mock_catalog):
    state = GameState.default_new_game()
    assert get_progress(state, 'unknown_triumph') is None


def test_get_progress_no_progress(mock_catalog):
    """Default state: tier 0, next_threshold = первый порог."""
    state = GameState.default_new_game()
    progress = get_progress(state, 'marathoner')
    assert progress['current_tier'] == 0
    assert progress['next_threshold'] == 10_000
    assert progress['current_value'] == 0
    assert progress['is_capstone'] is False
    assert progress['total_tiers'] == 3


def test_get_progress_partial_in_first_tier(mock_catalog):
    """5k / 10k = 50% progress в первом tier'е."""
    state = GameState.default_new_game()
    state.steps.total_used = 5_000

    progress = get_progress(state, 'marathoner')
    assert progress['current_tier'] == 0
    assert progress['current_value'] == 5_000
    assert progress['next_threshold'] == 10_000
    assert 49.0 < progress['progress_pct'] < 51.0


def test_get_progress_at_capstone(mock_catalog):
    """Все tiers unlocked → is_capstone=True, progress_pct=100."""
    state = GameState.default_new_game()
    state.steps.total_used = 5_000_000
    register_event(state, 'work_done', hours=1)  # тригрит unlocks

    progress = get_progress(state, 'marathoner')
    assert progress['current_tier'] == 3
    assert progress['is_capstone'] is True
    assert progress['progress_pct'] == 100.0
    assert progress['next_threshold'] is None


# --- total_score ---

def test_total_score_empty_state(mock_catalog):
    """Default state без unlocks → score = 0."""
    state = GameState.default_new_game()
    assert total_score(state) == 0


def test_total_score_with_unlocked_tiers(mock_catalog):
    """Marathoner tier 2 + Adventurer tier 1 = (2 + 1) * 10 = 30."""
    state = GameState.default_new_game()
    state.steps.total_used = 200_000

    for _ in range(10):
        register_event(state, 'adventure_done')

    # Sanity.
    assert state.triumphs['marathoner']['tier'] == 2
    assert state.triumphs['adventurer']['tier'] == 1
    # Score: 2 marathoner + 1 adventurer = 3 tier'а × 10 points = 30.
    assert total_score(state) == 30


# --- _format_progress_bar ---

def test_format_progress_bar_zero():
    """0 / N → all empty."""
    bar = _format_progress_bar(0, 100, width=10)
    assert bar == '▱' * 10


def test_format_progress_bar_full():
    """N / N → all filled."""
    bar = _format_progress_bar(100, 100, width=10)
    assert bar == '▰' * 10


def test_format_progress_bar_half():
    """50 / 100 → 5 filled + 5 empty."""
    bar = _format_progress_bar(50, 100, width=10)
    assert bar == '▰▰▰▰▰▱▱▱▱▱'


def test_format_progress_bar_over_target():
    """Current > target → clamp до full."""
    bar = _format_progress_bar(200, 100, width=10)
    assert bar == '▰' * 10


def test_format_progress_bar_negative_current():
    """Current < 0 → clamp до empty."""
    bar = _format_progress_bar(-5, 100, width=10)
    assert bar == '▱' * 10


def test_format_progress_bar_zero_target():
    """Target = 0 → all empty (defensive)."""
    bar = _format_progress_bar(50, 0, width=10)
    assert bar == '▱' * 10


def test_format_progress_bar_multi_tier_with_separators():
    """Multi-tier: separators между tier-segments."""
    bar = _format_progress_bar(30, 500, tier_thresholds=[10, 50, 100, 500], width=12)
    # Должен содержать `│` separators (3 штуки между 4 tier'ами).
    assert bar.count('│') == 3
    # Tier 1 (10) полностью filled, tier 2 (50) частично.
    assert bar.startswith('▰')


def test_format_progress_bar_multi_tier_single_tier_falls_back():
    """Single tier в списке = single-tier mode без separators."""
    bar = _format_progress_bar(50, 100, tier_thresholds=[100], width=10)
    assert '│' not in bar
    assert bar == '▰▰▰▰▰▱▱▱▱▱'


def test_format_progress_bar_custom_width():
    bar = _format_progress_bar(50, 100, width=20)
    assert len(bar) == 20
    assert bar == '▰' * 10 + '▱' * 10


# --- backfill_from_history ---

def test_backfill_missing_file_returns_empty(mock_catalog, tmp_path, monkeypatch):
    """Файла нет → пустой dict, state не мутируется."""
    state = GameState.default_new_game()
    monkeypatch.chdir(tmp_path)
    result = backfill_from_history(state, history_jsonl_path='nonexistent.jsonl')
    assert result == {}


def test_backfill_accumulates_event_counters(mock_catalog, tmp_path):
    """history.jsonl с adventure_done × 5 → adventurer counter = 5."""
    history = tmp_path / 'history.jsonl'
    events = [
        {'type': 'adventure_done', 'payload': {'name': 'walk_easy'}},
        {'type': 'adventure_done', 'payload': {'name': 'walk_normal'}},
        {'type': 'adventure_done', 'payload': {'name': 'walk_hard'}},
        {'type': 'work_done', 'payload': {'hours': 3, 'vacancy': 'watchman'}},
        {'type': 'adventure_done', 'payload': {'name': 'walk_easy'}},
        {'type': 'adventure_done', 'payload': {'name': 'walk_15k'}},
        {'type': 'work_done', 'payload': {'hours': 8, 'vacancy': 'factory'}},
    ]
    history.write_text('\n'.join(json.dumps(e) for e in events), encoding='utf-8')

    state = GameState.default_new_game()
    feedback = backfill_from_history(state, history_jsonl_path=str(history))

    assert state.triumphs['adventurer']['count'] == 5
    assert state.triumphs['worker']['count'] == 11  # 3 + 8
    assert feedback['adventurer'] == 5
    assert feedback['worker'] == 11


def test_backfill_idempotent(mock_catalog, tmp_path):
    """Повторный backfill с тем же history не дублирует counters."""
    history = tmp_path / 'history.jsonl'
    events = [{'type': 'adventure_done', 'payload': {}}] * 7
    history.write_text('\n'.join(json.dumps(e) for e in events), encoding='utf-8')

    state = GameState.default_new_game()

    backfill_from_history(state, history_jsonl_path=str(history))
    assert state.triumphs['adventurer']['count'] == 7

    # Повторный — counter тот же.
    backfill_from_history(state, history_jsonl_path=str(history))
    assert state.triumphs['adventurer']['count'] == 7


def test_backfill_triggers_tier_unlocks(mock_catalog, tmp_path):
    """Backfill даёт 12 adventures → tier 1 (10) unlock."""
    history = tmp_path / 'history.jsonl'
    events = [{'type': 'adventure_done', 'payload': {}}] * 12
    history.write_text('\n'.join(json.dumps(e) for e in events), encoding='utf-8')

    state = GameState.default_new_game()
    backfill_from_history(state, history_jsonl_path=str(history))

    assert state.triumphs['adventurer']['tier'] == 1


def test_backfill_skips_corrupt_lines(mock_catalog, tmp_path):
    """Битые JSON-line'ы пропускаются (не падаем)."""
    history = tmp_path / 'history.jsonl'
    history.write_text(
        '\n'.join([
            json.dumps({'type': 'adventure_done', 'payload': {}}),
            'this is not json',
            '',
            json.dumps({'type': 'adventure_done', 'payload': {}}),
        ]),
        encoding='utf-8',
    )

    state = GameState.default_new_game()
    backfill_from_history(state, history_jsonl_path=str(history))
    assert state.triumphs['adventurer']['count'] == 2  # 2 valid events
