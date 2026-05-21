"""Тесты GameStateRepo / StepsLogRepo (задача 4.14).

Покрываем:
- pure helpers `_state_dict_to_rows` / `_rows_to_state_dict` round-trip
- pure helper `_format_steps_entry`
- repo методы с моком gspread (без реального Sheets)
- StepsLogRepo: ensure_sheet auto-create, append, for_day filtering
- ts хранится как float (Unix timestamp)
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from google_sheets_db import (
    GameStateRepo,
    HistoryLogRepo,
    StepsLogRepo,
    _blob_rows_to_state_dict,
    _format_steps_entry,
    _is_legacy_kv_layout,
    _json_blob_default,
    _rows_to_state_dict,
    _state_dict_to_blob_rows,
    _state_dict_to_rows,
)


# ----- _state_dict_to_rows -----

def test_state_dict_to_rows_header_first():
    rows = _state_dict_to_rows({})
    assert rows == [['Key', 'Value']]


def test_state_dict_to_rows_basic_types():
    rows = _state_dict_to_rows({'energy': 50, 'money': 100})
    assert rows[0] == ['Key', 'Value']
    assert rows[1] == ['energy', 50]
    assert rows[2] == ['money', 100]


def test_state_dict_to_rows_serializes_dict_and_list():
    """list / dict → JSON-строка."""
    data = {'inventory': [{'a': 1}], 'equipment_head': {'k': 'v'}}
    rows = _state_dict_to_rows(data)
    inv_row = next(r for r in rows if r[0] == 'inventory')
    assert inv_row[1] == '[{"a": 1}]'
    eq_row = next(r for r in rows if r[0] == 'equipment_head')
    assert eq_row[1] == '{"k": "v"}'


def test_state_dict_to_rows_serializes_datetime():
    data = {'working_end': datetime(2026, 5, 1, 14, 30, 0)}
    rows = _state_dict_to_rows(data)
    we_row = next(r for r in rows if r[0] == 'working_end')
    assert we_row[1] == '2026-05-01 14:30:00.000000'


# ----- _rows_to_state_dict -----

def test_rows_to_state_dict_int_and_str():
    rows = [['energy', '50'], ['loc', 'home']]
    data = _rows_to_state_dict(rows)
    assert data == {'energy': 50, 'loc': 'home'}


def test_rows_to_state_dict_empty_string_to_none():
    rows = [['date_last_enter', '']]
    data = _rows_to_state_dict(rows)
    assert data == {'date_last_enter': None}


def test_rows_to_state_dict_bool():
    rows = [['working', 'true'], ['adventure', 'false']]
    data = _rows_to_state_dict(rows)
    assert data == {'working': True, 'adventure': False}


def test_rows_to_state_dict_float():
    rows = [['energy_time_stamp', '1746124425.5']]
    data = _rows_to_state_dict(rows)
    assert data == {'energy_time_stamp': 1746124425.5}


def test_rows_to_state_dict_json_list():
    rows = [['inventory', '[{"item": 1}]']]
    data = _rows_to_state_dict(rows)
    assert data == {'inventory': [{'item': 1}]}


def test_rows_to_state_dict_datetime_field():
    rows = [['working_end', '2026-05-01 14:30:00.000000']]
    data = _rows_to_state_dict(rows)
    assert data['working_end'] == datetime(2026, 5, 1, 14, 30, 0)


def test_rows_to_state_dict_skips_empty_rows():
    """Pустые строки (одна колонка или пустые) — пропускаются."""
    rows = [['energy', '50'], [], ['only_one_col']]
    data = _rows_to_state_dict(rows)
    assert data == {'energy': 50}


def test_state_round_trip():
    """to_rows → from_rows должен восстановить базовые типы."""
    original = {'energy': 50, 'money': 100, 'loc': 'home', 'inventory': [], 'working': True}
    rows = _state_dict_to_rows(original)
    # Skip header row.
    parsed = _rows_to_state_dict(rows[1:])
    assert parsed == original


# ----- 1.4.3 / 0.2.5: blob layout helpers -----

def test_state_dict_to_blob_rows_basic():
    """Blob layout: одна строка с 2 ячейками."""
    import json
    data = {'energy': 50, 'money': 100.5, 'last_modified': 123.45}
    rows = _state_dict_to_blob_rows(data)
    assert len(rows) == 1
    assert len(rows[0]) == 2
    assert rows[0][0] == 123.45  # A1 = last_modified
    parsed = json.loads(rows[0][1])  # B1 = JSON-blob
    assert parsed == data


def test_state_dict_to_blob_rows_no_last_modified():
    """Если в state нет last_modified — A1 = 0.0."""
    rows = _state_dict_to_blob_rows({'energy': 50})
    assert rows[0][0] == 0.0


def test_state_dict_to_blob_rows_serializes_datetime():
    """Datetime → strftime в legacy формате через _json_blob_default."""
    import json
    data = {'working_end': datetime(2026, 5, 1, 14, 30, 0)}
    rows = _state_dict_to_blob_rows(data)
    parsed = json.loads(rows[0][1])
    assert parsed['working_end'] == '2026-05-01 14:30:00.000000'


def test_state_dict_to_blob_rows_serializes_nested_dict_and_list():
    """Inventory / equipment / presets — nested структуры round-trip."""
    import json
    data = {
        'inventory': [{'item_type': ['ring'], 'bonus': [5]}, {'item_type': ['helmet']}],
        'equipment_head': {'item_name': ['Helm'], 'quality': [85.5]},
        'equipment_neck': None,
    }
    rows = _state_dict_to_blob_rows(data)
    parsed = json.loads(rows[0][1])
    assert parsed == data


def test_blob_rows_to_state_dict_round_trip():
    """to_blob_rows → from_blob_rows round-trip восстанавливает структуру."""
    original = {
        'energy': 50,
        'money': 100.5,
        'inventory': [{'a': 1}],
        'equipment_head': None,
        'working': True,
        'last_modified': 123.45,
    }
    rows = _state_dict_to_blob_rows(original)
    parsed = _blob_rows_to_state_dict(rows)
    assert parsed == original


def test_blob_rows_to_state_dict_datetime_round_trip():
    """Datetime поля восстанавливаются через strptime в from_blob_rows."""
    original = {'working_end': datetime(2026, 5, 1, 14, 30, 0)}
    rows = _state_dict_to_blob_rows(original)
    parsed = _blob_rows_to_state_dict(rows)
    assert parsed['working_end'] == datetime(2026, 5, 1, 14, 30, 0)


def test_blob_rows_to_state_dict_empty_rows():
    """Пустые rows → пустой dict (graceful, не raise)."""
    assert _blob_rows_to_state_dict([]) == {}
    assert _blob_rows_to_state_dict([[]]) == {}
    assert _blob_rows_to_state_dict([[123.45]]) == {}  # only A1, no blob


def test_blob_rows_to_state_dict_invalid_blob():
    """Невалидный JSON в B1 → {} (caller fallback на legacy)."""
    assert _blob_rows_to_state_dict([[123.45, 'not-a-json']]) == {}
    assert _blob_rows_to_state_dict([[123.45, '']]) == {}


def test_blob_rows_to_state_dict_non_dict_blob():
    """B1 содержит valid JSON но не dict (например list) → {}."""
    assert _blob_rows_to_state_dict([[123.45, '[1, 2, 3]']]) == {}


def test_is_legacy_kv_layout_true():
    """First row = ['Key', 'Value'] → legacy layout."""
    assert _is_legacy_kv_layout([['Key', 'Value'], ['energy', '50']]) is True


def test_is_legacy_kv_layout_false_blob_layout():
    """First row не header → НЕ legacy."""
    assert _is_legacy_kv_layout([[123.45, '{"energy": 50}']]) is False


def test_is_legacy_kv_layout_false_empty():
    """Empty rows → НЕ legacy (по умолчанию blob)."""
    assert _is_legacy_kv_layout([]) is False


def test_json_blob_default_datetime():
    """_json_blob_default конвертирует datetime в strftime формат."""
    dt = datetime(2026, 5, 1, 14, 30, 0)
    assert _json_blob_default(dt) == '2026-05-01 14:30:00.000000'


def test_json_blob_default_raises_for_unsupported_type():
    """_json_blob_default raises TypeError для неподдерживаемых типов."""
    import pytest
    with pytest.raises(TypeError):
        _json_blob_default(object())


# ----- _format_steps_entry -----

def test_format_steps_entry_returns_list_with_float_ts():
    entry = _format_steps_entry(1746124425.5, 'alex', 5000, 'manual')
    assert entry == [1746124425.5, 'alex', 5000, 'manual']
    assert isinstance(entry[0], float)
    assert isinstance(entry[2], int)


def test_format_steps_entry_coerces_steps_to_int():
    entry = _format_steps_entry(1.0, 'u', '5000', 'web')
    assert entry[2] == 5000


# ----- GameStateRepo (mock gspread) -----

def _mock_worksheet(values=None, meta=None):
    """Mock gspread worksheet.

    `values` — rows возвращаемые `ws.get_all_values()`.
    `meta` — значение `ws.acell('A1').value` (1.4.3 load_meta fast-path).
       `None` (default) → fast-path даёт None, fallback на scan rows.
       Передавай numeric string ("123.45") если хочешь test'ить blob layout
       где A1 содержит last_modified.
    """
    ws = MagicMock()
    ws.get_all_values.return_value = values or []
    cell = MagicMock()
    cell.value = meta
    ws.acell.return_value = cell
    return ws


def _mock_repo_with_ws(repo_cls, ws, monkeypatch):
    repo = repo_cls()
    monkeypatch.setattr(repo, '_worksheet', lambda: ws)
    return repo


def test_game_state_repo_save_writes_blob_layout(monkeypatch):
    """1.4.3 (0.2.5) — save пишет одну строку с 2 ячейками: [last_modified, JSON-blob]."""
    import json
    ws = _mock_worksheet()
    repo = _mock_repo_with_ws(GameStateRepo, ws, monkeypatch)
    repo.save({'energy': 50, 'last_modified': 123.45})

    ws.clear.assert_called_once()
    ws.update.assert_called_once()
    rows_passed = ws.update.call_args[0][0]
    assert len(rows_passed) == 1, 'Blob layout = одна строка'
    assert len(rows_passed[0]) == 2, '2 ячейки: A1=last_modified, B1=JSON-blob'
    assert rows_passed[0][0] == 123.45
    blob = rows_passed[0][1]
    parsed = json.loads(blob)
    assert parsed == {'energy': 50, 'last_modified': 123.45}


def test_game_state_repo_load_blob_layout(monkeypatch):
    """1.4.3 (0.2.5) — load парсит blob layout (A1=ts, B1=JSON)."""
    import json
    blob = json.dumps({'energy': 50, 'money': 100, 'last_modified': 123.45})
    ws = _mock_worksheet([[123.45, blob]])
    repo = _mock_repo_with_ws(GameStateRepo, ws, monkeypatch)
    data = repo.load()
    assert data == {'energy': 50, 'money': 100, 'last_modified': 123.45}


def test_game_state_repo_load_legacy_kv_layout(monkeypatch, capsys):
    """1.4.3 (0.2.5) — auto-detect: первая строка ['Key', 'Value'] → legacy parser."""
    ws = _mock_worksheet([['Key', 'Value'], ['energy', '50'], ['money', '100']])
    repo = _mock_repo_with_ws(GameStateRepo, ws, monkeypatch)
    data = repo.load()
    assert data == {'energy': 50, 'money': 100}
    # Migration notice печатается в stdout.
    out = capsys.readouterr().out
    assert 'migration 1.4.3' in out


# ----- 4.54.2: load_meta + save_safe (Optimistic concurrency) -----

def test_load_meta_fast_path_blob_layout(monkeypatch):
    """1.4.3 (0.2.5) — fast-path через acell('A1') когда blob layout.
    4.48.5.4 (0.2.5d) — acell вызывается с UNFORMATTED_VALUE чтобы избежать
    округления Sheets-форматирования (cell A1 имеет default "Number" format
    без decimals, FORMATTED возвращает rounded integer)."""
    from gspread.utils import ValueRenderOption

    # UNFORMATTED для number cell возвращает float напрямую (не string).
    ws = _mock_worksheet(meta=1747275600.123)
    repo = _mock_repo_with_ws(GameStateRepo, ws, monkeypatch)
    assert repo.load_meta() == 1747275600.123
    # acell вызвана с UNFORMATTED, get_all_values НЕ вызывалась (fast-path).
    ws.acell.assert_called_once_with(
        'A1', value_render_option=ValueRenderOption.unformatted
    )
    ws.get_all_values.assert_not_called()


def test_load_meta_handles_rounded_formatted_value(monkeypatch):
    """4.48.5.4 regression: до fix'а FORMATTED давал rounded integer string
    ('1779300151' вместо float 1779300150.71383) → load_meta возвращал
    округлённое значение → ложный STALE. После fix'а UNFORMATTED возвращает
    точный float напрямую."""
    # Симулируем UNFORMATTED behavior — возвращает float не string.
    ws = _mock_worksheet(meta=1779300150.71383)
    repo = _mock_repo_with_ws(GameStateRepo, ws, monkeypatch)
    result = repo.load_meta()
    assert result == 1779300150.71383
    assert result != 1779300151  # НЕ округление


def test_load_meta_legacy_fallback_when_present(monkeypatch):
    """4.54.2 — Legacy Key/Value layout: A1='Key', fallback на scan rows."""
    ws = _mock_worksheet([
        ['Key', 'Value'],
        ['energy', '50'],
        ['last_modified', '1747275600.123'],
        ['money', '100'],
    ], meta='Key')  # A1='Key' (legacy header)
    repo = _mock_repo_with_ws(GameStateRepo, ws, monkeypatch)
    assert repo.load_meta() == 1747275600.123


def test_load_meta_returns_zero_when_missing(monkeypatch):
    """4.54.2 — Legacy save без last_modified → default 0.0 (первый save_safe пройдёт)."""
    ws = _mock_worksheet([
        ['Key', 'Value'],
        ['energy', '50'],
        ['money', '100'],
    ], meta='Key')
    repo = _mock_repo_with_ws(GameStateRepo, ws, monkeypatch)
    assert repo.load_meta() == 0.0


def test_load_meta_returns_zero_on_bad_value(monkeypatch):
    """Невалидное float значение в ячейке → graceful 0.0 (не падаем)."""
    ws = _mock_worksheet([
        ['Key', 'Value'],
        ['last_modified', 'not-a-number'],
    ], meta='Key')
    repo = _mock_repo_with_ws(GameStateRepo, ws, monkeypatch)
    assert repo.load_meta() == 0.0


def test_save_safe_ok_when_expected_matches(monkeypatch):
    """Sheets timestamp == expected → save проходит, status OK."""
    ws = _mock_worksheet(meta='100.0')
    repo = _mock_repo_with_ws(GameStateRepo, ws, monkeypatch)
    state_dict = {'energy': 50, 'last_modified': 100.0}

    status = repo.save_safe(state_dict, expected_last_modified=100.0)

    assert status == "OK"
    ws.clear.assert_called_once()
    ws.update.assert_called_once()
    # state_dict мутирован — last_modified выставлен в time.time()
    assert state_dict['last_modified'] > 100.0


def test_save_safe_stale_when_sheets_newer(monkeypatch):
    """Sheets newer чем expected → STALE, save НЕ происходит, state_dict НЕ мутируется."""
    ws = _mock_worksheet(meta='200.0')
    repo = _mock_repo_with_ws(GameStateRepo, ws, monkeypatch)
    state_dict = {'energy': 50, 'last_modified': 100.0}

    status = repo.save_safe(state_dict, expected_last_modified=100.0)

    assert status == "STALE"
    ws.clear.assert_not_called()
    ws.update.assert_not_called()
    # state_dict не мутирован
    assert state_dict['last_modified'] == 100.0


def test_save_safe_ok_with_epsilon_tolerance(monkeypatch):
    """Идентичные float (с микросекундной разницей) НЕ дают false-positive STALE."""
    ws = _mock_worksheet(meta='100.001')  # на 1 ms newer, в пределах epsilon
    repo = _mock_repo_with_ws(GameStateRepo, ws, monkeypatch)
    state_dict = {'energy': 50, 'last_modified': 100.0}

    status = repo.save_safe(state_dict, expected_last_modified=100.0)

    assert status == "OK"


def test_save_safe_force_bypass_when_expected_none(monkeypatch):
    """4.54.2 — `expected=None` bypass check (Force option в CLI prompt 4.54.5).
    Save проходит даже если Sheets newer."""
    ws = _mock_worksheet(meta='999.0')  # на десятилетия newer
    repo = _mock_repo_with_ws(GameStateRepo, ws, monkeypatch)
    state_dict = {'energy': 50, 'last_modified': 100.0}

    status = repo.save_safe(state_dict, expected_last_modified=None)

    assert status == "OK"
    ws.clear.assert_called_once()
    ws.update.assert_called_once()
    assert state_dict['last_modified'] > 999.0  # обновлён к time.time()


def test_save_safe_legacy_first_save_passes(monkeypatch):
    """4.54.2 — Legacy Sheets без last_modified (load_meta=0.0) + state.last_modified=0.0
    → проходит проверку (0.0 ≤ 0.0). Первый save после deploy 4.54 запишет реальный timestamp."""
    ws = _mock_worksheet([
        ['Key', 'Value'],
        ['energy', '50'],
        # last_modified отсутствует
    ], meta='Key')  # legacy layout: A1='Key'
    repo = _mock_repo_with_ws(GameStateRepo, ws, monkeypatch)
    state_dict = {'energy': 50, 'last_modified': 0.0}

    status = repo.save_safe(state_dict, expected_last_modified=0.0)

    assert status == "OK"
    # last_modified теперь реальный
    assert state_dict['last_modified'] > 0.0


# ----- HistoryLogRepo.since (4.2 / 0.2.5e) -----

def test_history_since_filters_old_events(monkeypatch):
    """Events с ts < since не возвращаются."""
    ws = MagicMock()
    ws.get_values.return_value = [
        ['ts', 'datetime', 'user_id', 'game_version', 'event_type', 'payload_json'],
        [100.0, '2026-05-20 10:00:00', 'alex', '0.2.5d', 'work_done', '{"hours": 1}'],
        [200.0, '2026-05-20 11:00:00', 'alex', '0.2.5d', 'skill_upgraded', '{"skill": "stamina"}'],
        [300.0, '2026-05-20 12:00:00', 'alex', '0.2.5d', 'save', '{}'],
    ]
    repo = HistoryLogRepo()
    monkeypatch.setattr(repo, '_ensure_sheet', lambda: ws)

    events = repo.since(150.0)
    assert len(events) == 2
    assert events[0]['ts'] == 200.0
    assert events[1]['ts'] == 300.0


def test_history_since_parses_payload_json(monkeypatch):
    """Payload-колонка парсится из JSON-string в dict."""
    ws = MagicMock()
    ws.get_values.return_value = [
        ['ts', 'datetime', 'user_id', 'game_version', 'event_type', 'payload_json'],
        [100.0, '2026-05-20 10:00:00', 'alex', '0.2.5d', 'work_done',
         '{"vacancy": "watchman", "hours": 4, "salary": 40.0}'],
    ]
    repo = HistoryLogRepo()
    monkeypatch.setattr(repo, '_ensure_sheet', lambda: ws)

    events = repo.since(50.0)
    assert events[0]['type'] == 'work_done'
    assert events[0]['payload'] == {'vacancy': 'watchman', 'hours': 4, 'salary': 40.0}


def test_history_since_silent_fail_on_network_error(monkeypatch):
    """Sheets error → пустой list (report не критичен)."""
    repo = HistoryLogRepo()
    def failing(self):
        raise RuntimeError("Sheets unavailable")
    monkeypatch.setattr(HistoryLogRepo, '_ensure_sheet', failing)

    assert repo.since(100.0) == []


def test_history_since_skips_invalid_ts(monkeypatch):
    """Row с невалидным ts (не float-parseable) — пропускается."""
    ws = MagicMock()
    ws.get_values.return_value = [
        ['ts', 'datetime', 'user_id', 'game_version', 'event_type', 'payload_json'],
        ['not-a-number', '2026-05-20', 'alex', '0.2.5d', 'work_done', '{}'],
        [200.0, '2026-05-20', 'alex', '0.2.5d', 'skill_upgraded', '{}'],
    ]
    repo = HistoryLogRepo()
    monkeypatch.setattr(repo, '_ensure_sheet', lambda: ws)

    events = repo.since(100.0)
    assert len(events) == 1
    assert events[0]['type'] == 'skill_upgraded'


def test_history_since_handles_invalid_payload_json(monkeypatch):
    """Невалидный JSON payload → пустой dict, но event возвращается."""
    ws = MagicMock()
    ws.get_values.return_value = [
        ['ts', 'datetime', 'user_id', 'game_version', 'event_type', 'payload_json'],
        [100.0, '2026-05-20', 'alex', '0.2.5d', 'work_done', 'not-a-json'],
    ]
    repo = HistoryLogRepo()
    monkeypatch.setattr(repo, '_ensure_sheet', lambda: ws)

    events = repo.since(50.0)
    assert len(events) == 1
    assert events[0]['payload'] == {}


# ----- StepsLogRepo (mock gspread) -----

def test_steps_log_append_calls_append_row(monkeypatch):
    ws = MagicMock()
    repo = StepsLogRepo()
    monkeypatch.setattr(repo, '_ensure_sheet', lambda: ws)

    repo.append(ts=1746124425.5, steps=5000, source='manual', user_id='alex')

    ws.append_row.assert_called_once()
    args, kwargs = ws.append_row.call_args
    assert args[0] == [1746124425.5, 'alex', 5000, 'manual']
    # Изменено в 0.2.3g (07.05.2026): RAW вместо USER_ENTERED — иначе
    # Sheets парсит float ts по локали, на чтении ломается float() / ast.literal_eval.
    assert kwargs.get('value_input_option') == 'RAW'


def test_steps_log_append_uses_default_user_id(monkeypatch):
    """Без явного user_id берётся DEFAULT_USER_ID из config."""
    ws = MagicMock()
    repo = StepsLogRepo()
    monkeypatch.setattr(repo, '_ensure_sheet', lambda: ws)

    repo.append(ts=1.0, steps=100, source='auto')

    args, _ = ws.append_row.call_args
    assert args[0][1] == 'alex'  # config.DEFAULT_USER_ID


def test_steps_log_for_day_filters_by_user_and_date(monkeypatch):
    """for_day возвращает только записи нужного user_id + календарной даты."""
    today_ts = datetime(2026, 5, 1, 12, 0, 0).timestamp()
    today_ts_2 = datetime(2026, 5, 1, 18, 0, 0).timestamp()
    yesterday_ts = datetime(2026, 4, 30, 23, 0, 0).timestamp()

    ws = MagicMock()
    ws.get_all_values.return_value = [
        ['ts', 'user_id', 'steps', 'source'],         # header
        [str(today_ts), 'alex', '5000', 'manual'],
        [str(today_ts_2), 'alex', '7000', 'auto'],
        [str(today_ts), 'bob', '4000', 'manual'],     # другой user
        [str(yesterday_ts), 'alex', '12000', 'manual'],  # другой день
    ]
    repo = StepsLogRepo()
    monkeypatch.setattr(repo, '_ensure_sheet', lambda: ws)

    result = repo.for_day('2026-05-01', user_id='alex')

    assert len(result) == 2
    assert {r['steps'] for r in result} == {5000, 7000}
    assert all(r['user_id'] == 'alex' for r in result)


def test_steps_log_for_day_skips_malformed_rows(monkeypatch):
    """Битые строки (не числовой ts, нехватает колонок) — игнорируются."""
    ws = MagicMock()
    ws.get_all_values.return_value = [
        ['ts', 'user_id', 'steps', 'source'],
        ['not_a_number', 'alex', '5000', 'manual'],
        ['1', 'alex'],  # не хватает колонок
        [str(datetime(2026, 5, 1, 10, 0, 0).timestamp()), 'alex', 'not_int', 'manual'],
    ]
    repo = StepsLogRepo()
    monkeypatch.setattr(repo, '_ensure_sheet', lambda: ws)

    result = repo.for_day('2026-05-01', user_id='alex')
    assert result == []


def test_steps_log_for_day_returns_empty_when_log_empty(monkeypatch):
    ws = MagicMock()
    ws.get_all_values.return_value = [['ts', 'user_id', 'steps', 'source']]  # только header
    repo = StepsLogRepo()
    monkeypatch.setattr(repo, '_ensure_sheet', lambda: ws)

    assert repo.for_day('2026-05-01') == []
