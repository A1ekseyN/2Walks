from characteristics import char_characteristic
from colorama import Fore, Style


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

        print('\n--- 🛒 Вы находитесь в локации - Магазин --- 🛒'
              '\nВ этой локации, Вы можете приобрести разное оборудование, и расходные материалы.'
              f'\n{money}')
        print('\nВы можете приобрести: '
              '\n\t1. Еда, вода, расходные материалы'
              '\n\t2. Одежда (Не работает)'
              '\n\t3. Экипировка (Не работает)'
              '\n\t9. Продать товар (Не работает)'
              '\n\t0. Назад')
        try:
            ask = input('\nВыберите раздел меню: \n>>> ')
            if ask == '1':
                Shop.shop_menu_food_and_water(self, item=item, money=money)
                Shop.shop_menu(self)
            elif ask == '2':
                pass
            elif ask == '3':
                pass
            elif ask == '9':
                pass
            elif ask == '0':
                pass
            else:
                Shop.shop_menu(self)
        except:
            print('Ошибка выбора меню магазина.')
            Shop.shop_menu(self)

    def shop_menu_food_and_water(self, item, money):
        # Раздел для покупки Еды, воды, расходных материалов.
        print('\nВы можете купить еду и другие расходные материалы.'
              f'\n{money}'
              '\n\t1. 🍔 Чизбургер (🔋: + 5) - 2 $.'
              '\n\t2. ☕ Кофе (🔋: + 25) - 10 $.'
              '\n\t0. Назад')
        try:
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
        except:
            print('Error - Shop Menu Food And Water.')
            Shop.shop_menu_food_and_water(self, item, money)


    def shop_menu_clothes(self):
        # Раздел для покупки Одежды.
        pass

    def shop_menu_equipment(self):
        # Раздел для покупки экипировки.
        pass

    def shop_menu_sell_items(self):
        # Раздел для продажи купленых товаров
        pass

#Shop.shop_menu(self=None)
