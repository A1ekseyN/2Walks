from characteristics import char_characteristic
from equipment_bonus import *


def skill_bonus_energy_max():
    # Бонус Макс. Энергии от навыка
    char_characteristic['energy_max'] += char_characteristic['energy_max_skill']
    return char_characteristic['energy_max']


def equipment_bonus_stamina_steps():
    # Вычисления бонуса шагов через бонус экипировки.
    bonus = round((char_characteristic['steps_today'] / 100) * equipment_stamina_bonus())
    return bonus


def daily_steps_bonus():
    # Бонус за пройденное кол-во шагов, более 10к.
    bonus = round((char_characteristic['steps_today'] / 100) * char_characteristic['steps_daily_bonus'])
    return bonus

def level_steps_bonus():
    """Бонус к кол-ву шагов в зависимости от уровня прокачки навыка"""
    bonus = round((char_characteristic['steps_today'] / 100) * char_characteristic['lvl_up_skill_stamina'])
    return bonus


def apply_move_optimization_adventure(steps):
    """
    Функция для уменьшения необходимого количества шагов для прохождения Adventure
    Количество steps уменьшается на % прокачки навыка Оптимизация движений Adventure
    :param steps: Словарь с параметрами для прохождения Adventure
    """
    steps['steps'] *= (1 - char_characteristic['move_optimization_adventure'] / 100)
    steps['steps'] = int(steps['steps'])
    return steps


def apply_move_optimization_gym(steps):
    """
    Функция для уменьшения необходимого количества шагов для улучшения навыков в Gym
    Количество steps уменьшается на % прокачки навыка Оптимизация движений Gym
    :param steps: Словарь с параметрами для прохождения Gym
    """
    steps *= (1 - char_characteristic['move_optimization_gym'] / 100)
    steps = int(steps)
    return steps


def apply_move_optimization_work(steps):
    """
    Функция для уменьшения необходимого количества шагов для улучшения навыков в Gym
    Количество steps уменьшается на % прокачки навыка Оптимизация движений Gym
    :param steps: Словарь с параметрами для прохождения Gym
    """
    steps *= (1 - char_characteristic['move_optimization_work'] / 100)
    steps = int(steps)
    return steps


#equipment_bonus_stamina_steps()
#equipment_bonus_energy_max()
#daily_steps_bonus()
