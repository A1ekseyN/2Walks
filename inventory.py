from characteristics import char_characteristic
from operator import itemgetter


def inventory_menu():
    print('\n--- 🎒 Меню инвентаря 🎒 ---'
          f'\nВсего в инвентаре - {len(char_characteristic["inventory"])} предметов: ')
    inventory_view()

    ask = input('\nВыберите раздел Инвентаря: '
                '\ns. Sold / Продать'
                '\n0. Выход. '
                '\n>>> ')
    if ask == 's' or ask == 'ы' or ask == 'sold' or ask == 'ыщдв':
        sold_item()
    elif ask == '0':
        pass
    else:
        inventory_menu()


def inventory_view():
    """Отображает содержимое инвентаря"""
    sorted_inventory = sorted(
        char_characteristic['inventory'],
        key=lambda x: (
            x.get('item_type', ''),
            x.get('characteristic', ''),
            -x.get('bonus', [0])[0]  # Используем отрицательное значение для сортировки по убыванию
        )
    )

    if not sorted_inventory:
        print(' - Пусто')
    else:
        for ind, item in enumerate(sorted_inventory, start=1):
            print(f"\t{ind}. {item['item_type'][0].title()} {item['grade'][0]}, "
                  f"+ {item['bonus'][0]} {item['characteristic'][0].title()}, "
                  f"(Quality: {item['quality'][0]}), "
                  f"(Price: {item['price'][0]} $) ")

    return sorted_inventory


def sold_item():
    print('\n--- Продажа предметов из инвентаря: ---')
    print(f'Всего в инвентаре: {len(char_characteristic["inventory"])} предметов.')
    char_characteristic["inventory"] = inventory_view()

    try:
        item_to_sold = int(input(f'\t0. Назад'
                                 f'\n\nКакой предмет хотите продать? (Введите число от 1 до {len(char_characteristic["inventory"])}). \n>>> '))
        if item_to_sold <= len(char_characteristic["inventory"]) and item_to_sold != 0:
            item_index = item_to_sold - 1  # Корректируем индекс для доступа к списку
            item = char_characteristic["inventory"][item_index]

            print(f'\nВы выбрали предмет: '
                  f'\n\t- {item["item_type"][0].title()}, '
                  f'{item["grade"][0]}, '
                  f'+ {item["bonus"][0]} {item["characteristic"][0].title()}, '
                  f'(Quality: {item["quality"][0]}), '
                  f'(Price: {item["price"][0]} $) '
                  ### Тут нужно добавить название, характеристики и цену предмета. 
                  f'\n\t- Цена предмета 💰: {item["price"][0]} $')
            try:
                ask = input('\nВы уверены, что хотите продать этот предмет? '
                            '\n1. Да'
                            '\n0. Назад \n>>> ')
                if ask == '1':
                    print(f'\nВы продали предмет:'
                          f'\n\t- {item["item_type"][0].title()}, '
                          f'{item["grade"][0]}, '
                          f'+ {item["bonus"][0]} {item["characteristic"][0].title()}, '
                          f'(Quality: {item["quality"][0]}), '
                          f'(Price: {item["price"][0]} $) '
                          ### Тут нужно добавить название, характеристики и цену предмета. 
                          f'\n\t- Цена предмета 💰: {item["price"][0]} $')
                    try:  # Если нет цены у предмета, тогда exception. И предмет удаляется без прибыли.
                        char_characteristic['money'] += round(char_characteristic['inventory'][item_index]['price'][0])
                    except:
                        print('У предмета нет цены. Продажа за 0 $.')
                    del char_characteristic["inventory"][item_index]
                    inventory_menu()
                elif ask == '0':
                    sold_item()
                else:
                    sold_item()
            except:
                sold_item()
        elif item_to_sold == 0:
            inventory_menu()
        else:
            sold_item()
    except:
        sold_item()


class Wear_Equipped_Items:
    """Класс для подсчёта износа предметов"""
    equipped_items = {
        'equipment_head': char_characteristic['equipment_head'],
        'equipment_neck': char_characteristic['equipment_neck'],
        'equipment_torso': char_characteristic['equipment_torso'],
        'equipment_finger_01': char_characteristic['equipment_finger_01'],
        'equipment_finger_02': char_characteristic['equipment_finger_02'],
        'equipment_legs': char_characteristic['equipment_legs'],
        'equipment_foots': char_characteristic['equipment_foots'],
    }

    def __init__(self):
        self.max_durability = 10000000  # Максимальная прочность в единицах: 10.000.000
        self.durability = self.max_durability  # Начальная прочность, 100% (или 100/100)
        self.equipment_items = self.equipped_items

    def decrease_durability(self, steps):
        """Метод для уменьшения прочности предметов на указанное количество шагов"""
        for key, item_info in self.equipment_items.items():
            if item_info is not None:
                item_durability = self.durability * (item_info['quality'][0] / 100)
                item_durability -= steps
                if item_durability < 0:
                    item_durability = 0
                self.equipment_items[key]['quality'][0] = (item_durability / self.max_durability) * 100

                # Обновляем char_characteristics после изменения прочности предмета
                if key in char_characteristic:
                    char_characteristic[key]['quality'][0] = self.equipment_items[key]['quality'][0]

                # Можно также обновить self.durability, если требуется отслеживать общую прочность
                # self.durability = item_durability

# Пример использования:


# Создание экземпляра класса для работы с экипированными предметами
#equipped_items_reduce_quality = Wear_Equipped_Items()

# Запуск активности на 5000 шагов и уменьшение прочности предметов
#equipped_items_reduce_quality.decrease_durability(steps=200)

# Вывод текущей прочности экипированных предметов
#for key, item_info in equipped_items_reduce_quality.equipment_items.items():
#    if item_info is not None:
#        print(f"Прочность предмета '{key}': {item_info['quality']:.2f}%")

