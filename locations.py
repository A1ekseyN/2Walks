"""Locations — диспатчер между game.py и каждой локацией.

Phase 4 задачи 1.1 (commit 4): icon_loc / *_location принимают
`state: GameState` (default `state=None` → characteristics.game_state).
"""

from gym import gym_menu
from work import Work
from shop import Shop
from state import GameState


def _resolve_state(state):
    if state is None:
        from characteristics import game_state
        return game_state
    return state


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


def icon_loc(state: GameState = None):
    state = _resolve_state(state)
    return _LOC_ICONS.get(state.loc)


def home_location(state: GameState = None):
    print('\n--- 🏠 Home Location 🏠 ---')
    print('В данный момент вы находитесь Дома.')
    print('Содержимое локации находится в разработке.')


def gym_location(state: GameState = None):
    state = _resolve_state(state)
    gym_menu(state)


def shop_location(state: GameState = None):
    state = _resolve_state(state)
    Shop.shop_menu(self=None, state=state)


def work_location(state: GameState = None):
    state = _resolve_state(state)
    Work(state).work_choice()


def adventure_location(adventure_instance):
    adventure_instance.adventure_menu()


def garage_location(state: GameState = None):
    print('\n--- 🚗 Garage Location 🚗 ---')
    print('В данный момент вы находитесь в Гараже.')
    print('Содержимое локации находится в разработке.')


def auto_dialer_location(state: GameState = None):
    print('\n--- Auto Dialer Location ---')
    print('В данный момент вы находитесь у Авто-Дилера.')
    print('Содержимое локации находится в разработке.')


def bank_location(state: GameState = None):
    print('\n--- 🏛 Bank Location 🏛 ---')
    print('В данный момент вы находитесь в Банке.')
    print('Содержимое локации находится в разработке.')
