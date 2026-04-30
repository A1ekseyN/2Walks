"""Locations — диспатчер между game.py и каждой локацией."""

from gym import gym_menu
from work import Work
from shop import Shop
from state import GameState


_LOC_ICONS = {
    'home': '🏠',
    'gym': '🏋️',
    'shop': '🛒',
    'work': '🏭',
    'adventure': '🗺️',
    'garage': '🚗',
    'auto_dialer': None,
    'bank': '🏛',
}


def icon_loc(state: GameState):
    return _LOC_ICONS.get(state.loc)


def home_location(state: GameState):
    print('\n--- 🏠 Home Location 🏠 ---')
    print('В данный момент вы находитесь Дома.')
    print('Содержимое локации находится в разработке.')


def gym_location(state: GameState):
    gym_menu(state)


def shop_location(state: GameState):
    Shop.shop_menu(self=None, state=state)


def work_location(state: GameState):
    Work(state).work_choice()


def adventure_location(adventure_instance):
    adventure_instance.adventure_menu()


def garage_location(state: GameState):
    print('\n--- 🚗 Garage Location 🚗 ---')
    print('В данный момент вы находитесь в Гараже.')
    print('Содержимое локации находится в разработке.')


def auto_dialer_location(state: GameState):
    print('\n--- Auto Dialer Location ---')
    print('В данный момент вы находитесь у Авто-Дилера.')
    print('Содержимое локации находится в разработке.')


def bank_location(state: GameState):
    print('\n--- 🏛 Bank Location 🏛 ---')
    print('В данный момент вы находитесь в Банке.')
    print('Содержимое локации находится в разработке.')
