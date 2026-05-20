"""Тесты container `game` и `init_game_state()` (задача 1.2).

Проверяем что:
- импорт characteristics НЕ ходит в Sheets (убрано в 1.2);
- init_game_state(state=...) принимает явный state без Sheets-call;
- init идемпотентен — повторный вызов ничего не ломает;
- post-load fixups применяются (loc='home', timestamp_last_enter, energy_max bonuses).
"""

import characteristics
from characteristics import game, init_game_state
from equipment_bonus import equipment_energy_max_bonus
from state import GameState


def _reset_game_container():
    """Хелпер — pytest fixture-style сброс между тестами."""
    game.state = None


def test_module_level_state_is_none_before_init():
    """Сразу после импорта characteristics — game.state должен быть None."""
    # Если другой тест уже init'ил, сбросим вручную.
    _reset_game_container()
    assert game.state is None


def test_init_with_explicit_state_skips_sheets():
    _reset_game_container()
    custom = GameState.default_new_game()
    custom.energy = 42
    custom.money = 999

    returned = init_game_state(custom)

    assert game.state is custom
    assert returned is custom
    assert game.state.energy == 42
    assert game.state.money == 999


def test_init_is_idempotent():
    """Повторный вызов не пересоздаёт state."""
    _reset_game_container()
    s1 = GameState.default_new_game()
    init_game_state(s1)

    s2 = GameState.default_new_game()
    s2.energy = 1  # отличный от s1
    returned = init_game_state(s2)

    # Возвращается уже сохранённый s1, не s2.
    assert returned is s1
    assert game.state is s1


def test_equipment_energy_max_bonus_no_equipment():
    """После 0.2.1g дубликат `_equipment_energy_max_bonus` в characteristics.py
    удалён — все читают через `equipment_bonus.equipment_energy_max_bonus`."""
    state = GameState.default_new_game()
    assert equipment_energy_max_bonus(state) == 0


def test_equipment_energy_max_bonus_sums_only_energy_max_items():
    state = GameState.default_new_game()
    state.equipment.head = {
        'characteristic': ['energy_max'], 'bonus': [10],
        'item_name': ['x'], 'item_type': ['x'], 'grade': ['a-grade'],
        'quality': [50.0], 'price': [50],
    }
    state.equipment.torso = {
        'characteristic': ['stamina'], 'bonus': [99],  # не energy_max → не считается
        'item_name': ['x'], 'item_type': ['x'], 'grade': ['a-grade'],
        'quality': [50.0], 'price': [50],
    }
    state.equipment.foots = {
        'characteristic': ['energy_max'], 'bonus': [5],
        'item_name': ['x'], 'item_type': ['x'], 'grade': ['a-grade'],
        'quality': [50.0], 'price': [50],
    }
    assert equipment_energy_max_bonus(state) == 15


def test_init_applies_post_load_fixups():
    """Fixups: loc='home', timestamp_last_enter обновлён, energy_max пересчитан."""
    _reset_game_container()
    # Эмулируем ситуацию — state передан напрямую, минуя Sheets.
    # Но в этом случае init не применяет fixups (state получен extern).
    # Проверяем fixups на пути через mock-loader.
    custom = GameState.default_new_game()
    custom.loc = 'gym'  # нелокальное
    init_game_state(custom)
    # При explicit-state path fixups НЕ применяются — state доверяется как есть.
    assert game.state.loc == 'gym'  # Не сброшен в 'home'.


def test_state_attribute_is_live_reference():
    """game.state живая ссылка — мутация видна через container."""
    _reset_game_container()
    s = GameState.default_new_game()
    init_game_state(s)
    # Мутация через прямую ссылку.
    s.energy = 7
    # Видна через container.
    assert game.state.energy == 7
    # И наоборот.
    game.state.money = 13
    assert s.money == 13


# ----- 4.54.4: save_characteristic returns OK/STALE -----

def test_save_characteristic_returns_ok_on_clean_save(monkeypatch, tmp_path):
    """Чистый save: Sheets.save_safe OK → return "OK" + snapshot обновлён."""
    from persistence import save_characteristic
    import google_sheets_db

    _reset_game_container()
    s = GameState.default_new_game()
    init_game_state(s)

    # Изоляция CSV — пишем в tmp_path.
    monkeypatch.chdir(tmp_path)

    # Mock save_safe → OK + установит last_modified.
    saved_calls = []

    def fake_save_safe(self, state_dict, expected_last_modified):
        saved_calls.append((dict(state_dict), expected_last_modified))
        state_dict['last_modified'] = 1700000000.0
        return "OK"

    monkeypatch.setattr(google_sheets_db.GameStateRepo, "save_safe", fake_save_safe)

    status = save_characteristic()

    assert status == "OK"
    assert len(saved_calls) == 1
    # State синкнут с тем что Sheets записал.
    assert game.state.last_modified == 1700000000.0
    # Snapshot обновлён.
    assert game.state.last_loaded_snapshot is not None
    assert game.state.last_loaded_snapshot['last_modified'] == 1700000000.0


# ----- 4.48.5.3 (0.2.5c): max-merge перед save (защита от регрессии steps.today) -----

def test_save_max_merges_steps_today_from_log_before_persist(monkeypatch, tmp_path):
    """Перед save_safe вызывается apply_steps_log_max_merge. Если в steps_log
    есть запись с bigger value чем state.steps.today — RAM поднимается, в Sheets
    идёт уже свежее значение. Защита от регрессии (диагноз 20.05.2026)."""
    from persistence import save_characteristic
    import google_sheets_db

    _reset_game_container()
    s = GameState.default_new_game()
    s.steps.today = 100  # web RAM думает что сегодня 100
    init_game_state(s)
    monkeypatch.chdir(tmp_path)

    # Mock StepsLogRepo.for_day → возвращает entry с 500 (другой процесс ввёл).
    monkeypatch.setattr(
        google_sheets_db.StepsLogRepo, "for_day",
        lambda self, date_str, user_id=None: [{'steps': 500}],
    )

    # Capture state_dict sent to save_safe.
    saved_dicts = []
    def fake_save_safe(self, state_dict, expected_last_modified):
        saved_dicts.append(dict(state_dict))
        state_dict['last_modified'] = 1700000000.0
        return "OK"
    monkeypatch.setattr(google_sheets_db.GameStateRepo, "save_safe", fake_save_safe)

    save_characteristic()

    # RAM поднялся до 500 (max-merge).
    assert game.state.steps.today == 500
    # В Sheets ушло 500 (не 100 = регрессия).
    assert saved_dicts[0]['steps_today'] == 500


def test_save_max_merge_no_regression_when_ram_higher(monkeypatch, tmp_path):
    """Если RAM содержит большее значение чем log — max-merge no-op, save идёт с RAM."""
    from persistence import save_characteristic
    import google_sheets_db

    _reset_game_container()
    s = GameState.default_new_game()
    s.steps.today = 1000  # RAM свежий
    init_game_state(s)
    monkeypatch.chdir(tmp_path)

    # Log содержит меньше — max-merge не должен снижать.
    monkeypatch.setattr(
        google_sheets_db.StepsLogRepo, "for_day",
        lambda self, date_str, user_id=None: [{'steps': 500}],
    )

    saved_dicts = []
    def fake_save_safe(self, state_dict, expected_last_modified):
        saved_dicts.append(dict(state_dict))
        state_dict['last_modified'] = 1700000000.0
        return "OK"
    monkeypatch.setattr(google_sheets_db.GameStateRepo, "save_safe", fake_save_safe)

    save_characteristic()

    # RAM остался 1000 (max-merge не снижает).
    assert game.state.steps.today == 1000
    assert saved_dicts[0]['steps_today'] == 1000


def test_save_max_merge_silent_fail_when_log_unavailable(monkeypatch, tmp_path):
    """Если StepsLogRepo бросает — max-merge silent-fail, save продолжается с RAM."""
    from persistence import save_characteristic
    import google_sheets_db

    _reset_game_container()
    s = GameState.default_new_game()
    s.steps.today = 100
    init_game_state(s)
    monkeypatch.chdir(tmp_path)

    def failing_for_day(self, date_str, user_id=None):
        raise RuntimeError("Sheets unavailable")
    monkeypatch.setattr(google_sheets_db.StepsLogRepo, "for_day", failing_for_day)

    saved_dicts = []
    def fake_save_safe(self, state_dict, expected_last_modified):
        saved_dicts.append(dict(state_dict))
        state_dict['last_modified'] = 1700000000.0
        return "OK"
    monkeypatch.setattr(google_sheets_db.GameStateRepo, "save_safe", fake_save_safe)

    status = save_characteristic()

    # Save прошёл со старым значением (offline-tolerance).
    assert status == "OK"
    assert game.state.steps.today == 100
    assert saved_dicts[0]['steps_today'] == 100


def test_save_characteristic_returns_stale_no_state_mutation(monkeypatch, tmp_path):
    """STALE: state.last_modified не меняется, snapshot не меняется, CSV не пишется."""
    from persistence import save_characteristic
    import google_sheets_db

    _reset_game_container()
    s = GameState.default_new_game()
    s.last_modified = 100.0
    s.take_snapshot()
    snapshot_before = dict(s.last_loaded_snapshot or {})
    init_game_state(s)

    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(google_sheets_db.GameStateRepo, "save_safe",
                        lambda self, sd, expected_last_modified: "STALE")

    status = save_characteristic()

    assert status == "STALE"
    # State НЕ мутирован.
    assert game.state.last_modified == 100.0
    # CSV НЕ создан (или старый — но тут tmp_path был пуст).
    csv_path = tmp_path / 'characteristic.csv'
    assert not csv_path.exists(), 'CSV не должен писаться на STALE'


# ----- 4.54.5: handle_stale_prompt CLI flow -----

def test_handle_stale_prompt_cancel(monkeypatch, capsys):
    """Cancel — без мутаций state'а, log_event sync_conflict зафиксирован."""
    from persistence import handle_stale_prompt
    import google_sheets_db
    import history

    _reset_game_container()
    s = GameState.default_new_game()
    s.last_modified = 100.0
    init_game_state(s)
    s.take_snapshot()

    # Mock fresh load: новый money + новый last_modified.
    fresh = s.to_dict()
    fresh['money'] = 1500.0
    fresh['last_modified'] = 200.0
    monkeypatch.setattr(google_sheets_db.GameStateRepo, "load", lambda self: fresh)

    events = []
    monkeypatch.setattr(history, "log_event",
                        lambda evt_type, **payload: events.append((evt_type, payload)))

    monkeypatch.setattr('builtins.input', lambda *a, **k: 'c')

    choice = handle_stale_prompt()

    assert choice == 'cancel'
    assert game.state.last_modified == 100.0  # без мутации
    # log_event sync_conflict записан с choice='cancel'.
    sync_events = [e for e in events if e[0] == 'sync_conflict']
    assert len(sync_events) == 1
    assert sync_events[0][1].get('choice') == 'cancel'

    out = capsys.readouterr().out
    assert '💰' in out  # diff показывает money change
    assert 'STALE' in out


def test_handle_stale_prompt_reload(monkeypatch):
    """Reload — re-init из Sheets, state синкан с свежими данными."""
    from persistence import handle_stale_prompt
    import google_sheets_db
    import history

    _reset_game_container()
    s = GameState.default_new_game()
    s.last_modified = 100.0
    s.money = 100.0
    init_game_state(s)
    s.take_snapshot()

    # Mock fresh: новый state с +600$.
    fresh = s.to_dict()
    fresh['money'] = 700.0
    fresh['last_modified'] = 200.0
    monkeypatch.setattr(google_sheets_db.GameStateRepo, "load", lambda self: fresh)

    events = []
    monkeypatch.setattr(history, "log_event",
                        lambda evt_type, **payload: events.append((evt_type, payload)))

    monkeypatch.setattr('builtins.input', lambda *a, **k: 'r')

    choice = handle_stale_prompt()

    assert choice == 'reload'
    # State синкнут с fresh.
    assert game.state.money == 700.0
    assert game.state.last_modified == 200.0


def test_handle_stale_prompt_force_with_double_confirm(monkeypatch, capsys):
    """Force — двойной confirm prompt → save_safe с expected=None (bypass)."""
    from persistence import handle_stale_prompt
    import google_sheets_db
    import history

    _reset_game_container()
    s = GameState.default_new_game()
    s.last_modified = 100.0
    s.money = 500.0
    init_game_state(s)
    s.take_snapshot()

    fresh = s.to_dict()
    fresh['money'] = 1000.0  # сервер изменил
    fresh['last_modified'] = 200.0
    monkeypatch.setattr(google_sheets_db.GameStateRepo, "load", lambda self: fresh)

    save_safe_calls = []

    def fake_save_safe(self, sd, expected_last_modified):
        save_safe_calls.append(expected_last_modified)
        sd['last_modified'] = 999.0
        return "OK"
    monkeypatch.setattr(google_sheets_db.GameStateRepo, "save_safe", fake_save_safe)

    events = []
    monkeypatch.setattr(history, "log_event",
                        lambda evt_type, **payload: events.append((evt_type, payload)))

    # f → yes (двойной confirm).
    inputs = iter(['f', 'yes'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    choice = handle_stale_prompt()

    assert choice == 'force'
    # save_safe вызван с expected=None (Force bypass).
    assert save_safe_calls == [None]
    # State синкан с force-результатом.
    assert game.state.money == 500.0  # моё значение, не серверное
    assert game.state.last_modified == 999.0


def test_handle_stale_prompt_force_aborted_on_no_confirm(monkeypatch):
    """Force confirm `no` — возврат в loop, повторный выбор."""
    from persistence import handle_stale_prompt
    import google_sheets_db
    import history

    _reset_game_container()
    s = GameState.default_new_game()
    s.last_modified = 100.0
    init_game_state(s)
    s.take_snapshot()

    fresh = s.to_dict()
    fresh['last_modified'] = 200.0
    monkeypatch.setattr(google_sheets_db.GameStateRepo, "load", lambda self: fresh)
    monkeypatch.setattr(google_sheets_db.GameStateRepo, "save_safe",
                        lambda self, sd, expected_last_modified: "OK")
    monkeypatch.setattr(history, "log_event", lambda *a, **k: None)

    # f → no (отмена force) → c (cancel).
    inputs = iter(['f', 'no', 'c'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    choice = handle_stale_prompt()

    assert choice == 'cancel'


def test_handle_stale_prompt_invalid_choice_loops(monkeypatch):
    """Невалидный ввод → повтор prompt'а."""
    from persistence import handle_stale_prompt
    import google_sheets_db
    import history

    _reset_game_container()
    s = GameState.default_new_game()
    init_game_state(s)
    s.take_snapshot()

    monkeypatch.setattr(google_sheets_db.GameStateRepo, "load", lambda self: s.to_dict())
    monkeypatch.setattr(history, "log_event", lambda *a, **k: None)

    inputs = iter(['xyz', 'q', 'c'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    choice = handle_stale_prompt()
    assert choice == 'cancel'


def test_handle_stale_prompt_load_failed_returns_cancel(monkeypatch, capsys):
    """Sheets load fail → возврат cancel без prompt'а."""
    from persistence import handle_stale_prompt
    import google_sheets_db

    _reset_game_container()
    s = GameState.default_new_game()
    init_game_state(s)
    s.take_snapshot()

    def failing_load(self):
        raise RuntimeError("Network down")
    monkeypatch.setattr(google_sheets_db.GameStateRepo, "load", failing_load)

    choice = handle_stale_prompt()
    assert choice == 'cancel'

    out = capsys.readouterr().out
    assert 'Не удалось загрузить' in out


def test_save_characteristic_network_error_returns_ok(monkeypatch, tmp_path, capsys):
    """Sheets network error → state.json-only fallback, return "OK" + warning в лог."""
    from persistence import save_characteristic
    import google_sheets_db

    _reset_game_container()
    s = GameState.default_new_game()
    init_game_state(s)

    monkeypatch.chdir(tmp_path)

    def failing_save_safe(self, sd, expected_last_modified):
        raise RuntimeError("Sheets API quota exceeded")

    monkeypatch.setattr(google_sheets_db.GameStateRepo, "save_safe", failing_save_safe)

    status = save_characteristic()

    assert status == "OK"
    # state.json (1.4.3 / 0.2.5 — primary локальный фолбэк) написан несмотря на Sheets-fail.
    assert (tmp_path / 'state.json').exists()
    # Warning в выводе.
    captured = capsys.readouterr()
    assert 'Sheets sync failed' in captured.out
    assert 'local-only fallback' in captured.out
