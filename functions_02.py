from datetime import timedelta

from colorama import Fore, Style


# Минут в более крупных единицах (для time(x) — задача 2.10).
_MIN_PER_HOUR = 60
_MIN_PER_DAY = 24 * 60          # 1440
_MIN_PER_MONTH = 30 * 24 * 60   # 43 200
_MIN_PER_YEAR = 365 * 24 * 60   # 525 600


def _color(n: int) -> str:
    """Числовое значение в colorama LIGHTBLUE — единый стиль для всех частей time()."""
    return f'{Fore.LIGHTBLUE_EX}{n}{Style.RESET_ALL}'


def time(x: int) -> str:
    """Функция для преобразования времени в часы / дни / месяцы / годы.

    Принимает количество **минут**, возвращает строку с colorama-кодами.
    Используется для отображения стоимости активностей (gym/work/adventure)
    в cost-меню. Для countdown-таймеров используйте `format_timedelta(td)`.

    Формат (задача 2.10 — расширено в 0.2.1t):
    - x ≤ 60 минут              → "X мин."
    - 60 < x < 1440 (1 день)    → "H ч. M мин."
    - 1440 ≤ x < 43200 (30 дн)  → "D дн. H ч. M мин."
    - 43200 ≤ x < 525600 (1 г)  → "MO мес. D дн. H ч. M мин."
    - x ≥ 525600                → "Y г. MO мес. D дн. H ч. M мин."

    Логика "ведущие нули": если значение не превышает порог следующей
    единицы (например, x < 43200 → нет месяцев), эта единица не
    показывается. Если есть — показываются ВСЕ младшие компоненты,
    даже если они равны нулю (например, ровно 3 дня → "3 дн. 0 ч. 0 мин.").

    Месяц приближённо = 30 дней, год = 365 дней (упрощённо, как в
    `format_timedelta`).

    После 0.2.1s (задача 2.11): несклоняемое полное слово "час" заменено
    на сокращение "ч.", все единицы — сокращения с точкой ("дн.", "мес.",
    "г.").
    """
    if x <= 60:
        return f'{_color(x)} мин.'

    if x < _MIN_PER_DAY:
        h, m = divmod(x, _MIN_PER_HOUR)
        return f'{_color(h)} ч. {_color(m)} мин.'

    if x < _MIN_PER_MONTH:
        d, rest = divmod(x, _MIN_PER_DAY)
        h, m = divmod(rest, _MIN_PER_HOUR)
        return f'{_color(d)} дн. {_color(h)} ч. {_color(m)} мин.'

    if x < _MIN_PER_YEAR:
        mo, rest = divmod(x, _MIN_PER_MONTH)
        d, rest = divmod(rest, _MIN_PER_DAY)
        h, m = divmod(rest, _MIN_PER_HOUR)
        return f'{_color(mo)} мес. {_color(d)} дн. {_color(h)} ч. {_color(m)} мин.'

    y, rest = divmod(x, _MIN_PER_YEAR)
    mo, rest = divmod(rest, _MIN_PER_MONTH)
    d, rest = divmod(rest, _MIN_PER_DAY)
    h, m = divmod(rest, _MIN_PER_HOUR)
    return (f'{_color(y)} г. {_color(mo)} мес. {_color(d)} дн. '
            f'{_color(h)} ч. {_color(m)} мин.')


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
