"""Тесты history.py — лог значимых игровых событий (4.6).

Покрывают:
- Структуру event'а (`_build_event`).
- Local write в JSONL (через tmp_path).
- Sheets write через mocked `HistoryLogRepo`.
- Fail-silent поведение для Sheets.
- Что `log_event` действительно вызывает обе функции записи.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

import history
from history import _build_event, _write_local, _write_sheets, log_event


# ---------- _build_event ----------

def test_build_event_has_required_fields():
    """Event-dict содержит все обязательные поля (v, ts, date, time, user_id, game_version, type, payload)."""
    event = _build_event('test_event', {'foo': 'bar'})
    expected_keys = {'v', 'ts', 'date', 'time', 'user_id', 'game_version', 'type', 'payload'}
    assert set(event.keys()) == expected_keys


def test_build_event_schema_version_is_1():
    event = _build_event('test', {})
    assert event['v'] == history.EVENT_SCHEMA_VERSION
    assert event['v'] == 1


def test_build_event_user_id_is_default():
    """user_id берётся из config.DEFAULT_USER_ID. Сейчас 'alex'."""
    event = _build_event('test', {})
    from config import DEFAULT_USER_ID
    assert event['user_id'] == DEFAULT_USER_ID


def test_build_event_game_version_from_version_module():
    from version import VERSION
    event = _build_event('test', {})
    assert event['game_version'] == VERSION


def test_build_event_payload_passed_through():
    payload = {'salary': 40, 'hours': 4, 'vacancy': 'watchman'}
    event = _build_event('work_done', payload)
    assert event['payload'] == payload


def test_build_event_type_set():
    event = _build_event('skill_upgraded', {})
    assert event['type'] == 'skill_upgraded'


def test_build_event_ts_is_float():
    event = _build_event('test', {})
    assert isinstance(event['ts'], float)
    assert event['ts'] > 0


def test_build_event_date_format():
    """date в формате YYYY-MM-DD."""
    event = _build_event('test', {})
    import re
    assert re.match(r'^\d{4}-\d{2}-\d{2}$', event['date'])


def test_build_event_time_format():
    """time в формате HH:MM:SS."""
    event = _build_event('test', {})
    import re
    assert re.match(r'^\d{2}:\d{2}:\d{2}$', event['time'])


# ---------- _write_local (JSONL append) ----------

def test_write_local_appends_jsonl_line(tmp_path, monkeypatch):
    """Каждый вызов _write_local дописывает одну строку JSONL в файл."""
    log_file = tmp_path / 'history.jsonl'
    monkeypatch.setattr(history, 'HISTORY_FILE', str(log_file))

    event1 = {'v': 1, 'ts': 1.0, 'type': 'a', 'payload': {}}
    event2 = {'v': 1, 'ts': 2.0, 'type': 'b', 'payload': {'x': 1}}
    _write_local(event1)
    _write_local(event2)

    lines = log_file.read_text(encoding='utf-8').strip().split('\n')
    assert len(lines) == 2
    assert json.loads(lines[0]) == event1
    assert json.loads(lines[1]) == event2


def test_write_local_no_crash_on_io_error(tmp_path, monkeypatch, capsys):
    """Если файл не доступен на запись — log_event не валит игру (только warning)."""
    # Намеренно невалидный путь.
    monkeypatch.setattr(history, 'HISTORY_FILE', '/nonexistent_dir_xyz/history.jsonl')
    _write_local({'v': 1, 'ts': 1.0, 'type': 'test', 'payload': {}})
    out = capsys.readouterr().out
    assert 'history.jsonl write failed' in out


# ---------- _write_sheets (best-effort) ----------

def test_write_sheets_calls_repo_append(monkeypatch):
    """_write_sheets создаёт HistoryLogRepo и вызывает append."""
    mock_repo = MagicMock()
    mock_repo_class = MagicMock(return_value=mock_repo)
    monkeypatch.setattr('google_sheets_db.HistoryLogRepo', mock_repo_class)

    event = {'v': 1, 'ts': 1.0, 'date': '2026-05-08', 'time': '10:00:00',
             'user_id': 'test', 'game_version': '0.0.0', 'type': 'test',
             'payload': {}}
    _write_sheets(event)

    mock_repo_class.assert_called_once()
    mock_repo.append.assert_called_once_with(event)


def test_write_sheets_silent_on_exception(monkeypatch):
    """Если Sheets бросает исключение — _write_sheets молчит (best-effort)."""
    mock_repo = MagicMock()
    mock_repo.append.side_effect = ConnectionError('Sheets unavailable')
    mock_repo_class = MagicMock(return_value=mock_repo)
    monkeypatch.setattr('google_sheets_db.HistoryLogRepo', mock_repo_class)

    # Не должно бросать наружу.
    _write_sheets({'v': 1, 'ts': 1.0, 'date': '2026-05-08', 'time': '10:00:00',
                   'user_id': 'test', 'game_version': '0.0.0', 'type': 'test',
                   'payload': {}})


# ---------- log_event (full flow) ----------

def test_log_event_writes_local_and_sheets(tmp_path, monkeypatch):
    """log_event вызывает обе функции записи (local + Sheets)."""
    log_file = tmp_path / 'history.jsonl'
    monkeypatch.setattr(history, 'HISTORY_FILE', str(log_file))

    mock_repo = MagicMock()
    monkeypatch.setattr('google_sheets_db.HistoryLogRepo', MagicMock(return_value=mock_repo))

    log_event('work_done', salary=40, hours=4, vacancy='watchman')

    # Local: одна строка JSONL с правильными полями.
    line = log_file.read_text(encoding='utf-8').strip()
    parsed = json.loads(line)
    assert parsed['type'] == 'work_done'
    assert parsed['payload'] == {'salary': 40, 'hours': 4, 'vacancy': 'watchman'}

    # Sheets: append вызван 1 раз с тем же event.
    mock_repo.append.assert_called_once()
    sheets_event = mock_repo.append.call_args.args[0]
    assert sheets_event['type'] == 'work_done'
    assert sheets_event['payload'] == {'salary': 40, 'hours': 4, 'vacancy': 'watchman'}


def test_log_event_local_works_even_if_sheets_fails(tmp_path, monkeypatch):
    """При сбое Sheets local запись всё равно срабатывает."""
    log_file = tmp_path / 'history.jsonl'
    monkeypatch.setattr(history, 'HISTORY_FILE', str(log_file))

    mock_repo = MagicMock()
    mock_repo.append.side_effect = RuntimeError('boom')
    monkeypatch.setattr('google_sheets_db.HistoryLogRepo', MagicMock(return_value=mock_repo))

    log_event('test_event', x=1)
    # Local-файл должен содержать запись несмотря на failure Sheets.
    line = log_file.read_text(encoding='utf-8').strip()
    parsed = json.loads(line)
    assert parsed['type'] == 'test_event'
    assert parsed['payload'] == {'x': 1}


def test_log_event_with_no_payload(tmp_path, monkeypatch):
    """log_event без kwargs — payload = пустой dict."""
    log_file = tmp_path / 'history.jsonl'
    monkeypatch.setattr(history, 'HISTORY_FILE', str(log_file))
    monkeypatch.setattr('google_sheets_db.HistoryLogRepo', MagicMock())

    log_event('save')
    line = log_file.read_text(encoding='utf-8').strip()
    parsed = json.loads(line)
    assert parsed['type'] == 'save'
    assert parsed['payload'] == {}
