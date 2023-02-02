from characteristics import char_characteristic


def inventory_menu():
    print('\n--- 🎒 Меню инвентаря 🎒 ---'
          '\nНа данный момент в инвентаре находится: ')
    inventory_view()

    ask = input('\nВыберите раздел Инвентаря: '
                '\n0. Выход. '
                '\n>>> ')
    if ask == '0':
        pass
    else:
        inventory_menu()


def inventory_view():
    # Отображает содержимое инвентаря
    if char_characteristic['inventory'] == []:
        print(' - Пусто')
    else:
        for i in char_characteristic['inventory']:
            try:
                print(f'- {i["item_name"][0].title()}: ', end='')
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

#inventory_menu()
