"""Инвентарь — отображение, продажа, износ экипированных предметов.

Чистая логика (`_sort_inventory`, `_sell_item_at_index`) выделена для
тестируемости — UI-обёртки `inventory_menu` / `sold_item` остаются с input/print.
"""

from state import GameState


# ----- Чистая логика (тестируется напрямую) -----

def _sort_inventory(inventory):
    """Сортирует инвентарь по (item_type, characteristic, -bonus). Pure."""
    return sorted(
        inventory,
        key=lambda x: (
            x.get('item_type', ''),
            x.get('characteristic', ''),
            -x.get('bonus', [0])[0],
        ),
    )


def _sell_item_at_index(state: GameState, index: int):
    """Продажа предмета по индексу — мутирует state.inventory и state.money.

    Возвращает (item, refund). Refund добавляется к state.money.
    Если у предмета нет цены — refund=0.
    """
    item = state.inventory[index]
    try:
        refund = round(item['price'][0])
    except (KeyError, IndexError, TypeError):
        refund = 0
    state.money += refund
    del state.inventory[index]
    return item, refund


# ----- UI-обёртки -----

def inventory_menu(state: GameState):
    print('\n--- 🎒 Меню инвентаря 🎒 ---'
          f'\nВсего в инвентаре - {len(state.inventory)} предметов: ')
    inventory_view(state)

    ask = input('\nВыберите раздел Инвентаря: '
                '\ns. Sold / Продать'
                '\n0. Выход. '
                '\n>>> ')
    if ask in ('s', 'ы', 'sold', 'ыщдв'):
        sold_item(state)
    elif ask == '0':
        pass
    else:
        inventory_menu(state)


def inventory_view(state: GameState):
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


def sold_item(state: GameState):
    print('\n--- Продажа предметов из инвентаря: ---')
    print(f'Всего в инвентаре: {len(state.inventory)} предметов.')
    state.inventory = inventory_view(state)

    try:
        item_to_sold = int(input(f'\t0. Назад'
                                 f'\n\nКакой предмет хотите продать? (Введите число от 1 до {len(state.inventory)}). \n>>> '))
        if item_to_sold <= len(state.inventory) and item_to_sold != 0:
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
            elif ask == '0':
                sold_item(state)
            else:
                sold_item(state)
        elif item_to_sold == 0:
            inventory_menu(state)
        else:
            sold_item(state)
    except ValueError:
        sold_item(state)


# ----- Износ экипировки -----

class Wear_Equipped_Items:
    """Подсчёт износа экипированных предметов после активности (Gym/Work/Adventure).

    Phase 4: state читается в момент вызова (не при определении класса), так что
    экипировка отражает актуальные слоты, а не зафиксированные в момент импорта.
    """

    def __init__(self, state: GameState):
        self._state = state
        self.max_durability = 10000000
        self.durability = self.max_durability
        self.neatness_factor = 1 - (self._state.gym.neatness_in_using_things / 100)

    def _slots(self):
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
        }

    def decrease_durability(self, steps):
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

    def recalc_item_prices(self):
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

    def reduce_wear(self, steps):
        """Уменьшает износ предметов с дополнительным учётом neatness (legacy API)."""
        reduced_steps = steps * (1 - (self._state.gym.neatness_in_using_things / 100))
        self.decrease_durability(reduced_steps)

    def view_wear_reduce_change(self, item_name, initial_quality, steps, adjusted_steps,
                                final_quality, wear_without_skill, wear_with_skill):
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
