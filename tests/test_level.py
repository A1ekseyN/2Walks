"""Тесты CharLevel после миграции на GameState (Phase 3 задачи 1.1)."""

from state import GameState
from level import CharLevel


def test_init_with_state():
    state = GameState.default_new_game()
    state.steps.total_used = 25000
    state.char_level.level = 2
    cl = CharLevel(state)
    assert cl.total_used_steps == 25000
    assert cl.level == 2


def test_calculate_level_from_total_used_steps():
    state = GameState.default_new_game()
    state.steps.total_used = 0
    cl = CharLevel(state)
    assert cl.calculate_level_from_total_used_steps() == 0

    state.steps.total_used = 10000   # ровно на пороге уровня 1
    assert cl.calculate_level_from_total_used_steps() == 1

    state.steps.total_used = 19999   # уровень 1 ещё держится
    assert cl.calculate_level_from_total_used_steps() == 1

    state.steps.total_used = 20000   # уровень 2
    assert cl.calculate_level_from_total_used_steps() == 2

    state.steps.total_used = 1_500_000  # порог key=8 (1.3M) пройден → new_level = 9
    assert cl.calculate_level_from_total_used_steps() == 9


def test_update_level_grants_skill_points():
    """При levelup начисляется по 1 очку навыков за каждый перешагнутый уровень."""
    state = GameState.default_new_game()
    state.steps.total_used = 50000  # → уровень 3
    state.char_level.level = 0
    state.char_level.up_skills = 0

    cl = CharLevel(state)
    cl.update_level()

    assert state.char_level.level == 3
    assert state.char_level.up_skills == 3


def test_update_level_no_change_no_points():
    state = GameState.default_new_game()
    state.steps.total_used = 25000
    state.char_level.level = 2
    state.char_level.up_skills = 5

    cl = CharLevel(state)
    cl.update_level()

    assert state.char_level.level == 2
    assert state.char_level.up_skills == 5


def test_progress_to_next_level_at_zero():
    state = GameState.default_new_game()
    state.steps.total_used = 5000
    state.char_level.level = 0
    cl = CharLevel(state)
    # 5000 / 10000 = 50%
    assert cl.progress_to_next_level() == 50.0


def test_progress_to_next_level_mid_level():
    state = GameState.default_new_game()
    state.steps.total_used = 15000
    state.char_level.level = 1  # порог уровня 1 = 10k, уровня 2 = 20k → диапазон 10k
    cl = CharLevel(state)
    # (15000 - 10000) / (20000 - 10000) = 50%
    assert cl.progress_to_next_level() == 50.0


def test_progress_bar_lvl_up_message_when_points_available():
    state = GameState.default_new_game()
    state.char_level.up_skills = 3
    cl = CharLevel(state)
    msg = cl.progress_bar_lvl_up_message()
    assert "+ 3" in msg
    assert "Skill points" in msg


def test_progress_bar_lvl_up_message_when_no_points():
    state = GameState.default_new_game()
    state.char_level.up_skills = 0
    cl = CharLevel(state)
    assert cl.progress_bar_lvl_up_message() == ""


