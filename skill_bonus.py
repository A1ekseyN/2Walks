# Файл для расчёта бонусов от навыков.
from characteristics import char_characteristic


def stamina_skill_bonus_def():
    stamina_skill_bonus = round(char_characteristic['steps_today'] / 100) * char_characteristic['stamina']
    return stamina_skill_bonus


stamina_skill_bonus = stamina_skill_bonus_def()
