"""Тесты для persistence._parse_value — unified parser CSV ↔ Sheets (1.4.2).

Покрывает все ветки приоритетной цепочки парсинга:
1. Non-string → as-is
2. Empty string → None
3. JSON (int/float/bool/null/dict/list)
4. ast.literal_eval (Python repr с single quotes)
5. Manual type detection (legacy compat)
6. Datetime для DATE_KEYS
7. Plain string fallback
"""

from datetime import datetime

from persistence import _DATETIME_FMT, _parse_value


# --- 1. Non-string passthrough ---

def test_parse_value_returns_int_as_is():
    assert _parse_value(42) == 42


def test_parse_value_returns_float_as_is():
    assert _parse_value(3.14) == 3.14


def test_parse_value_returns_dict_as_is():
    assert _parse_value({'a': 1}) == {'a': 1}


def test_parse_value_returns_none_as_is():
    assert _parse_value(None) is None


# --- 2. Empty string ---

def test_parse_value_empty_string_returns_none():
    assert _parse_value('') is None


# --- 3. JSON parsing ---

def test_parse_value_json_int():
    assert _parse_value('42') == 42


def test_parse_value_json_negative_int():
    assert _parse_value('-7') == -7


def test_parse_value_json_float():
    assert _parse_value('1.5') == 1.5


def test_parse_value_json_lowercase_bool():
    assert _parse_value('true') is True
    assert _parse_value('false') is False


def test_parse_value_json_null():
    assert _parse_value('null') is None


def test_parse_value_json_list():
    assert _parse_value('[1, 2, 3]') == [1, 2, 3]


def test_parse_value_json_dict():
    assert _parse_value('{"a": 1, "b": "x"}') == {'a': 1, 'b': 'x'}


def test_parse_value_json_nested_dict():
    assert _parse_value('{"outer": {"inner": [1, 2]}}') == {'outer': {'inner': [1, 2]}}


# --- 4. ast.literal_eval (Python repr с single quotes) ---

def test_parse_value_python_repr_dict():
    """Sheets иногда хранит dict через str(dict) с одинарными кавычками."""
    result = _parse_value("{'item_name': ['ring'], 'bonus': [5]}")
    assert result == {'item_name': ['ring'], 'bonus': [5]}


def test_parse_value_python_repr_list_with_dicts():
    """Inventory как list of dicts с single quotes — legacy CSV/Sheets формат."""
    result = _parse_value("[{'a': 1}, {'b': 2}]")
    assert result == [{'a': 1}, {'b': 2}]


# --- 5. Manual type detection (fallback после JSON/ast) ---

def test_parse_value_manual_capital_True():
    """'True'/'False' с заглавной — JSON падает, ast возвращает bool, manual fallback тоже работает."""
    assert _parse_value('True') is True
    assert _parse_value('False') is False


def test_parse_value_plain_string():
    """Не парсится ни как JSON ни как Python — plain string."""
    assert _parse_value('hello world') == 'hello world'


def test_parse_value_string_with_special_chars():
    assert _parse_value('walk_easy') == 'walk_easy'


# --- 6. Datetime parsing для DATE_KEYS ---

def test_parse_value_datetime_with_matching_key():
    """skill_training_time_end — один из DATE_KEYS, datetime парсится."""
    dt_str = '2026-05-20 14:30:00.123456'
    result = _parse_value(dt_str, key='skill_training_time_end')
    assert isinstance(result, datetime)
    assert result.year == 2026
    assert result.month == 5
    assert result.microsecond == 123456


def test_parse_value_datetime_format_matches_dt_fmt():
    """Format соответствует _DATETIME_FMT — round-trip через strftime."""
    dt = datetime(2026, 5, 20, 14, 30, 0, 123456)
    s = dt.strftime(_DATETIME_FMT)
    result = _parse_value(s, key='working_end')
    assert result == dt


def test_parse_value_datetime_without_matching_key_returns_string():
    """date_last_enter не в DATE_KEYS (хранится как YYYY-MM-DD string) — возвращает string."""
    result = _parse_value('2026-05-20 14:30:00.123456', key='date_last_enter')
    # Without key match → fall to plain string.
    assert result == '2026-05-20 14:30:00.123456'


def test_parse_value_datetime_invalid_format_returns_string():
    """Кривой datetime string + matching key → fall to plain string (no crash)."""
    result = _parse_value('not-a-date', key='skill_training_time_end')
    assert result == 'not-a-date'


# --- 7. Edge cases / regression ---

def test_parse_value_string_looking_like_number_with_leading_zero():
    """'007' — isdigit() returns True. JSON parses as int → 7."""
    assert _parse_value('007') == 7


def test_parse_value_quoted_string_in_json_returns_original():
    """'"text"' → JSON парсит как string ("text") → fall through (мы не возвращаем
    string-результаты JSON / ast). Manual checks fail → возвращает оригинал
    с кавычками. Это OK — quoted strings в сейвах не встречаются на практике,
    но если попадутся — не теряем содержимое."""
    result = _parse_value('"text"')
    assert result == '"text"'  # original kept verbatim


def test_parse_value_empty_list_string():
    assert _parse_value('[]') == []


def test_parse_value_empty_dict_string():
    assert _parse_value('{}') == {}


def test_parse_value_zero():
    assert _parse_value('0') == 0


def test_parse_value_negative_float():
    assert _parse_value('-3.14') == -3.14


def test_parse_value_no_key_argument_skips_datetime():
    """Без key=… datetime parsing не вызывается даже для valid формата."""
    result = _parse_value('2026-05-20 14:30:00.123456')
    # Plain string — нет datetime trigger.
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# 1.4.3 (0.2.5) — state.json primary + CSV legacy fallback
# ---------------------------------------------------------------------------

def test_load_state_json_round_trip(tmp_path, monkeypatch):
    """save → load round-trip через state.json."""
    import json
    from persistence import STATE_JSON_PATH, load_state_json

    monkeypatch.chdir(tmp_path)
    data = {'energy': 50, 'money': 100.5, 'inventory': [{'a': 1}], 'last_modified': 123.45}
    (tmp_path / STATE_JSON_PATH).write_text(json.dumps(data), encoding='utf-8')
    loaded = load_state_json()
    assert loaded == data


def test_load_state_json_converts_datetime_strings(tmp_path, monkeypatch):
    """Datetime поля (из _DATETIME_KEYS) приходят как strftime str → конвертируется обратно."""
    import json
    from persistence import STATE_JSON_PATH, load_state_json

    monkeypatch.chdir(tmp_path)
    data = {'working_end': '2026-05-01 14:30:00.000000', 'energy': 50}
    (tmp_path / STATE_JSON_PATH).write_text(json.dumps(data), encoding='utf-8')
    loaded = load_state_json()
    assert loaded['working_end'] == datetime(2026, 5, 1, 14, 30, 0)
    assert loaded['energy'] == 50


def test_load_state_json_non_dict_raises(tmp_path, monkeypatch):
    """state.json содержит не-dict (например list) → ValueError."""
    import json
    import pytest
    from persistence import STATE_JSON_PATH, load_state_json

    monkeypatch.chdir(tmp_path)
    (tmp_path / STATE_JSON_PATH).write_text(json.dumps([1, 2, 3]), encoding='utf-8')
    with pytest.raises(ValueError):
        load_state_json()


def test_load_state_json_missing_file_raises(tmp_path, monkeypatch):
    """Если state.json нет → FileNotFoundError (caller делает CSV fallback)."""
    import pytest
    from persistence import load_state_json

    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        load_state_json()


def test_load_local_fallback_prefers_state_json(tmp_path, monkeypatch):
    """state.json и CSV оба присутствуют → читаем state.json (primary)."""
    import csv as csv_mod
    import json
    from persistence import (
        CHARACTERISTIC_CSV_PATH,
        STATE_JSON_PATH,
        _load_local_fallback,
    )

    monkeypatch.chdir(tmp_path)
    (tmp_path / STATE_JSON_PATH).write_text(
        json.dumps({'energy': 50, 'source': 'json'}), encoding='utf-8'
    )
    with open(tmp_path / CHARACTERISTIC_CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv_mod.DictWriter(f, fieldnames=['energy', 'source'])
        writer.writeheader()
        writer.writerow({'energy': 99, 'source': 'csv'})

    loaded = _load_local_fallback()
    assert loaded['source'] == 'json'  # primary
    assert loaded['energy'] == 50


def test_load_local_fallback_csv_when_no_json(tmp_path, monkeypatch, capsys):
    """state.json отсутствует → CSV legacy fallback."""
    import csv as csv_mod
    from persistence import CHARACTERISTIC_CSV_PATH, _load_local_fallback

    monkeypatch.chdir(tmp_path)
    with open(tmp_path / CHARACTERISTIC_CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv_mod.DictWriter(f, fieldnames=['energy', 'source'])
        writer.writeheader()
        writer.writerow({'energy': 99, 'source': 'csv'})

    loaded = _load_local_fallback()
    assert loaded['source'] == 'csv'
    # CSV legacy notice печатается.
    out = capsys.readouterr().out
    assert 'legacy fallback' in out


def test_load_local_fallback_empty_when_neither(tmp_path, monkeypatch):
    """Ни state.json, ни CSV → пустой dict."""
    from persistence import _load_local_fallback

    monkeypatch.chdir(tmp_path)
    loaded = _load_local_fallback()
    assert loaded == {}


def test_json_default_datetime():
    """_json_default конвертирует datetime в legacy strftime формат."""
    from persistence import _json_default

    dt = datetime(2026, 5, 1, 14, 30, 0)
    assert _json_default(dt) == '2026-05-01 14:30:00.000000'


def test_json_default_raises_for_unsupported_type():
    """_json_default raises TypeError для unsupported types (object, set и т.п.)."""
    import pytest
    from persistence import _json_default

    with pytest.raises(TypeError):
        _json_default(object())
