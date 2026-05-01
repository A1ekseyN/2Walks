"""Тесты max-merge для steps_log (задача 4.15).

После load из game_state листа `state.steps.today` поднимается до максимума по
записям лога за сегодня — чтобы свежий ввод через любой канал (CLI / Web /
iPhone Shortcut) применялся немедленно, независимо от того, обновлён ли
game_state snapshot в Sheets.
"""

from datetime import datetime

import pytest

from characteristics import apply_steps_log_max_merge, game
from state import GameState


def _make_log_entry(steps: int, source: str = "manual"):
    return {
        "ts": datetime.now().timestamp(),
        "user_id": "alex",
        "steps": steps,
        "source": source,
    }


def test_max_merge_raises_today_when_log_has_higher(monkeypatch):
    from google_sheets_db import StepsLogRepo
    monkeypatch.setattr(StepsLogRepo, "for_day",
                        lambda self, date_str, user_id=None: [_make_log_entry(5000)])

    state = GameState.default_new_game()
    state.steps.today = 1000
    state.steps.used = 200

    apply_steps_log_max_merge(state)

    assert state.steps.today == 5000
    # can_use пересчитан: today - used + bonuses (0 у default state).
    assert state.steps.can_use == 5000 - 200


def test_max_merge_does_not_lower_today(monkeypatch):
    from google_sheets_db import StepsLogRepo
    monkeypatch.setattr(StepsLogRepo, "for_day",
                        lambda self, date_str, user_id=None: [_make_log_entry(2000)])

    state = GameState.default_new_game()
    state.steps.today = 7000  # уже выше
    state.steps.can_use = 6500

    apply_steps_log_max_merge(state)

    assert state.steps.today == 7000  # не уменьшается
    assert state.steps.can_use == 6500  # не пересчитан если today не менялся


def test_max_merge_picks_max_among_multiple_entries(monkeypatch):
    from google_sheets_db import StepsLogRepo
    monkeypatch.setattr(StepsLogRepo, "for_day",
                        lambda self, date_str, user_id=None: [
                            _make_log_entry(1500, "manual"),
                            _make_log_entry(8500, "web"),
                            _make_log_entry(3000, "auto"),
                        ])

    state = GameState.default_new_game()
    state.steps.today = 0

    apply_steps_log_max_merge(state)

    assert state.steps.today == 8500


def test_max_merge_empty_log_is_no_op(monkeypatch):
    from google_sheets_db import StepsLogRepo
    monkeypatch.setattr(StepsLogRepo, "for_day",
                        lambda self, date_str, user_id=None: [])

    state = GameState.default_new_game()
    state.steps.today = 1500
    state.steps.can_use = 1300

    apply_steps_log_max_merge(state)

    assert state.steps.today == 1500
    assert state.steps.can_use == 1300


def test_max_merge_silent_fail_on_sheets_error(monkeypatch):
    """Сетевая ошибка → state не меняется, не падаем."""
    from google_sheets_db import StepsLogRepo

    def failing(self, date_str, user_id=None):
        raise RuntimeError("Network down")

    monkeypatch.setattr(StepsLogRepo, "for_day", failing)

    state = GameState.default_new_game()
    state.steps.today = 1000

    # Не должно бросать.
    apply_steps_log_max_merge(state)

    assert state.steps.today == 1000


def test_max_merge_recomputes_can_use_with_bonuses(monkeypatch):
    """can_use = today - used + total_bonus_steps."""
    from google_sheets_db import StepsLogRepo
    monkeypatch.setattr(StepsLogRepo, "for_day",
                        lambda self, date_str, user_id=None: [_make_log_entry(10000)])

    state = GameState.default_new_game()
    state.steps.today = 5000
    state.steps.used = 1000
    state.gym.stamina = 5  # bonus = round(today/100) * 5

    apply_steps_log_max_merge(state)

    # После max-merge: today=10000, used=1000, stamina_bonus = round(10000/100)*5 = 500.
    # can_use = 10000 - 1000 + 500 = 9500.
    assert state.steps.today == 10000
    assert state.steps.can_use == 9500
