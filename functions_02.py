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


def format_minutes(x: int) -> str:
    """Plain-text версия `time(x)` без colorama — для web template'ов
    (HTML / Jinja). Та же логика разбивки на units (мин / ч / дн / мес / г),
    но без ANSI escape sequences.

    Принимает количество **минут**, возвращает обычную строку.

    Примеры:
        format_minutes(45)    → "45 мин."
        format_minutes(103)   → "1 ч. 43 мин."
        format_minutes(1500)  → "1 дн. 1 ч. 0 мин."
        format_minutes(50000) → "1 мес. 4 дн. 17 ч. 20 мин."

    Зарегистрировано как Jinja global в web/main.py (4.48.3 polish, 0.2.4s) —
    используется в Adventure section'е для отображения cost_time_min
    («🕑 ~103 мин» → «🕑 ~1 ч. 43 мин.»).
    """
    if x <= 60:
        return f'{x} мин.'

    if x < _MIN_PER_DAY:
        h, m = divmod(x, _MIN_PER_HOUR)
        return f'{h} ч. {m} мин.'

    if x < _MIN_PER_MONTH:
        d, rest = divmod(x, _MIN_PER_DAY)
        h, m = divmod(rest, _MIN_PER_HOUR)
        return f'{d} дн. {h} ч. {m} мин.'

    if x < _MIN_PER_YEAR:
        mo, rest = divmod(x, _MIN_PER_MONTH)
        d, rest = divmod(rest, _MIN_PER_DAY)
        h, m = divmod(rest, _MIN_PER_HOUR)
        return f'{mo} мес. {d} дн. {h} ч. {m} мин.'

    y, rest = divmod(x, _MIN_PER_YEAR)
    mo, rest = divmod(rest, _MIN_PER_MONTH)
    d, rest = divmod(rest, _MIN_PER_DAY)
    h, m = divmod(rest, _MIN_PER_HOUR)
    return f'{y} г. {mo} мес. {d} дн. {h} ч. {m} мин.'


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
        timedelta(days=1, hours=5)       -> "1 д 5:00:00"
        timedelta(days=8)                -> "1 нед 1 д 0:00:00"
        timedelta(days=35)               -> "1 мес 5 д 0:00:00"
        timedelta(days=400)              -> "1 г 1 мес 5 д 0:00:00"
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
        parts.append(f"{y} г")
    mo, total = divmod(total, _MONTH_S)
    if mo > 0:
        parts.append(f"{mo} мес")
    w, total = divmod(total, _WEEK_S)
    if w > 0:
        parts.append(f"{w} нед")
    d, total = divmod(total, _DAY_S)
    if d > 0:
        parts.append(f"{d} д")
    h, total = divmod(total, _HOUR_S)
    m, s = divmod(total, _MINUTE_S)
    parts.append(f"{h}:{m:02d}:{s:02d}")
    return " ".join(parts)


# Часов в более крупных единицах (для format_hours — 0.2.1v).
_HOURS_PER_DAY = 24
_HOURS_PER_MONTH = 30 * 24    # 720
_HOURS_PER_YEAR = 365 * 24    # 8760


def format_money(amount: float, decimals: int = 2) -> str:
    """Единый форматтер денег для всех CLI / web дисплеев (4.20.1).

    Возвращает строку вида `"1,234.56"` (или `"1,234"` при `decimals=0`).
    Plain text без colorama / dollar sign — caller сам добавляет `$` и цвет.

    После 0.2.3a / задачи 4.20 деньги в проекте = `float` (state.money +
    цены через apply_money_saving после скидки + bank deposit/loan
    capitalize-on-change). Этот helper стандартизирует формат — `:,.2f` по
    умолчанию (две цифры после запятой + разделитель тысяч), чтобы:
    1. Игрок видел копейки везде где они могут появиться (не только в Bank).
    2. Не было разночтений между CLI status_bar / Gym header / Shop / web.
    3. Было одно место для будущих правок (e.g. локаль с другим разделителем).
    """
    return f"{amount:,.{decimals}f}"


def format_hours(hours: int) -> str:
    """Часы → "Y г. MO мес. D дн. H ч." с ведущими нулями. Plain text без colorama.

    Используется на web для длительности смены работы (`state.work.hours`),
    чтобы не показывать "71 ч" вместо "2 дн. 23 ч.". Стиль аналогичен CLI
    `time(x)`, но входное значение — часы (а не минуты), компонента "минуты"
    исключена, и colorama НЕ применяется (текст идёт прямо в HTML).

    Логика "ведущие нули": если значение не превышает порог следующей единицы
    (например, hours < 720 → нет месяцев), эта единица не показывается. Если
    есть — показываются ВСЕ младшие компоненты, даже если они равны нулю
    (3 дня → "3 дн. 0 ч."). Месяц = 30 дней, год = 365 дней (как в `time()`
    и `format_timedelta`).
    """
    if hours < _HOURS_PER_DAY:
        return f"{hours} ч."

    if hours < _HOURS_PER_MONTH:
        d, h = divmod(hours, _HOURS_PER_DAY)
        return f"{d} дн. {h} ч."

    if hours < _HOURS_PER_YEAR:
        mo, rest = divmod(hours, _HOURS_PER_MONTH)
        d, h = divmod(rest, _HOURS_PER_DAY)
        return f"{mo} мес. {d} дн. {h} ч."

    y, rest = divmod(hours, _HOURS_PER_YEAR)
    mo, rest = divmod(rest, _HOURS_PER_MONTH)
    d, h = divmod(rest, _HOURS_PER_DAY)
    return f"{y} г. {mo} мес. {d} дн. {h} ч."
