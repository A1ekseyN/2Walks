from operator import itemgetter
from characteristics import char_characteristic


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
                except (KeyError, IndexError, TypeError):
                    print('У предмета нет цены. Продажа за 0 $.')
                del char_characteristic["inventory"][item_index]
                inventory_menu()
            elif ask == '0':
                sold_item()
            else:
                sold_item()
        elif item_to_sold == 0:
            inventory_menu()
        else:
            sold_item()
    except ValueError:
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
        self.max_durability = 10000000  # Максимальная прочность
        self.durability = self.max_durability  # Начальная прочность
        self.equipment_items = self.equipped_items
        self.neatness_factor = 1 - (char_characteristic['neatness_in_using_things'] / 100)

    def decrease_durability(self, steps):
        """Уменьшает прочность предметов на заданное число шагов с учётом аккуратности."""
        adjusted_steps = steps * self.neatness_factor

        for key, item_info in self.equipment_items.items():
            if item_info is not None:
                initial_quality = item_info['quality'][0]
                # Вычисляем износ в процентах
                wear_without_skill = steps / self.max_durability * 100
                wear_with_skill = adjusted_steps / self.max_durability * 100

                # Обновляем прочность: здесь просто уменьшаем прочность пропорционально количеству шагов
                item_durability = self.durability * (initial_quality / 100)
                item_durability -= adjusted_steps
                if item_durability < 0:
                    item_durability = 0
                final_quality = (item_durability / self.max_durability) * 100
                self.equipment_items[key]['quality'][0] = final_quality

                # Обновляем глобальные характеристики, если есть
                if key in char_characteristic and char_characteristic[key] is not None:
                    char_characteristic[key]['quality'][0] = final_quality

                # Вывод отладочной информации (если нужно)
                self.view_wear_reduce_change(key, initial_quality, steps, adjusted_steps, final_quality, wear_without_skill, wear_with_skill)

        # После уменьшения прочности пересчитываем цену
        self.recalc_item_prices()

    def recalc_item_prices(self):
        """Пересчитывает стоимость каждого предмета на основе обновлённого качества.
            Новая цена рассчитывается с использованием коэффициента для грейда и округляется вниз.
            """
        for key, item_info in self.equipment_items.items():
            if item_info is not None:
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

                # Обновляем цену в экипированном предмете
                self.equipment_items[key]['price'][0] = new_price
                # Если в глобальном словаре char_characteristic также хранится этот предмет, обновляем его цену
                if key in char_characteristic and char_characteristic[key] is not None:
                    char_characteristic[key]['price'][0] = new_price

#                print(f"Updated price for {key}: {new_price}")

    def reduce_wear(self, steps):
        """Метод для уменьшения износа предметов с учётом навыка аккуратности."""
        reduced_steps = steps * (1 - (char_characteristic['neatness_in_using_things'] / 100))
        self.decrease_durability(reduced_steps)

    def view_wear_reduce_change(self, item_name, initial_quality, steps, adjusted_steps, final_quality, wear_without_skill, wear_with_skill):
        """Отображает изменения прочности предметов (для отладки)."""
        wear_reduction_percentage = ((steps - adjusted_steps) / steps) * 100  # Процент уменьшения износа
        saved_wear = wear_without_skill - wear_with_skill  # Экономия износа

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


# Создание экземпляра класса для работы с экипированными предметами
#equipped_items_reduce_quality = Wear_Equipped_Items()

# Запуск активности на 5000 шагов и уменьшение прочности предметов
#equipped_items_reduce_quality.decrease_durability(steps=200)

# Вывод текущей прочности экипированных предметов
#for key, item_info in equipped_items_reduce_quality.equipment_items.items():
#    if item_info is not None:
#        print(f"Прочность предмета '{key}': {item_info['quality']:.2f}%")
