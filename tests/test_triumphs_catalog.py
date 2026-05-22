"""Тесты Triumphs catalog (4.62.1.x — категории по одной).

Catalog entries — данные, не logic. Тесты проверяют:
- Структура каждого entry правильная (name / category / tiers / metric или event_hooks)
- Реальные unlocks работают на mock'нутом state
- Backwards-compat: removed entries не ломают persist (legacy state с unknown triumph_id)
"""

import pytest

from state import GameState
from triumphs import register_event, get_progress, total_score
from triumphs_data import TRIUMPHS


# ===========================================================================
# 4.62.1.1 — Marathoner (Steps)
# ===========================================================================

class TestMarathoner:
    """🏃 Marathoner — metric-based, state.steps.total_used."""

    def test_marathoner_in_catalog(self):
        assert 'marathoner' in TRIUMPHS
        spec = TRIUMPHS['marathoner']
        assert spec['name'] == 'Marathoner'
        assert spec['category'] == 'steps'
        assert spec['tiers'] == [100_000, 500_000, 1_000_000, 5_000_000, 10_000_000]
        assert 'metric' in spec  # metric-based, не event-based
        assert 'event_hooks' not in spec

    def test_marathoner_metric_reads_total_used(self):
        """Lambda metric читает state.steps.total_used."""
        state = GameState.default_new_game()
        state.steps.total_used = 123_456
        spec = TRIUMPHS['marathoner']
        assert spec['metric'](state) == 123_456

    def test_marathoner_no_unlock_below_first_tier(self):
        """state.steps.total_used = 50k → no unlock (tier 1 = 100k)."""
        state = GameState.default_new_game()
        state.steps.total_used = 50_000
        unlocked = register_event(state, 'work_done', hours=1)  # any event triggers metric recheck
        marathoner_unlocks = [u for u in unlocked if u['triumph_id'] == 'marathoner']
        assert marathoner_unlocks == []
        assert state.triumphs.get('marathoner', {}).get('tier', 0) == 0

    def test_marathoner_unlock_tier_1(self):
        """100k → tier 1 unlock."""
        state = GameState.default_new_game()
        state.steps.total_used = 100_000
        register_event(state, 'work_done', hours=1)
        assert state.triumphs['marathoner']['tier'] == 1

    def test_marathoner_unlock_multiple_tiers_at_once(self):
        """1.8M → tiers 1+2+3 unlock (user's actual state)."""
        state = GameState.default_new_game()
        state.steps.total_used = 1_800_000  # симулирует Oleksii's state
        unlocked = register_event(state, 'work_done', hours=1)
        marathoner_unlocks = [u for u in unlocked if u['triumph_id'] == 'marathoner']
        # 3 tier'а одновременно: 100k, 500k, 1M.
        assert len(marathoner_unlocks) == 3
        assert state.triumphs['marathoner']['tier'] == 3
        # Capstone (tier 5 = 10M) ещё не достигнут.
        assert not any(u['is_capstone'] for u in marathoner_unlocks)

    def test_marathoner_capstone_at_10m(self):
        """10M total_used → tier 5 (capstone) unlock."""
        state = GameState.default_new_game()
        state.steps.total_used = 10_000_000
        unlocked = register_event(state, 'work_done', hours=1)
        marathoner_unlocks = [u for u in unlocked if u['triumph_id'] == 'marathoner']
        assert len(marathoner_unlocks) == 5  # все 5 tier'ов unlocked
        assert state.triumphs['marathoner']['tier'] == 5
        # Capstone marker на последнем tier'е.
        assert marathoner_unlocks[-1]['is_capstone'] is True

    def test_marathoner_score_contribution(self):
        """Tier 3 unlocked → score = 3 × 10 = 30."""
        state = GameState.default_new_game()
        state.steps.total_used = 1_800_000
        register_event(state, 'work_done', hours=1)
        # Только marathoner в catalog'е → весь score от него.
        assert total_score(state) == 30

    def test_marathoner_progress_in_tier_4(self):
        """1.8M / 5M tier 4 → ~37% progress в текущем tier'е (1M to 5M)."""
        state = GameState.default_new_game()
        state.steps.total_used = 1_800_000
        register_event(state, 'work_done', hours=1)
        progress = get_progress(state, 'marathoner')
        assert progress['current_tier'] == 3  # tier 1+2+3 unlocked
        assert progress['next_threshold'] == 5_000_000
        assert progress['current_value'] == 1_800_000
        assert progress['is_capstone'] is False
        # Progress в текущем tier'е: (1.8M - 1M) / (5M - 1M) = 800k / 4M = 20%.
        assert 19.0 < progress['progress_pct'] < 21.0

    def test_marathoner_idempotent_recheck(self):
        """Повторный register_event при уже unlocked tier — no new unlock."""
        state = GameState.default_new_game()
        state.steps.total_used = 500_000
        register_event(state, 'work_done', hours=1)
        assert state.triumphs['marathoner']['tier'] == 2

        # Повторный — тот же tier, ничего нового.
        unlocked = register_event(state, 'work_done', hours=1)
        marathoner = [u for u in unlocked if u['triumph_id'] == 'marathoner']
        assert marathoner == []
        assert state.triumphs['marathoner']['tier'] == 2
