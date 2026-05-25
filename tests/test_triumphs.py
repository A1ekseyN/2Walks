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
    init_metric_check,
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
    """Multi-tier: separators между tier-segments (equal-sized 22.05.2026 fix)."""
    bar = _format_progress_bar(30, 500, tier_thresholds=[10, 50, 100, 500], width=12)
    # Должен содержать `│` separators (3 штуки между 4 tier'ами).
    assert bar.count('│') == 3
    # Tier 1 (10) полностью filled (30 >= 10), tier 2 (50) частично.
    assert bar.startswith('▰')


def test_format_progress_bar_multi_tier_equal_sized():
    """22.05.2026 — equal-sized segments: каждый tier = равное число cells.

    Для Marathoner-like: 5 tiers, width=15 → 3 cells per tier.
    """
    # Все tiers unlocked (current >= max).
    bar = _format_progress_bar(10_000_000, 10_000_000,
                                tier_thresholds=[100_000, 500_000, 1_000_000, 5_000_000, 10_000_000],
                                width=15)
    # 5 tiers × 3 cells = 15 cells + 4 separators = 19 chars.
    assert len(bar) == 19
    assert bar.count('│') == 4
    # Все cells filled.
    assert bar.count('▰') == 15
    assert bar.count('▱') == 0


def test_format_progress_bar_multi_tier_partial_in_one():
    """5 tiers, 3 done, partial in 4th."""
    # User scenario: 1.79M в Marathoner [100k, 500k, 1M, 5M, 10M].
    bar = _format_progress_bar(1_791_812, 10_000_000,
                                tier_thresholds=[100_000, 500_000, 1_000_000, 5_000_000, 10_000_000],
                                width=15)
    # 5 segments separated by 4 │.
    segments = bar.split('│')
    assert len(segments) == 5
    # Tier 1, 2, 3: fully filled (3 cells each).
    assert segments[0] == '▰▰▰'
    assert segments[1] == '▰▰▰'
    assert segments[2] == '▰▰▰'
    # Tier 4 (5M): partial — (1.79M - 1M) / (5M - 1M) = 0.197 → round(0.197 * 3) = 1 cell filled.
    assert segments[3] == '▰▱▱'
    # Tier 5: empty.
    assert segments[4] == '▱▱▱'


def test_format_progress_bar_uneven_distribution():
    """4 tiers width=10 → 3+3+2+2 (remainder=2 → first 2 tiers get +1)."""
    bar = _format_progress_bar(0, 100, tier_thresholds=[25, 50, 75, 100], width=10)
    segments = bar.split('│')
    assert len(segments) == 4
    assert len(segments[0]) == 3  # base 2 + remainder 1
    assert len(segments[1]) == 3
    assert len(segments[2]) == 2
    assert len(segments[3]) == 2


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


# --- init_metric_check (22.05.2026 UX fix) ---

def test_init_metric_check_unlocks_metric_based(mock_catalog):
    """init_metric_check unlock'ает metric-based triumphs без log_event."""
    state = GameState.default_new_game()
    state.steps.total_used = 500_000

    unlocked = init_metric_check(state)

    marathoner_unlocks = [u for u in unlocked if u['triumph_id'] == 'marathoner']
    assert len(marathoner_unlocks) == 2  # tier 1 (10k) + tier 2 (100k) из mock_catalog
    assert state.triumphs['marathoner']['tier'] == 2


def test_init_metric_check_skips_event_based(mock_catalog):
    """init_metric_check НЕ трогает event-based counters."""
    state = GameState.default_new_game()
    # adventurer / worker — event-based, не должны быть affected.
    init_metric_check(state)
    assert state.triumphs.get('adventurer', {}).get('count', 0) == 0
    assert state.triumphs.get('worker', {}).get('count', 0) == 0


def test_init_metric_check_idempotent(mock_catalog):
    """Повторный вызов с тем же state не unlock'ает уже-unlocked."""
    state = GameState.default_new_game()
    state.steps.total_used = 500_000

    first = init_metric_check(state)
    assert len(first) == 2

    second = init_metric_check(state)
    assert second == []  # ничего нового


def test_init_metric_check_none_state():
    """Defensive: None state → no-op."""
    assert init_metric_check(None) == []


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


# ============================================================================
# 4.62.4 — Unclaimed unlocks (claim mechanic)
# ============================================================================

from triumphs import (
    append_unclaimed,
    backfill_unclaimed_from_existing,
    claim_all,
    claim_triumph,
    get_unclaimed_for,
)


class TestUnclaimedQueue:
    """Tests for 4.62.4 claim queue."""

    def test_append_adds_entry(self):
        state = GameState.default_new_game()
        append_unclaimed(state, [{'triumph_id': 'foo', 'tier_index': 1}])
        assert len(state.unclaimed_unlocks) == 1
        assert state.unclaimed_unlocks[0]['triumph_id'] == 'foo'
        assert state.unclaimed_unlocks[0]['tier'] == 1
        assert 'unlocked_ts' in state.unclaimed_unlocks[0]

    def test_append_dedupes(self):
        """Same triumph_id+tier второй раз = no-op."""
        state = GameState.default_new_game()
        append_unclaimed(state, [{'triumph_id': 'foo', 'tier_index': 1}])
        append_unclaimed(state, [{'triumph_id': 'foo', 'tier_index': 1}])
        assert len(state.unclaimed_unlocks) == 1

    def test_append_keeps_different_tiers(self):
        state = GameState.default_new_game()
        append_unclaimed(state, [
            {'triumph_id': 'foo', 'tier_index': 1},
            {'triumph_id': 'foo', 'tier_index': 2},
        ])
        assert len(state.unclaimed_unlocks) == 2

    def test_append_empty_noop(self):
        state = GameState.default_new_game()
        append_unclaimed(state, [])
        assert state.unclaimed_unlocks == []

    def test_get_unclaimed_for_filters(self):
        state = GameState.default_new_game()
        append_unclaimed(state, [
            {'triumph_id': 'foo', 'tier_index': 1},
            {'triumph_id': 'bar', 'tier_index': 1},
            {'triumph_id': 'foo', 'tier_index': 2},
        ])
        assert len(get_unclaimed_for(state, 'foo')) == 2
        assert len(get_unclaimed_for(state, 'bar')) == 1
        assert get_unclaimed_for(state, 'baz') == []

    def test_claim_triumph_removes_entries(self):
        state = GameState.default_new_game()
        append_unclaimed(state, [
            {'triumph_id': 'foo', 'tier_index': 1},
            {'triumph_id': 'foo', 'tier_index': 2},
            {'triumph_id': 'bar', 'tier_index': 1},
        ])
        count = claim_triumph(state, 'foo')
        assert count == 2
        assert len(state.unclaimed_unlocks) == 1
        assert state.unclaimed_unlocks[0]['triumph_id'] == 'bar'

    def test_claim_triumph_unknown_returns_zero(self):
        state = GameState.default_new_game()
        append_unclaimed(state, [{'triumph_id': 'foo', 'tier_index': 1}])
        count = claim_triumph(state, 'unknown')
        assert count == 0
        assert len(state.unclaimed_unlocks) == 1

    def test_claim_all_clears_queue(self):
        state = GameState.default_new_game()
        append_unclaimed(state, [
            {'triumph_id': 'foo', 'tier_index': 1},
            {'triumph_id': 'bar', 'tier_index': 1},
        ])
        count = claim_all(state)
        assert count == 2
        assert state.unclaimed_unlocks == []

    def test_claim_all_empty_queue_zero(self):
        state = GameState.default_new_game()
        assert claim_all(state) == 0

    def test_register_event_populates_unclaimed_via_helper(self, mock_catalog):
        """register_event возвращает unlocks; auto-hook в history.log_event
        push'ит их в unclaimed. Здесь тестируем что unlocks приходят правильной
        формы для append_unclaimed."""
        state = GameState.default_new_game()
        state.steps.total_used = 100_000
        unlocks = register_event(state, 'work_done', hours=1)
        # Marathoner должен unlock tier 1+2 (10k, 100k).
        marathoner_unlocks = [u for u in unlocks if u['triumph_id'] == 'marathoner']
        assert len(marathoner_unlocks) == 2
        # Симулируем auto-hook.
        append_unclaimed(state, unlocks)
        assert len(get_unclaimed_for(state, 'marathoner')) == 2


class TestBackfillUnclaimedFromExisting:
    """4.62.4 one-shot backfill для existing players."""

    def test_synth_creates_entries_for_unlocked_tiers(self, mock_catalog):
        """Existing player с unlocked tier'ами получает synth unclaimed
        entries для каждого tier'а."""
        state = GameState.default_new_game()
        # Симулируем что Marathoner tier 2 уже unlocked.
        state.triumphs['marathoner'] = {'tier': 2, 'unlocked_at': {}, 'count': 0}
        count = backfill_unclaimed_from_existing(state)
        # 2 unclaimed entries (tier 1 + tier 2).
        assert count == 2
        unclaimed = get_unclaimed_for(state, 'marathoner')
        assert len(unclaimed) == 2
        tiers = sorted(e['tier'] for e in unclaimed)
        assert tiers == [1, 2]

    def test_synth_skips_tier_zero(self, mock_catalog):
        """Triumph с tier=0 (not unlocked) → no synth entries."""
        state = GameState.default_new_game()
        state.triumphs['marathoner'] = {'tier': 0, 'unlocked_at': {}, 'count': 0}
        count = backfill_unclaimed_from_existing(state)
        assert count == 0
        assert state.unclaimed_unlocks == []

    def test_synth_idempotent(self, mock_catalog):
        """Повторный вызов с уже-backfilled queue не создаёт duplicates
        (dedupe в append_unclaimed)."""
        state = GameState.default_new_game()
        state.triumphs['marathoner'] = {'tier': 2, 'unlocked_at': {}, 'count': 0}
        backfill_unclaimed_from_existing(state)
        first_count = len(state.unclaimed_unlocks)
        backfill_unclaimed_from_existing(state)
        assert len(state.unclaimed_unlocks) == first_count


class TestUnclaimedRoundTrip:
    """4.62.4 round-trip через to_dict / from_dict."""

    def test_to_dict_includes_unclaimed(self):
        state = GameState.default_new_game()
        append_unclaimed(state, [
            {'triumph_id': 'foo', 'tier_index': 1},
            {'triumph_id': 'bar', 'tier_index': 2},
        ])
        d = state.to_dict()
        assert 'unclaimed_unlocks' in d
        assert len(d['unclaimed_unlocks']) == 2

    def test_from_dict_restores_unclaimed(self):
        d = GameState.default_new_game().to_dict()
        d['unclaimed_unlocks'] = [
            {'triumph_id': 'foo', 'tier': 1, 'unlocked_ts': 1.0},
        ]
        state = GameState.from_dict(d)
        assert len(state.unclaimed_unlocks) == 1
        assert state.unclaimed_unlocks[0]['triumph_id'] == 'foo'

    def test_legacy_save_no_unclaimed_field_defaults_empty(self):
        """Сейв до 4.62.4 (без unclaimed_unlocks key) → default []."""
        d = GameState.default_new_game().to_dict()
        del d['unclaimed_unlocks']
        state = GameState.from_dict(d)
        assert state.unclaimed_unlocks == []


# ============================================================================
# 4.62.3 — Seals & Titles
# ============================================================================

from triumphs import (
    available_seals,
    available_titles,
    check_seal_unlocks,
    is_seal_unlocked,
    set_title,
)


@pytest.fixture
def seal_catalog(monkeypatch):
    """Mock TRIUMPHS + SEALS для seal tests.

    Category 'steps' имеет 1 triumph (Marathoner) с capstone 100.
    Category 'work' имеет 2 triumph'а (Hard Worker, Watchman) — обоим нужен
    capstone для seal.
    """
    import triumphs_data
    test_triumphs = {
        'marathoner': {
            'name': 'Marathoner', 'category': 'steps',
            'tiers': [50, 100],
            'metric': lambda s: s.steps.total_used,
        },
        'hard_worker': {
            'name': 'Hard Worker', 'category': 'work',
            'tiers': [10, 100],
            'event_hooks': ['work_done'],
            'count_delta': lambda p: int(p.get('hours', 0) or 0),
        },
        'watchman': {
            'name': 'Watchman', 'category': 'work',
            'tiers': [10, 100],
            'event_hooks': ['work_done'],
            'event_filter': lambda p: p.get('vacancy') == 'watchman',
            'count_delta': lambda p: int(p.get('hours', 0) or 0),
        },
    }
    test_seals = {
        'steps': {'name': 'Marathoner', 'icon': '🏃'},
        'work': {'name': 'Workaholic', 'icon': '🏭'},
    }
    monkeypatch.setattr(triumphs, 'TRIUMPHS', test_triumphs)
    monkeypatch.setattr(triumphs_data, 'TRIUMPHS', test_triumphs)
    monkeypatch.setattr(triumphs_data, 'SEALS', test_seals)
    return test_triumphs, test_seals


class TestSealUnlock:
    """is_seal_unlocked / available_seals / available_titles."""

    def test_empty_category_returns_false(self, monkeypatch):
        monkeypatch.setattr(triumphs, 'TRIUMPHS', {})
        state = GameState.default_new_game()
        assert is_seal_unlocked(state, 'steps') is False

    def test_partial_capstones_returns_false(self, seal_catalog):
        """Один triumph на capstone, другой нет → seal locked."""
        state = GameState.default_new_game()
        # hard_worker capstone (tier 2), watchman только tier 1.
        state.triumphs['hard_worker'] = {'tier': 2, 'unlocked_at': {}, 'count': 0}
        state.triumphs['watchman'] = {'tier': 1, 'unlocked_at': {}, 'count': 0}
        assert is_seal_unlocked(state, 'work') is False

    def test_all_capstones_returns_true(self, seal_catalog):
        state = GameState.default_new_game()
        state.triumphs['hard_worker'] = {'tier': 2, 'unlocked_at': {}, 'count': 0}
        state.triumphs['watchman'] = {'tier': 2, 'unlocked_at': {}, 'count': 0}
        assert is_seal_unlocked(state, 'work') is True

    def test_single_triumph_category(self, seal_catalog):
        """Steps category — 1 triumph (Marathoner). Capstone = seal unlocked."""
        state = GameState.default_new_game()
        state.triumphs['marathoner'] = {'tier': 2, 'unlocked_at': {}, 'count': 0}
        assert is_seal_unlocked(state, 'steps') is True

    def test_available_seals_filters_locked(self, seal_catalog):
        state = GameState.default_new_game()
        state.triumphs['marathoner'] = {'tier': 2, 'unlocked_at': {}, 'count': 0}
        # work seal locked (watchman не capstone'нут).
        state.triumphs['hard_worker'] = {'tier': 2, 'unlocked_at': {}, 'count': 0}
        seals = available_seals(state)
        assert seals == ['steps']

    def test_available_titles_returns_names(self, seal_catalog):
        state = GameState.default_new_game()
        state.triumphs['marathoner'] = {'tier': 2, 'unlocked_at': {}, 'count': 0}
        titles = available_titles(state)
        assert titles == ['Marathoner']


class TestSealCheckUnlocks:
    """check_seal_unlocks возвращает только newly-unlocked seals (idempotent)."""

    def test_first_call_returns_new_seals(self, seal_catalog):
        state = GameState.default_new_game()
        state.triumphs['marathoner'] = {'tier': 2, 'unlocked_at': {}, 'count': 0}
        new = check_seal_unlocks(state)
        assert len(new) == 1
        assert new[0]['triumph_id'] == 'steps'
        assert new[0]['kind'] == 'seal'
        assert new[0]['name'] == 'Marathoner'
        assert new[0]['is_capstone'] is True

    def test_second_call_idempotent(self, seal_catalog):
        """Повторный call после первого = no new seals (acknowledged tracked)."""
        state = GameState.default_new_game()
        state.triumphs['marathoner'] = {'tier': 2, 'unlocked_at': {}, 'count': 0}
        check_seal_unlocks(state)
        # Repeated call.
        new = check_seal_unlocks(state)
        assert new == []

    def test_locked_seals_not_returned(self, seal_catalog):
        state = GameState.default_new_game()
        # No capstones → no seals.
        new = check_seal_unlocks(state)
        assert new == []


class TestSetTitle:
    """set_title / state.title manipulation."""

    def test_set_title_string(self):
        state = GameState.default_new_game()
        set_title(state, 'Marathoner')
        assert state.title == 'Marathoner'

    def test_clear_title_with_none(self):
        state = GameState.default_new_game()
        state.title = 'Old Title'
        set_title(state, None)
        assert state.title is None


class TestSealEntryInClaimQueue:
    """Seal entries в unclaimed_unlocks работают через append_unclaimed +
    claim_triumph с kind='seal'."""

    def test_seal_entry_appended_with_kind_field(self):
        state = GameState.default_new_game()
        append_unclaimed(state, [
            {'triumph_id': 'steps', 'tier_index': 0, 'kind': 'seal'},
        ])
        assert len(state.unclaimed_unlocks) == 1
        assert state.unclaimed_unlocks[0]['kind'] == 'seal'

    def test_dedupe_uses_kind(self):
        """Triumph 'foo' и seal 'foo' — НЕ дубли (разный kind)."""
        state = GameState.default_new_game()
        append_unclaimed(state, [
            {'triumph_id': 'foo', 'tier_index': 0, 'kind': 'triumph'},
            {'triumph_id': 'foo', 'tier_index': 0, 'kind': 'seal'},
        ])
        assert len(state.unclaimed_unlocks) == 2

    def test_claim_triumph_default_kind_does_not_claim_seal(self):
        """claim_triumph(kind='triumph') не трогает seal entries."""
        state = GameState.default_new_game()
        append_unclaimed(state, [
            {'triumph_id': 'foo', 'tier_index': 0, 'kind': 'triumph'},
            {'triumph_id': 'foo', 'tier_index': 0, 'kind': 'seal'},
        ])
        # Default kind='triumph' clears only triumph entry.
        claim_triumph(state, 'foo')
        assert len(state.unclaimed_unlocks) == 1
        assert state.unclaimed_unlocks[0]['kind'] == 'seal'

    def test_claim_triumph_with_seal_kind_clears_seal(self):
        state = GameState.default_new_game()
        append_unclaimed(state, [
            {'triumph_id': 'foo', 'tier_index': 0, 'kind': 'seal'},
        ])
        claim_triumph(state, 'foo', kind='seal')
        assert state.unclaimed_unlocks == []
