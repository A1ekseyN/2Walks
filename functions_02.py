from datetime import timedelta

from colorama import Fore, Style


def time(x):
    # Функция для преобразования времени в часы и минуты.
    if x <= 60:
        return f'{Fore.LIGHTBLUE_EX}{x}{Style.RESET_ALL} мин.'
    elif x > 60:
        hours = int(x // 60)
        min = int(x % 60)
        return f'{Fore.LIGHTBLUE_EX}{hours}{Style.RESET_ALL} час {Fore.LIGHTBLUE_EX}{min}{Style.RESET_ALL} мин.'


# Константы длительности (секунды) для format_timedelta.
_YEAR_S = 365 * 24 * 3600
_MONTH_S = 30 * 24 * 3600
_WEEK_S = 7 * 24 * 3600
_DAY_S = 24 * 3600
_HOUR_S = 3600
_MINUTE_S = 60


def format_timedelta(td) -> str:
    """Форматирует timedelta / число секунд в строку с разбивкой по
    единицам времени: `Yг Mмес Wнед Dд H:MM:SS`. Месяц приближённо = 30
    дней, год = 365 дней (точная календарная логика не нужна — таймеры
    в игре максимум недели/месяцы при экстремальной прокачке).

    Принимает либо `datetime.timedelta`, либо число секунд (int / float).
    Отрицательные / нулевые значения → "0:00:00".

    Примеры:
        timedelta(seconds=45)            -> "0:00:45"
        timedelta(hours=17, minutes=25)  -> "17:25:00"
        timedelta(days=1, hours=5)       -> "1д 5:00:00"
        timedelta(days=8)                -> "1нед 1д 0:00:00"
        timedelta(days=35)               -> "1мес 5д 0:00:00"
        timedelta(days=400)              -> "1г 1мес 5д 0:00:00"
    """
    if isinstance(td, timedelta):
        total = int(td.total_seconds())
    else:
        total = int(td)

    if total <= 0:
        return "0:00:00"

    parts = []
    y, total = divmod(total, _YEAR_S)
    if y > 0:
        parts.append(f"{y}г")
    mo, total = divmod(total, _MONTH_S)
    if mo > 0:
        parts.append(f"{mo}мес")
    w, total = divmod(total, _WEEK_S)
    if w > 0:
        parts.append(f"{w}нед")
    d, total = divmod(total, _DAY_S)
    if d > 0:
        parts.append(f"{d}д")
    h, total = divmod(total, _HOUR_S)
    m, s = divmod(total, _MINUTE_S)
    parts.append(f"{h}:{m:02d}:{s:02d}")
    return " ".join(parts)
