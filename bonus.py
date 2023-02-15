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


#equipment_bonus_stamina_steps()
#equipment_bonus_energy_max()
