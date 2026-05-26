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

from typing import Any, Optional

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


def _extract_field(item: dict, key: str) -> Any:
    """Извлекает field из item-dict с учётом list-обёрток (`['grade'][0]`)."""
    v = item.get(key)
    if isinstance(v, list) and v:
        return v[0]
    return v


def _title(v: Any) -> str:
    """Безопасный .title() для возможного None / не-строки."""
    return str(v if v is not None else '?').title()


# Цвет строки по типу события (для CLI). Default — без цвета.
def _event_color(t: str) -> str:
    if t in ('work_done', 'work_extend'):
        return str(Fore.GREEN)
    if t in ('skill_upgraded', 'skill_train_start', 'skill_alloc', 'level_up'):
        return str(Fore.LIGHTCYAN_EX)
    if t in ('adventure_start', 'adventure_done'):
        return str(Fore.LIGHTBLUE_EX)
    if t in ('drop', 'drop_pending', 'drop_auto_collected', 'drop_resolved_sell_existing'):
        return str(Fore.LIGHTMAGENTA_EX)
    if t in ('drop_force_sold', 'drop_resolved_sell_new', 'item_sold', 'item_bought',
             'deposit', 'withdraw', 'take_loan', 'repay_loan', 'new_day'):
        return str(Fore.LIGHTYELLOW_EX)
    if t == 'sync_conflict':
        return str(Fore.LIGHTRED_EX)
    return ''


def _event_emoji_text(event: dict) -> tuple[str, str]:
    """Единое ядро форматирования (4.6.2): event → (emoji, plain_text) для ВСЕХ
    ~30 типов. Используется и CLI (`_format_event_cli` + colorama), и web
    (`_format_event_web`). Плоский payload (как реально пишет `log_event`) —
    не nested `item` (до 4.6.2 форматтер ошибочно читал `p.get('item')`, из-за
    чего drop-строки в away-report рендерились как «None ?»). Незнакомый тип →
    generic fallback. Все `.get` с дефолтами — устойчиво к неполному payload.
    """
    t = event['type']
    p = event.get('payload', {})

    if t == 'work_done':
        return '🏭', f"{_title(p.get('vacancy'))}: {p.get('hours', 0)} ч → +{format_money(p.get('salary', 0))} $"
    if t == 'work_extend':
        return '🏭', (f"{_title(p.get('vacancy'))}: +{p.get('added_hours', 0)} ч к смене "
                      f"(всего {p.get('total_hours', 0)} ч)")
    if t == 'skill_upgraded':
        return '🏋', f"{_title(p.get('skill'))}: lvl {p.get('from_level', '?')} → {p.get('to_level', '?')}"
    if t == 'skill_train_start':
        return '🏋', f"Старт прокачки {_title(p.get('skill'))} → lvl {p.get('next_level', '?')}"
    if t == 'skill_alloc':
        return '⭐', f"Очко навыка: {_title(p.get('skill'))} → lvl {p.get('new_level', '?')}"
    if t == 'level_up':
        return '⭐', f"Level up: {p.get('from_level', '?')} → {p.get('to_level', '?')} (+1 skill point — распредели в u)"
    if t == 'adventure_start':
        return '🗺', f"Старт приключения: {p.get('name', '?')}"
    if t == 'adventure_done':
        return '🗺', f"Приключение завершено: {p.get('name', '?')}"
    if t == 'drop':
        return '🎁', (f"Дроп: {p.get('grade', '?')} {_title(p.get('item_type'))} "
                      f"+{p.get('bonus', '?')} {p.get('characteristic', '?')}")
    if t == 'drop_pending':
        return '🎒', f"Находка в ожидании (рюкзак полон): {p.get('grade', '?')} {_title(p.get('item_type'))}"
    if t == 'drop_force_sold':
        return '💰', f"Авто-продажа находки (нет места): {_title(p.get('item_type'))} за {format_money(p.get('price', 0))} $"
    if t == 'drop_auto_collected':
        return '🎁', f"Подобрана отложенная находка: {p.get('grade', '?')} {_title(p.get('item_type'))}"
    if t == 'drop_resolved_sell_existing':
        return '🎒', (f"Продал {_title(p.get('sold_type'))} (+{format_money(p.get('sold_refund', 0))} $), "
                      f"взял находку {_title(p.get('kept_type'))}")
    if t == 'drop_resolved_sell_new':
        return '💰', f"Продал находку {_title(p.get('item_type'))} ({p.get('grade', '?')}) за {format_money(p.get('refund', 0))} $"
    if t == 'item_bought':
        name = p.get('item_name') or p.get('item_type')
        return '🛒', f"Куплено: {_title(name)} ({p.get('grade', '?')}) за {format_money(p.get('cost', 0))} $"
    if t == 'item_sold':
        return '💰', f"Продано: {_title(p.get('item_type'))} ({p.get('grade', '?')})"
    if t == 'item_equipped':
        return '🧥', f"Надето [{p.get('slot', '?')}]: {_title(p.get('item_type'))} ({p.get('grade', '?')})"
    if t == 'item_unequipped':
        return '🧥', f"Снято [{p.get('slot', '?')}]: {_title(p.get('item_type'))} ({p.get('grade', '?')})"
    if t == 'deposit':
        return '🏦', f"Депозит +{format_money(p.get('amount', 0))} $ (баланс: {format_money(p.get('balance_after', 0))} $)"
    if t == 'withdraw':
        return '🏦', f"Снятие −{format_money(p.get('amount', 0))} $ (баланс: {format_money(p.get('balance_after', 0))} $)"
    if t == 'take_loan':
        return '💳', f"Кредит +{format_money(p.get('amount', 0))} $ (долг: {format_money(p.get('debt_after', 0))} $)"
    if t == 'repay_loan':
        return '💳', f"Погашение −{format_money(p.get('amount', 0))} $ (долг: {format_money(p.get('debt_after', 0))} $)"
    if t == 'loadout_optimized':
        return '⚙️', f"Авто-оптимизация ({p.get('characteristic', '?')}): {p.get('slots_changed', 0)} слот."
    if t == 'loadout_applied':
        return '⚙️', f"Лоадаут применён: {p.get('slots_changed', 0)} слот."
    if t == 'preset_saved':
        return '💾', f"Пресет сохранён: {p.get('name', '?')}"
    if t == 'preset_applied':
        return '💾', f"Пресет применён: {p.get('name', '?')} ({p.get('slots_changed', 0)} слот.)"
    if t == 'preset_deleted':
        return '🗑️', f"Пресет удалён: {p.get('name', '?')}"
    if t == 'new_day':
        return '🌅', f"Новый день: {p.get('new_date', '?')}"
    if t == 'steps_set':
        return '👟', f"Шаги: {p.get('previous', '?')} → {p.get('value', '?')} ({p.get('source', '?')})"
    if t == 'save':
        return '💾', "Сохранение"
    if t == 'sync_conflict':
        return '⚠️', f"Конфликт синхронизации ({p.get('source', '?')}, {p.get('choice', '?')})"
    # Fallback для неизвестных types.
    return '•', f"{t}: {p}"


def _format_event_cli(event: dict) -> str:
    """Форматирует один event для CLI (emoji + текст + per-category colorama)."""
    emoji, text = _event_emoji_text(event)
    color = _event_color(event['type'])
    if color:
        return f'   {emoji} {color}{text}{Style.RESET_ALL}'
    return f'   {emoji} {text}'


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
    """Форматирует event для web banner-template — emoji + text, без colorama.
    Thin-wrapper над общим ядром `_event_emoji_text` (4.6.2)."""
    emoji, text = _event_emoji_text(event)
    return {'emoji': emoji, 'text': text}


# --- 4.6.2 — CLI просмотрщик истории (команда `h`) ---

def read_recent_history(limit: Optional[int] = None) -> list[dict]:
    """Возвращает события newest-first. `limit=None` → все (для пагинации в
    viewer'е); иначе — последние `limit`.

    Источник (4.6.2): Sheets `history` лист (полная кросс-девайс картина CLI +
    web) через `HistoryLogRepo.since(0)`; при сетевой ошибке — fallback на
    локальный `history.jsonl` (только события этой машины). Оба источника
    silent-fail → пустой список (viewer покажет «история пуста»).
    """
    events: list[dict] = []
    # Primary — Sheets.
    try:
        from google_sheets_db import HistoryLogRepo
        events = HistoryLogRepo().since(0)
    except Exception:  # noqa: BLE001 — сеть / API / quota → fallback
        events = []
    # Fallback — local jsonl.
    if not events:
        import json
        import os
        from config import HISTORY_FILE
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            except OSError:
                events = []
    # Сортируем по ts ASC → newest-first. limit=None → все.
    events.sort(key=lambda e: e.get('ts', 0))
    newest_first = list(reversed(events))
    return newest_first if limit is None else newest_first[:limit]


def _event_timestamp_label(event: dict) -> str:
    """`[YYYY-MM-DD HH:MM]` из `ts` (есть и в Sheets-since, и в jsonl). Fallback
    на date/time поля jsonl, иначе '?'. Фиксит `[? ?]` (Sheets-since не отдаёт
    отдельные date/time, только ts + datetime)."""
    from datetime import datetime
    ts = event.get('ts')
    if isinstance(ts, (int, float)) and ts > 0:
        return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
    if event.get('datetime'):
        return str(event['datetime'])[:16]
    return f"{event.get('date', '?')} {str(event.get('time', '?'))[:5]}"


def _print_history_page(chunk: list[dict], page: int, total_pages: int,
                        total: int, page_size: int) -> None:
    """Печатает одну страницу истории (helper — без input, тестируемо)."""
    sep = '═' * 60
    print(sep)
    print(f'📜 {Fore.LIGHTBLUE_EX}История{Style.RESET_ALL} · '
          f'страница {page + 1}/{total_pages} · '
          f'{total} событий · по {page_size} на стр.')
    print(sep)
    if not chunk:
        print('   — история пуста (или Sheets/лог недоступны).')
    else:
        for e in chunk:
            stamp = _event_timestamp_label(e)
            emoji, text = _event_emoji_text(e)
            color = _event_color(e.get('type', ''))
            body = f'{color}{text}{Style.RESET_ALL}' if color else text
            print(f'   [{Fore.LIGHTBLACK_EX}{stamp}{Style.RESET_ALL}] {emoji} {body}')
    print(sep)


def open_history_viewer(state=None) -> None:
    """CLI-команда `h`: интерактивный просмотр истории с пагинацией (4.6.2).

    Управление: `m`/Enter — следующая страница (более старые события); `1`-`9` —
    размер страницы (×10, т.е. 10..90, сброс на стр. 1); `0` — выход.

    Read-only — `state` не используется (сигнатура для единообразия с другими
    CLI-командами). Все события (`read_recent_history(None)`) грузятся один раз,
    пагинация — в памяти.
    """
    events = read_recent_history(None)  # все, newest-first
    page_size = 20
    page = 0
    while True:
        total = len(events)
        total_pages = max(1, (total + page_size - 1) // page_size)
        page = max(0, min(page, total_pages - 1))
        start = page * page_size
        chunk = events[start:start + page_size]
        _print_history_page(chunk, page, total_pages, total, page_size)

        has_more = page + 1 < total_pages
        hint = '[m] ещё · ' if has_more else ''
        choice = input(f'\n{hint}[1-9] размер ×10 · [0] выход\n>>> ').strip().lower()

        if choice in ('0', 'й'):  # 'й' — RU-раскладка для 'q'-подобного выхода
            return
        if choice in ('m', 'ь', ''):  # m / ь (RU) / Enter — следующая страница
            if has_more:
                page += 1
            else:
                print('— это последняя страница.')
            continue
        if choice in '123456789' and len(choice) == 1:
            page_size = int(choice) * 10
            page = 0
            continue
        # Неизвестный ввод — перерисовываем текущую страницу.
