from datetime import datetime, timedelta
from characteristics import char_characteristic, skill_training_table, save_characteristic
from settings import debug_mode
from colorama import Fore, Style
from skill_bonus import stamina_skill_bonus, stamina_skill_bonus_def
from functions_02 import time


lvl_up_stamina = f'🏃: {Fore.LIGHTCYAN_EX}{skill_training_table[char_characteristic["stamina"] + 1]["steps"]}{Style.RESET_ALL} / ' \
                 f'🔋: {Fore.GREEN}{skill_training_table[char_characteristic["stamina"] + 1]["energy"]}{Style.RESET_ALL} эн. / ' \
                 f'💰: {Fore.LIGHTYELLOW_EX}{skill_training_table[char_characteristic["stamina"] + 1]["money"]}{Style.RESET_ALL} $ / ' \
                 f'🕑: {time(round(skill_training_table[char_characteristic["stamina"] + 1]["time"] - ((skill_training_table[char_characteristic["stamina"] + 1]["time"] / 100) * char_characteristic["speed_skill"])))}'
lvl_up_energy_max = f'🏃: {Fore.LIGHTCYAN_EX}{skill_training_table[char_characteristic["energy_max"] - 49]["steps"]}{Style.RESET_ALL} / ' \
                    f'🔋: {Fore.GREEN}{skill_training_table[char_characteristic["energy_max"] - 49]["energy"]}{Style.RESET_ALL} эн. / ' \
                    f'💰: {Fore.LIGHTYELLOW_EX}{skill_training_table[char_characteristic["energy_max"] - 49]["money"]}{Style.RESET_ALL} $ / ' \
                    f'🕑: {time(round(skill_training_table[char_characteristic["energy_max"] - 49]["time"] - ((skill_training_table[char_characteristic["energy_max"] - 49]["time"] / 100) * char_characteristic["speed_skill"])))}'
lvl_up_speed_skill = f'🏃: {Fore.LIGHTCYAN_EX}{skill_training_table[char_characteristic["speed_skill"] + 1]["steps"]}{Style.RESET_ALL} / ' \
                     f'🔋: {Fore.GREEN}{skill_training_table[char_characteristic["speed_skill"] + 1]["energy"]}{Style.RESET_ALL} эн. / ' \
                     f'💰: {Fore.LIGHTYELLOW_EX}{skill_training_table[char_characteristic["speed_skill"] + 1]["money"]}{Style.RESET_ALL} $ / ' \
                     f'🕑: {time(round(skill_training_table[char_characteristic["speed_skill"] + 1]["time"] - ((skill_training_table[char_characteristic["speed_skill"] + 1]["time"] / 100) * char_characteristic["speed_skill"])))}'


def gym_menu():
    # Меню выбора навыка для прокачки.
    global char_characteristic
    print('\n🏋 --- Вы находитесь в локации - Спортзал. --- 🏋')
    if char_characteristic['skill_training']:
        print(f'\t🏋 Улучшаем навык - {char_characteristic["skill_training_name"].title()} до {Fore.LIGHTCYAN_EX}{char_characteristic[char_characteristic["skill_training_name"]] + 1}{Style.RESET_ALL} уровня.'
              f'\n\t🕑 Улучшение через: {Fore.CYAN}{char_characteristic["skill_training_time_end"] - datetime.fromtimestamp(datetime.now().timestamp())}{Style.RESET_ALL}.')
    print('На данный момент вы можете улучшить: '
          f'\n\t1. Выносливость - {Fore.LIGHTCYAN_EX}{char_characteristic["stamina"] + 1}{Style.RESET_ALL} lvl ({lvl_up_stamina}).'
          f'\n\t2. Energy Max.  - {Fore.LIGHTCYAN_EX}{char_characteristic["energy_max"] - 49}{Style.RESET_ALL} lvl ({lvl_up_energy_max}).'
          f'\n\t3. Speed        - {Fore.LIGHTCYAN_EX}{char_characteristic["speed_skill"] + 1}{Style.RESET_ALL} lvl ({lvl_up_speed_skill}).'
          '\n\t0. Назад.')
    try:
        temp_number = input('\nВыберите какой навык улучшить: \n>>> ')
    except:
        print('\nОшибка ввода. Введите число.')
        gym_menu()

    if char_characteristic['skill_training']:
        print(f'В данный момент вы изучаете навык: {char_characteristic["skill_training_name"].title()}.')
        gym_menu()
    else:
        if temp_number == '1':      # Выносливость
            Skill.stamina_skill_training()
            try:
                ask = input('\t1. Повысить Выносливость на + 1.'
                            '\n\t0. Назад\n>>> ')
                if ask == '1':
                    char_characteristic['skill_training_name'] = 'stamina'
                    Start = Skill_Training(char_characteristic['skill_training'], char_characteristic['skill_training_name'], char_characteristic['skill_training_timestamp'], char_characteristic['skill_training_time_end'], datetime.now().timestamp())
                    Start.check_requirements()
    #                Start.start_skill_training()   # Старый метод, без проверки условий: шагов, энергии, денег.
                elif ask == '0':
                    gym_menu()
                else:
                    gym_menu()
            except:
                gym_menu()
    #        stamina_skill_training()       # Старая Функция прокачки Stamina, пускай, пока побудет здесь.

        elif temp_number == '2':    # Energy max.
            Skill.enegry_max_skill_training()
            try:
                ask = input(f'\t1. Повысить Максимальный запас энергии на + 1.'
                            f'\n\t0. Назад.\n>>> ')
                if ask == '1':
                    char_characteristic['skill_training_name'] = 'energy_max_skill'
                    Start = Skill_Training(char_characteristic['skill_training'], char_characteristic['skill_training_name'], char_characteristic['skill_training_timestamp'], char_characteristic['skill_training_time_end'], datetime.now().timestamp())
                    Start.check_requirements()
#                    Start.start_skill_training()
                elif ask == '0':
                    gym_menu()
                else:
                    gym_menu()
            except:
                gym_menu()
        elif temp_number == '3':    # Speed.
            Skill.speed_skill_training()
            try:
                ask = input('\t1. Повысить скорость персонажа на 1 %.'
                            '\n\t0. Назад.\n>>> ')
                if ask == '1':
                    char_characteristic['skill_training_name'] = 'speed_skill'
                    Start = Skill_Training(char_characteristic['skill_training'], char_characteristic['skill_training_name'], char_characteristic['skill_training_timestamp'], char_characteristic['skill_training_time_end'], datetime.now().timestamp())
                    Start.check_requirements()
                elif ask == '0':
                    gym_menu()
                else:
                    gym_menu()
            except:
                gym_menu()

        elif temp_number == '0':
            # Выход в основное меню.
            pass
        else:
            gym_menu()


def skill_training_check_done():
    # Проверка или закончилось изучение навыка
    global char_characteristic
    if debug_mode:
        if char_characteristic['skill_training'] == False:
            print('\nНавыки не изучаются.')

    if char_characteristic['skill_training']:
        if datetime.fromtimestamp(datetime.now().timestamp()) >= char_characteristic['skill_training_time_end']:
            char_characteristic[char_characteristic['skill_training_name']] += 1
            print(f'\n🏋 Навык {char_characteristic["skill_training_name"].title()} улучшен до {char_characteristic[char_characteristic["skill_training_name"]]}')
            char_characteristic['skill_training'] = False
            char_characteristic['skill_training_name'] = None
            char_characteristic['skill_training_timestamp'] = None
            char_characteristic['skill_training_time_end'] = None
            stamina_skill_bonus_def()
            save_characteristic()
            return char_characteristic


"""
def stamina_skill_training():
    # Повышение выносливости. 1 lvl + 1 % к общему кол-ву пройденых шагов.
    global char_characteristic

    print(f'\nВыносливость: {Fore.GREEN}{char_characteristic["stamina"]}{Style.RESET_ALL} уровень.')
    print('Выносливость - за каждый уровень, на 1 % повышает пройденное кол-во шагов на протяжении дня.')

    try:
        ask = input(f'\t1. Повысить уровень навыка до - {char_characteristic["stamina"] + 1} уровня.'
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
                char_characteristic['skill_training_time_end'] = datetime.fromtimestamp(datetime.now().timestamp()) + timedelta(minutes=(skill_training_table[char_characteristic['stamina'] + 1]['time']))
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
            gym_menu()
"""

#def energy_max_skill_training():
#    # Повышение кол-ва макс. энергии.
#    pass


class Skill_Training():
    # Класс инициализации работы

    def __init__(self, training, name, timestamp, time_end, time_stamp_now):
        # Инициализация атрибутов
        self.training = training
        self.name = name
        self.timestamp = timestamp
        self.time_end = time_end
        self.timestamp_now = time_stamp_now

    def check_requirements(self):
        # Проверка кол-ва шагов, энергии, и денег.
        if char_characteristic['steps_can_use'] >= skill_training_table[char_characteristic[self.name] + 1]["steps"] \
            and char_characteristic['energy'] >= skill_training_table[char_characteristic[self.name] + 1]["energy"]\
            and char_characteristic['money'] >= skill_training_table[char_characteristic[self.name] + 1]["money"]:
            print('\nПроверка кол-ва шагов, энергии и денег - успешна.')

            ### Проверить или здесь все нормально работает. И все ли хорошо с переменными.
            Skill_Training.start_skill_training(self)       # Начало прокачки навыка, если выполнены требования.

        else:
            print('\nУ вас не достаточно ресурсов: ')
            if char_characteristic['steps_can_use'] <= skill_training_table[char_characteristic[self.name] + 1]["steps"]:
                print(f'\t- 🏃: Не хватает - {skill_training_table[char_characteristic[self.name] + 1]["steps"] - char_characteristic["steps_can_use"]} шагов.')
            if char_characteristic['energy'] <= skill_training_table[char_characteristic[self.name] + 1]["energy"]:
                print(f'\t- 🔋: Не хватает - {skill_training_table[char_characteristic[self.name] + 1]["energy"] - char_characteristic["energy"]} энергии.')
            if char_characteristic['money'] <= skill_training_table[char_characteristic[self.name] + 1]["money"]:
                print(f'\t- 💰: Не хватает - {skill_training_table[char_characteristic[self.name] + 1]["money"] - char_characteristic["money"]} money.')

    def start_skill_training(self):
        # Начало обучения навыка
        skill_training_time = round(skill_training_table[char_characteristic['speed_skill'] + 1]['time']) * 60
        skill_training_speed_skill = skill_training_time - ((skill_training_time / 100) * char_characteristic['speed_skill'])
        skill_training_time_with_bonus = datetime.fromtimestamp(datetime.now().timestamp() + skill_training_speed_skill)

        char_characteristic['skill_training'] = True
        char_characteristic['skill_training_name'] = self.name
        char_characteristic['skill_training_timestamp'] = datetime.now().timestamp()
#        char_characteristic['skill_training_time_end'] = datetime.fromtimestamp(datetime.now().timestamp()) + timedelta(minutes=(skill_training_table[char_characteristic[self.name] + 1]['time']))
        char_characteristic['skill_training_time_end'] = skill_training_time_with_bonus
        char_characteristic['steps_today_used'] += (char_characteristic[self.name] + 1) * 1000
        char_characteristic['energy'] -= (char_characteristic[self.name] + 1) * 5
        char_characteristic['money'] -= (char_characteristic[self.name] + 1) * 10

        print(f'\n🏋️ {self.name.title()} - Начато улучшение навыка.')
        print(f'🕑 Окончание тренировки навыка через: {char_characteristic["skill_training_time_end"] - datetime.fromtimestamp(datetime.now().timestamp())}.')
        return char_characteristic

    def stamina_skill_training(self):
        print(f'\nВыносливость: {Fore.GREEN}{char_characteristic["stamina"]}{Style.RESET_ALL} уровень.')
        print('Выносливость - за каждый уровень, на 1 % повышает пройденное кол-во шагов на протяжении дня.')
        print(f'\nДля улучшения до {Fore.GREEN}{char_characteristic["stamina"] + 1}{Style.RESET_ALL} уровня необходимо: ({lvl_up_stamina}).')

    def enegry_max_skill_training(self):
        print(f'\nМаксимальный запас энергии: {Fore.GREEN}{char_characteristic["energy_max_skill"]}{Style.RESET_ALL} уровень.')
        print(f'Максимальный запас энергии - каждый уровень, добавляет + 1 эдиницу к максимальному запасу энергии.')
        print(f'\nДля улучшения необходимо: ({lvl_up_energy_max}).')

    def speed_skill_training(self):
        print(f'Скорость: {Fore.GREEN}{char_characteristic["speed_skill"]}{Style.RESET_ALL} уровень.')
        print(f'Скорость - каждый уровень добавляет + 1% к общей скорости персонажа. Влияет на работу, прокачку навыков, прохождение приключений.')
        print(f'Для улучшения необходимо: ({lvl_up_speed_skill}).')


Skill = Skill_Training(char_characteristic['skill_training'], char_characteristic['skill_training_name'],
                       char_characteristic['skill_training_timestamp'], char_characteristic['skill_training_time_end'], datetime.now().timestamp())
