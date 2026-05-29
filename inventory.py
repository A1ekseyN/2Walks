"""Инвентарь — отображение, продажа, износ экипированных предметов.

Чистая логика (`_sort_inventory`, `_sell_item_at_index`) выделена для
тестируемости — UI-обёртки `inventory_menu` / `sold_item` остаются с input/print.
"""

from bonus import apply_trader, backpack_capacity
from state import GameState


# ----- Чистая логика (тестируется напрямую) -----

def _sort_inventory(inventory: list[dict]) -> list[dict]:
    """Сортирует инвентарь по (item_type, characteristic, -bonus). Pure."""
    return sorted(
        inventory,
        key=lambda x: (
            x.get('item_type', ''),
            x.get('characteristic', ''),
            -x.get('bonus', [0])[0],
        ),
    )


def _resolve_pending_drop_sell_existing(state: GameState, inventory_index: int) -> tuple[dict, dict, float]:
    """4.50.1 — Resolve pending drop: продать предмет инвентаря по индексу,
    положить pending на освободившийся слот.

    Возвращает (sold_item, kept_item, refund). Mutates: inventory[index] removed,
    money += refund, pending appended to inventory, pending=None.
    """
    sold_item = state.inventory[inventory_index]
    try:
        # 4.28 (0.2.4h) — apply_trader применяет skill-бонус к цене продажи.
        refund = apply_trader(sold_item['price'][0], state)
    except (KeyError, IndexError, TypeError):
        refund = 0
    state.money += refund
    del state.inventory[inventory_index]

    kept_item = state.pending_drop
    state.pending_drop = None
    state.inventory.append(kept_item)

    from history import log_event
    log_event('drop_resolved_sell_existing',
              sold_type=_first(sold_item.get('item_type')),
              sold_grade=_first(sold_item.get('grade')),
              sold_refund=refund,
              kept_type=_first(kept_item.get('item_type')),
              kept_grade=_first(kept_item.get('grade')),
              kept_characteristic=_first(kept_item.get('characteristic')),
              kept_bonus=_first(kept_item.get('bonus')),
              kept_quality=_first(kept_item.get('quality')),
              kept_price=_first(kept_item.get('price')))
    return sold_item, kept_item, refund


def _resolve_pending_drop_sell_new(state: GameState) -> tuple[dict, float]:
    """4.50.1 — Resolve pending drop: продать саму находку за base price.
    Инвентарь не трогается. Возвращает (sold_pending, refund)."""
    pending = state.pending_drop
    try:
        # 4.28 (0.2.4h) — apply_trader применяет skill-бонус к цене продажи.
        refund = apply_trader(pending['price'][0], state)
    except (KeyError, IndexError, TypeError):
        refund = 0
    state.money += refund
    state.pending_drop = None

    from history import log_event
    log_event('drop_resolved_sell_new',
              item_type=_first(pending.get('item_type')),
              grade=_first(pending.get('grade')),
              refund=refund)
    return pending, refund


def _sell_item_at_index(state: GameState, index: int) -> tuple[dict, float]:
    """Продажа предмета по индексу — мутирует state.inventory и state.money.

    Возвращает (item, refund). Refund добавляется к state.money.
    Если у предмета нет цены — refund=0.
    """
    item = state.inventory[index]
    try:
        # 4.28 (0.2.4h) — apply_trader применяет skill-бонус к цене продажи.
        refund = apply_trader(item['price'][0], state)
    except (KeyError, IndexError, TypeError):
        refund = 0
    state.money += refund
    del state.inventory[index]
    # 4.6 — log_event продажи предмета. _first() безопасно достаёт значение
    # из list-обёртки legacy item-формата (рефакторинг в 1.6).
    from history import log_event
    log_event('item_sold',
              item_type=_first(item.get('item_type')),
              grade=_first(item.get('grade')),
              characteristic=_first(item.get('characteristic')),
              bonus=_first(item.get('bonus')),
              refund=refund)
    return item, refund


def _first(values):
    """Безопасно достать первый элемент list-обёртки item-поля. None если пусто."""
    if not values:
        return None
    return values[0]


# ----- UI-обёртки -----

def inventory_menu(state: GameState) -> None:
    # Цикл retry на невалиде (1.5.3 — 0.2.1h, было: рекурсивный self-call).
    while True:
        # 4.50.1 — Pending drop resolve (если есть). Показываем prompt в начале
        # каждого захода в Inventory; игрок может skip — pending остаётся, prompt
        # повторится в следующий заход. Persist делает caller (game.py main loop).
        if state.pending_drop is not None:
            _pending_drop_prompt(state)
            # После prompt'а — продолжить обычное меню инвентаря (resolve мог
            # очистить pending или нет; в любом случае показываем меню).

        cap = backpack_capacity(state)
        print('\n--- 🎒 Меню инвентаря 🎒 ---'
              f'\nВсего в инвентаре - {len(state.inventory)}/{cap} предметов: ')
        inventory_view(state)

        ask = input('\nВыберите раздел Инвентаря: '
                    '\ns. Sold / Продать'
                    '\n0. Выход. '
                    '\n>>> ')
        if ask in ('s', 'ы', 'sold', 'ыщдв'):
            sold_item(state)
            return
        if ask == '0':
            return


def _pending_drop_prompt(state: GameState) -> None:
    """4.50.1 — Interactive resolve для `state.pending_drop`. 3 опции:

    - 1..N — продать предмет №N из инвентаря, положить pending на его слот.
    - s — продать саму находку (pending) за base price.
    - 0 — skip (pending остаётся, prompt появится при следующем заходе).

    Цикл retry на невалидном вводе.
    """
    pending = state.pending_drop
    while True:
        print('\n--- 🎁 Pending drop ---'
              f'\nПока тебя ждала находка: '
              f'\n- {pending["grade"][0]}: {pending["item_type"][0].title()} '
              f'+ {pending["bonus"][0]} {pending["characteristic"][0].title()} '
              f'(Качество: {pending["quality"][0]}) (Цена: {pending["price"][0]} $).'
              '\n\nЧто делаем:'
              '\n  1..N — продать предмет №N из инвентаря, положить находку на освободившийся слот'
              '\n  s    — продать находку за её base price'
              '\n  0    — отложить (находка останется, prompt появится при следующем заходе)')

        # Текущее содержимое инвентаря — игрок выбирает что продать.
        sorted_inv = _sort_inventory(state.inventory)
        if sorted_inv:
            print('\nИнвентарь:')
            for ind, item in enumerate(sorted_inv, start=1):
                space = "" if ind >= 10 else " "
                print(f"\t{space}{ind}. {item['item_type'][0].title()} {item['grade'][0]}, "
                      f"+ {item['bonus'][0]} {item['characteristic'][0].title()}, "
                      f"(Quality: {item['quality'][0]}), "
                      f"(Price: {item['price'][0]} $) ")
        else:
            print('\nИнвентарь пуст.')

        ask = input('\n>>> ').strip()
        if ask == '0':
            return  # skip — pending остаётся
        if ask in ('s', 'ы'):
            sold, refund = _resolve_pending_drop_sell_new(state)
            print(f'\nНаходка продана за {refund} $.')
            return
        try:
            idx_one_based = int(ask)
        except ValueError:
            continue
        if not (1 <= idx_one_based <= len(state.inventory)):
            continue
        # Sorted view — но удаляем по индексу из исходного state.inventory.
        # Поскольку sorted_inv = _sort_inventory(state.inventory) возвращает
        # ту же ссылку на dict, используем identity-поиск для надёжности.
        chosen = sorted_inv[idx_one_based - 1]
        try:
            real_index = state.inventory.index(chosen)
        except ValueError:
            continue
        sold, kept, refund = _resolve_pending_drop_sell_existing(state, real_index)
        print(f'\nПродан предмет: {sold["item_type"][0].title()} {sold["grade"][0]} '
              f'(+{refund} $). Находка положена в инвентарь.')
        return


def inventory_view(state: GameState) -> list[dict]:
    """Отображает содержимое инвентаря и возвращает отсортированный список."""
    sorted_inventory = _sort_inventory(state.inventory)

    if sorted_inventory:
        for ind, item in enumerate(sorted_inventory, start=1):
            space = "" if ind >= 10 else " "
            if isinstance(item['quality'][0], float):
                item['quality'][0] = round(item['quality'][0], 2)

            print(f"\t{space}{ind}. {item['item_type'][0].title()} {item['grade'][0]}, "
                  f"+ {item['bonus'][0]} {item['characteristic'][0].title()}, "
                  f"(Quality: {item['quality'][0]}), "
                  f"(Price: {item['price'][0]} $) ")
    else:
        print(' - Пусто')

    return sorted_inventory


def sold_item(state: GameState) -> None:
    # Цикл retry на невалиде / ValueError / неподтверждении (1.5.3 — 0.2.1h).
    while True:
        cap = backpack_capacity(state)
        print('\n--- Продажа предметов из инвентаря: ---')
        print(f'Всего в инвентаре: {len(state.inventory)}/{cap} предметов.')
        state.inventory = inventory_view(state)

        try:
            item_to_sold = int(input(f'\t0. Назад'
                                     f'\n\nКакой предмет хотите продать? (Введите число от 1 до {len(state.inventory)}). \n>>> '))
        except ValueError:
            continue

        if item_to_sold == 0:
            inventory_menu(state)
            return
        if not (1 <= item_to_sold <= len(state.inventory)):
            continue  # вне диапазона — повторяем меню

        item_index = item_to_sold - 1
        item = state.inventory[item_index]

        print(f'\nВы выбрали предмет: '
              f'\n\t- {item["item_type"][0].title()}, '
              f'{item["grade"][0]}, '
              f'+ {item["bonus"][0]} {item["characteristic"][0].title()}, '
              f'(Quality: {item["quality"][0]}), '
              f'(Price: {item["price"][0]} $) '
              f'\n\t- Цена предмета 💰: {item["price"][0]} $')
        ask = input('\nВы уверены, что хотите продать этот предмет? '
                    '\n1. Да'
                    '\n0. Назад \n>>> ')
        if ask == '1':
            sold, refund = _sell_item_at_index(state, item_index)
            print(f'\nВы продали предмет:'
                  f'\n\t- {sold["item_type"][0].title()}, '
                  f'{sold["grade"][0]}, '
                  f'+ {sold["bonus"][0]} {sold["characteristic"][0].title()}, '
                  f'(Quality: {sold["quality"][0]}), '
                  f'(Price: {sold["price"][0]} $) '
                  f'\n\t- Цена предмета 💰: {sold["price"][0]} $')
            if refund == 0:
                print('У предмета нет цены. Продажа за 0 $.')
            inventory_menu(state)
            return
        # ask == '0' или любой другой невалид — продолжаем цикл (показать меню снова).


# ----- Износ экипировки -----

class Wear_Equipped_Items:
    """Подсчёт износа экипированных предметов после активности (Gym/Work/Adventure).

    Phase 4: state читается в момент вызова (не при определении класса), так что
    экипировка отражает актуальные слоты, а не зафиксированные в момент импорта.
    """

    def __init__(self, state: GameState) -> None:
        self._state = state
        self.max_durability = 10000000
        self.durability = self.max_durability
        self.neatness_factor = 1 - (self._state.gym.neatness_in_using_things / 100)

    def _slots(self) -> dict:
        """Текущие предметы по слотам: dict {legacy_key: item_dict_or_None}."""
        eq = self._state.equipment
        return {
            'equipment_head': eq.head,
            'equipment_neck': eq.neck,
            'equipment_torso': eq.torso,
            'equipment_finger_01': eq.finger_01,
            'equipment_finger_02': eq.finger_02,
            'equipment_legs': eq.legs,
            'equipment_foots': eq.foots,
            'equipment_back': eq.back,  # 4.51 — рюкзак изнашивается как все
        }

    def decrease_durability(self, steps: int) -> None:
        """Уменьшает прочность всех экипированных предметов на adjusted_steps.

        adjusted_steps = steps * (1 - neatness/100). Качество <= 0 клэмпится в 0.
        Цены пересчитываются по итогу (recalc_item_prices)."""
        adjusted_steps = steps * self.neatness_factor

        for key, item_info in self._slots().items():
            if item_info is None:
                continue
            initial_quality = item_info['quality'][0]
            wear_without_skill = steps / self.max_durability * 100
            wear_with_skill = adjusted_steps / self.max_durability * 100

            item_durability = self.durability * (initial_quality / 100)
            item_durability -= adjusted_steps
            if item_durability < 0:
                item_durability = 0
            final_quality = (item_durability / self.max_durability) * 100
            item_info['quality'][0] = final_quality

            self.view_wear_reduce_change(key, initial_quality, steps, adjusted_steps,
                                         final_quality, wear_without_skill, wear_with_skill)

        self.recalc_item_prices()

    def recalc_item_prices(self) -> None:
        """Пересчитывает цену каждого предмета на основе обновлённого качества и грейда."""
        for key, item_info in self._slots().items():
            if item_info is None:
                continue
            grade = item_info.get('grade', [None])[0]
            quality = item_info.get('quality', [None])[0]
            if grade is None or quality is None:
                continue
            if grade == 'c-grade':
                new_price = int(quality * 0.5)
            elif grade == 'b-grade':
                new_price = int(quality * 1)
            elif grade == 'a-grade':
                new_price = int(quality * 1.5)
            elif grade == 's-grade':
                new_price = int(quality * 2)
            elif grade == 's+grade':
                new_price = int(quality * 2.5)
            else:
                new_price = item_info.get('price', [0])[0]
            item_info['price'][0] = new_price

    def reduce_wear(self, steps: int) -> None:
        """Уменьшает износ предметов с дополнительным учётом neatness (legacy API)."""
        reduced_steps = int(steps * (1 - (self._state.gym.neatness_in_using_things / 100)))
        self.decrease_durability(reduced_steps)

    def view_wear_reduce_change(self, item_name: str, initial_quality: float,
                                steps: int, adjusted_steps: float,
                                final_quality: float,
                                wear_without_skill: float,
                                wear_with_skill: float) -> None:
        """Debug-вывод износа (по умолчанию выключен флагом show_changes)."""
        wear_reduction_percentage = ((steps - adjusted_steps) / steps) * 100
        saved_wear = wear_without_skill - wear_with_skill

        show_changes = False
        if show_changes:
            print(f"\nИзменение прочности '{item_name}':"
                  f"\n- Начальное качество: {initial_quality:.6f} %"
                  f"\n- Шагов: {steps}"
                  f"\n- Шагов с учетом навыка: {adjusted_steps:.6f}"
                  f"\n- Износ: {initial_quality - final_quality:.6f} %"
                  f"\n- Конечное качество: {final_quality:.6f} %"
                  f"\n- Уменьшение износа: {int(wear_reduction_percentage)} %"
                  f"\n- Экономия износа: {saved_wear:.6f} %")
