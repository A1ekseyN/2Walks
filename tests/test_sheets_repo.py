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
    StepsLogRepo,
    _format_steps_entry,
    _rows_to_state_dict,
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

def _mock_worksheet(values=None):
    ws = MagicMock()
    ws.get_all_values.return_value = values or []
    return ws


def _mock_repo_with_ws(repo_cls, ws, monkeypatch):
    repo = repo_cls()
    monkeypatch.setattr(repo, '_worksheet', lambda: ws)
    return repo


def test_game_state_repo_save_calls_clear_then_update(monkeypatch):
    ws = _mock_worksheet()
    repo = _mock_repo_with_ws(GameStateRepo, ws, monkeypatch)
    repo.save({'energy': 50})

    ws.clear.assert_called_once()
    ws.update.assert_called_once()
    rows_passed = ws.update.call_args[0][0]
    assert rows_passed[0] == ['Key', 'Value']
    assert ['energy', 50] in rows_passed


def test_game_state_repo_load_skips_header(monkeypatch):
    ws = _mock_worksheet([['Key', 'Value'], ['energy', '50'], ['money', '100']])
    repo = _mock_repo_with_ws(GameStateRepo, ws, monkeypatch)
    data = repo.load()
    assert data == {'energy': 50, 'money': 100}


# ----- StepsLogRepo (mock gspread) -----

def test_steps_log_append_calls_append_row(monkeypatch):
    ws = MagicMock()
    repo = StepsLogRepo()
    monkeypatch.setattr(repo, '_ensure_sheet', lambda: ws)

    repo.append(ts=1746124425.5, steps=5000, source='manual', user_id='alex')

    ws.append_row.assert_called_once()
    args, kwargs = ws.append_row.call_args
    assert args[0] == [1746124425.5, 'alex', 5000, 'manual']
    assert kwargs.get('value_input_option') == 'USER_ENTERED'


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
