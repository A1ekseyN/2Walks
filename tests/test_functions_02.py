"""Тесты functions_02.py — formatter'ов времени.

Существующая `time(x)` (минуты → "H час M мин.") используется для
длительностей активностей; не тестируется здесь — это legacy display
helper с colorama-кодами, формат не меняется.

Новый `format_timedelta(td)` (0.2.1i / задача 2.10) форматирует timedelta
или число секунд в `Yг Mмес Wнед Dд H:MM:SS` для игровых таймеров (work
shift, training, adventure).
"""

from datetime import timedelta

from functions_02 import format_timedelta


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
