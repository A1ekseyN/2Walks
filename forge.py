"""Forge — Кузница (4.59). Ремонт + Crafting + (deferred) Gems system.

4.59.0 (0.2.4m) — infra + skeleton меню с 5 пунктами.
4.59.1 (0.2.4n) — Repair: восстановление quality предметов через шаги/деньги/энергию.
4.59.2 (0.2.4o) — Crafting: upgrade Grade (2 идентичных → 1 next grade),
    quality = avg, bonus = item_bonus_value(next), price = item_price formula.
    Cost линейный по tier: C→B 1k/100/10 ... S→S+ 4k/400/40. Cap = s+grade.

Все handler'ы 3-5 — stub'ы для отложенной 4.59.3 (Gems system).
"""

from typing import Optional

from colorama import Fore, Style

from actions import try_spend
from bonus import apply_trader, backpack_capacity
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
    # 4.60 — эффективная цена за 1% с учётом forge-скидок (steps/money).
    eff_steps, eff_money, eff_energy = repair_cost_effective(1, state)
    by_steps = headroom if eff_steps <= 0 else state.steps.can_use // eff_steps
    by_money = headroom if eff_money <= 0 else int(state.money // eff_money)
    by_energy = headroom if eff_energy <= 0 else state.energy // eff_energy
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


_EQUIPMENT_SLOT_LABELS = {label for _, label in _EQUIPMENT_SLOTS}


def _candidate_label(location: str, item: dict) -> str:
    """`[Голова] Helmet a-grade (qty 67.5)` — строка для меню выбора.

    Для equipped предметов префикс `[Слот]` подсвечивается зелёным
    (тот же оттенок что и Energy в status_bar) — игрок сразу видит
    что предмет надет.
    """
    item_type = item.get('item_type', ['?'])[0]
    grade = item.get('grade', ['?'])[0]
    quality = item.get('quality', [0])[0]
    if isinstance(quality, float):
        quality = round(quality, 2)
    if location in _EQUIPMENT_SLOT_LABELS:
        prefix = f'[{Fore.GREEN}{location}{Style.RESET_ALL}]'
    else:
        prefix = f'[{location}]'
    return f'{prefix} {str(item_type).title()} {grade} (Quality: {_c_quality(quality)})'


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
    steps, money, energy = repair_cost_effective(percent, state)
    from_quality = item['quality'][0]
    if not try_spend(state, steps=steps, energy=energy, money=float(money)):
        return False
    # 4.60 — forge_repair_quality: восстанавливаем percent × множитель (≥1).
    from bonus import forge_repair_multiplier
    restored = percent * forge_repair_multiplier(state)
    item['quality'][0] = min(100.0, from_quality + restored)
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

# ----- Цвет ресурсов (симметрично с functions.status_bar) -----

def _c_steps(n) -> str:
    """Steps в LIGHTCYAN_EX с thousands separator."""
    return f'{Fore.LIGHTCYAN_EX}{n:,}{Style.RESET_ALL}'


def _c_money(n) -> str:
    """Money в LIGHTYELLOW_EX. Принимает int (cost) или str (отформатированный)."""
    return f'{Fore.LIGHTYELLOW_EX}{n}{Style.RESET_ALL}'


def _c_energy(n) -> str:
    """Energy в GREEN."""
    return f'{Fore.GREEN}{n}{Style.RESET_ALL}'


def _c_quality(quality) -> str:
    """Цветной quality по 3-зонной шкале:
    < 20 — красный (критично), 20..50 — жёлтый, ≥ 50 — зелёный.
    Игрок мгновенно видит что срочно ремонтировать.
    """
    try:
        q = float(quality)
    except (TypeError, ValueError):
        return str(quality)
    if q < 20:
        color = Fore.LIGHTRED_EX
    elif q < 50:
        color = Fore.LIGHTYELLOW_EX
    else:
        color = Fore.GREEN
    return f'{color}{quality}{Style.RESET_ALL}'


def _fmt_cost(steps: int, money: float, energy: int, sep: str = ' + ',
              energy_word: str = 'эн') -> str:
    """Цветной cost-string: 'X шагов + Y $ + Z эн' с status_bar-цветами.

    money может быть float (forge-скидки округляют до 2 знаков) — целые
    значения показываем без хвоста '.0'.
    """
    money_disp: object = int(money) if float(money).is_integer() else round(money, 2)
    return (f'{_c_steps(steps)} шагов{sep}'
            f'{_c_money(money_disp)} ${sep}'
            f'{_c_energy(energy)} {energy_word}')


def _print_forge_header(state: GameState) -> None:
    """Шапка меню Кузницы — текущие ресурсы.

    Цвета/формат симметричны с `functions.status_bar`:
    Steps — LIGHTCYAN_EX + thousands separator, Energy — GREEN,
    Money — LIGHTYELLOW_EX + format_money.
    """
    print('\n--- 🔨 Кузница 🔨 ---')
    print(f'Steps 🏃: {_c_steps(state.steps.can_use)}, '
          f'Energy 🔋: {_c_energy(state.energy)}, '
          f'Money 💰: {_c_money(format_money(state.money))} $.')


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
        print(f'Цена ремонта: 1% = '
              f'{_fmt_cost(REPAIR_STEPS_PER_PERCENT, REPAIR_MONEY_PER_PERCENT, REPAIR_ENERGY_PER_PERCENT)}.\n')
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
    full_steps, full_money, full_energy = repair_cost_effective(headroom, state)

    item_type = item.get('item_type', ['?'])[0]
    grade = item.get('grade', ['?'])[0]
    print(f'\n{str(item_type).title()} {grade} '
          f'(quality: {round(float(quality), 2)} / 100, repair cap: +{headroom}%)')
    print(f'На полное восстановление нужно: '
          f'{_fmt_cost(full_steps, full_money, full_energy, energy_word="энергии")}.')

    if max_pct == 0:
        print(f'Не хватает ресурсов даже на 1% (нужно '
              f'{_fmt_cost(REPAIR_STEPS_PER_PERCENT, REPAIR_MONEY_PER_PERCENT, REPAIR_ENERGY_PER_PERCENT)}).')
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
    steps_spent, money_spent, energy_spent = repair_cost_effective(pct, state)
    print(f'\n✅ Ремонт +{pct}%. Quality: {round(float(quality), 2)} → '
          f'{round(float(new_quality), 2)}. '
          f'Потрачено: {_fmt_cost(steps_spent, money_spent, energy_spent, sep=" / ")}.')


# ----- 4.59.2 Crafting: pure helpers -----

GRADE_TIER: dict[str, int] = {
    'c-grade': 1,
    'b-grade': 2,
    'a-grade': 3,
    's-grade': 4,
    's+grade': 5,
}

GRADE_NEXT: dict[str, str] = {
    'c-grade': 'b-grade',
    'b-grade': 'a-grade',
    'a-grade': 's-grade',
    's-grade': 's+grade',
    # s+grade — cap, нет next
}

GRADE_BONUS_VALUE: dict[str, int] = {
    'c-grade': 1,
    'b-grade': 2,
    'a-grade': 3,
    's-grade': 4,
    's+grade': 5,
}

GRADE_PRICE_MULTIPLIER: dict[str, float] = {
    'c-grade': 0.5,
    'b-grade': 1.0,
    'a-grade': 1.5,
    's-grade': 2.0,
    's+grade': 2.5,
}


def crafting_cost(source_grade: str) -> tuple[int, int, int]:
    """Cost upgrade одного источника grade'а на 1 ступень.

    Линейный по tier: cost = tier × (1000 шагов, 100 $, 10 эн).
    s+grade → (0, 0, 0) (cap, нельзя крафтить).
    """
    if source_grade == 's+grade':
        return (0, 0, 0)
    tier = GRADE_TIER.get(source_grade, 0)
    return (tier * 1000, tier * 100, tier * 10)


# 4.60 — Эффективная стоимость с учётом forge-навыков экономии (steps/money).
# Energy не трогаем (по дизайну 28.05.2026 — energy-навыка пока нет).
def repair_cost_effective(percent: int, state: GameState) -> tuple[int, float, int]:
    """repair_cost со скидками forge_steps_saving / forge_money_saving.

    money — float (apply_forge_money_saving округляет до 2 знаков); steps/energy — int.
    """
    from bonus import apply_forge_steps_saving, apply_forge_money_saving
    steps, money, energy = repair_cost(percent)
    return apply_forge_steps_saving(steps, state), apply_forge_money_saving(money, state), energy


def crafting_cost_effective(source_grade: str, state: GameState) -> tuple[int, float, int]:
    """crafting_cost со скидками forge_steps_saving / forge_money_saving.

    money — float (apply_forge_money_saving округляет до 2 знаков); steps/energy — int.
    """
    from bonus import apply_forge_steps_saving, apply_forge_money_saving
    steps, money, energy = crafting_cost(source_grade)
    return apply_forge_steps_saving(steps, state), apply_forge_money_saving(money, state), energy


def _item_key(item: dict) -> Optional[tuple[str, str, str]]:
    """Identity для группировки crafting: (item_type, characteristic, grade).

    None если у предмета нет одного из полей (например, consumable из shop).
    """
    item_type = item.get('item_type', [None])[0]
    characteristic = item.get('characteristic', [None])[0]
    grade = item.get('grade', [None])[0]
    if item_type is None or characteristic is None or grade is None:
        return None
    return (item_type, characteristic, grade)


def _iter_all_items(state: GameState):
    """Yields (item_ref, location_label, slot_attr_or_none).

    slot_attr: 'head'/'neck'/... для equipment, None для inventory.
    """
    for slot_attr, slot_label in _EQUIPMENT_SLOTS:
        item = getattr(state.equipment, slot_attr)
        if item is None:
            continue
        yield item, slot_label, slot_attr
    for item in state.inventory:
        yield item, 'Инвентарь', None


def find_craftable_groups(state: GameState) -> list[dict]:
    """Группы предметов с count ≥ 2, готовые для crafting.

    Возвращает список dict'ов:
        {
            'item_type': str, 'characteristic': str, 'grade': str,
            'next_grade': Optional[str],  # None если уже s+grade
            'cost': (steps, money, energy),  # (0,0,0) если cap
            'candidates': [(item_ref, location_label, slot_attr), ...],
        }
    Группы сортируются по grade asc (C первым) для стабильности UI.
    """
    by_key: dict[tuple[str, str, str], list[tuple[dict, str, Optional[str]]]] = {}
    for item, location, slot_attr in _iter_all_items(state):
        key = _item_key(item)
        if key is None:
            continue
        by_key.setdefault(key, []).append((item, location, slot_attr))

    groups: list[dict] = []
    for (item_type, characteristic, grade), candidates in by_key.items():
        if len(candidates) < 2:
            continue
        next_grade = GRADE_NEXT.get(grade)
        cost = crafting_cost_effective(grade, state)
        groups.append({
            'item_type': item_type,
            'characteristic': characteristic,
            'grade': grade,
            'next_grade': next_grade,
            'cost': cost,
            'candidates': candidates,
        })
    groups.sort(key=lambda g: (GRADE_TIER.get(g['grade'], 0), g['item_type'], g['characteristic']))
    return groups


def craft_item(state: GameState, item_a: dict, item_b: dict) -> Optional[dict]:
    """Атомарный crafting: 2 идентичных source → 1 next grade.

    Returns dict нового item'а при успехе, None при отказе. Pre-checks:
    - item_a != item_b (по identity, не по значению),
    - оба ссылочно валидны (есть в equipment слотах или inventory),
    - одинаковые (item_type, characteristic, grade),
    - grade != 's+grade' (cap),
    - ресурсов хватает (try_spend),
    - после удаления sources + add new — инвентарь не overflow.

    Snyatii equipped sources (slot = None) + удаление inventory sources +
    append нового item'а в inventory + log_event. Возвращает новый item.
    """
    if item_a is item_b:
        return None
    key_a = _item_key(item_a)
    key_b = _item_key(item_b)
    if key_a is None or key_b is None or key_a != key_b:
        return None
    _, _, grade = key_a
    next_grade = GRADE_NEXT.get(grade)
    if next_grade is None:  # s+grade cap
        return None

    sources_meta = _locate_sources(state, [item_a, item_b])
    if sources_meta is None:
        return None  # один из item'ов не нашли в state

    # Inventory capacity check: после операции inventory size =
    # текущий - кол-во inventory-sources + 1 (новый item).
    n_inv_sources = sum(1 for slot_attr in sources_meta if slot_attr is None)
    n_equipped_sources = len(sources_meta) - n_inv_sources
    projected_inv_size = len(state.inventory) - n_inv_sources + 1
    if projected_inv_size > backpack_capacity(state):
        return None

    steps, money, energy = crafting_cost_effective(grade, state)
    if not try_spend(state, steps=steps, energy=energy, money=float(money)):
        return None

    # Снимаем equipped sources (slot = None).
    for slot_attr in sources_meta:
        if slot_attr is not None:
            setattr(state.equipment, slot_attr, None)
    # Удаляем inventory sources (identity-based — by `is`).
    state.inventory = [it for it in state.inventory if it is not item_a and it is not item_b]

    # Создаём новый item.
    quality_a = float(item_a['quality'][0])
    quality_b = float(item_b['quality'][0])
    new_quality = round((quality_a + quality_b) / 2, 2)
    new_item: dict = {
        'item_name': [item_a['item_type'][0]],
        'item_type': [item_a['item_type'][0]],
        'grade': [next_grade],
        'characteristic': [item_a['characteristic'][0]],
        'bonus': [GRADE_BONUS_VALUE[next_grade]],
        'quality': [new_quality],
        'price': [int(new_quality * GRADE_PRICE_MULTIPLIER[next_grade])],
    }
    state.inventory.append(new_item)

    from history import log_event
    log_event(
        'item_crafted',
        item_type=item_a['item_type'][0],
        characteristic=item_a['characteristic'][0],
        from_grade=grade,
        to_grade=next_grade,
        qual_1=round(quality_a, 2),
        qual_2=round(quality_b, 2),
        new_quality=new_quality,
        new_price=new_item['price'][0],
        was_equipped=n_equipped_sources,
        # 4.62.1.4 (22.05.2026) — cost_* в payload для Triumphs energy tracking.
        cost_steps=steps,
        cost_money=money,
        cost_energy=energy,
    )
    return new_item


def _locate_sources(state: GameState, items: list[dict]) -> Optional[list[Optional[str]]]:
    """Для каждого item возвращает slot_attr ('head'/...) или None (inventory).

    None для всего списка если хотя бы один item не найден ни в equipment,
    ни в inventory (защита от stale ссылок).
    """
    result: list[Optional[str]] = []
    for item in items:
        found = False
        for slot_attr, _ in _EQUIPMENT_SLOTS:
            if getattr(state.equipment, slot_attr) is item:
                result.append(slot_attr)
                found = True
                break
        if found:
            continue
        if item in state.inventory:
            result.append(None)
            continue
        return None
    return result


# ----- UI: Crafting flow -----

def _do_craft(state: GameState) -> None:
    """4.59.2 — Crafting UI. Auto-scan → manual selection → preview → yes confirm."""
    groups = find_craftable_groups(state)
    if not groups:
        print('\n📭 Нечего улучшать: нужно ≥ 2 идентичных предметов '
              '(один item_type + characteristic + grade).')
        return

    print('\n--- 🔨 Улучшение предметов ---')
    print('Доступно для улучшения:\n')
    for idx, g in enumerate(groups, start=1):
        n_steps, n_money, n_energy = g['cost']
        if g['next_grade'] is None:
            target_str = f'(cap — {g["grade"]} уже max, нельзя крафтить)'
            cost_str = '—'
        else:
            target_str = (f'→ {g["item_type"].title()} {g["next_grade"]} '
                          f'{g["characteristic"]} (+{GRADE_BONUS_VALUE[g["next_grade"]]})')
            cost_str = _fmt_cost(n_steps, n_money, n_energy, energy_word='энергии')
        print(f'  {idx}. {g["item_type"].title()} {g["grade"]} {g["characteristic"]} '
              f'({len(g["candidates"])} шт.) {target_str}')
        print(f'     Cost: {cost_str}')
    print('\n  0. Назад')

    choice = _ask_int('>>> ')
    if choice is None or choice == 0:
        return
    if not (1 <= choice <= len(groups)):
        print('\nНеверный выбор.')
        return

    group = groups[choice - 1]
    if group['next_grade'] is None:
        print(f'\n{group["grade"]} — это cap, дальше улучшать нельзя.')
        return

    _craft_group_flow(state, group)


def _craft_group_flow(state: GameState, group: dict) -> None:
    """Шаг 2: показ candidates → выбор 2 → preview → yes confirm → craft."""
    steps, money, energy = group['cost']
    affordable = (state.steps.can_use >= steps and state.money >= money
                  and state.energy >= energy)
    print(f'\n--- Выбери 2 предмета для крафта ---')
    print(f'Cost: {_fmt_cost(steps, money, energy, energy_word="энергии")} '
          f'(хватает: {"✓" if affordable else "✗"})\n')
    print('  #   Quality  Sell  Status')
    for idx, (item, location, slot_attr) in enumerate(group['candidates'], start=1):
        quality = item['quality'][0]
        if isinstance(quality, float):
            quality = round(quality, 2)
        sell_price = apply_trader(item.get('price', [0])[0], state)
        marker = '🟢 ' if slot_attr is not None else '   '
        loc_label = f'{location} ({slot_attr})' if slot_attr else location
        print(f'  {idx:<3} {str(quality):<7} {_c_money(format_money(sell_price))} '
              f'$ {marker}{loc_label}')
    print('\nВведи 2 номера через запятую (например: 4,5). 0 — назад.')

    raw = input('>>> ').strip()
    if raw == '0' or not raw:
        return
    indices = _parse_two_indices(raw, len(group['candidates']))
    if indices is None:
        print('\nНеверный формат (нужно 2 разных номера в диапазоне).')
        return

    i_a, i_b = indices
    item_a, loc_a, slot_a = group['candidates'][i_a - 1]
    item_b, loc_b, slot_b = group['candidates'][i_b - 1]

    _craft_preview_and_confirm(state, group, item_a, item_b,
                                (loc_a, slot_a), (loc_b, slot_b))


def _parse_two_indices(raw: str, max_idx: int) -> Optional[tuple[int, int]]:
    """'4,5' → (4, 5) если два разных int в 1..max_idx. None при ошибке."""
    parts = [p.strip() for p in raw.replace(' ', ',').split(',') if p.strip()]
    if len(parts) != 2:
        return None
    try:
        a, b = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if a == b:
        return None
    if not (1 <= a <= max_idx and 1 <= b <= max_idx):
        return None
    return (a, b)


def _craft_preview_and_confirm(
    state: GameState,
    group: dict,
    item_a: dict,
    item_b: dict,
    meta_a: tuple[str, Optional[str]],
    meta_b: tuple[str, Optional[str]],
) -> None:
    """Preview + warning если equipped + explicit `yes` confirmation."""
    next_grade = group['next_grade']
    quality_a = float(item_a['quality'][0])
    quality_b = float(item_b['quality'][0])
    new_quality = round((quality_a + quality_b) / 2, 2)
    new_bonus = GRADE_BONUS_VALUE[next_grade]
    new_price_est = int(new_quality * GRADE_PRICE_MULTIPLIER[next_grade])
    new_price_with_trader = apply_trader(new_price_est, state)
    steps, money, energy = group['cost']

    print(f'\nТы выбрал:')
    for item, (loc, slot) in [(item_a, meta_a), (item_b, meta_b)]:
        loc_label = f'{loc} ({slot})' if slot else loc
        print(f'  - {item["item_type"][0].title()} {item["grade"][0]} '
              f'{item["characteristic"][0]} (qual {round(float(item["quality"][0]), 2)}, '
              f'{loc_label})')

    print(f'\nРезультат: {item_a["item_type"][0].title()} {next_grade} '
          f'{item_a["characteristic"][0]} +{new_bonus}')
    print(f'  quality = ({round(quality_a, 2)} + {round(quality_b, 2)}) / 2 = {new_quality}')
    print(f'  price ≈ {_c_money(format_money(new_price_with_trader))} $ (с учётом trader skill)')
    print(f'\nCost: {_fmt_cost(steps, money, energy, energy_word="энергии")}')

    # Equipped warning
    equipped_sources = [
        (item, meta) for item, meta in [(item_a, meta_a), (item_b, meta_b)]
        if meta[1] is not None
    ]
    if equipped_sources:
        print(f'\n⚠️  ВНИМАНИЕ: {len(equipped_sources)} '
              f'{"предмета" if len(equipped_sources) == 2 else "предмет"} сейчас '
              f'{"надеты" if len(equipped_sources) == 2 else "надет"}:')
        for item, (loc, slot) in equipped_sources:
            print(f'   - {slot} ({item["item_type"][0].title()} {item["grade"][0]} '
                  f'{item["characteristic"][0]}, qual {round(float(item["quality"][0]), 2)})')
        slots = ', '.join(meta[1] for _, meta in equipped_sources if meta[1])
        print(f'\nПосле крафта слот{"ы" if len(equipped_sources) > 1 else ""} '
              f'{slots} останутся пустыми — ты потеряешь бонус.')

    confirm = input("\nПодтвердить улучшение? Введи 'yes' для подтверждения:\n>>> ").strip().lower()
    if confirm not in ('yes', 'y'):
        print('\nКрафт отменён.')
        return

    result = craft_item(state, item_a, item_b)
    if result is None:
        print('\nНе удалось выполнить крафт (ресурсы / overflow инвентаря / stale ссылки).')
        return

    print(f'\n✅ Создан: {result["item_type"][0].title()} {result["grade"][0]} '
          f'{result["characteristic"][0]} +{result["bonus"][0]} '
          f'(quality {result["quality"][0]}, price {_c_money(result["price"][0])} $). '
          f'Положен в инвентарь.')


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
