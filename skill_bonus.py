# Файл для расчёта бонусов от навыков.
from characteristics import char_characteristic
from equipment_bonus import equipment_speed_skill_bonus


def stamina_skill_bonus_def():
    # Бонус кол-ва шагов.
    stamina_skill_bonus = round(char_characteristic['steps_today'] / 100) * char_characteristic['stamina']
    return stamina_skill_bonus


def speed_skill_equipment_and_level_bonus(x):
    # Бонус от скорости
    x = int(x - (x / 100) * (char_characteristic['speed_skill'] + equipment_speed_skill_bonus() + char_characteristic["lvl_up_skill_speed"]))
    return x


stamina_skill_bonus = stamina_skill_bonus_def()
