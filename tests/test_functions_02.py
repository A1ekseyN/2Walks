"""Тесты functions_02.py — formatter'ов времени.

Существующая `time(x)` (минуты → "H час M мин.") используется для
длительностей активностей; не тестируется здесь — это legacy display
helper с colorama-кодами, формат не меняется.

Новый `format_timedelta(td)` (0.2.1i / задача 2.10) форматирует timedelta
или число секунд в `Yг Mмес Wнед Dд H:MM:SS` для игровых таймеров (work
shift, training, adventure).
"""

import re
from datetime import timedelta

from functions_02 import format_hours, format_timedelta, time as time_fmt


# ----- Edge cases -----

def test_format_timedelta_zero():
    assert format_timedelta(timedelta(0)) == "0:00:00"


def test_format_timedelta_negative():
    """Отрицательное значение → 0:00:00 (как JS-формул в dashboard)."""
    assert format_timedelta(timedelta(seconds=-5)) == "0:00:00"
    assert format_timedelta(-100) == "0:00:00"


def test_format_timedelta_accepts_int():
    assert format_timedelta(45) == "0:00:45"
    assert format_timedelta(3600) == "1:00:00"


def test_format_timedelta_accepts_float():
    assert format_timedelta(45.7) == "0:00:45"  # truncated


# ----- Менее суток (без префиксов) -----

def test_format_timedelta_seconds_only():
    assert format_timedelta(timedelta(seconds=45)) == "0:00:45"


def test_format_timedelta_minutes_seconds():
    assert format_timedelta(timedelta(minutes=2, seconds=30)) == "0:02:30"


def test_format_timedelta_hours_minutes_seconds():
    assert format_timedelta(timedelta(hours=17, minutes=25, seconds=42)) == "17:25:42"


def test_format_timedelta_just_under_day():
    assert format_timedelta(timedelta(hours=23, minutes=59, seconds=59)) == "23:59:59"


# ----- Дни -----

def test_format_timedelta_one_day_exact():
    assert format_timedelta(timedelta(days=1)) == "1д 0:00:00"


def test_format_timedelta_days_with_time():
    assert format_timedelta(timedelta(days=1, hours=5)) == "1д 5:00:00"


def test_format_timedelta_multiple_days_under_week():
    assert format_timedelta(timedelta(days=3, hours=12, minutes=30)) == "3д 12:30:00"


# ----- Недели -----

def test_format_timedelta_one_week():
    assert format_timedelta(timedelta(days=7)) == "1нед 0:00:00"


def test_format_timedelta_week_plus_days():
    assert format_timedelta(timedelta(days=8)) == "1нед 1д 0:00:00"


def test_format_timedelta_multiple_weeks():
    assert format_timedelta(timedelta(days=21)) == "3нед 0:00:00"


# ----- Месяцы (30 дней) -----

def test_format_timedelta_one_month():
    assert format_timedelta(timedelta(days=30)) == "1мес 0:00:00"


def test_format_timedelta_month_plus_days():
    # 35 дней = 1мес (30) + 5д
    assert format_timedelta(timedelta(days=35)) == "1мес 5д 0:00:00"


def test_format_timedelta_month_plus_week_plus_days():
    # 39 дней = 1мес (30) + 1нед (7) + 2д
    assert format_timedelta(timedelta(days=39)) == "1мес 1нед 2д 0:00:00"


# ----- Годы (365 дней) -----

def test_format_timedelta_one_year():
    assert format_timedelta(timedelta(days=365)) == "1г 0:00:00"


def test_format_timedelta_year_plus_month_plus_week_plus_day():
    # 400 дней = 1г (365) + 1мес (30) + 5д
    assert format_timedelta(timedelta(days=400)) == "1г 1мес 5д 0:00:00"


def test_format_timedelta_year_plus_full_time():
    # 1 год + 5 часов 30 минут.
    assert format_timedelta(timedelta(days=365, hours=5, minutes=30)) == "1г 5:30:00"


# ----- Realistic game timer values -----

def test_format_timedelta_typical_work_shift():
    """Watchman 8 часов + speed-бонус 30% → ~5 часов 36 минут."""
    assert format_timedelta(timedelta(hours=5, minutes=36)) == "5:36:00"


def test_format_timedelta_long_training():
    """Skill level 30 без speed-бонуса = 9999 минут × 60 ≈ 6.94 дня."""
    assert format_timedelta(timedelta(minutes=9999)) == "6д 22:39:00"


def test_format_timedelta_extreme_extension():
    """Гипотетический extension смены до 100 часов → 4д 4:00:00."""
    assert format_timedelta(timedelta(hours=100)) == "4д 4:00:00"


# ---------------------------------------------------------------------------
# time(x) — форматтер минут для cost-меню Gym/Work/Adventure (задача 2.10).
# Принимает int минут, возвращает строку с colorama-кодами. Тесты используют
# regex-strip ANSI-escape для сравнения чистого текста.
# ---------------------------------------------------------------------------

_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')


def _strip(s: str) -> str:
    """Убирает ANSI-escape (colorama) для сравнения чистого текста."""
    return _ANSI_RE.sub('', s)


# ----- minutes only -----

def test_time_minutes_only():
    """0 < x ≤ 60 → "X мин."."""
    assert _strip(time_fmt(5)) == "5 мин."
    assert _strip(time_fmt(60)) == "60 мин."  # граничный случай


# ----- hours + minutes (no days) -----

def test_time_under_day():
    """60 < x < 1440 → "H ч. M мин."."""
    # 90 мин = 1 ч 30 мин
    assert _strip(time_fmt(90)) == "1 ч. 30 мин."
    # 120 мин = 2 ч 0 мин
    assert _strip(time_fmt(120)) == "2 ч. 0 мин."
    # 1439 мин = 23 ч 59 мин — последний под суткой
    assert _strip(time_fmt(1439)) == "23 ч. 59 мин."


# ----- days + hours + minutes (no months) -----

def test_time_with_days_exact():
    """Ровно 1440 мин = 1 дн. — все младшие компоненты показываются нулями."""
    assert _strip(time_fmt(1440)) == "1 дн. 0 ч. 0 мин."


def test_time_with_days_and_partial():
    """skill_lvl 19 ≈ 2890 мин = 2 дн. 0 ч. 10 мин. (пример из TASKS 2.10)."""
    assert _strip(time_fmt(2890)) == "2 дн. 0 ч. 10 мин."


def test_time_skill_lvl_30():
    """skill_training_table[30]['time'] = 6000 мин = 4 дн. 4 ч. 0 мин."""
    assert _strip(time_fmt(6000)) == "4 дн. 4 ч. 0 мин."


def test_time_just_under_month():
    """43199 мин < 30 дн — без месяца. 43200 мин = 30*1440 → 1 мес."""
    # 43199 = 29 дн 23 ч 59 мин (29*1440 = 41760, 43199-41760 = 1439 → 23ч 59мин)
    assert _strip(time_fmt(43199)) == "29 дн. 23 ч. 59 мин."


# ----- months + days + ... (no years) -----

def test_time_one_month_exact():
    """43200 мин (30 дней) = 1 мес. 0 дн. 0 ч. 0 мин."""
    assert _strip(time_fmt(43200)) == "1 мес. 0 дн. 0 ч. 0 мин."


def test_time_with_months_partial():
    """45 дней = 1 мес. 15 дн. 0 ч. 0 мин."""
    assert _strip(time_fmt(45 * 1440)) == "1 мес. 15 дн. 0 ч. 0 мин."


def test_time_just_under_year():
    """525599 мин (< 365 дней) — без года, с месяцами/днями."""
    # 525599 = 12 мес (12*43200 = 518400), остаток 7199 = 4 дн 23 ч 59 мин
    assert _strip(time_fmt(525599)) == "12 мес. 4 дн. 23 ч. 59 мин."


# ----- years + ... -----

def test_time_one_year_exact():
    """525600 мин (365 дней) = 1 г. 0 мес. 0 дн. 0 ч. 0 мин."""
    assert _strip(time_fmt(525600)) == "1 г. 0 мес. 0 дн. 0 ч. 0 мин."


def test_time_year_plus_months_days():
    """1 год + 1 мес + 5 дн + 3 ч + 30 мин."""
    x = 525600 + 43200 + 5 * 1440 + 3 * 60 + 30
    assert _strip(time_fmt(x)) == "1 г. 1 мес. 5 дн. 3 ч. 30 мин."


# ----- colorama не теряется -----

def test_time_contains_colorama_codes():
    """Числа всё ещё обёрнуты в colorama LIGHTBLUE."""
    out = time_fmt(90)  # 1 ч. 30 мин.
    assert '\x1b[' in out  # есть ANSI-escape


# ---------------------------------------------------------------------------
# format_hours(hours) — форматтер часов для web summary смены работы
# (0.2.1v). Стиль аналогичен time(), но без минут и без colorama.
# ---------------------------------------------------------------------------

def test_format_hours_zero():
    """0 часов → "0 ч." (граничный случай)."""
    assert format_hours(0) == "0 ч."


def test_format_hours_one():
    assert format_hours(1) == "1 ч."


def test_format_hours_under_day():
    """1 ≤ h < 24 → "X ч."."""
    assert format_hours(8) == "8 ч."
    assert format_hours(23) == "23 ч."


def test_format_hours_one_day_exact():
    """24 часа = 1 дн. 0 ч. (ведущие нули — все младшие компоненты показываются)."""
    assert format_hours(24) == "1 дн. 0 ч."


def test_format_hours_typical_work_shift():
    """71 час = 2 дн. 23 ч. (пример из dashboard, смена с продлениями)."""
    assert format_hours(71) == "2 дн. 23 ч."


def test_format_hours_just_under_month():
    """719 часов < 30 дней → без месяца. 29 дн. 23 ч."""
    assert format_hours(719) == "29 дн. 23 ч."


def test_format_hours_one_month_exact():
    """720 часов (30 дней) = 1 мес. 0 дн. 0 ч."""
    assert format_hours(720) == "1 мес. 0 дн. 0 ч."


def test_format_hours_month_plus_partial():
    """720 + 5*24 + 3 = 863 часа = 1 мес. 5 дн. 3 ч."""
    assert format_hours(720 + 5 * 24 + 3) == "1 мес. 5 дн. 3 ч."


def test_format_hours_just_under_year():
    """8759 часов (< 365 дней) — без года, с месяцами/днями."""
    # 8759 = 12 мес (12*720 = 8640), остаток 119 = 4 дн. 23 ч.
    assert format_hours(8759) == "12 мес. 4 дн. 23 ч."


def test_format_hours_one_year_exact():
    """8760 часов (365 дней) = 1 г. 0 мес. 0 дн. 0 ч."""
    assert format_hours(8760) == "1 г. 0 мес. 0 дн. 0 ч."


def test_format_hours_year_plus_full():
    """1 год + 1 мес + 5 дн + 3 ч."""
    h = 8760 + 720 + 5 * 24 + 3
    assert format_hours(h) == "1 г. 1 мес. 5 дн. 3 ч."


def test_format_hours_no_colorama():
    """Plain text — никаких ANSI-escape, идёт прямо в HTML."""
    out = format_hours(71)
    assert '\x1b[' not in out
