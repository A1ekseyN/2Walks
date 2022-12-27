from datetime import datetime
from characteristics import char_characteristic


def gym_menu():
    # Функция для прокачки навыков.
    print('\n🏋 --- В локации Спортзал можно улучшить навыки персонажа. --- 🏋')
    print('На данный момент вы можете улучшить: '
          f'\n\t1. Выносливость. + 1 % в кол-ву пройденных шагов на протяжении дня: (🕑: ???; 🔋: {(char_characteristic["stamina"] + 1) * 5}; 💰: ???).'
          f'\n\t2. Energy Max. + 1 ед. эн (Time 🕑: ???; Energy 🔋: ???; Money 💰: ???).'
          '\n\t0. Назад.'
          )
    try:
        temp_number = input('\nВыберите какой навык улучшить: \n>>> ')
    except:
        print('\nОшибка ввода. Введите число.')
        gym_menu()

    if temp_number == '1':      # Выносливость
        stamina_skill_training()
    elif temp_number == '2':    # Energy max.
        pass
    elif temp_number == '0':
        # Функция для выхода в основное меню.
        pass


def skill_training_check_done():
    # Проверка или закончилось изучение навыка
    pass


def stamina_skill_training():
    # Повышение выносливости. 1 lvl + 1 % к общему кол-ву пройденых шагов.
    global char_characteristic

    print('\nВыносливость - за каждый уровень, на 1 % повышает пройденное кол-во шагов на протяжении дня.')
    print(f'Выносливость: {char_characteristic["stamina"]} уровень.')
    try:
        ask = input('\t1. Для повышения уровня навыка'
                    '\n\t0. Назад\n>>> ')
    except:
        print('\nОшибка ввода. Введите число.')
        stamina_skill_training()

    if char_characteristic['skill_training']:
        print('\nВ данный момент, вы уже изучаете навык.')
    elif char_characteristic['skill_training'] == False:
        if ask == '1':
            if char_characteristic['steps_can_use'] >= (char_characteristic['stamina'] + 1) * 1000 and char_characteristic['energy'] >= (char_characteristic['stamina'] + 1) * 5 and char_characteristic['money'] >= (char_characteristic['stamina'] + 1) * 10:
                print('\nВыносливость - Начато улучшение навыка.')
                char_characteristic['skill_training'] = True
                char_characteristic['skill_training'] = 'stamina'
                char_characteristic['skill_training_timestamp'] = datetime.now().timestamp()
                char_characteristic['steps_today_used'] += (char_characteristic['stamina'] + 1) * 1000
                char_characteristic['energy'] -= (char_characteristic['stamina'] + 1) * 5
                char_characteristic['money'] -= (char_characteristic['stamina'] + 1) * 10
                return char_characteristic
            else:
                print('\n--- Требования для повышения уровня навыка не выполнены. ---\nДля изучения навыка, вам нужно:')
                if char_characteristic['steps_can_use'] <= (char_characteristic['stamina'] + 1) * 1000:
                    print(f'\n- Шаги 🏃: {char_characteristic["steps_can_use"]} - Нужно 🏃: {(char_characteristic["stamina"] + 1) * 1000}.', end='')
                if char_characteristic['energy'] <= (char_characteristic['stamina'] + 1) * 5:
                    print(f'\n- Энергия 🔋: {char_characteristic["energy"]} - Нужно 🔋: {(char_characteristic["stamina"] + 1) * 5}.', end='')
                if char_characteristic['money'] <= (char_characteristic['stamina'] + 1) * 10:
                    print(f'\n- Money 💰: {char_characteristic["money"]} - Нужно 💰: {(char_characteristic["stamina"] + 1) * 10}.')
                print()
        elif ask == '0':
            # Вернуться назад
            pass


def energy_max_skill_training():
    # Повышение кол-ва макс. энергии.
    pass
