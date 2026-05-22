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


# ===========================================================================
# 4.62.1.4 — Energy (Endurance + Workhorse + Disciplined + Pathfinder)
# ===========================================================================

class TestEnergyTriumphs:
    """🔋 Energy — event-based через cost_energy в payload."""

    # ----- Catalog structure -----

    def test_all_4_in_catalog(self):
        assert 'endurance' in TRIUMPHS
        assert 'workhorse' in TRIUMPHS
        assert 'disciplined' in TRIUMPHS
        assert 'pathfinder' in TRIUMPHS

    def test_all_4_have_same_tiers(self):
        """Tiers same as total per design choice 22.05.2026."""
        expected = [1_000, 5_000, 10_000, 50_000]
        for triumph_id in ('endurance', 'workhorse', 'disciplined', 'pathfinder'):
            assert TRIUMPHS[triumph_id]['tiers'] == expected
            assert TRIUMPHS[triumph_id]['category'] == 'energy'

    def test_endurance_hooks_all_6_event_types(self):
        """Endurance — total, должен hook'ать всё что spends energy."""
        hooks = TRIUMPHS['endurance']['event_hooks']
        assert 'work_start' in hooks
        assert 'work_extend' in hooks
        assert 'skill_train_start' in hooks
        assert 'adventure_start' in hooks
        assert 'item_repaired' in hooks
        assert 'item_crafted' in hooks

    def test_per_source_triumphs_only_their_events(self):
        """Per-source — только relevant events, не общие."""
        assert TRIUMPHS['workhorse']['event_hooks'] == ['work_start', 'work_extend']
        assert TRIUMPHS['disciplined']['event_hooks'] == ['skill_train_start']
        assert TRIUMPHS['pathfinder']['event_hooks'] == ['adventure_start']

    # ----- count_delta lambda reads cost_energy -----

    def test_count_delta_reads_cost_energy(self):
        """Lambda берёт payload['cost_energy']."""
        delta_fn = TRIUMPHS['endurance']['count_delta']
        assert delta_fn({'cost_energy': 50}) == 50
        assert delta_fn({'cost_energy': 0}) == 0
        assert delta_fn({}) == 0  # missing key → 0

    # ----- Event accumulation -----

    def test_endurance_accumulates_work_event(self):
        """Endurance counter растёт на cost_energy при work_start."""
        state = GameState.default_new_game()
        register_event(state, 'work_start', cost_energy=32, vacancy='watchman')
        assert state.triumphs['endurance']['count'] == 32
        # Workhorse тоже растёт (work_start hook).
        assert state.triumphs['workhorse']['count'] == 32
        # Disciplined / Pathfinder не растут (другие hooks).
        assert state.triumphs.get('disciplined', {}).get('count', 0) == 0
        assert state.triumphs.get('pathfinder', {}).get('count', 0) == 0

    def test_endurance_accumulates_training_event(self):
        """Skill training — Endurance + Disciplined растут."""
        state = GameState.default_new_game()
        register_event(state, 'skill_train_start', cost_energy=20, skill='stamina')
        assert state.triumphs['endurance']['count'] == 20
        assert state.triumphs['disciplined']['count'] == 20
        # Workhorse / Pathfinder не растут.
        assert state.triumphs.get('workhorse', {}).get('count', 0) == 0
        assert state.triumphs.get('pathfinder', {}).get('count', 0) == 0

    def test_endurance_accumulates_adventure_event(self):
        """Adventure — Endurance + Pathfinder растут."""
        state = GameState.default_new_game()
        register_event(state, 'adventure_start', cost_energy=150, name='walk_30k')
        assert state.triumphs['endurance']['count'] == 150
        assert state.triumphs['pathfinder']['count'] == 150

    def test_endurance_accumulates_forge_repair_event(self):
        """Forge repair тоже считается в total Endurance."""
        state = GameState.default_new_game()
        register_event(state, 'item_repaired', cost_energy=80, item_type='helmet')
        assert state.triumphs['endurance']['count'] == 80
        # Workhorse / Training / Adventure НЕ растут (forge — отдельная активность).
        assert state.triumphs.get('workhorse', {}).get('count', 0) == 0

    def test_endurance_tier_unlock(self):
        """1000 эн → Endurance tier 1 unlock."""
        state = GameState.default_new_game()
        # Накопим 1000 эн через несколько events.
        register_event(state, 'work_start', cost_energy=500, vacancy='watchman')
        register_event(state, 'adventure_start', cost_energy=500, name='walk_easy')
        assert state.triumphs['endurance']['count'] == 1000
        assert state.triumphs['endurance']['tier'] == 1

    def test_endurance_capstone_at_50k(self):
        """50k эн → Endurance tier 4 (capstone)."""
        state = GameState.default_new_game()
        unlocked = register_event(state, 'work_start', cost_energy=50_000, vacancy='watchman')
        assert state.triumphs['endurance']['tier'] == 4
        endurance_unlocks = [u for u in unlocked if u['triumph_id'] == 'endurance']
        assert any(u['is_capstone'] for u in endurance_unlocks)

    def test_missing_cost_energy_payload_no_increment(self):
        """Event без cost_energy (или 0) — counter не растёт."""
        state = GameState.default_new_game()
        register_event(state, 'work_start', vacancy='watchman')  # no cost_energy
        assert state.triumphs.get('endurance', {}).get('count', 0) == 0
        register_event(state, 'work_start', cost_energy=0, vacancy='watchman')  # 0 explicit
        assert state.triumphs.get('endurance', {}).get('count', 0) == 0


# ===========================================================================
# 4.62.1.2 + 4.62.1.3 — Adventures (Adventurer + 7 per-walk)
# ===========================================================================

class TestAdventureTriumphs:
    """🗺 Adventures — metric-based через state.adventure.counters."""

    PER_WALK = (
        ('stroller', 'walk_easy'),
        ('hiker', 'walk_normal'),
        ('trekker', 'walk_hard'),
        ('roamer', 'walk_15k'),
        ('voyager', 'walk_20k'),
        ('explorer', 'walk_25k'),
        ('conqueror', 'walk_30k'),
    )

    EXPECTED_TIERS = [10, 50, 100, 500, 1000]

    # ----- Catalog structure -----

    def test_all_8_in_catalog(self):
        assert 'adventurer' in TRIUMPHS
        for triumph_id, _ in self.PER_WALK:
            assert triumph_id in TRIUMPHS

    def test_all_8_same_tiers_and_category(self):
        """Все одинаковые [10/50/100/500/1000], category=adventures."""
        for triumph_id in ('adventurer', *(t for t, _ in self.PER_WALK)):
            spec = TRIUMPHS[triumph_id]
            assert spec['tiers'] == self.EXPECTED_TIERS
            assert spec['category'] == 'adventures'

    def test_all_8_are_metric_based(self):
        """Все 8 metric-based (event_hooks отсутствует)."""
        for triumph_id in ('adventurer', *(t for t, _ in self.PER_WALK)):
            spec = TRIUMPHS[triumph_id]
            assert 'metric' in spec
            assert 'event_hooks' not in spec

    # ----- Metric lambdas -----

    def test_adventurer_metric_sums_all_counters(self):
        """Adventurer = sum of all 7 per-walk counters."""
        state = GameState.default_new_game()
        state.adventure.counters = {
            'walk_easy': 10, 'walk_normal': 5, 'walk_hard': 3,
            'walk_15k': 2, 'walk_20k': 1, 'walk_25k': 0, 'walk_30k': 0,
        }
        assert TRIUMPHS['adventurer']['metric'](state) == 21

    def test_per_walk_metrics_read_correct_counter(self):
        """Каждый per-walk triumph читает свой counter."""
        state = GameState.default_new_game()
        state.adventure.counters = {
            'walk_easy': 11, 'walk_normal': 22, 'walk_hard': 33,
            'walk_15k': 44, 'walk_20k': 55, 'walk_25k': 66, 'walk_30k': 77,
        }
        expected = {
            'stroller': 11, 'hiker': 22, 'trekker': 33, 'roamer': 44,
            'voyager': 55, 'explorer': 66, 'conqueror': 77,
        }
        for triumph_id, walk_key in self.PER_WALK:
            assert TRIUMPHS[triumph_id]['metric'](state) == expected[triumph_id]

    # ----- Unlocks -----

    def test_adventurer_no_unlock_below_first_tier(self):
        """sum=5 → no unlock (tier 1 = 10)."""
        state = GameState.default_new_game()
        state.adventure.counters['walk_easy'] = 5
        register_event(state, 'work_done', hours=1)
        assert state.triumphs.get('adventurer', {}).get('tier', 0) == 0

    def test_adventurer_unlock_tier_1(self):
        """sum=10 → tier 1."""
        state = GameState.default_new_game()
        state.adventure.counters['walk_easy'] = 10
        register_event(state, 'work_done', hours=1)
        assert state.triumphs['adventurer']['tier'] == 1

    def test_adventurer_multiple_tiers_at_once(self):
        """sum=120 (10 + 50 + 100 thresholds reached, not 500) → tier 3."""
        state = GameState.default_new_game()
        state.adventure.counters = {
            'walk_easy': 50, 'walk_normal': 30, 'walk_hard': 20,
            'walk_15k': 10, 'walk_20k': 5, 'walk_25k': 3, 'walk_30k': 2,
        }  # sum=120
        unlocked = register_event(state, 'work_done', hours=1)
        adv_unlocks = [u for u in unlocked if u['triumph_id'] == 'adventurer']
        assert len(adv_unlocks) == 3
        assert state.triumphs['adventurer']['tier'] == 3
        assert not any(u['is_capstone'] for u in adv_unlocks)

    def test_adventurer_capstone_at_1000(self):
        """sum=1000 → tier 5 (capstone)."""
        state = GameState.default_new_game()
        state.adventure.counters['walk_easy'] = 1000
        unlocked = register_event(state, 'work_done', hours=1)
        adv_unlocks = [u for u in unlocked if u['triumph_id'] == 'adventurer']
        assert state.triumphs['adventurer']['tier'] == 5
        assert adv_unlocks[-1]['is_capstone'] is True

    def test_per_walk_unlock_isolated(self):
        """walk_30k=10 → conqueror tier 1 unlock, остальные per-walk не растут."""
        state = GameState.default_new_game()
        state.adventure.counters['walk_30k'] = 10
        register_event(state, 'work_done', hours=1)
        assert state.triumphs['conqueror']['tier'] == 1
        # Stroller etc — не unlocked (counters не задеты).
        for triumph_id, _ in self.PER_WALK:
            if triumph_id == 'conqueror':
                continue
            assert state.triumphs.get(triumph_id, {}).get('tier', 0) == 0

    def test_per_walk_capstone_at_1000(self):
        """walk_easy=1000 → stroller tier 5 (capstone)."""
        state = GameState.default_new_game()
        state.adventure.counters['walk_easy'] = 1000
        unlocked = register_event(state, 'work_done', hours=1)
        stroller_unlocks = [u for u in unlocked if u['triumph_id'] == 'stroller']
        assert state.triumphs['stroller']['tier'] == 5
        assert stroller_unlocks[-1]['is_capstone'] is True

    def test_init_metric_check_auto_unlocks_on_existing_state(self):
        """Симулирует existing player: counters накоплены → init_metric_check
        auto-unlock'ает соответствующие triumph'ы без любых events."""
        from triumphs import init_metric_check
        state = GameState.default_new_game()
        state.adventure.counters = {
            'walk_easy': 50, 'walk_normal': 12, 'walk_hard': 5,
            'walk_15k': 3, 'walk_20k': 2, 'walk_25k': 1, 'walk_30k': 0,
        }  # sum=73
        unlocked = init_metric_check(state)
        # Adventurer sum=73 → tier 2 (10, 50).
        assert state.triumphs['adventurer']['tier'] == 2
        # Stroller (walk_easy=50) → tier 2 (10, 50).
        assert state.triumphs['stroller']['tier'] == 2
        # Hiker (walk_normal=12) → tier 1 (10).
        assert state.triumphs['hiker']['tier'] == 1
        # Trekker (walk_hard=5) → tier 0 (no unlock).
        assert state.triumphs.get('trekker', {}).get('tier', 0) == 0
        # Sanity: на каждом unlocked triumph'е есть запись в unlocked list.
        triumph_ids = {u['triumph_id'] for u in unlocked}
        assert 'adventurer' in triumph_ids
        assert 'stroller' in triumph_ids
        assert 'hiker' in triumph_ids
