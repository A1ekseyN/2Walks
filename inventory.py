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

#inventory_menu()
