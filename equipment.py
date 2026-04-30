"""Управление экипировкой персонажа — отображение слотов, надевание / снятие.

Чистая логика (`_equip_from_inventory`, `_unequip`) выделена для тестируемости —
UI-обёртки в Equipment.* остаются с input/print.
"""

from inventory import inventory_view
from state import GameState


# Маппинг legacy-ключа слота ('equipment_head') → атрибут state.equipment.
_SLOT_ATTR = {
    'equipment_head': 'head',
    'equipment_neck': 'neck',
    'equipment_torso': 'torso',
    'equipment_finger_01': 'finger_01',
    'equipment_finger_02': 'finger_02',
    'equipment_legs': 'legs',
    'equipment_foots': 'foots',
}


# ----- Чистая логика -----

def _equip_from_inventory(state: GameState, slot_attr: str, inventory_index: int):
    """Надеть предмет из inventory[index] на слот state.equipment.<slot_attr>.

    Если слот занят — старый предмет возвращается в inventory.
    Возвращает (new_item, prev_item).
    """
    new_item = state.inventory[inventory_index]
    prev_item = getattr(state.equipment, slot_attr)
    setattr(state.equipment, slot_attr, new_item)
    del state.inventory[inventory_index]
    if prev_item is not None:
        state.inventory.append(prev_item)
    return new_item, prev_item


def _unequip(state: GameState, slot_attr: str):
    """Снять предмет со слота — возвращается в inventory.

    Возвращает снятый предмет или None, если слот был пуст.
    """
    item = getattr(state.equipment, slot_attr)
    if item is None:
        return None
    setattr(state.equipment, slot_attr, None)
    state.inventory.append(item)
    return item


# ----- UI-обёртки -----

class Equipment:
    """Отображение и смена экипировки. Все методы фактически статические — `self`
    в них не используется (вызовы передают `self=None`)."""

    def equipment_view(self, state: GameState):
        eq = state.equipment

        print('\n--- 🎒 Экипировка персонажа 🎒 ---')
        if all(slot is None for slot in (
            eq.head, eq.neck, eq.torso, eq.finger_01, eq.finger_02, eq.legs, eq.foots
        )):
            print('\nНа персонаже нет вещей: ')

        if eq.head is not None:
            print(f'1. Голова:            {eq.head["item_name"][0].title()} {eq.head["grade"][0].title()}: + {eq.head["bonus"][0]} {eq.head["characteristic"][0].title()} (Quality: {eq.head["quality"][0]:,.2f})')
        else:
            print('1. Голова:            Нет одежды')

        if eq.neck is not None:
            print(f'2. Шея:               {eq.neck["item_name"][0].title()} {eq.neck["grade"][0].title()}: + {eq.neck["bonus"][0]} {eq.neck["characteristic"][0].title()} (Quality: {eq.neck["quality"][0]:,.2f})')
        else:
            print('2. Шея:               Нет одежды')

        if eq.torso is not None:
            print(f'3. Торс:              {eq.torso["item_name"][0].title()} {eq.torso["grade"][0].title()}: + {eq.torso["bonus"][0]} {eq.torso["characteristic"][0].title()} (Quality: {eq.torso["quality"][0]:,.2f})')
        else:
            print('3. Торс:              Нет одежды')

        if eq.finger_01 is not None:
            print(f'4. Палец левой руки:  {eq.finger_01["item_name"][0].title()} {eq.finger_01["grade"][0].title()}: + {eq.finger_01["bonus"][0]} {eq.finger_01["characteristic"][0].title()} (Quality: {eq.finger_01["quality"][0]:,.2f})')
        else:
            print('4. Палец левой руки:  Нет кольца')

        if eq.finger_02 is not None:
            print(f'5. Палец правой руки: {eq.finger_02["item_name"][0].title()} {eq.finger_02["grade"][0].title()}: + {eq.finger_02["bonus"][0]} {eq.finger_02["characteristic"][0].title()} (Quality: {eq.finger_02["quality"][0]:,.2f})')
        else:
            print('5. Палец правой руки: Нет кольца')

        if eq.foots is not None:
            print(f'6. Ступни:            {eq.foots["item_name"][0].title()} {eq.foots["grade"][0].title()}: + {eq.foots["bonus"][0]} {eq.foots["characteristic"][0].title()} (Quality: {eq.foots["quality"][0]:,.2f})')
        else:
            print('6. Ступни:            Нет обуви')

        print('0. Назад')
        Equipment.equipment_change(self, state)

    def equipment_change(self, state: GameState):
        ask = input('\nВыберите слот, в котором хотите заменить одежду или экипировку: \n>>> ')
        slot_map = {
            '1': ('голова',           'helmet',   'equipment_head'),
            '2': ('шея',              'necklace', 'equipment_neck'),
            '3': ('торс',             't-shirt',  'equipment_torso'),
            '4': ('палец левой руки', 'ring',     'equipment_finger_01'),
            '5': ('палец правой руки', 'ring',     'equipment_finger_02'),
            '6': ('ступни',           'shoes',    'equipment_foots'),
        }
        if ask in slot_map:
            item_name, item_type, item_slot = slot_map[ask]
            Equipment.equipment_change_item_in_slot(self, item_name, item_type, item_slot, state)
        elif ask == '0':
            pass
        else:
            Equipment.equipment_change(self, state)

    def equipment_change_item_in_slot(self, item_name, item_type, item_slot, state: GameState):
        slot_attr = _SLOT_ATTR[item_slot]
        cnt = 0
        list_cnt = []

        current_in_slot = getattr(state.equipment, slot_attr)
        if current_in_slot is None:
            print(f'\n{item_name.title()} - ничего не надето.')
        else:
            print(f'\nНа {item_name} у персонажа надето: '
                  f'\n- {current_in_slot["item_name"][0].title()} {current_in_slot["grade"][0].title()}: + {current_in_slot["bonus"][0]} {current_in_slot["characteristic"][0].title()} (Quality: {current_in_slot["quality"][0]:,.2f})')

        print(f'\nВ инвентаре имеются предметы, которые можно экипировать: ')

        state.inventory = sorted(
            state.inventory,
            key=lambda x: (x['item_type'], x['characteristic'], x['bonus']),
            reverse=True,
        )

        for i in state.inventory:
            cnt += 1
            if i["item_type"][0] == item_type:
                print(f'{cnt}. {i["item_name"][0].title()} {i["grade"][0]}: + {i["bonus"][0]} {i["characteristic"][0].title()} (Quality: {i["quality"][0]:,.2f})')
                list_cnt.append(cnt)

        print('\n0. Назад'
              '\n99. Снять предмет экипировки')

        Equipment.change_item_in_slot(self, item_name, item_type, item_slot, list_cnt, state)

    def change_item_in_slot(self, item_name, item_type, item_slot, list_cnt, state: GameState):
        slot_attr = _SLOT_ATTR[item_slot]
        try:
            index = int(input('\n>>> '))
            if index in list_cnt:
                chosen = state.inventory[index - 1]
                print(f'\nВы выбрали предмет:'
                      f'\n- {chosen["item_name"][0].title()} {chosen["grade"][0].title()}: + {chosen["bonus"][0]} {chosen["characteristic"][0].title()} (Quality: {chosen["quality"][0]:,.2f}).')
                ask = input('\nНадеть элемент экипировки на персонажа: \n1. Да\n0. Назад \n>>> ')
                if ask == '1':
                    new_item, prev_item = _equip_from_inventory(state, slot_attr, index - 1)
                    print('\nВы надели предмет на персонажа: ')
                    print(f'- {new_item["item_name"][0].title()} {new_item["grade"][0].title()}: + {new_item["bonus"][0]} {new_item["characteristic"][0].title()} (Quality: {new_item["quality"][0]:,.2f})')
                    if prev_item is not None:
                        print('\nВы заменили один предмет экипировки на другой.')
                    Equipment.equipment_view(self=None, state=state)
                else:
                    Equipment.equipment_change_item_in_slot(self, item_name, item_type, item_slot, state)

            elif index == 0:
                Equipment.equipment_view(self=None, state=state)
            elif index == 99:
                removed = _unequip(state, slot_attr)
                if removed is not None:
                    print(f'\nВы сняли предмет экипировки: '
                          f'\n- {removed["item_name"][0].title()} {removed["grade"][0].title()}: + {removed["bonus"][0]} {removed["characteristic"][0].title()} (Quality: {removed["quality"][0]})')
            else:
                print('\nПопробуйте еще раз ввести число: ')
                Equipment.equipment_change_item_in_slot(self, item_name, item_type, item_slot, state)
        except ValueError:
            print('\nПроизошла ошибка при выборе экипировки. Введите число.')
            Equipment.equipment_change_item_in_slot(self, item_name, item_type, item_slot, state)

    def inventory_view(self, state: GameState):
        print(f'\nВ инвентаре находится {len(state.inventory)} предметов: ')
        inventory_view(state)
