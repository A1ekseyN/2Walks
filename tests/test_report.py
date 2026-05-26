"""Тесты для report.py — «пока тебя не было» summary (task 4.2)."""

import time

import pytest

from report import (
    INTERESTING_EVENT_TYPES,
    _extract_field,
    _event_emoji_text,
    _format_event_cli,
    _format_event_web,
    build_away_report,
    build_report_view,
    format_report_cli,
    format_timedelta_simple,
    open_history_viewer,
    read_recent_history,
)


# --- INTERESTING_EVENT_TYPES ---

def test_interesting_types_contain_key_events():
    """Report должен включать work_done / skill_upgraded / drops / level_up / new_day."""
    assert 'work_done' in INTERESTING_EVENT_TYPES
    assert 'skill_upgraded' in INTERESTING_EVENT_TYPES
    assert 'adventure_done' in INTERESTING_EVENT_TYPES
    assert 'drop' in INTERESTING_EVENT_TYPES
    assert 'drop_auto_collected' in INTERESTING_EVENT_TYPES
    assert 'level_up' in INTERESTING_EVENT_TYPES
    assert 'new_day' in INTERESTING_EVENT_TYPES


def test_interesting_types_excludes_player_actions():
    """Player-initiated actions НЕ должны попадать (skill_alloc / bank ops / save)."""
    assert 'skill_alloc' not in INTERESTING_EVENT_TYPES
    assert 'bank_deposit' not in INTERESTING_EVENT_TYPES
    assert 'save' not in INTERESTING_EVENT_TYPES
    assert 'steps_set' not in INTERESTING_EVENT_TYPES


# --- format_timedelta_simple ---

def test_format_timedelta_minutes():
    assert format_timedelta_simple(60 * 5) == '5 мин'
    assert format_timedelta_simple(60 * 59) == '59 мин'


def test_format_timedelta_hours_only():
    assert format_timedelta_simple(60 * 60 * 2) == '2 ч'


def test_format_timedelta_hours_and_minutes():
    assert format_timedelta_simple(60 * 60 * 2 + 60 * 30) == '2 ч 30 мин'


def test_format_timedelta_days_only():
    assert format_timedelta_simple(60 * 60 * 24 * 3) == '3 дн'


def test_format_timedelta_days_and_hours():
    assert format_timedelta_simple(60 * 60 * 24 * 1 + 60 * 60 * 5) == '1 дн 5 ч'


def test_format_timedelta_negative_returns_zero():
    assert format_timedelta_simple(-100) == '0 мин'


# --- _extract_field ---

def test_extract_field_list_wrapper():
    """item['grade'] = ['s+'] → extract returns 's+'."""
    assert _extract_field({'grade': ['s+']}, 'grade') == 's+'


def test_extract_field_plain_value():
    """item['grade'] = 's+' (без обёртки) → возвращает 's+'."""
    assert _extract_field({'grade': 's+'}, 'grade') == 's+'


def test_extract_field_missing_key():
    assert _extract_field({}, 'grade') is None


def test_extract_field_empty_list():
    assert _extract_field({'grade': []}, 'grade') == []


# --- _format_event_cli ---

def test_format_cli_work_done():
    event = {'type': 'work_done',
             'payload': {'vacancy': 'watchman', 'hours': 4, 'salary': 40.0}}
    out = _format_event_cli(event)
    assert 'Watchman' in out
    assert '4 ч' in out
    assert '40' in out


def test_format_cli_skill_upgraded():
    event = {'type': 'skill_upgraded',
             'payload': {'skill': 'stamina', 'from_level': 4, 'to_level': 5}}
    out = _format_event_cli(event)
    assert 'Stamina' in out
    assert 'lvl 4 → 5' in out


def test_format_cli_drop_flat_payload():
    """4.6.2 — drop payload плоский (как реально пишет log_event), не nested item."""
    event = {'type': 'drop',
             'payload': {'adventure': 'walk_easy', 'grade': 'b-grade',
                         'item_type': 'ring', 'characteristic': 'speed',
                         'bonus': 2, 'quality': 80.0, 'price': 30}}
    out = _format_event_cli(event)
    assert 'b-grade' in out
    assert 'Ring' in out
    assert '+2' in out
    assert 'speed' in out


def test_format_cli_level_up():
    event = {'type': 'level_up', 'payload': {'from_level': 9, 'to_level': 10}}
    out = _format_event_cli(event)
    # colorama escape вокруг '10', проверяем components отдельно.
    assert 'Level up:' in out
    assert '9' in out
    assert '10' in out
    assert 'skill point' in out


def test_format_cli_new_day():
    event = {'type': 'new_day', 'payload': {'new_date': '2026-05-21'}}
    out = _format_event_cli(event)
    assert '2026-05-21' in out


def test_format_cli_unknown_type_fallback():
    """Незнакомый тип — fallback на raw text."""
    event = {'type': 'mystery_event', 'payload': {'x': 1}}
    out = _format_event_cli(event)
    assert 'mystery_event' in out


# --- _format_event_web ---

def test_format_web_work_done_returns_dict():
    event = {'type': 'work_done',
             'payload': {'vacancy': 'factory', 'hours': 8, 'salary': 64.0}}
    out = _format_event_web(event)
    assert out['emoji'] == '🏭'
    assert 'Factory' in out['text']
    assert '8 ч' in out['text']


def test_format_web_skill_upgraded():
    event = {'type': 'skill_upgraded',
             'payload': {'skill': 'luck_skill', 'from_level': 1, 'to_level': 2}}
    out = _format_event_web(event)
    assert out['emoji'] == '🏋'
    assert 'Luck_Skill' in out['text']
    assert 'lvl 1 → 2' in out['text']


def test_format_web_drop():
    event = {'type': 'drop',
             'payload': {'adventure': 'walk_20k', 'grade': 's', 'item_type': 'necklace',
                         'characteristic': 'luck', 'bonus': 5, 'quality': 90.0, 'price': 200}}
    out = _format_event_web(event)
    assert out['emoji'] == '🎁'
    assert 'Necklace' in out['text']
    assert '+5' in out['text']


def test_format_web_no_colorama_codes():
    """Web format не должен содержать ANSI escape codes."""
    event = {'type': 'work_done',
             'payload': {'vacancy': 'watchman', 'hours': 1, 'salary': 2.0}}
    out = _format_event_web(event)
    assert '\x1b[' not in out['text']  # ANSI escape
    assert '\x1b[' not in out['emoji']


# --- build_away_report ---

def test_build_away_report_zero_since_ts():
    """since_ts=0 → пустой list (legacy save без timestamp)."""
    assert build_away_report(0.0) == []


def test_build_away_report_negative_since_ts():
    """Отрицательный since_ts (защита от мусора) → пустой list."""
    assert build_away_report(-1.0) == []


def test_build_away_report_filters_interesting_only(monkeypatch):
    """Sheets history содержит mix events — возвращаем только interesting."""
    import google_sheets_db

    fake_events = [
        {'ts': 100.0, 'type': 'work_done', 'payload': {}},
        {'ts': 200.0, 'type': 'save', 'payload': {}},  # uninteresting
        {'ts': 300.0, 'type': 'skill_upgraded', 'payload': {}},
        {'ts': 400.0, 'type': 'skill_alloc', 'payload': {}},  # uninteresting
    ]
    monkeypatch.setattr(google_sheets_db.HistoryLogRepo, 'since',
                        lambda self, ts: fake_events)
    result = build_away_report(50.0)
    assert len(result) == 2
    assert {e['type'] for e in result} == {'work_done', 'skill_upgraded'}


def test_build_away_report_empty_when_no_interesting(monkeypatch):
    import google_sheets_db
    monkeypatch.setattr(google_sheets_db.HistoryLogRepo, 'since',
                        lambda self, ts: [
                            {'ts': 100.0, 'type': 'save', 'payload': {}},
                            {'ts': 200.0, 'type': 'steps_set', 'payload': {}},
                        ])
    assert build_away_report(50.0) == []


# --- format_report_cli ---

def test_format_report_cli_empty_returns_empty_string():
    assert format_report_cli([], 100.0) == ''


def test_format_report_cli_with_events():
    events = [{'type': 'work_done',
               'payload': {'vacancy': 'watchman', 'hours': 4, 'salary': 40.0}}]
    out = format_report_cli(events, time.time() - 3600)  # 1 час назад
    assert 'Пока тебя не было' in out
    assert 'Watchman' in out
    assert '═' in out  # рамка


# --- build_report_view ---

def test_build_report_view_empty():
    """Пустой events → has_events=False, без doer полей."""
    view = build_report_view([], 100.0)
    assert view == {'has_events': False}


def test_build_report_view_with_events():
    """С events → has_events=True, items список, meta строки."""
    events = [
        {'type': 'work_done',
         'payload': {'vacancy': 'factory', 'hours': 3, 'salary': 24.0}},
        {'type': 'level_up', 'payload': {'from_level': 5, 'to_level': 6}},
    ]
    view = build_report_view(events, time.time() - 7200)  # 2 часа
    assert view['has_events'] is True
    assert view['count'] == 2
    assert len(view['items']) == 2
    assert '2 ч' in view['elapsed_label']
    assert view['items'][0]['emoji'] == '🏭'
    assert view['items'][1]['emoji'] == '⭐'


# --- 4.6.2 — read_recent_history + open_history_viewer + extended formatter ---

def test_event_emoji_text_covers_new_types():
    assert _event_emoji_text({'type': 'deposit',
                              'payload': {'amount': 100, 'balance_after': 100}})[0] == '🏦'
    assert _event_emoji_text({'type': 'item_bought',
                              'payload': {'item_type': 'shoes', 'grade': 'c-grade', 'cost': 50}})[0] == '🛒'
    e, t = _event_emoji_text({'type': 'sync_conflict',
                              'payload': {'source': 'cli', 'choice': 'reload'}})
    assert e == '⚠️' and 'reload' in t
    # Fallback для незнакомого типа.
    e, t = _event_emoji_text({'type': 'mystery', 'payload': {'x': 1}})
    assert e == '•' and 'mystery' in t


def test_read_recent_history_sheets_primary_newest_first(monkeypatch):
    import google_sheets_db as gdb
    events = [
        {'ts': 1.0, 'type': 'work_done', 'payload': {}},
        {'ts': 3.0, 'type': 'level_up', 'payload': {}},
        {'ts': 2.0, 'type': 'new_day', 'payload': {}},
    ]
    monkeypatch.setattr(gdb.HistoryLogRepo, 'since', lambda self, ts: list(events))
    out = read_recent_history(limit=2)
    assert [e['ts'] for e in out] == [3.0, 2.0]  # newest-first, limited


def test_read_recent_history_falls_back_to_jsonl(monkeypatch, tmp_path):
    import json
    import google_sheets_db as gdb
    import config

    def _boom(self, ts):
        raise RuntimeError('net down')
    monkeypatch.setattr(gdb.HistoryLogRepo, 'since', _boom)
    f = tmp_path / 'history.jsonl'
    f.write_text(json.dumps({'ts': 5.0, 'type': 'save', 'payload': {}}) + '\n', encoding='utf-8')
    monkeypatch.setattr(config, 'HISTORY_FILE', str(f))
    out = read_recent_history()
    assert len(out) == 1 and out[0]['type'] == 'save'


def test_read_recent_history_empty_when_all_unavailable(monkeypatch, tmp_path):
    import google_sheets_db as gdb
    import config
    monkeypatch.setattr(gdb.HistoryLogRepo, 'since', lambda self, ts: [])
    monkeypatch.setattr(config, 'HISTORY_FILE', str(tmp_path / 'nope.jsonl'))
    assert read_recent_history() == []


def test_open_history_viewer_prints_events(monkeypatch, capsys):
    import datetime as _dt
    ts = _dt.datetime(2026, 5, 26, 14, 30).timestamp()
    monkeypatch.setattr('report.read_recent_history',
                        lambda limit=None: [{'ts': ts, 'type': 'work_done',
                                             'payload': {'vacancy': 'watchman', 'hours': 4, 'salary': 40.0}}])
    monkeypatch.setattr('builtins.input', lambda *a: '0')  # сразу выход
    open_history_viewer(None)
    out = capsys.readouterr().out
    assert 'История' in out
    assert 'Watchman' in out
    assert '2026-05-26 14:30' in out  # дата из ts (фикс [? ?])


def test_open_history_viewer_empty(monkeypatch, capsys):
    monkeypatch.setattr('report.read_recent_history', lambda limit=None: [])
    monkeypatch.setattr('builtins.input', lambda *a: '0')
    open_history_viewer(None)
    out = capsys.readouterr().out
    assert 'история пуста' in out


def _fake_events(n):
    """n событий с убывающим ts (newest-first как отдаёт read_recent_history)."""
    return [{'ts': float(n - i), 'type': 'save', 'payload': {}} for i in range(n)]


def test_history_viewer_pagination_next_page(monkeypatch, capsys):
    """`m` → следующая страница; страница X/Y растёт."""
    monkeypatch.setattr('report.read_recent_history', lambda limit=None: _fake_events(45))
    # page_size default 20 → 3 страницы. m, m, затем выход.
    inputs = iter(['m', 'm', '0'])
    monkeypatch.setattr('builtins.input', lambda *a: next(inputs))
    open_history_viewer(None)
    out = capsys.readouterr().out
    assert 'страница 1/3' in out
    assert 'страница 2/3' in out
    assert 'страница 3/3' in out


def test_history_viewer_page_size_digit(monkeypatch, capsys):
    """Цифра N → размер страницы N×10, сброс на стр.1."""
    monkeypatch.setattr('report.read_recent_history', lambda limit=None: _fake_events(45))
    inputs = iter(['5', '0'])  # 5 → 50 на страницу → всё на 1 странице
    monkeypatch.setattr('builtins.input', lambda *a: next(inputs))
    open_history_viewer(None)
    out = capsys.readouterr().out
    assert 'по 50 на стр.' in out
    assert 'страница 1/1' in out


def test_history_viewer_last_page_more_noop(monkeypatch, capsys):
    """`m` на последней странице → сообщение, не падает."""
    monkeypatch.setattr('report.read_recent_history', lambda limit=None: _fake_events(5))
    inputs = iter(['m', '0'])  # 5 событий = 1 страница; m → последняя
    monkeypatch.setattr('builtins.input', lambda *a: next(inputs))
    open_history_viewer(None)
    out = capsys.readouterr().out
    assert 'последняя страница' in out
