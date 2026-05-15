"""Глобальные pytest-фикстуры (применяются ко всем тестам).

После 4.6 (history.log_event) — mutation helpers пишут в history.jsonl и Sheets
`history` лист на каждом вызове. Чтобы тесты не загрязняли эти ресурсы, тут
автоматически подменяем `history.log_event` на no-op для всех тестов кроме
`test_history.py` (он тестирует сам log_event и monkeypatch'ит pathто внутри).
"""

import pytest


@pytest.fixture(autouse=True)
def _disable_history_log_for_non_history_tests(monkeypatch, request):
    """Для всех тестов кроме test_history.py — `history.log_event` no-op.

    test_history.py имеет свои monkeypatch'и (HISTORY_FILE → tmp_path,
    HistoryLogRepo → MagicMock) — не ломаем их.
    """
    if request.node.fspath.basename == 'test_history.py':
        return  # test_history.py сам управляет log_event поведением
    import history
    monkeypatch.setattr(history, 'log_event', lambda *args, **kwargs: None)


@pytest.fixture(autouse=True)
def _stub_steps_log_for_day(monkeypatch, request):
    """Default-mock `StepsLogRepo.for_day` → `[]` для всех тестов.

    Ловушка (обнаружена 15.05.2026 при 4.54.7): `init_game_state()` зовёт
    `apply_steps_log_max_merge()` → `StepsLogRepo().for_day()` — это **реальный
    Sheets API call** даже в unit-тестах, если сам `for_day` не замокан.
    Тесты вроде `test_handle_stale_prompt_reload` (Reload re-init'ит state)
    тратили ~2 сек на сетевой round-trip + могли пройти в офлайне молча
    (silent-fail catches all).

    Этот autouse fixture даёт безопасный default — пустой лог, no-op merge.
    Тесты, которым нужно специфическое поведение for_day (test_steps_max_merge,
    test_sheets_repo), переопределяют через свои monkeypatch.setattr.

    Skip:
    - test_sheets_repo.py — тестирует сам StepsLogRepo через MagicMock gspread
      (свои repo.for_day(...) вызовы должны идти через настоящий код метода).
    - test_history.py — мокать ему ничего не надо.
    """
    skip = {'test_sheets_repo.py', 'test_history.py'}
    if request.node.fspath.basename in skip:
        return
    import google_sheets_db
    monkeypatch.setattr(google_sheets_db.StepsLogRepo, 'for_day',
                        lambda self, date_str, user_id=None: [])
