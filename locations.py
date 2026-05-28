"""Locations — диспатчер между game.py и каждой локацией."""

from bank import bank_menu
from forge import forge_menu
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
    'forge': '🔨',  # 4.59 — Кузница
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
    bank_menu(state)


def forge_location(state: GameState):
    """4.59 — Кузница / Blacksmith. Repair + Crafting + (deferred) Gems.

    4.60 — Локация заблокирована, пока не прокачан хотя бы один forge-навык
    (forge_steps_saving / forge_money_saving / forge_repair_quality) до ≥1.
    Навыки качаются в Спортзале (Gym).
    """
    g = state.gym
    if (g.forge_steps_saving < 1 and g.forge_money_saving < 1
            and g.forge_repair_quality < 1 and g.forge_speed < 1):
        print('\n🔒 Кузница заблокирована. Прокачай любой навык Кузницы в '
              'Спортзале (экономия шагов / золота / качество ремонта / скорость) '
              'до 1 уровня.')
        return
    forge_menu(state)
