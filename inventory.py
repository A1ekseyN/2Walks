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
    # Отображает содержимое инвентаря
    # Отображение инвентаря сделано циклом в одну строчку. Фактически вывод можно сделать одной строчкой.
    item_counter = 0

    if char_characteristic['inventory'] == []:
        print(' - Пусто')
    else:
        for i in char_characteristic['inventory']:
            item_counter += 1
            try:
                print(f'{item_counter}. {i["item_name"][0].title()}: ', end='')
            except:
                pass
            print(f'{i["item_type"][0].title()} ', end='')               # Item Type
            try:                                                            # Item Grade
                if i['grade'][0]:
                    print(f'{i["grade"][0]}, ', end='')
            except:                                                         # Если ничего нет, то ничего не отображать
                pass
            print(f'+ {i["bonus"][0]} '                                     # Bonus
                  f'{i["characteristic"][0].title()} ', end='')
            try:
                if i['quality'][0]:                                             # Quality
                    print(f'(Качество: {i["quality"][0]}) ', end='')
#                  f'- (Price: {i["price"][0]})')
            except:
                pass
            try:                                                            # Price
                if i['price'][0]:
                    print(f'(Price: {i["price"][0]} $)')
            except:
                print()

def sold_item():
    print('\n--- Продажа предметов из инвентаря: ---')
    print(f'Всего в инвентаре: {len(char_characteristic["inventory"])} предметов.')
    inventory_view()

#    try:
    item_to_sold = int(input(f'\nКакой предмет хотите продать? (Введите число от 0 до {len(char_characteristic["inventory"])}). \n>>> '))
    if item_to_sold <= len(char_characteristic["inventory"]):
        print(f'\nВы выбрали предмет: {char_characteristic["inventory"][item_to_sold - 1]}'
              f'\nЦена предмета: ??? $')
        try:
            ask = input('\nВы уверены, что хотите продать этот предмет? '
                        '\n1. Да'
                        '\n0. Назад \n>>> ')
            if ask == '1':
                print(f'\nВы продали предмет {char_characteristic["inventory"][item_to_sold - 1]}'
                      f'\nЦена продажи: ??? $.')
                try:        # Если нет цены у предмета, тогда exception. И предмет удаляется без прибыли.
                    char_characteristic['money'] += round(char_characteristic['inventory'][item_to_sold - 1]['price'][0] / 2)
                except:
                    print('У предмета нет цены. Продажа за 0 $.')
                del char_characteristic["inventory"][item_to_sold - 1]
                inventory_menu()
            elif ask == '0':
                sold_item()
            else:
                sold_item()
        except:
            sold_item()
    if ask == '0':
        inventory_menu()
#        else:
#            inventory_menu()
#    except:
#        inventory_menu()

#inventory_menu()
