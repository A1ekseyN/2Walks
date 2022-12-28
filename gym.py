from datetime import datetime, timedelta
from characteristics import char_characteristic, skill_training_table, save_characteristic
from settings import debug_mode
from colorama import Fore, Style


def gym_menu():
    # Меню выбора навыка для прокачки.
    print('\n🏋 --- Вы находитесь в локации - Спортзал. --- 🏋')
    print('На данный момент вы можете улучшить: '
          f'\n\t1. Выносливость - {Fore.LIGHTCYAN_EX}{char_characteristic["stamina"]}{Style.RESET_ALL} lvl. ('
                f'🏃: {Fore.LIGHTCYAN_EX}{skill_training_table[char_characteristic["stamina"] + 1]["steps"]}{Style.RESET_ALL}; '
                f'🔋: {Fore.GREEN}{skill_training_table[char_characteristic["stamina"] + 1]["energy"]}{Style.RESET_ALL} эн.; '
                f'💰: {Fore.LIGHTYELLOW_EX}{skill_training_table[char_characteristic["stamina"] + 1]["money"]}{Style.RESET_ALL} $ '
                f'🕑: {Fore.LIGHTBLUE_EX}{skill_training_table[char_characteristic["stamina"] + 1]["time"]}{Style.RESET_ALL} мин.).'
          f'\n\t2. Energy Max. - {Fore.LIGHTCYAN_EX}{char_characteristic["energy_max"] - 50}{Style.RESET_ALL} lvl. ('
                f'🏃: {Fore.LIGHTCYAN_EX}{skill_training_table[char_characteristic["energy_max"] - 49]["steps"]}{Style.RESET_ALL}; '
                f'🔋: {Fore.GREEN}{skill_training_table[char_characteristic["energy_max"] - 49]["energy"]}{Style.RESET_ALL} эн.; '
                f'💰: {Fore.LIGHTYELLOW_EX}{skill_training_table[char_characteristic["energy_max"] - 49]["money"]}{Style.RESET_ALL} $; '
                f'🕑: {Fore.LIGHTBLUE_EX}{skill_training_table[char_characteristic["energy_max"] - 49]["time"]}{Style.RESET_ALL} мин.). (Не работает).'
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
    global char_characteristic

    if debug_mode:
        if char_characteristic['skill_training'] == False:
            print('\nНавыки не изучаются.')

    if char_characteristic['skill_training']:
        if datetime.fromtimestamp(datetime.now().timestamp()) >= char_characteristic['skill_training_time_end']:
            char_characteristic[char_characteristic['skill_training_name']] += 1
            print(f'\nНавык {char_characteristic["skill_training_name"].title()} улучшен до {char_characteristic[char_characteristic["skill_training_name"]]}')
            char_characteristic['skill_training'] = False
            char_characteristic['skill_training_name'] = None
            char_characteristic['skill_training_timestamp'] = None
            char_characteristic['skill_training_time_end'] = None
            save_characteristic()
            return char_characteristic


def stamina_skill_training():
    # Повышение выносливости. 1 lvl + 1 % к общему кол-ву пройденых шагов.
    global char_characteristic

    print(f'\nВыносливость: {Fore.GREEN}{char_characteristic["stamina"]}{Style.RESET_ALL} уровень.')
    print('Выносливость - за каждый уровень, на 1 % повышает пройденное кол-во шагов на протяжении дня.')
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
                char_characteristic['skill_training'] = True
                char_characteristic['skill_training_name'] = 'stamina'
                char_characteristic['skill_training_timestamp'] = datetime.now().timestamp()
                char_characteristic['skill_training_time_end'] = datetime.fromtimestamp(datetime.now().timestamp()) + timedelta(minutes=5)
                char_characteristic['steps_today_used'] += (char_characteristic['stamina'] + 1) * 1000
                char_characteristic['energy'] -= (char_characteristic['stamina'] + 1) * 5
                char_characteristic['money'] -= (char_characteristic['stamina'] + 1) * 10
                print('\n🏋️ Выносливость - Начато улучшение навыка.')
                print(f'🕑 Окончание тренировки навыка через: {char_characteristic["skill_training_time_end"] - datetime.fromtimestamp(datetime.now().timestamp())}.')
                return char_characteristic
            else:
                print('\n--- Требования для повышения уровня навыка не выполнены. ---\nДля изучения навыка, вам нужно:')
                if char_characteristic['steps_can_use'] <= (char_characteristic['stamina'] + 1) * 1000:
                    print(f'\n- Шаги 🏃: {char_characteristic["steps_can_use"]} - Нужно 🏃: {(char_characteristic["stamina"] + 1) * 1000}.', end='')
                if char_characteristic['energy'] <= (char_characteristic['stamina'] + 1) * 5:
                    print(f'\n- Энергия 🔋: {char_characteristic["energy"]} - Нужно 🔋: {(char_characteristic["stamina"] + 1) * 5}.', end='')
                if char_characteristic['money'] <= (char_characteristic['stamina'] + 1) * 10:
                    print(f'\n- Money 💰: {char_characteristic["money"]} - Нужно 💰: {(char_characteristic["stamina"] + 1) * 10}.')
        elif ask == '0':
            # Вернуться назад
            pass


def energy_max_skill_training():
    # Повышение кол-ва макс. энергии.
    pass
