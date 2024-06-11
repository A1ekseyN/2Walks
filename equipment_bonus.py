from characteristics import char_characteristic


def equipment_bonus():
    # Бонус всей экипировки и всех бонусов
    equipment_bonus_stamina = 0
    equipment_bonus_max_energy = 0
    equipment_bonus_speed_skill = 0
    equipment_bonus_luck = 0

    bonus_list = ['stamina', 'energy_max', 'speed_skill', 'luck']
    equipment_list = [char_characteristic['equipment_head'], char_characteristic['equipment_neck'], char_characteristic['equipment_torso'], char_characteristic['equipment_finger_01'], char_characteristic['equipment_finger_02'], char_characteristic['equipment_legs'], char_characteristic['equipment_foots']]

    for item in equipment_list:
        if item is not None:
            for characteristic in bonus_list:
                if item['characteristic'][0] == characteristic:
                    if item['characteristic'][0] == 'stamina':
                        equipment_bonus_stamina += item['bonus'][0]
                    elif item['characteristic'][0] == 'energy_max':
                        equipment_bonus_max_energy += item['bonus'][0]
                    elif item['characteristic'][0] == 'speed_skill':
                        equipment_bonus_speed_skill += item['bonus'][0]
                    elif item['characteristic'][0] == 'luck':
                        equipment_bonus_luck += item['bonus'][0]
    return equipment_bonus_stamina, equipment_bonus_max_energy, equipment_bonus_speed_skill, equipment_bonus_luck

#    print(equipment_bonus_stamina)
#    print(equipment_bonus_max_energy)
#    print(equipment_bonus_speed_skill)
#    print(equipment_bonus_luck)

#equipment_bonus()


equipment_list = [char_characteristic['equipment_head'], char_characteristic['equipment_neck'],
                  char_characteristic['equipment_torso'], char_characteristic['equipment_finger_01'],
                  char_characteristic['equipment_finger_02'], char_characteristic['equipment_legs'],
                  char_characteristic['equipment_foots']]


def equipment_stamina_bonus():
    equipment_stamina_bonus = 0
    for item in equipment_list:
        if item is not None:
            if item['characteristic'][0] == 'stamina':
                equipment_stamina_bonus += item['bonus'][0]
#    print(f'Stamina: {equipment_stamina_bonus}')
    return equipment_stamina_bonus


def equipment_energy_max_bonus():
    equipment_bonus_max_energy = 0
    for item in equipment_list:
        if item is not None:
            if item['characteristic'][0] == 'energy_max':
                equipment_bonus_max_energy += item['bonus'][0]
#    print(f'Energy Max: {equipment_bonus_max_energy}')
    return equipment_bonus_max_energy


def equipment_speed_skill_bonus():
    equipment_bonus_speed_skill = 0
    for item in equipment_list:
        if item is not None:
            if item['characteristic'][0] == 'speed_skill':
                equipment_bonus_speed_skill += item['bonus'][0]
#    print(f'Speed: {equipment_bonus_speed_skill}')
    return equipment_bonus_speed_skill


def equipment_luck_bonus():
    equipment_bonus_luck = 0
    for item in equipment_list:
        if item is not None:
            if item['characteristic'][0] == 'luck':
                equipment_bonus_luck += item['bonus'][0]
#    print(f'Luck: {equipment_bonus_luck}')
    return equipment_bonus_luck
