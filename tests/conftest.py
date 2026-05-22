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
    """Default-mock `StepsLogRepo.for_day` → `[]` и `.append` → no-op для всех
    тестов. Защищает Sheets от загрязнения тест-данными.

    Ловушка #1 (обнаружена 15.05.2026 при 4.54.7): `init_game_state()` зовёт
    `apply_steps_log_max_merge()` → `StepsLogRepo().for_day()` — это **реальный
    Sheets API call** даже в unit-тестах, если сам `for_day` не замокан.
    Тесты вроде `test_handle_stale_prompt_reload` (Reload re-init'ит state)
    тратили ~2 сек на сетевой round-trip + могли пройти в офлайне молча
    (silent-fail catches all).

    Ловушка #2 (обнаружена 19.05.2026 после 4.48.3 — реальный bug с потерей
    UX-консистентности): тесты POST'ящие в `/web/steps` или `/api/steps`
    ходят через `_apply_new_steps()` → `StepsLogRepo().append(...)` —
    **реальная запись в Sheets steps_log**. Pollution накапливается с каждым
    pytest-прогоном; max-merge на следующий load игры подтянет тестовые
    значения как actual today (например, тест с `steps=5100` → today=5100
    на следующее F5 в production web). Симптом: игрок видит
    `Steps: 5,100 / 8,007` утром при никаких действиях — на самом деле это
    leak из тестов. После фикса append тоже no-op в default-фикстуре.

    Этот autouse fixture даёт безопасный default — пустой лог, no-op merge,
    no-op append. Тесты, которым нужно специфическое поведение for_day или
    append (`test_steps_max_merge`, `test_sheets_repo`), переопределяют
    через свои `monkeypatch.setattr`.

    Skip:
    - `test_sheets_repo.py` — тестирует сам StepsLogRepo через MagicMock
      gspread (свои repo.for_day/append вызовы должны идти через настоящий
      код метода).
    - `test_history.py` — мокать ему ничего не надо.
    """
    skip = {'test_sheets_repo.py', 'test_history.py'}
    if request.node.fspath.basename in skip:
        return
    import google_sheets_db
    monkeypatch.setattr(google_sheets_db.StepsLogRepo, 'for_day',
                        lambda self, date_str, user_id=None: [])
    monkeypatch.setattr(google_sheets_db.StepsLogRepo, 'append',
                        lambda self, ts, steps, source, user_id=None: None)


@pytest.fixture(autouse=True)
def _disable_triumphs_register_event_for_non_triumphs_tests(monkeypatch, request):
    """4.62.0.2 — `triumphs.register_event` no-op для тестов кроме triumphs-tests.

    Engine вызывается из `history.log_event` (hook) на каждом event'е. Без
    мока тесты которые делают log_event mock или обходят его — могут случайно
    мутировать state.triumphs (если catalog не пустой). Также защищает от
    side-effects если catalog (4.62.1.x) добавится.

    Skip:
    - `test_triumphs.py` — тестирует сам engine, register_event должен работать.
    - `test_triumphs_catalog.py` — тестирует catalog entries (4.62.1.x) через
      реальный register_event с metric/event hooks.
    """
    skip = {'test_triumphs.py', 'test_triumphs_catalog.py'}
    if request.node.fspath.basename in skip:
        return
    import triumphs
    monkeypatch.setattr(triumphs, 'register_event',
                        lambda state, event_type, **payload: [])
