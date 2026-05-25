"""Triumphs CLI menu — UI слой для engine (task 4.62.0.3 + 4.62.4 Pinned/Claim).

Отдельный модуль (vs `triumphs.py`) — `triumphs.py` остаётся pure logic
(без print/input), здесь UI-слой. Pattern как `report.py` (format helpers
без UI) vs `game.py` (print/input).

**Навигация (4.62.4):**
- Main menu → Category view → Detail view (3-level).
- Main: pinned section + unclaimed banner + claim_all + numbered categories.
- Category: numbered triumphs внутри.
- Detail: progress + actions (Pin/Unpin toggle, Claim, Назад).

Главный entry: `open_triumphs_menu(state)`.
"""

from __future__ import annotations

import os

from colorama import Fore, Style

from config import HISTORY_FILE
from triumphs import (
    available_seals,
    backfill_from_history,
    claim_all,
    claim_triumph,
    get_progress,
    get_unclaimed_for,
    is_seal_unlocked,
    set_title,
    total_score,
    _format_progress_bar,
)
from triumphs_data import CATEGORIES, SEALS, TRIUMPHS


_SEP = '═' * 60
_PINNED_CAP = 3


# --- Headers / common ---

def _print_header(state) -> None:
    """Заголовок с total score."""
    score = total_score(state)
    print(f'\n{_SEP}')
    print(f'🏆 {Fore.LIGHTYELLOW_EX}Triumphs{Style.RESET_ALL} '
          f'(Score: {Fore.LIGHTCYAN_EX}{score}{Style.RESET_ALL})')
    print(_SEP)


# --- First-launch backfill prompt ---

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
    has_event_based = any('event_hooks' in spec for spec in TRIUMPHS.values())
    if not has_event_based:
        return False

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
        try:
            from persistence import save_characteristic
            save_characteristic()
        except Exception:  # noqa: BLE001
            pass
    return True


def _do_backfill(state) -> None:
    """Запускает backfill_from_history + печатает feedback."""
    print(f'\n{Fore.LIGHTBLUE_EX}🔄 Сканирую history...{Style.RESET_ALL}')
    feedback = backfill_from_history(state, history_jsonl_path=HISTORY_FILE)
    if not feedback:
        print(f'{Fore.LIGHTBLACK_EX}История прочитана, но event-based triumph counters '
              f'без изменений (catalog пуст или нет соответствующих events).{Style.RESET_ALL}')
        return
    print(f'\n{Fore.LIGHTGREEN_EX}✅ Backfill завершён.{Style.RESET_ALL} Добавлено:')
    for triumph_id, delta in feedback.items():
        name = TRIUMPHS.get(triumph_id, {}).get('name', triumph_id)
        print(f'  • {name}: +{delta}')
    try:
        from persistence import save_characteristic
        save_characteristic()
    except Exception:  # noqa: BLE001
        pass


# --- Render helpers ---

def _render_triumph_line(state, triumph_id: str) -> str:
    """Одна строка для display: «Marathoner: ▰▰▰▱▱▱▱▱▱▱ (Tier 1/4) 30k/100k».

    4.62.4: суффикс «  ✨» если есть unclaimed entries для triumph'а,
    суффикс «  📌» если pinned.
    """
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
        bar = _format_progress_bar(
            current_value,
            tiers[-1],
            tier_thresholds=tiers,
            width=15,
        )
        tier_label = f'Tier {current_tier}/{total_tiers}'
        target_str = f'{current_value:,}/{next_threshold:,}'

    # 4.62.4 markers
    markers = ''
    if get_unclaimed_for(state, triumph_id):
        markers += f' {Fore.LIGHTGREEN_EX}✨{Style.RESET_ALL}'
    if triumph_id in (state.pinned_triumphs or []):
        markers += f' {Fore.LIGHTYELLOW_EX}📌{Style.RESET_ALL}'

    return f'   {Fore.LIGHTCYAN_EX}{name}{Style.RESET_ALL}: {bar} ({tier_label}) {target_str}{markers}'


def _category_counts(state, cat_key: str) -> tuple[int, int]:
    """Returns (unlocked_count, total_count) для category."""
    triumph_ids = [tid for tid, spec in TRIUMPHS.items() if spec.get('category') == cat_key]
    total = len(triumph_ids)
    unlocked = sum(
        1 for tid in triumph_ids
        if int(state.triumphs.get(tid, {}).get('tier', 0)) > 0
    )
    return unlocked, total


def _category_has_unclaimed(state, cat_key: str) -> bool:
    """True если в category хотя бы один triumph имеет unclaimed entries."""
    if not state.unclaimed_unlocks:
        return False
    cat_triumph_ids = {tid for tid, spec in TRIUMPHS.items() if spec.get('category') == cat_key}
    return any(e.get('triumph_id') in cat_triumph_ids for e in state.unclaimed_unlocks)


# --- Pinned ↔ Unclaimed status bar ---

def render_pinned_status_bar(state) -> str:
    """Pinned triumphs + unclaimed banner для status_bar.

    Returns multi-line string или пустая строка если ни pinned, ни unclaimed.
    Используется в `functions.status_bar`.

    Layout:
    - Если есть unclaimed → top line «🎁 N закрыто: имя1, имя2, имя3 (и ещё X) — открой [t]»
    - Если есть pinned → header «🏆 Pinned:» + up to 3 lines (each may have ✨ marker)
    """
    parts: list[str] = []

    # 4.62.4 — Unclaimed banner.
    if state.unclaimed_unlocks:
        # Уникальные (triumph_id, kind) в unclaimed (для имён).
        # 4.62.3: kind='seal' entries использует SEALS catalog, не TRIUMPHS.
        seen: list[tuple[str, str]] = []
        for entry in state.unclaimed_unlocks:
            tid = entry.get('triumph_id')
            kind = entry.get('kind', 'triumph')
            if tid and (tid, kind) not in seen:
                seen.append((tid, kind))
        total = len(state.unclaimed_unlocks)

        def _entry_name(tid: str, kind: str) -> str:
            if kind == 'seal':
                return str(SEALS.get(tid, {}).get('name', tid)) + ' (Seal)'
            return str(TRIUMPHS.get(tid, {}).get('name', tid))

        names = [_entry_name(tid, kind) for tid, kind in seen[:3]]
        more = len(seen) - 3
        names_str = ', '.join(names)
        if more > 0:
            names_str += f' и ещё {more}'
        parts.append(
            f'\t{Fore.LIGHTGREEN_EX}🎁 {total} закрыто:{Style.RESET_ALL} '
            f'{names_str} — открой [{Fore.LIGHTCYAN_EX}t{Style.RESET_ALL}]'
        )

    # Pinned section.
    if state.pinned_triumphs and TRIUMPHS:
        parts.append(f'\t{Fore.LIGHTYELLOW_EX}🏆 Pinned:{Style.RESET_ALL}')
        for triumph_id in state.pinned_triumphs[:_PINNED_CAP]:
            if triumph_id not in TRIUMPHS:
                continue
            line = _render_triumph_line(state, triumph_id)
            parts.append('\t' + line.lstrip())

    return '\n'.join(parts)


# --- Persistence helper ---

def _persist_silent() -> None:
    """Save после mutation. Silent-fail (UI не должен падать на network error)."""
    try:
        from persistence import save_characteristic
        save_characteristic()
    except Exception:  # noqa: BLE001
        pass


# --- Pin / Unpin logic (4.62.4) ---

def _toggle_pin(state, triumph_id: str) -> None:
    """Pin/Unpin toggle. Если pinned == cap при попытке pin → smart replace prompt."""
    if state.pinned_triumphs is None:
        state.pinned_triumphs = []

    if triumph_id in state.pinned_triumphs:
        # Unpin.
        state.pinned_triumphs.remove(triumph_id)
        name = TRIUMPHS.get(triumph_id, {}).get('name', triumph_id)
        print(f'\n{Fore.LIGHTBLACK_EX}📌 Открепил «{name}»{Style.RESET_ALL}')
        _persist_silent()
        return

    # Pin path.
    if len(state.pinned_triumphs) < _PINNED_CAP:
        state.pinned_triumphs.append(triumph_id)
        name = TRIUMPHS.get(triumph_id, {}).get('name', triumph_id)
        print(f'\n{Fore.LIGHTGREEN_EX}📌 Закрепил «{name}» '
              f'({len(state.pinned_triumphs)}/{_PINNED_CAP}){Style.RESET_ALL}')
        _persist_silent()
        return

    # Cap reached → smart replace prompt.
    print(f'\n{Fore.LIGHTYELLOW_EX}У тебя уже {_PINNED_CAP} закреплено. '
          f'Какой заменить?{Style.RESET_ALL}')
    for i, pid in enumerate(state.pinned_triumphs[:_PINNED_CAP], start=1):
        pname = TRIUMPHS.get(pid, {}).get('name', pid)
        print(f'  [{Fore.LIGHTCYAN_EX}{i}{Style.RESET_ALL}] {pname}')
    print(f'  [{Fore.LIGHTCYAN_EX}c{Style.RESET_ALL}] Отмена')

    choice = input('\n>>> ').strip().lower()
    if choice == 'c':
        print(f'{Fore.LIGHTBLACK_EX}Отменено.{Style.RESET_ALL}')
        return
    if choice in ('1', '2', '3') and int(choice) <= len(state.pinned_triumphs):
        idx = int(choice) - 1
        replaced_id = state.pinned_triumphs[idx]
        replaced_name = TRIUMPHS.get(replaced_id, {}).get('name', replaced_id)
        state.pinned_triumphs[idx] = triumph_id
        new_name = TRIUMPHS.get(triumph_id, {}).get('name', triumph_id)
        print(f'\n{Fore.LIGHTGREEN_EX}📌 Заменил «{replaced_name}» → '
              f'«{new_name}»{Style.RESET_ALL}')
        _persist_silent()
    else:
        print(f'{Fore.LIGHTRED_EX}Неизвестная команда. Отменено.{Style.RESET_ALL}')


# --- Claim logic (4.62.4) ---

def _do_claim(state, triumph_id: str) -> None:
    """Claim все unclaimed entries для одного triumph'а + UI feedback."""
    count = claim_triumph(state, triumph_id)
    if count == 0:
        return
    name = TRIUMPHS.get(triumph_id, {}).get('name', triumph_id)
    points = count * 10  # POINTS_PER_TIER (TODO: per-triumph override если будет)
    new_total = total_score(state)
    print(f'\n{Fore.LIGHTGREEN_EX}🎉 {name}: {count} tier'
          f'{"" if count == 1 else "ов"} собран'
          f'{"" if count == 1 else "о"}!{Style.RESET_ALL} '
          f'+{points} score (total {new_total})')
    input(f'{Fore.LIGHTBLACK_EX}[Enter]{Style.RESET_ALL}')
    _persist_silent()


def _do_claim_all(state) -> None:
    """Claim все unclaimed entries за один раз + UI feedback."""
    count = claim_all(state)
    if count == 0:
        return
    points = count * 10
    new_total = total_score(state)
    print(f'\n{Fore.LIGHTGREEN_EX}🎉 Собрано: {count} tier'
          f'{"" if count == 1 else "ов"} / {points} score points.{Style.RESET_ALL} '
          f'Total: {new_total}')
    input(f'{Fore.LIGHTBLACK_EX}[Enter]{Style.RESET_ALL}')
    _persist_silent()


# --- Detail view (4.62.4) ---

def _open_detail_view(state, triumph_id: str) -> None:
    """Detail view для одного triumph'а: progress + actions (Pin/Claim/Назад)."""
    while True:
        progress = get_progress(state, triumph_id)
        if progress is None:
            print(f'{Fore.LIGHTRED_EX}Triumph {triumph_id!r} не найден.{Style.RESET_ALL}')
            return

        # Header.
        spec = TRIUMPHS.get(triumph_id, {})
        cat_key = spec.get('category', 'misc')
        cat_label = CATEGORIES.get(cat_key, {}).get('label', cat_key.title())
        print(f'\n{_SEP}')
        print(f'{cat_label}  ›  {Fore.LIGHTCYAN_EX}{progress["name"]}{Style.RESET_ALL}')
        print(_SEP)

        # Progress.
        print(_render_triumph_line(state, triumph_id))

        # Tiers list (mark unlocked).
        print()
        for i, threshold in enumerate(progress['tiers'], start=1):
            done = i <= progress['current_tier']
            marker = (f'{Fore.LIGHTGREEN_EX}✓{Style.RESET_ALL}' if done
                      else f'{Fore.LIGHTBLACK_EX}·{Style.RESET_ALL}')
            label_color = Fore.LIGHTGREEN_EX if done else Fore.LIGHTBLACK_EX
            print(f'   {marker} Tier {i}: {label_color}{threshold:,}{Style.RESET_ALL}')

        # Unclaimed counter.
        unclaimed = get_unclaimed_for(state, triumph_id)
        if unclaimed:
            print(f'\n{Fore.LIGHTGREEN_EX}🎁 Несобранных tier'
                  f'{"" if len(unclaimed) == 1 else "ов"}: {len(unclaimed)}{Style.RESET_ALL}')

        # Actions.
        print(f'\n{Fore.LIGHTBLACK_EX}Действия:{Style.RESET_ALL}')
        is_pinned = triumph_id in (state.pinned_triumphs or [])
        pin_label = ('📌 Открепить' if is_pinned else '📌 Закрепить')
        print(f'  [{Fore.LIGHTCYAN_EX}1{Style.RESET_ALL}] {pin_label}')
        if unclaimed:
            print(f'  [{Fore.LIGHTCYAN_EX}c{Style.RESET_ALL}] ✓ Собрать ({len(unclaimed)})')
        print(f'  [{Fore.LIGHTCYAN_EX}0{Style.RESET_ALL}] Назад')

        choice = input('\n>>> ').strip().lower()

        if choice == '0':
            return
        if choice == '1':
            _toggle_pin(state, triumph_id)
            continue
        if choice == 'c' and unclaimed:
            _do_claim(state, triumph_id)
            continue
        print(f'{Fore.LIGHTRED_EX}Неизвестная команда.{Style.RESET_ALL}')


# --- Category view (4.62.4) ---

def _open_category_view(state, cat_key: str) -> None:
    """Список triumph'ов одной категории, navigate в detail."""
    cat_label = CATEGORIES.get(cat_key, {}).get('label', cat_key.title())

    while True:
        # Triumphs sorted by id (stable order).
        triumph_ids = sorted([
            tid for tid, spec in TRIUMPHS.items()
            if spec.get('category') == cat_key
        ])

        print(f'\n{_SEP}')
        print(f'{cat_label}')
        print(_SEP)

        if not triumph_ids:
            print(f'{Fore.LIGHTBLACK_EX}Категория пустая.{Style.RESET_ALL}')
            print(f'\n  [{Fore.LIGHTCYAN_EX}0{Style.RESET_ALL}] Назад')
            choice = input('\n>>> ').strip().lower()
            if choice == '0':
                return
            continue

        for i, tid in enumerate(triumph_ids, start=1):
            line = _render_triumph_line(state, tid)
            # Replace leading 3 spaces with [N] prefix.
            print(f'  [{Fore.LIGHTCYAN_EX}{i}{Style.RESET_ALL}]{line[3:]}')

        print(f'\n  [{Fore.LIGHTCYAN_EX}0{Style.RESET_ALL}] Назад')

        choice = input('\n>>> ').strip().lower()
        if choice == '0':
            return
        if choice.isdigit() and 1 <= int(choice) <= len(triumph_ids):
            _open_detail_view(state, triumph_ids[int(choice) - 1])
            continue
        print(f'{Fore.LIGHTRED_EX}Неизвестная команда.{Style.RESET_ALL}')


# --- Main menu ---

def _print_main_menu(state) -> list[str]:
    """Рендерит main menu (pinned, unclaimed, categories). Returns ordered
    list category keys (для mapping числа → cat)."""
    # Unclaimed banner на самом верху если есть.
    if state.unclaimed_unlocks:
        total = len(state.unclaimed_unlocks)
        print(f'\n{Fore.LIGHTGREEN_EX}🎁 {total} закрытых не собрано'
              f'{Style.RESET_ALL}')
        print(f'  [{Fore.LIGHTCYAN_EX}a{Style.RESET_ALL}] ✓ Собрать все ({total})')

    # Pinned section.
    if state.pinned_triumphs and TRIUMPHS:
        print(f'\n{Fore.LIGHTYELLOW_EX}📌 Pinned ({len(state.pinned_triumphs)}/{_PINNED_CAP}){Style.RESET_ALL}')
        for triumph_id in state.pinned_triumphs[:_PINNED_CAP]:
            if triumph_id not in TRIUMPHS:
                continue
            print(_render_triumph_line(state, triumph_id))

    # Categories list (numbered).
    if not TRIUMPHS:
        print(f'\n{Fore.LIGHTBLACK_EX}Каталог триумфов пуст — будут добавлены '
              f'в следующих обновлениях (задачи 4.62.1.x).{Style.RESET_ALL}')
        return []

    # Sort categories by their CATEGORIES order field; only include those
    # которые имеют хотя бы один triumph в catalog'е.
    present_cats = set()
    for spec in TRIUMPHS.values():
        present_cats.add(spec.get('category', 'misc'))
    ordered_cats = sorted(
        present_cats,
        key=lambda c: CATEGORIES.get(c, {}).get('order', 999)
    )

    print(f'\n{Fore.LIGHTBLACK_EX}Категории:{Style.RESET_ALL}')
    for i, cat in enumerate(ordered_cats, start=1):
        label = CATEGORIES.get(cat, {}).get('label', cat.title())
        unlocked, total_t = _category_counts(state, cat)
        marker = ''
        if _category_has_unclaimed(state, cat):
            marker = f' {Fore.LIGHTGREEN_EX}✨{Style.RESET_ALL}'
        print(f'  [{Fore.LIGHTCYAN_EX}{i}{Style.RESET_ALL}] {label} '
              f'({unlocked}/{total_t}){marker}')

    return ordered_cats


def _print_main_commands(state) -> None:
    """Список общих команд внизу main menu."""
    print(f'\n{Fore.LIGHTBLACK_EX}Команды:{Style.RESET_ALL}')
    # 4.62.3 — Seals & Titles entry. Показывает count unlocked/total.
    total_seals = len(SEALS)
    unlocked_seals = len(available_seals(state))
    print(f'  [{Fore.LIGHTCYAN_EX}s{Style.RESET_ALL}] 🏅 Seals & Titles '
          f'({unlocked_seals}/{total_seals} unlocked)')
    print(f'  [{Fore.LIGHTCYAN_EX}r{Style.RESET_ALL}] 🔄 Sync from history (вручную)')
    print(f'  [{Fore.LIGHTCYAN_EX}0{Style.RESET_ALL}] Назад')


# --- 4.62.3 Seals view ---

def _open_seals_view(state) -> None:
    """Список всех SEALS + UI выбора title.

    Каждый seal:
    - ✅ UNLOCKED → опция «Носить» (если не текущий title) или «Снять» (если)
    - 🔒 LOCKED → progress «N/M capstones»
    """
    while True:
        print(f'\n{_SEP}')
        print(f'🏅 {Fore.LIGHTYELLOW_EX}Seals & Titles{Style.RESET_ALL}')
        print(_SEP)

        # Текущий title.
        current = state.title
        if current:
            print(f'\nТекущий титул: {Fore.LIGHTYELLOW_EX}👑 {current}{Style.RESET_ALL}'
                  f'  [{Fore.LIGHTCYAN_EX}u{Style.RESET_ALL}] снять')
        else:
            print(f'\nТекущий титул: {Fore.LIGHTBLACK_EX}(не выбран){Style.RESET_ALL}')

        # Список seals по order из CATEGORIES.
        seal_keys = sorted(
            SEALS.keys(),
            key=lambda k: CATEGORIES.get(k, {}).get('order', 999)
        )
        print()
        for i, cat_key in enumerate(seal_keys, start=1):
            meta = SEALS[cat_key]
            name = meta.get('name', cat_key.title())
            icon = meta.get('icon', '🏅')
            cat_triumph_ids = [
                tid for tid, spec in TRIUMPHS.items()
                if spec.get('category') == cat_key
            ]
            total = len(cat_triumph_ids)
            unlocked = sum(
                1 for tid in cat_triumph_ids
                if int(state.triumphs.get(tid, {}).get('tier', 0)) >=
                   len(TRIUMPHS[tid].get('tiers', []))
                and len(TRIUMPHS[tid].get('tiers', [])) > 0
            )

            is_unlocked = is_seal_unlocked(state, cat_key)
            if is_unlocked:
                status = f'{Fore.LIGHTGREEN_EX}✅ UNLOCKED{Style.RESET_ALL}'
                is_worn = (current == name)
                action = (f'  [{Fore.LIGHTCYAN_EX}{i}{Style.RESET_ALL}] '
                          f'{"Снять" if is_worn else "Носить"}')
                worn_marker = (f' {Fore.LIGHTYELLOW_EX}(надет){Style.RESET_ALL}'
                               if is_worn else '')
                print(f'  {icon} {Fore.LIGHTCYAN_EX}{name}{Style.RESET_ALL}'
                      f'{worn_marker}  {status}{action}')
            else:
                status = (f'{Fore.LIGHTBLACK_EX}🔒 LOCKED — '
                          f'{unlocked}/{total} capstones{Style.RESET_ALL}')
                print(f'  {icon} {Fore.LIGHTBLACK_EX}{name}{Style.RESET_ALL}  {status}')

        print(f'\n  [{Fore.LIGHTCYAN_EX}0{Style.RESET_ALL}] Назад')

        choice = input('\n>>> ').strip().lower()

        if choice == '0':
            return
        if choice == 'u':
            if state.title is not None:
                old = state.title
                set_title(state, None)
                print(f'{Fore.LIGHTBLACK_EX}Снял титул «{old}».{Style.RESET_ALL}')
                _persist_silent()
            continue
        if choice.isdigit() and 1 <= int(choice) <= len(seal_keys):
            cat_key = seal_keys[int(choice) - 1]
            if not is_seal_unlocked(state, cat_key):
                print(f'{Fore.LIGHTRED_EX}Этот seal ещё не открыт.{Style.RESET_ALL}')
                continue
            name = SEALS[cat_key]['name']
            if state.title == name:
                # Toggle off — snimaiem.
                set_title(state, None)
                print(f'{Fore.LIGHTBLACK_EX}Снял титул «{name}».{Style.RESET_ALL}')
            else:
                set_title(state, name)
                print(f'\n{Fore.LIGHTGREEN_EX}👑 Надел титул '
                      f'«{name}».{Style.RESET_ALL}')
            _persist_silent()
            continue
        print(f'{Fore.LIGHTRED_EX}Неизвестная команда.{Style.RESET_ALL}')


def open_triumphs_menu(state) -> None:
    """Главный entry для CLI menu. Loop'ится пока игрок не нажмёт «0».

    Flow:
    1. Если первый launch (флаг не установлен и history.jsonl есть) — prompt backfill
    2. Печать main menu (pinned + unclaimed banner + categories)
    3. Input loop: 0 (back), r (sync), a (claim all), 1..N (категория)
    """
    _check_first_launch_backfill_prompt(state)

    while True:
        _print_header(state)
        ordered_cats = _print_main_menu(state)
        _print_main_commands(state)

        choice = input('\n>>> ').strip().lower()

        if choice == '0':
            return
        if choice in ('r', 'р'):
            _do_backfill(state)
            continue
        if choice == 'a':
            _do_claim_all(state)
            continue
        if choice == 's':
            _open_seals_view(state)
            continue
        if choice.isdigit() and ordered_cats:
            num = int(choice)
            if 1 <= num <= len(ordered_cats):
                _open_category_view(state, ordered_cats[num - 1])
                continue
        print(f'\n{Fore.LIGHTRED_EX}Неизвестная команда.{Style.RESET_ALL}')
