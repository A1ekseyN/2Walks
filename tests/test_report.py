"""Тесты для report.py — «пока тебя не было» summary (task 4.2)."""

import time

import pytest

from report import (
    INTERESTING_EVENT_TYPES,
    _extract_field,
    _format_event_cli,
    _format_event_web,
    build_away_report,
    build_report_view,
    format_report_cli,
    format_timedelta_simple,
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


def test_format_cli_drop_with_list_wrappers():
    """item-поля как list (legacy формат)."""
    event = {'type': 'drop',
             'payload': {'item': {'grade': ['b-grade'], 'item_type': ['ring'],
                                  'characteristic': ['speed'], 'bonus': [2]}}}
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
             'payload': {'item': {'grade': ['s'], 'item_type': ['necklace'],
                                  'characteristic': ['luck'], 'bonus': [5]}}}
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
