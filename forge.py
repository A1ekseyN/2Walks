"""Forge — Кузница (4.59). Ремонт + Crafting + (deferred) Gems system.

4.59.0 (0.2.4m) — infra + skeleton меню с 5 пунктами.
4.59.1 (0.2.4n) — Repair: восстановление quality предметов через шаги/деньги/энергию.

Все handler'ы 3-5 — stub'ы для отложенной 4.59.3 (Gems system).
"""

from typing import Optional

from actions import try_spend
from functions_02 import format_money
from state import GameState


# ----- 4.59.1 Repair: pure helpers -----

REPAIR_STEPS_PER_PERCENT = 1000
REPAIR_MONEY_PER_PERCENT = 100
REPAIR_ENERGY_PER_PERCENT = 10

_EQUIPMENT_SLOTS = [
    ('head', 'Голова'),
    ('neck', 'Шея'),
    ('torso', 'Торс'),
    ('finger_01', 'Палец 1'),
    ('finger_02', 'Палец 2'),
    ('legs', 'Ноги'),
    ('foots', 'Ступни'),
]


def repair_cost(percent: int) -> tuple[int, int, int]:
    """Стоимость ремонта на N процентных пунктов quality.

    Линейная: 1% = 1000 шагов + 100 $ + 10 энергии. См. 4.59.1.
    """
    return (
        percent * REPAIR_STEPS_PER_PERCENT,
        percent * REPAIR_MONEY_PER_PERCENT,
        percent * REPAIR_ENERGY_PER_PERCENT,
    )


def max_repair_percent(state: GameState, item: dict) -> int:
    """Максимально доступный ремонт в процентных пунктах.

    min(100 - current_quality, steps//1000, money//100, energy//10).
    Возвращает 0, если предмет без quality или уже 100%.
    """
    quality = item.get('quality', [None])[0]
    if quality is None:
        return 0
    headroom = max(0, int(100 - quality))
    if headroom == 0:
        return 0
    by_steps = state.steps.can_use // REPAIR_STEPS_PER_PERCENT
    by_money = int(state.money) // REPAIR_MONEY_PER_PERCENT
    by_energy = state.energy // REPAIR_ENERGY_PER_PERCENT
    return min(headroom, by_steps, by_money, by_energy)


def _recalc_item_price(item: dict) -> None:
    """Пересчитывает price предмета по grade × quality.

    Standalone-версия `Wear_Equipped_Items.recalc_item_prices` для одного
    item-dict'а (нужна для ремонта inventory items, не только equipment).
    Формула 1:1 с inventory.py:325.
    """
    grade = item.get('grade', [None])[0]
    quality = item.get('quality', [None])[0]
    if grade is None or quality is None:
        return
    multipliers = {
        'c-grade': 0.5,
        'b-grade': 1.0,
        'a-grade': 1.5,
        's-grade': 2.0,
        's+grade': 2.5,
    }
    mul = multipliers.get(grade)
    if mul is None:
        return
    item['price'][0] = int(quality * mul)


def _candidate_label(location: str, item: dict) -> str:
    """`[Голова] Helmet a-grade (qty 67.5)` — строка для меню выбора."""
    item_type = item.get('item_type', ['?'])[0]
    grade = item.get('grade', ['?'])[0]
    quality = item.get('quality', [0])[0]
    if isinstance(quality, float):
        quality = round(quality, 2)
    return f'[{location}] {str(item_type).title()} {grade} (Quality: {quality})'


def repair_candidates(state: GameState) -> list[tuple[str, dict]]:
    """Все предметы с quality < 100: equipment + inventory.

    Сортировка по (100 - quality) desc — самые повреждённые первыми.
    Возвращает [(label, item_dict), ...]. item — живая ссылка, мутация
    через item['quality'][0] видна в state.
    """
    candidates: list[tuple[str, dict]] = []
    for slot_attr, slot_label in _EQUIPMENT_SLOTS:
        item = getattr(state.equipment, slot_attr)
        if item is None:
            continue
        quality = item.get('quality', [None])[0]
        if quality is None or quality >= 100:
            continue
        candidates.append((_candidate_label(slot_label, item), item))
    for item in state.inventory:
        quality = item.get('quality', [None])[0]
        if quality is None or quality >= 100:
            continue
        candidates.append((_candidate_label('Инвентарь', item), item))
    candidates.sort(key=lambda pair: pair[1].get('quality', [0])[0])
    return candidates


def repair_item(state: GameState, item: dict, percent: int) -> bool:
    """Атомарный ремонт: try_spend → quality += percent → recalc price → log.

    Возвращает False без мутаций если percent > max_repair_percent.
    """
    if percent <= 0:
        return False
    max_pct = max_repair_percent(state, item)
    if percent > max_pct:
        return False
    steps, money, energy = repair_cost(percent)
    from_quality = item['quality'][0]
    if not try_spend(state, steps=steps, energy=energy, money=float(money)):
        return False
    item['quality'][0] = min(100.0, from_quality + percent)
    _recalc_item_price(item)
    from history import log_event
    log_event(
        'item_repaired',
        item_type=item.get('item_type', [None])[0],
        grade=item.get('grade', [None])[0],
        from_quality=round(float(from_quality), 2),
        to_quality=round(float(item['quality'][0]), 2),
        cost_steps=steps,
        cost_money=money,
        cost_energy=energy,
    )
    return True


# ----- UI: меню Кузницы -----

def _print_forge_header(state: GameState) -> None:
    """Шапка меню Кузницы — текущие ресурсы."""
    print('\n--- 🔨 Кузница 🔨 ---')
    print(f'Steps 🏃: {state.steps.can_use}, '
          f'Energy 🔋: {state.energy}, '
          f'Money 💰: {format_money(state.money)} $.')


def _ask_int(prompt: str) -> Optional[int]:
    """Числовой prompt: int или None при невалидном вводе/пустой строке."""
    raw = input(prompt).strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _do_repair(state: GameState) -> None:
    """4.59.1 — Repair UI. Выбор предмета → выбор процентов → confirm."""
    while True:
        candidates = repair_candidates(state)
        if not candidates:
            print('\n✅ Все предметы в идеальном состоянии (quality 100) либо нечего ремонтировать.')
            return
        print('\n--- 🔧 Ремонт предметов ---')
        print(f'Цена ремонта: 1% = {REPAIR_STEPS_PER_PERCENT:,} шагов '
              f'+ {REPAIR_MONEY_PER_PERCENT} $ + {REPAIR_ENERGY_PER_PERCENT} эн.\n')
        for idx, (label, _) in enumerate(candidates, start=1):
            print(f'\t{idx}. {label}')
        print('\t0. Назад')

        choice = _ask_int('>>> ')
        if choice is None:
            print('\nНеверный выбор. Попробуйте ещё раз.')
            continue
        if choice == 0:
            return
        if not (1 <= choice <= len(candidates)):
            print('\nНеверный выбор. Попробуйте ещё раз.')
            continue

        _, item = candidates[choice - 1]
        _repair_preview_and_apply(state, item)
        return  # после repair (или отказа) — выход в меню Кузницы


def _repair_preview_and_apply(state: GameState, item: dict) -> None:
    """Preview cost-расчёта + prompt процентов + try_spend."""
    quality = item['quality'][0]
    headroom = max(0, int(100 - quality))
    max_pct = max_repair_percent(state, item)
    full_steps, full_money, full_energy = repair_cost(headroom)

    item_type = item.get('item_type', ['?'])[0]
    grade = item.get('grade', ['?'])[0]
    print(f'\n{str(item_type).title()} {grade} '
          f'(quality: {round(float(quality), 2)} / 100, repair cap: +{headroom}%)')
    print(f'На полное восстановление нужно: '
          f'{full_steps:,} шагов + {full_money} $ + {full_energy} энергии.')

    if max_pct == 0:
        print('Не хватает ресурсов даже на 1% (нужно 1,000 шагов + 100 $ + 10 эн).')
        return

    print(f'Можешь восстановить: до {max_pct}% (хватает ресурсов).')
    pct = _ask_int(f'Сколько процентов восстановить (1..{max_pct}, 0 — отмена)? \n>>> ')
    if pct is None or pct == 0:
        print('\nРемонт отменён.')
        return
    if not (1 <= pct <= max_pct):
        print('\nЗначение вне диапазона. Ремонт отменён.')
        return

    if not repair_item(state, item, pct):
        print('\nНе удалось списать ресурсы (race condition?). Ремонт отменён.')
        return

    new_quality = item['quality'][0]
    steps_spent, money_spent, energy_spent = repair_cost(pct)
    print(f'\n✅ Ремонт +{pct}%. Quality: {round(float(quality), 2)} → '
          f'{round(float(new_quality), 2)}. '
          f'Потрачено: {steps_spent:,} шагов / {money_spent} $ / {energy_spent} эн.')


def _do_craft(state: GameState) -> None:
    """4.59.2 — Crafting: upgrade grade (2 → 1). TODO."""
    print('\n⚙ Улучшить Grade предмета — функционал в разработке (4.59.2).')


def _do_socket_create(state: GameState) -> None:
    """4.59.3 — Gem sockets (deferred, low-priority)."""
    print('\n⚙ Сделать дырку в предмете для камня — в разработке (4.59.3, отложено).')


def _do_socket_insert(state: GameState) -> None:
    """4.59.3 — Insert gem in socket (deferred, low-priority)."""
    print('\n⚙ Вставить камень в предмет — в разработке (4.59.3, отложено).')


def _do_gem_combine(state: GameState) -> None:
    """4.59.3 — Combine 3 gems → 1 higher grade (deferred, low-priority)."""
    print('\n⚙ Объединить камни — в разработке (4.59.3, отложено).')


def forge_menu(state: GameState) -> None:
    """Главное меню Кузницы. Цикл retry — выходит только по '0'.

    Pattern идентичен `bank_menu` (4.49). UI loop с шапкой ресурсов
    и dispatch на handler-функции. Невалидный выбор → continue цикла.
    """
    while True:
        _print_forge_header(state)
        print('\nВ кузнице можно:')
        print('\t1. Отремонтировать предмет')
        print('\t2. Улучшить Grade предмета')
        print('\t3. Сделать дырку в предмете для камня (В разработке)')
        print('\t4. Вставить камень в предмет (В разработке)')
        print('\t5. Объединить камни (В разработке)')
        print('\t0. Назад')
        choice = input('>>> ').strip()
        if choice == '0':
            return
        if choice == '1':
            _do_repair(state)
        elif choice == '2':
            _do_craft(state)
        elif choice == '3':
            _do_socket_create(state)
        elif choice == '4':
            _do_socket_insert(state)
        elif choice == '5':
            _do_gem_combine(state)
        else:
            print('\nНеверный выбор. Попробуйте ещё раз.')
