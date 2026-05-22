"""Triumphs CLI menu — UI слой для engine (task 4.62.0.3).

Отдельный модуль (vs `triumphs.py`) — `triumphs.py` остаётся pure logic
(без print/input), здесь UI-слой. Pattern как `report.py` (format helpers
без UI) vs `game.py` (print/input).

Главный entry: `open_triumphs_menu(state)`.
"""

from __future__ import annotations

import os

from colorama import Fore, Style

from config import HISTORY_FILE
from triumphs import (
    backfill_from_history,
    get_progress,
    total_score,
    _format_progress_bar,
)
from triumphs_data import CATEGORIES, TRIUMPHS


_SEP = '═' * 60


def _print_header(state) -> None:
    """Заголовок с total score."""
    score = total_score(state)
    print(f'\n{_SEP}')
    print(f'🏆 {Fore.LIGHTYELLOW_EX}Triumphs{Style.RESET_ALL} '
          f'(Score: {Fore.LIGHTCYAN_EX}{score}{Style.RESET_ALL})')
    print(_SEP)


def _check_first_launch_backfill_prompt(state) -> bool:
    """Проверяет нужен ли one-time backfill prompt.

    Условия:
    - state.triumphs_backfill_dismissed == False (игрок ещё не выбрал «Skip»)
    - history.jsonl существует и не пустой
    - В catalog'е есть event-based triumphs (если их нет — backfill нечего
      делать, metric-based triumphs auto-unlock'аются на старте через
      init_metric_check — см. 4.62.1.1 fix 22.05.2026).

    Returns True если prompt был показан и обработан (any choice).
    """
    if state.triumphs_backfill_dismissed:
        return False
    if not os.path.exists(HISTORY_FILE):
        return False
    try:
        size = os.path.getsize(HISTORY_FILE)
    except OSError:
        return False
    if size == 0:
        return False
    # 22.05.2026 — Skip prompt если в catalog нет event-based triumphs.
    # Backfill бесполезен для metric-based (они auto-unlock через
    # init_metric_check / register_event), показывать prompt = confusing UX.
    has_event_based = any('event_hooks' in spec for spec in TRIUMPHS.values())
    if not has_event_based:
        return False

    # Counting events для UX (~ how many lines в file). Cheap.
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            event_count = sum(1 for _ in f if _.strip())
    except OSError:
        event_count = 0

    print(f'\n{Fore.LIGHTGREEN_EX}✨ Найдена существующая история{Style.RESET_ALL} '
          f'({event_count} events).')
    print('Backfill triumph event counters из истории?')
    print('(Может занять до 30 сек — зависит от размера истории)')
    print(f'\n  [{Fore.LIGHTCYAN_EX}y{Style.RESET_ALL}] Да — backfill сейчас')
    print(f'  [{Fore.LIGHTCYAN_EX}n{Style.RESET_ALL}] Позже — спросить при следующем входе')
    print(f'  [{Fore.LIGHTCYAN_EX}s{Style.RESET_ALL}] Skip — не показывать больше')

    choice = input('\n>>> ').strip().lower()

    if choice == 'y':
        _do_backfill(state)
    elif choice == 's':
        state.triumphs_backfill_dismissed = True
        print(f'{Fore.LIGHTBLACK_EX}Backfill prompt отключён. '
              f'Можно запустить вручную через "r" в Triumphs меню.{Style.RESET_ALL}')
        # Persist flag — lazy import, не критично если fail (повторный prompt не страшен).
        try:
            from persistence import save_characteristic
            save_characteristic()
        except Exception:  # noqa: BLE001
            pass
    # 'n' / любой другой → no-op (prompt появится снова на след входе)
    return True


def _do_backfill(state) -> None:
    """Запускает backfill_from_history + печатает feedback."""
    print(f'\n{Fore.LIGHTBLUE_EX}🔄 Сканирую historу...{Style.RESET_ALL}')
    feedback = backfill_from_history(state, history_jsonl_path=HISTORY_FILE)
    if not feedback:
        print(f'{Fore.LIGHTBLACK_EX}История прочитана, но event-based triumph counters '
              f'без изменений (catalog пуст или нет соответствующих events).{Style.RESET_ALL}')
        return
    print(f'\n{Fore.LIGHTGREEN_EX}✅ Backfill завершён.{Style.RESET_ALL} Добавлено:')
    for triumph_id, delta in feedback.items():
        name = TRIUMPHS.get(triumph_id, {}).get('name', triumph_id)
        print(f'  • {name}: +{delta}')
    # Persist после backfill — counters важны.
    try:
        from persistence import save_characteristic
        save_characteristic()
    except Exception:  # noqa: BLE001
        pass


def _render_triumph_line(state, triumph_id: str) -> str:
    """Одна строка для display: «Marathoner: ▰▰▰▱▱▱▱▱▱▱ (Tier 1/4) 30k/100k»."""
    progress = get_progress(state, triumph_id)
    if progress is None:
        return f'   {triumph_id}: (unknown)'
    name = progress['name']
    current_tier = progress['current_tier']
    total_tiers = progress['total_tiers']
    current_value = progress['current_value']
    tiers = progress['tiers']

    if progress['is_capstone']:
        bar = _format_progress_bar(current_value, current_value, width=15)
        tier_label = f'{Fore.LIGHTYELLOW_EX}Capstone ({total_tiers}/{total_tiers}){Style.RESET_ALL}'
        target_str = f'{current_value:,}'
    else:
        next_threshold = progress['next_threshold']
        # 22.05.2026 — width=15 даёт clean 3 cells per tier для 5-tier triumph'ов
        # (типичный case Marathoner / Adventurer). Для 4-tier — 4-4-4-3.
        bar = _format_progress_bar(
            current_value,
            tiers[-1],
            tier_thresholds=tiers,
            width=15,
        )
        tier_label = f'Tier {current_tier}/{total_tiers}'
        target_str = f'{current_value:,}/{next_threshold:,}'

    return f'   {Fore.LIGHTCYAN_EX}{name}{Style.RESET_ALL}: {bar} ({tier_label}) {target_str}'


def _print_categories(state) -> None:
    """Выводит triumph'ы сгруппированные по category."""
    if not TRIUMPHS:
        print(f'\n{Fore.LIGHTBLACK_EX}Каталог триумфов пуст — будут добавлены '
              f'в следующих обновлениях (задачи 4.62.1.x).{Style.RESET_ALL}')
        print(f'{Fore.LIGHTBLACK_EX}Следите за прогрессом — engine уже '
              f'отслеживает события.{Style.RESET_ALL}')
        return

    # Group triumph'ы по category.
    by_category: dict[str, list[str]] = {}
    for triumph_id, spec in TRIUMPHS.items():
        cat = spec.get('category', 'misc')
        by_category.setdefault(cat, []).append(triumph_id)

    # Печатаем в order из CATEGORIES.
    ordered_cats = sorted(by_category.keys(),
                          key=lambda c: CATEGORIES.get(c, {}).get('order', 999))
    for cat in ordered_cats:
        cat_meta = CATEGORIES.get(cat, {})
        cat_label = cat_meta.get('label', cat.title())
        print(f'\n{cat_label}')
        for triumph_id in sorted(by_category[cat]):
            print(_render_triumph_line(state, triumph_id))


def _print_commands() -> None:
    """Список команд внизу меню."""
    print(f'\n{Fore.LIGHTBLACK_EX}Команды:{Style.RESET_ALL}')
    print(f'  [{Fore.LIGHTCYAN_EX}r{Style.RESET_ALL}] 🔄 Sync from history (вручную)')
    print(f'  [{Fore.LIGHTCYAN_EX}0{Style.RESET_ALL}] Назад')


def open_triumphs_menu(state) -> None:
    """Главный entry для CLI menu. Loop'ится пока игрок не нажмёт «0».

    Flow:
    1. Если первый launch (флаг не установлен и history.jsonl есть) — prompt backfill
    2. Печать header + categories + commands
    3. Input loop
    """
    # First-launch backfill prompt (один раз per session).
    _check_first_launch_backfill_prompt(state)

    while True:
        _print_header(state)
        _print_categories(state)
        _print_commands()

        choice = input('\n>>> ').strip().lower()

        if choice == '0':
            return
        if choice == 'r':
            _do_backfill(state)
            # После backfill показываем меню снова (next iteration loop'а).
            continue
        if choice in ('р',):  # ru layout for 'r'
            _do_backfill(state)
            continue
        print(f'\n{Fore.LIGHTRED_EX}Неизвестная команда. Доступны: r, 0.{Style.RESET_ALL}')


def render_pinned_status_bar(state) -> str:
    """Pinned triumphs для status_bar (compact, ≤3 строки).

    Returns multi-line string или пустая строка если pinned нет.
    Используется в `functions.status_bar` (call site добавится в 4.62.0.3).
    """
    if not state.pinned_triumphs:
        return ''
    if not TRIUMPHS:
        return ''  # pinned IDs могут указывать на не существующие в catalog'е
    lines = [f'\t{Fore.LIGHTYELLOW_EX}🏆 Pinned:{Style.RESET_ALL}']
    for triumph_id in state.pinned_triumphs[:3]:
        if triumph_id not in TRIUMPHS:
            continue
        line = _render_triumph_line(state, triumph_id)
        lines.append('\t' + line.lstrip())
    return '\n'.join(lines)
