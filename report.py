"""«Пока тебя не было» report (task 4.2).

При входе в игру (CLI / web) показывает summary блок значимых событий,
произошедших с прошлого захода — пропущенные финализации работы / тренировки /
приключения, level-up'ы, переходы дня. Полезен после паузы 1-2+ часов: вместо
россыпи финализатор-print'ов даёт one-glance понимание «что я пропустил».

**Architecture:**
- Источник — Sheets `history` лист (полная картина CLI + web events, в отличие
  от local `history.jsonl` который per-machine). Cost — 1 Sheets API call
  (~500-700 мс) на старте.
- Period — `state.timestamp_last_enter` (предыдущее значение, до перезаписи
  на init). Захватывает всё с прошлого init_game_state.
- Trigger — только если >= 1 interesting event. Иначе блок не показывается.
- Stored in runtime-only `state.startup_report: list[dict]`. CLI printer и
  web template читают, потом caller очищает.
"""

from typing import Any

from colorama import Fore, Style

from functions_02 import format_money


# Типы events которые показываются в report'е. Pasive events (timer / auto),
# не активные действия игрока (skill_alloc / bank ops / item_repaired — игрок
# сам это делал, не интересно «пока тебя не было»).
INTERESTING_EVENT_TYPES = frozenset({
    'work_done',           # Зарплата начислена (таймер истёк)
    'skill_upgraded',      # Навык прокачен (тренировка закончилась)
    'adventure_done',      # Приключение завершилось
    'drop',                # Дроп из приключения
    'drop_auto_collected', # Pending-дроп подобрался после освобождения слота
    'drop_force_sold',     # Forced sale (full inventory + pending заняты)
    'level_up',            # Новый уровень персонажа
    'new_day',             # День сменился (rollover)
})


# Эмодзи и формат для каждого типа events.
def _format_event_cli(event: dict) -> str:
    """Форматирует один event для CLI summary (с colorama)."""
    t = event['type']
    p = event.get('payload', {})
    if t == 'work_done':
        vacancy = str(p.get('vacancy', '?')).title()
        hours = p.get('hours', 0)
        salary = p.get('salary', 0)
        return (f'   🏭 {Fore.GREEN}{vacancy}{Style.RESET_ALL}: '
                f'{hours} ч → +{Fore.LIGHTYELLOW_EX}{format_money(salary)}{Style.RESET_ALL} $')
    if t == 'skill_upgraded':
        skill = str(p.get('skill', '?')).title()
        from_lvl = p.get('from_level', '?')
        to_lvl = p.get('to_level', '?')
        return (f'   🏋 {Fore.LIGHTCYAN_EX}{skill}{Style.RESET_ALL}: '
                f'lvl {from_lvl} → {to_lvl}')
    if t == 'adventure_done':
        name = str(p.get('name', '?'))
        return f'   🗺 Приключение завершено: {Fore.LIGHTBLUE_EX}{name}{Style.RESET_ALL}'
    if t == 'drop':
        item = p.get('item', {})
        # item может быть как dict с list-полями ['grade'][0], так и упрощённый
        grade = _extract_field(item, 'grade')
        item_type = str(_extract_field(item, 'item_type') or '?').title()
        characteristic = str(_extract_field(item, 'characteristic') or '?')
        bonus = _extract_field(item, 'bonus')
        return (f'   🎁 Дроп: {Fore.LIGHTMAGENTA_EX}{grade}{Style.RESET_ALL} '
                f'{item_type} +{bonus} {characteristic}')
    if t == 'drop_auto_collected':
        item = p.get('item', {})
        item_type = str(_extract_field(item, 'item_type') or '?').title()
        return f'   🎁 Освободилось место — подобрана отложенная находка: {item_type}'
    if t == 'drop_force_sold':
        item = p.get('item', {})
        item_type = str(_extract_field(item, 'item_type') or '?').title()
        price = p.get('price', 0)
        return (f'   💰 Forced sale (рюкзак полон + pending): {item_type} '
                f'за {Fore.LIGHTYELLOW_EX}{format_money(price)}{Style.RESET_ALL} $')
    if t == 'level_up':
        from_lvl = p.get('from_level', '?')
        to_lvl = p.get('to_level', '?')
        return (f'   ⭐ Level up: {from_lvl} → {Fore.LIGHTGREEN_EX}{to_lvl}{Style.RESET_ALL} '
                f'(+1 skill point — распредели в u)')
    if t == 'new_day':
        new_date = str(p.get('new_date', '?'))
        return f'   🌅 Новый день: {Fore.LIGHTYELLOW_EX}{new_date}{Style.RESET_ALL}'
    # Fallback для неизвестных types (если попадут).
    return f'   • {t}: {p}'


def _extract_field(item: dict, key: str) -> Any:
    """Извлекает field из item-dict с учётом list-обёрток (`['grade'][0]`)."""
    v = item.get(key)
    if isinstance(v, list) and v:
        return v[0]
    return v


def build_away_report(since_ts: float) -> list[dict]:
    """Читает Sheets history с `ts >= since_ts`, фильтрует interesting types.

    Returns list dicts со схемой HistoryLogRepo.since. Пустой список если
    Sheets unavailable или нет interesting events.
    """
    if since_ts <= 0:
        return []  # legacy save без timestamp — не показываем report
    from google_sheets_db import HistoryLogRepo
    events = HistoryLogRepo().since(since_ts)
    return [e for e in events if e['type'] in INTERESTING_EVENT_TYPES]


def format_report_cli(events: list[dict], since_ts: float) -> str:
    """Форматирует events в CLI-блок (с colorama / unicode рамкой).

    Возвращает пустую строку если events пуст — caller не печатает рамку
    впустую.
    """
    if not events:
        return ''
    from datetime import datetime
    import time as time_mod
    elapsed_sec = time_mod.time() - since_ts
    elapsed_label = format_timedelta_simple(elapsed_sec)
    since_dt = datetime.fromtimestamp(since_ts).strftime('%d.%m %H:%M')
    sep = '═' * 60
    lines = [
        sep,
        f'🕒 {Fore.LIGHTBLUE_EX}Пока тебя не было{Style.RESET_ALL} '
        f'(последний вход: {since_dt}, прошло {elapsed_label})',
        sep,
    ]
    for e in events:
        lines.append(_format_event_cli(e))
    lines.append(sep)
    return '\n'.join(lines)


def format_timedelta_simple(seconds: float) -> str:
    """Простой human-readable формат для elapsed time. Без сложных edge cases.

    Примеры: '5 мин', '2 ч 30 мин', '1 дн 5 ч', '3 дн'.
    """
    if seconds < 0:
        return '0 мин'
    minutes = int(seconds // 60)
    if minutes < 60:
        return f'{minutes} мин'
    hours = minutes // 60
    rem_min = minutes % 60
    if hours < 24:
        return f'{hours} ч {rem_min} мин' if rem_min else f'{hours} ч'
    days = hours // 24
    rem_h = hours % 24
    return f'{days} дн {rem_h} ч' if rem_h else f'{days} дн'


def build_report_view(events: list[dict], since_ts: float) -> dict:
    """Pre-computed view для web template. Returns dict со списком events
    и meta (since_dt, elapsed_label, total_count).

    Каждое event-dict содержит: emoji, text, item-related поля если применимо.
    """
    if not events:
        return {'has_events': False}
    from datetime import datetime
    import time as time_mod
    elapsed_sec = time_mod.time() - since_ts
    items = []
    for e in events:
        items.append(_format_event_web(e))
    return {
        'has_events': True,
        'since_dt': datetime.fromtimestamp(since_ts).strftime('%d.%m %H:%M'),
        'elapsed_label': format_timedelta_simple(elapsed_sec),
        'count': len(events),
        'items': items,
    }


def _format_event_web(event: dict) -> dict:
    """Форматирует event для web banner-template — emoji + text, без colorama."""
    t = event['type']
    p = event.get('payload', {})
    if t == 'work_done':
        return {
            'emoji': '🏭',
            'text': f"{str(p.get('vacancy', '?')).title()}: "
                    f"{p.get('hours', 0)} ч → +{format_money(p.get('salary', 0))} $",
        }
    if t == 'skill_upgraded':
        return {
            'emoji': '🏋',
            'text': f"{str(p.get('skill', '?')).title()}: "
                    f"lvl {p.get('from_level', '?')} → {p.get('to_level', '?')}",
        }
    if t == 'adventure_done':
        return {
            'emoji': '🗺',
            'text': f"Приключение завершено: {p.get('name', '?')}",
        }
    if t == 'drop':
        item = p.get('item', {})
        return {
            'emoji': '🎁',
            'text': f"Дроп: {_extract_field(item, 'grade')} "
                    f"{str(_extract_field(item, 'item_type') or '?').title()} "
                    f"+{_extract_field(item, 'bonus')} {_extract_field(item, 'characteristic')}",
        }
    if t == 'drop_auto_collected':
        item = p.get('item', {})
        return {
            'emoji': '🎁',
            'text': f"Подобрана отложенная находка: "
                    f"{str(_extract_field(item, 'item_type') or '?').title()}",
        }
    if t == 'drop_force_sold':
        return {
            'emoji': '💰',
            'text': f"Forced sale: {format_money(p.get('price', 0))} $",
        }
    if t == 'level_up':
        return {
            'emoji': '⭐',
            'text': f"Level up: {p.get('from_level', '?')} → {p.get('to_level', '?')}",
        }
    if t == 'new_day':
        return {
            'emoji': '🌅',
            'text': f"Новый день: {p.get('new_date', '?')}",
        }
    return {'emoji': '•', 'text': str(t)}
