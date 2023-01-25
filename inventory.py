from characteristics import char_characteristic


def inventory_menu():
    print('\n--- 🎒 Меню инвентаря 🎒 ---'
          '\nНа данный момент в инвентаре находится: ')
    inventory_view()

    ask = input('\nВыберите раздел Инвентаря: '
                '\n0. Выход. '
                '\n\n>>> ')
    if ask == '0':
        pass
    else:
        inventory_menu()


def inventory_view():
    if char_characteristic['inventory'] == []:
        print(' - Пусто')
    else:
        for i in char_characteristic['inventory']:
            print(f'- {i["item_type"][0]}: {i["grade"][0]}, + {i["bonus"][0]} {i["characteristic"][0].title()} (Качество: {i["quality"][0]})')


#inventory_menu()
