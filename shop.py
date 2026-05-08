"""Shop — магазин: еда/напитки + одежда (тестовый режим).

Чистая логика покупки выделена в `_buy_item` для тестируемости — UI-методы
Shop.shop_menu* остаются с input/print.
"""

from typing import Any, Optional

from colorama import Fore, Style

from bonus import apply_money_saving
from functions_02 import format_money
from state import GameState


def _money_line(state: GameState) -> str:
    return f'Money 💰: {Fore.LIGHTYELLOW_EX}{format_money(state.money)}{Style.RESET_ALL} $.'


def _empty_item() -> dict:
    return {
        'item_name': [], 'item_type': [], 'grade': [],
        'characteristic': [], 'bonus': [], 'quality': [], 'price': [],
    }


# ----- Чистая логика покупки -----

def _buy_item(state: GameState, item: dict, cost: float) -> bool:
    """Атомарная покупка: списывает money и кладёт item в inventory.

    `cost` — float (после применения скидки `apply_money_saving`). Сравнение
    и списание работают со state.money (тоже float с 0.2.2).

    Возвращает True при успехе, False — если денег не хватает (state не меняется).
    """
    if state.money < cost:
        return False
    state.money -= cost
    state.inventory.append(item)
    # 4.6 — log_event покупки в магазине. Items хранят значения в list-обёртках
    # (legacy формат, рефакторинг в 1.6), извлекаем безопасно через _first().
    from history import log_event
    log_event('item_bought',
              item_name=_first(item.get('item_name')),
              item_type=_first(item.get('item_type')),
              grade=_first(item.get('grade')),
              cost=round(cost, 2))
    return True


def _first(values: Optional[list]) -> Any:
    """Безопасно достать первый элемент list-обёртки item-поля. None если пусто."""
    if not values:
        return None
    return values[0]


# ----- UI -----

class Shop:
    """Магазин — UI-обёртка вокруг покупок."""

    def shop_menu(self, state: GameState) -> None:
        # Цикл retry на невалиде / возврате из подменю (1.5.4 — 0.2.1h).
        while True:
            money = _money_line(state)
            item = _empty_item()

            print('\n--- 🛒 Магазин --- 🛒'
                  '\nВ этой локации, Вы можете приобрести разное оборудование, и расходные материалы.'
                  f'\n{money}')
            print('\nВы можете приобрести: '
                  '\n\t1. Еда, вода, расходные материалы'
                  '\n\t2. Одежда (Тестовый режим)'
                  '\n\t0. Назад')
            ask = input('\nВыберите раздел меню: \n>>> ')
            if ask == '1':
                Shop.shop_menu_food_and_water(self, item=item, money=money, state=state)
                continue
            if ask == '2':
                Shop.shop_menu_clothes(self, item=item, money=money, state=state)
                continue
            if ask in ('3', '9', '0'):
                return

    def shop_menu_food_and_water(self, item: dict, money: str, state: GameState) -> None:
        # Цикл retry на невалиде (1.5.4 — 0.2.1h).
        while True:
            print('\nВы можете купить еду и другие расходные материалы.'
                  f'\n{money}'
                  f'\n\t1. 🍔 Чизбургер (🔋: + 5) - {format_money(apply_money_saving(2, state))} $.'
                  f'\n\t2. ☕ Кофе (🔋: + 25) - {format_money(apply_money_saving(10, state))} $.'
                  '\n\t0. Назад')
            ask = input('\nВыберите вариант, который хотите приобрести: \n>>> ')
            if ask == '1':
                cb_cost = apply_money_saving(2, state)
                cb = _empty_item()
                cb['item_name'].append('cheeseburger')
                cb['item_type'].append('food')
                cb['characteristic'].append('energy')
                cb['bonus'].append(5)
                cb['price'].append(2)
                if _buy_item(state, cb, cb_cost):
                    print(f'\nВы приобрели 🍔 Чизбургер - за {format_money(cb_cost)} $.')
                    return
                print('\nУ Вас не достаточно денег для покупки.')
                continue

            if ask == '2':
                coffee_cost = apply_money_saving(10, state)
                coffee = _empty_item()
                coffee['item_name'].append('coffee')
                coffee['item_type'].append('drink')
                coffee['characteristic'].append('energy')
                coffee['bonus'].append(25)
                coffee['price'].append(10)
                if _buy_item(state, coffee, coffee_cost):
                    print(f'\nВы приобрели ☕ Coffee - за {format_money(coffee_cost)} $.')
                    return
                print('\nУ Вас не достаточно денег для покупки.')
                continue

            if ask == '0':
                return  # возврат в shop_menu происходит через цикл там
            # любой невалид — повторяем меню.

    def shop_menu_clothes(self, item: dict, money: str, state: GameState) -> None:
        def _clothes_stub(label: str, header: str) -> None:
            # Generic stub-цикл для одежды (заглушки до 4.7).
            while True:
                print(f'\n{header}: '
                      f'\n{money}'
                      '\n\t1. ---'
                      '\n\t2. ---'
                      '\n\t3. ---'
                      '\n\t0. Назад')
                ask = input('\nЧто вы хотите приобрести? \n>>> ')
                if ask in ('1', '2', '3'):
                    print(f'\n--- Тестовая - {label}')
                    return
                if ask == '0':
                    return

        def clothes_shoes(money: str) -> None:
            shoe_specs = {
                '1': ('c-grade', 1, 25),
                '2': ('b-grade', 2, 50),
                '3': ('a-grade', 3, 100),
            }
            while True:
                print('\nВ этом меню можно приобрести обувь: '
                      f'\n{money}'
                      f'\n\t1. Кеды - C-Grade (+ 1 % шагов) (Цена: {format_money(apply_money_saving(25, state))} $)'
                      f'\n\t2. Кеды - B-Grade (+ 2 % шагов) (Цена: {format_money(apply_money_saving(50, state))} $)'
                      f'\n\t3. Кеды - A-Grade (+ 3 % шагов) (Цена: {format_money(apply_money_saving(100, state))} $)'
                      f'\n\t0. Назад')
                ask = input('\nЧто вы хотите приобрести? \n>>> ')
                if ask in shoe_specs:
                    grade, bonus, price = shoe_specs[ask]
                    shoe_cost = apply_money_saving(price, state)
                    shoe = _empty_item()
                    shoe['item_name'].append('Кеды')
                    shoe['item_type'].append('shoes')
                    shoe['grade'].append(grade)
                    shoe['characteristic'].append('stamina')
                    shoe['bonus'].append(bonus)
                    shoe['quality'].append(100)
                    shoe['price'].append(price)
                    if _buy_item(state, shoe, shoe_cost):
                        print(f'\nВы приобрели: Кеды - {grade.upper()} (+ {bonus} % шагов) за - {format_money(shoe_cost)} $.')
                        return
                    print(f'\nУ вас не достаточно денег. Не хватает 💰: {format_money(shoe_cost - state.money)} $.')
                    return
                if ask == '0':
                    return

        # Цикл retry на главном меню одежды (1.5.4 — 0.2.1h).
        while True:
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
                _clothes_stub('шапка', 'В этом меню можно приобрести головной убор')
            elif ask == '2':
                _clothes_stub('куртка', 'В этом меню можно приобрести куртку')
            elif ask == '3':
                _clothes_stub('штаны', 'В этом меню можно приобрести штаны')
            elif ask == '4':
                _clothes_stub('перчатки', 'В этом меню можно приобрести перчатки')
            elif ask == '5':
                clothes_shoes(money)
            elif ask == '0':
                return
            # любой невалид — повторяем меню.

    def shop_menu_equipment(self) -> None:
        # Раздел для покупки экипировки.
        pass

    def shop_menu_sell_items(self) -> None:
        # Раздел для продажи купленных товаров.
        pass
