from gym import gym_menu
from work import Work
#from work import work_choice
from adventure import Adventure
from characteristics import char_characteristic
from shop import Shop


def icon_loc():
    # Отображение иконки локации
    if char_characteristic['loc'] == 'home':
        return '🏠'
    elif char_characteristic['loc'] == 'gym':
        return '🏋️'
    elif char_characteristic['loc'] == 'shop':
        return '🛒'
    elif char_characteristic['loc'] == 'work':
        return '🏭'
    elif char_characteristic['loc'] == 'adventure':
        return '🗺️'
    elif char_characteristic['loc'] == 'garage':
        return '🚗'
    elif char_characteristic['loc'] == 'auto_dialer':
        pass
    elif char_characteristic['loc'] == 'bank':
        return '🏛'


def home_location():
    # Локация - Дом.
    print('\n--- 🏠 Home Location 🏠 ---')
    print('В данный момент вы находитесь Дома.')
    print('Содержимое локации находится в разработке.')


def gym_location():
    # Локация - Спортзал.
    # На тренировку тратяться шаги + энергия + $.
    gym_menu()


def shop_location():
    # Локация - Магазин.
    Shop.shop_menu(self=None)
#    print('\n--- 🛒 Shop Location 🛒 ---')
#    print('В данный момент вы находитесь в Магазине.')
#    print('Содержимое локации находится в разработке.')


def work_location():
    # Локация - Работа.
    Work.work_choice(self=0)


def adventure_location():
    # Локация - Приключения.
#    print('\n--- 🗺️ Adventure Location 🗺 ---')
    Adventure.adventure_menu(self=None)
#    print('В данный момент вы находитесь в Приключениях.')
#    print('Содержимое локации находится в разработке.')


def garage_location():
    # Локация - Гараж.
    print('\n--- 🚗 Garage Location 🚗 ---')
    print('В данный момент вы находитесь в Гараже.')
    print('Содержимое локации находится в разработке.')


def auto_dialer_location():
    # Локация - Авто-дилер.
    print('\n--- Auto Dialer Location ---')
    print('В данный момент вы находитесь у Авто-Дилера.')
    print('Содержимое локации находится в разработке.')


def bank_location():
    # Локация - Банк.
    print('\n--- 🏛 Bank Location 🏛 ---')
    print('В данный момент вы находитесь в Банке.')
    print('Содержимое локации находится в разработке.')
