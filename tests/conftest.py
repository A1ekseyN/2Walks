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
