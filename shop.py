from colorama import Fore, Style

from characteristics import char_characteristic


class Shop():
    # Класс для магазина
    def shop_menu(self):
        money = f'Money 💰: {Fore.LIGHTYELLOW_EX}{char_characteristic["money"]}{Style.RESET_ALL} $.'
        item = {
            'item_name': [],
            'item_type': [],
            'grade': [],
            'characteristic': [],
            'bonus': [],
            'quality': [],
            'price': [],
        }

        print('\n--- 🛒 Магазин --- 🛒'
              '\nВ этой локации, Вы можете приобрести разное оборудование, и расходные материалы.'
              f'\n{money}')
        print('\nВы можете приобрести: '
              '\n\t1. Еда, вода, расходные материалы'
              '\n\t2. Одежда (Тестовый режим)'
#              '\n\t3. Экипировка (Не работает)'
#              '\n\t9. Продать товар (Не работает)'
              '\n\t0. Назад')
        ask = input('\nВыберите раздел меню: \n>>> ')
        if ask == '1':
            Shop.shop_menu_food_and_water(self, item=item, money=money)
            Shop.shop_menu(self)
        elif ask == '2':
            Shop.shop_menu_clothes(self, item=item, money=money)
            Shop.shop_menu(self)
        elif ask == '3':
            pass
        elif ask == '9':
            pass
        elif ask == '0':
            pass
        else:
            Shop.shop_menu(self)

    def shop_menu_food_and_water(self, item, money):
        # Раздел для покупки Еды, воды, расходных материалов.
        print('\nВы можете купить еду и другие расходные материалы.'
              f'\n{money}'
              '\n\t1. 🍔 Чизбургер (🔋: + 5) - 2 $.'
              '\n\t2. ☕ Кофе (🔋: + 25) - 10 $.'
              '\n\t0. Назад')
        ask = input('\nВыберите вариант, который хотите приобрести: \n>>> ')
        if ask == '1':
            # Покупка Cheeseburger
            if char_characteristic['money'] >= 2:
                item['item_name'].append('cheeseburger')
                item['item_type'].append('food')
#                   item['grade'].append('C-Grade')
                item['characteristic'].append('energy')
                item['bonus'].append(5)
#                    item['quality'].append(100)
                item['price'].append(2)
                char_characteristic['inventory'].append(item)
                char_characteristic['money'] -= 2
                print('\nВы приобрели 🍔 Чизбургер - за 2 $.')
            elif char_characteristic['money'] < 2:
                print('\nУ Вас не достаточно денег для покупки.')
                Shop.shop_menu_food_and_water(self, item, money)

        elif ask == '2':
            # Покупка Coffee
            if char_characteristic['money'] >= 10:
                item['item_name'].append('coffee')
                item['item_type'].append('drink')
                item['characteristic'].append('energy')
                item['bonus'].append(25)
                item['price'].append(10)
                char_characteristic['inventory'].append(item)
                char_characteristic['money'] -= 10
                print('\nВы приобрели ☕ Coffee - за 10 $.')
            elif char_characteristic['money'] < 10:
                print('\nУ Вас не достаточно денег для покупки.')
                Shop.shop_menu_food_and_water(self, item, money)

        elif ask == '0':
            Shop.shop_menu(self)
        else:
            Shop.shop_menu(self)


    def shop_menu_clothes(self, item, money):
        # Раздел для покупки Одежды.
        def clothes_head(self, money):
            print('\nВ этом меню можно приобрести головной убор: '
                  f'\n{money}'
                  '\n\t1. ---'
                  '\n\t2. ---'
                  '\n\t3. ---'
                  '\n\t0. Назад')
            ask = input('\nЧто вы хотите приобрести? \n>>> ')
            if ask == '1':
                print('\n--- Тестовая - шапка')
            elif ask == '2':
                print('\n--- Тестовая - шапка')
            elif ask == '3':
                print('\n--- Тестовая - шапка')
            elif ask == '0':
                Shop.shop_menu_clothes(self, item, money)
            else:
                clothes_head(self, money)

        def clothes_jacket(self, money):
            print('\nВ этом меню можно приобрести куртку: '
                  f'\n{money}'
                  '\n\t1. ---'
                  '\n\t2. ---'
                  '\n\t3. ---'
                  '\n\t0. Назад')
            ask = input('\nЧто вы хотите приобрести? \n>>> ')
            if ask == '1':
                print('\n--- Тестовая покупка - куртка')
            elif ask == '2':
                print('\n--- Тестовая покупка - куртка')
            elif ask == '3':
                print('\n--- Тестовая покупка - куртка')
            elif ask == '0':
                Shop.shop_menu_clothes(self, item, money)
            else:
                clothes_jacket(self, money)

        def clothes_pants(self, money):
            print('\nВ этом меню можно приобрести штаны: '
                  f'\n{money}'
                  '\n\t1. ---'
                  '\n\t2. ---'
                  '\n\t3. ---'
                  '\n\t0. Назад')
            ask = input('\nЧто вы хотите приобрести? \n>>> ')
            if ask == '1':
                print('\n--- Тестовая - штаны')
            elif ask == '2':
                print('\n--- Тестовая - штаны')
            elif ask == '3':
                print('\n--- Тестовая - штаны')
            elif ask == '0':
                Shop.shop_menu_clothes(self, item, money)
            else:
                clothes_pants(self, money)

        def clothes_gloves(self, money):
            print('\nВ этом меню можно приобрести перчатки: '
                  f'\n{money}'
                  '\n\t1. ---'
                  '\n\t2. ---'
                  '\n\t3. ---'
                  '\n\t0. Назад')
            ask = input('\nЧто вы хотите приобрести? \n>>> ')
            if ask == '1':
                print('\n--- Тестовая покупка - перчатки')
            elif ask == '2':
                print('\n--- Тестовая покупка - перчатки')
            elif ask == '3':
                print('\n--- Тестовая покупка - перчатки')
            elif ask == '0':
                Shop.shop_menu_clothes(self, item, money)
            else:
                clothes_gloves(self, money)

        def clothes_shoes(self, item, money):
            print('\nВ этом меню можно приобрести обувь: '
                  f'\n{money}'
                  f'\n\t1. Кеды - C-Grade (+ 1 % шагов) (Цена: 25 $)'
                  f'\n\t2. Кеды - B-Grade (+ 2 % шагов) (Цена: 50 $)'
                  f'\n\t3. Кеды - A-Grade (+ 3 % шагов) (Цена: 100 $)'
                  f'\n\t0. Назад')
            ask = input('\nЧто вы хотите приобрести? \n>>> ')
            if ask == '1':
                if char_characteristic['money'] >= 25:
                    item['item_name'].append('Кеды')
                    item['item_type'].append('shoes')
                    item['grade'].append('c-grade')
                    item['characteristic'].append('stamina')
                    item['bonus'].append(1)
                    item['quality'].append(100)
                    item['price'].append(25)
                    char_characteristic['inventory'].append(item)
                    char_characteristic['money'] -= 25
                    print('\nВы приобрели: Кеды - C-Grade (+ 1 % шагов) за - 25 $.')
                else:
                    print(f'\nУ вас не достаточно денег. Не хватает 💰: {25 - char_characteristic["money"]} $.')
            elif ask == '2':
                if char_characteristic['money'] >= 50:
                    item['item_name'].append('Кеды')
                    item['item_type'].append('shoes')
                    item['grade'].append('b-grade')
                    item['characteristic'].append('stamina')
                    item['bonus'].append(2)
                    item['quality'].append(100)
                    item['price'].append(50)
                    char_characteristic['inventory'].append(item)
                    char_characteristic['money'] -= 50
                    print('\nВы приобрели: Кеды - B-Grade (+ 2 % шагов) за - 50 $.')
                else:
                    print(f'\nУ вас не достаточно денег. Не хватает 💰: {50 - char_characteristic["money"]} $.')
            elif ask == '3':
                if char_characteristic['money'] >= 100:
                    item['item_name'].append('Кеды')
                    item['item_type'].append('shoes')
                    item['grade'].append('a-grade')
                    item['characteristic'].append('stamina')
                    item['bonus'].append(3)
                    item['quality'].append(100)
                    item['price'].append(100)
                    char_characteristic['inventory'].append(item)
                    char_characteristic['money'] -= 100
                    print('\nВы приобрели: Кеды - A-Grade (+ 3 % шагов) за - 100 $.')
                else:
                    print(f'\nУ вас не достаточно денег. Не хватает 💰: {100 - char_characteristic["money"]} $.')
            elif ask == '0':
                Shop.shop_menu_clothes(self, item, money)
            else:
                Shop.shop_menu_clothes(self, item, money)

        print('\nВ можете купить одежду для персонажа.'
            f'\n{money}'
            '\n\t1. Шапка'
            '\n\t2. Куртка'
            '\n\t3. Штаны'
            '\n\t4. Перчатки'
            '\n\t5. Обувь'
            '\n\t0. Назад')
        ask = input('\nВыберите раздел товара, который хотите приобрести: \n>>> ')
        if ask == '1':
            clothes_head(self, money)
        elif ask == '2':
            clothes_jacket(self, money)
        elif ask == '3':
            clothes_pants(self, money)
        elif ask == '4':
            clothes_gloves(self, money)
        elif ask == '5':
            clothes_shoes(self, item, money)
            Shop.shop_menu_clothes(self, item, money)
        elif ask == '0':
            pass
#                Shop.shop_menu(self)
#                Shop.shop_menu_clothes(self, item, money)
        else:
            Shop.shop_menu_clothes(self, item, money)
#            Shop.shop_menu_clothes(self, item, money)


    def shop_menu_equipment(self):
        # Раздел для покупки экипировки.
        pass

    def shop_menu_sell_items(self):
        # Раздел для продажи купленных товаров
        pass

#Shop.shop_menu(self=None)
