from datetime import datetime, timedelta
from characteristics import char_characteristic, skill_training_table, save_characteristic
from settings import debug_mode
from colorama import Fore, Style
from skill_bonus import stamina_skill_bonus, stamina_skill_bonus_def
from functions_02 import time
from equipment_bonus import equipment_speed_skill_bonus, equipment_energy_max_bonus


lvl_up_stamina = f'🏃: {Fore.LIGHTCYAN_EX}{skill_training_table[char_characteristic["stamina"] + 1]["steps"]:,.0f}{Style.RESET_ALL} / ' \
                 f'🔋: {Fore.GREEN}{skill_training_table[char_characteristic["stamina"] + 1]["energy"]}{Style.RESET_ALL} эн. / ' \
                 f'💰: {Fore.LIGHTYELLOW_EX}{skill_training_table[char_characteristic["stamina"] + 1]["money"]}{Style.RESET_ALL} $ / ' \
                 f'🕑: {time(round(skill_training_table[char_characteristic["stamina"] + 1]["time"] - ((skill_training_table[char_characteristic["stamina"] + 1]["time"] / 100) * (char_characteristic["speed_skill"] + equipment_speed_skill_bonus() + char_characteristic["lvl_up_skill_speed"]))))}'
lvl_up_energy_max = f'🏃: {Fore.LIGHTCYAN_EX}{skill_training_table[char_characteristic["energy_max"] - 49 - equipment_energy_max_bonus() - char_characteristic["steps_daily_bonus"]]["steps"]:,.0f}{Style.RESET_ALL} / ' \
                    f'🔋: {Fore.GREEN}{skill_training_table[char_characteristic["energy_max"] - 49 - equipment_energy_max_bonus() - char_characteristic["steps_daily_bonus"]]["energy"]}{Style.RESET_ALL} эн. / ' \
                    f'💰: {Fore.LIGHTYELLOW_EX}{skill_training_table[char_characteristic["energy_max"] - 49 - equipment_energy_max_bonus() - char_characteristic["steps_daily_bonus"]]["money"]}{Style.RESET_ALL} $ / ' \
                    f'🕑: {time(round(skill_training_table[char_characteristic["energy_max"] - 49 - equipment_energy_max_bonus() - char_characteristic["steps_daily_bonus"]]["time"] - ((skill_training_table[char_characteristic["energy_max"] - 49]["time"] / 100) * (char_characteristic["speed_skill"] + equipment_speed_skill_bonus() + char_characteristic["lvl_up_skill_speed"]))))}'
lvl_up_speed_skill = f'🏃: {Fore.LIGHTCYAN_EX}{skill_training_table[char_characteristic["speed_skill"] + 1]["steps"]:,.0f}{Style.RESET_ALL} / ' \
                     f'🔋: {Fore.GREEN}{skill_training_table[char_characteristic["speed_skill"] + 1]["energy"]}{Style.RESET_ALL} эн. / ' \
                     f'💰: {Fore.LIGHTYELLOW_EX}{skill_training_table[char_characteristic["speed_skill"] + 1]["money"]}{Style.RESET_ALL} $ / ' \
                     f'🕑: {time(round(skill_training_table[char_characteristic["speed_skill"] + 1]["time"] - ((skill_training_table[char_characteristic["speed_skill"] + 1]["time"] / 100) * (char_characteristic["speed_skill"] + equipment_speed_skill_bonus() + char_characteristic["lvl_up_skill_speed"]))))}'
lvl_up_luck_skill = f'🏃: {Fore.LIGHTCYAN_EX}{skill_training_table[char_characteristic["luck_skill"] + 1]["steps"]:,.0f}{Style.RESET_ALL} / ' \
                     f'🔋: {Fore.GREEN}{skill_training_table[char_characteristic["luck_skill"] + 1]["energy"]}{Style.RESET_ALL} эн. / ' \
                     f'💰: {Fore.LIGHTYELLOW_EX}{skill_training_table[char_characteristic["luck_skill"] + 1]["money"]}{Style.RESET_ALL} $ / ' \
                     f'🕑: {time(round(skill_training_table[char_characteristic["luck_skill"] + 1]["time"] - ((skill_training_table[char_characteristic["luck_skill"] + 1]["time"] / 100) * (char_characteristic["speed_skill"] + equipment_speed_skill_bonus() + char_characteristic["lvl_up_skill_speed"]))))}'


def gym_menu():
    # Меню выбора навыка для прокачки.
    global char_characteristic
    print('\n🏋 --- Вы находитесь в локации - Спортзал. --- 🏋')

    if char_characteristic['skill_training']:
        print(f'\t🏋 Улучшаем навык - {char_characteristic["skill_training_name"].title()} до {Fore.LIGHTCYAN_EX}{char_characteristic[char_characteristic["skill_training_name"]] + 1}{Style.RESET_ALL} уровня.'
              f'\n\t🕑 Улучшение через: {Fore.CYAN}{char_characteristic["skill_training_time_end"] - datetime.fromtimestamp(datetime.now().timestamp())}{Style.RESET_ALL}.')
    else:
        print('На данный момент вы можете улучшить: '
              f'\n\t1. Выносливость - {Fore.LIGHTCYAN_EX}{char_characteristic["stamina"] + 1}{Style.RESET_ALL} lvl ({lvl_up_stamina}).'
              f'\n\t2. Energy Max.  - {Fore.LIGHTCYAN_EX}{char_characteristic["energy_max"] - 49 - equipment_energy_max_bonus() - char_characteristic["steps_daily_bonus"]}{Style.RESET_ALL} lvl ({lvl_up_energy_max}).'
              f'\n\t3. Speed        - {Fore.LIGHTCYAN_EX}{char_characteristic["speed_skill"] + 1}{Style.RESET_ALL} lvl ({lvl_up_speed_skill}).'
              f'\n\t4. Luck         - {Fore.LIGHTCYAN_EX}{char_characteristic["luck_skill"] + 1}{Style.RESET_ALL} lvl ({lvl_up_luck_skill}).'
              '\n\t0. Назад.')
        try:
            temp_number = input('\nВыберите какой навык улучшить: \n>>> ')
        except:
            print('\nОшибка ввода. Введите число.')
            gym_menu()

        if temp_number == '1':      # Выносливость
            Skill.stamina_skill_training()
            try:
                ask = input('\t1. Повысить Выносливость на + 1.'
                            '\n\t0. Назад\n>>> ')
                if ask == '1':
                    char_characteristic['skill_training_name'] = 'stamina'
                    Start = Skill_Training(char_characteristic['skill_training'],
                                           char_characteristic['skill_training_name'],
                                           char_characteristic['skill_training_timestamp'],
                                           char_characteristic['skill_training_time_end'],
                                           datetime.now().timestamp())
                    Start.check_requirements()
                elif ask == '0':
                    gym_menu()
                else:
                    gym_menu()
            except:
                gym_menu()

        elif temp_number == '2':    # Energy max.
            Skill.enegry_max_skill_training()
            try:
                ask = input(f'\t1. Повысить Максимальный запас энергии на + 1.'
                            f'\n\t0. Назад.\n>>> ')
                if ask == '1':
                    char_characteristic['skill_training_name'] = 'energy_max_skill'
                    Start = Skill_Training(char_characteristic['skill_training'],
                                           char_characteristic['skill_training_name'],
                                           char_characteristic['skill_training_timestamp'],
                                           char_characteristic['skill_training_time_end'],
                                           datetime.now().timestamp())
                    Start.check_requirements()
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
                    Start = Skill_Training(char_characteristic['skill_training'],
                                           char_characteristic['skill_training_name'],
                                           char_characteristic['skill_training_timestamp'],
                                           char_characteristic['skill_training_time_end'],
                                           datetime.now().timestamp())
                    Start.check_requirements()
                elif ask == '0':
                    gym_menu()
                else:
                    gym_menu()
            except:
                gym_menu()

        elif temp_number == '4':    # luck.
            Skill.luck_skill_training()
            try:
                ask = input('\t1. Повысить Удачу персонажа на 1 %.'
                            '\n\t0. Назад.\n>>> ')
                if ask == '1':
                    char_characteristic['skill_training_name'] = 'luck_skill'
                    Start = Skill_Training(char_characteristic['skill_training'],
                                           char_characteristic['skill_training_name'],
                                           char_characteristic['skill_training_timestamp'],
                                           char_characteristic['skill_training_time_end'],
                                           datetime.now().timestamp())
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


class Skill_Training():
    # Класс инициализации прокачки навыков
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
            print(f'\n{Fore.RED}У вас не достаточно ресурсов: {Style.RESET_ALL}')
            if char_characteristic['steps_can_use'] <= skill_training_table[char_characteristic[self.name] + 1]["steps"]:
                print(f'\t- 🏃: Не хватает - {skill_training_table[char_characteristic[self.name] + 1]["steps"] - char_characteristic["steps_can_use"]} шагов.')
            if char_characteristic['energy'] <= skill_training_table[char_characteristic[self.name] + 1]["energy"]:
                print(f'\t- 🔋: Не хватает - {skill_training_table[char_characteristic[self.name] + 1]["energy"] - char_characteristic["energy"]} энергии.')
            if char_characteristic['money'] <= skill_training_table[char_characteristic[self.name] + 1]["money"]:
                print(f'\t- 💰: Не хватает - {skill_training_table[char_characteristic[self.name] + 1]["money"] - char_characteristic["money"]} money.')
            gym_menu()

    def start_skill_training(self):
        # Начало обучения навыка
        skill_training_time = round(skill_training_table[char_characteristic[self.name] + 1]['time']) * 60
        skill_training_speed_skill = skill_training_time - ((skill_training_time / 100) * (char_characteristic[self.name] + equipment_speed_skill_bonus() + char_characteristic["lvl_up_skill_speed"]))
        skill_training_time_with_bonus = datetime.fromtimestamp(datetime.now().timestamp() + skill_training_speed_skill)

        char_characteristic['skill_training'] = True
        char_characteristic['skill_training_name'] = self.name
        char_characteristic['skill_training_timestamp'] = datetime.now().timestamp()
        char_characteristic['skill_training_time_end'] = skill_training_time_with_bonus
        char_characteristic['steps_today_used'] += skill_training_table[char_characteristic[self.name] + 1]['steps']
        char_characteristic['steps_total_used'] += skill_training_table[char_characteristic[self.name] + 1]['steps']
        char_characteristic['energy'] -= skill_training_table[char_characteristic[self.name] + 1]['energy']
        char_characteristic['money'] -= skill_training_table[char_characteristic[self.name] + 1]['money']

        print(f'\n🏋️ {self.name.title()} - Начато улучшение навыка. 🏋')
        print(f'На улучшение навыка {self.name} потрачено:'
              f'\n- 🏃: {skill_training_table[char_characteristic[self.name] + 1]["steps"]:,.0f} steps'
              f'\n- 🔋: {skill_training_table[char_characteristic[self.name] + 1]["energy"]} эн.'
              f'\n- 💰: {skill_training_table[char_characteristic[self.name] + 1]["money"]} $'
              f'\n- 🕑 Окончание тренировки навыка через: {Fore.LIGHTBLUE_EX}{time(round(skill_training_table[char_characteristic[self.name] + 1]["time"] - ((skill_training_table[char_characteristic[self.name] + 1]["time"] / 100) * (char_characteristic["speed_skill"] + equipment_speed_skill_bonus() + char_characteristic["lvl_up_skill_speed"]))))}{Style.RESET_ALL}')
        return char_characteristic

    def stamina_skill_training(self):
        print(f'\nВыносливость: {Fore.GREEN}{char_characteristic["stamina"]}{Style.RESET_ALL} уровень.')
        print('\nВыносливость - за каждый уровень, на 1 % повышает пройденное кол-во шагов на протяжении дня.')
        print(f'\nДля улучшения до {Fore.GREEN}{char_characteristic["stamina"] + 1}{Style.RESET_ALL} уровня необходимо: ({lvl_up_stamina}).')

    def enegry_max_skill_training(self):
        print(f'\nМаксимальный запас энергии: {Fore.GREEN}{char_characteristic["energy_max_skill"]}{Style.RESET_ALL} уровень.')
        print(f'\nМаксимальный запас энергии - каждый уровень, добавляет + 1 единицу к максимальному запасу энергии.')
        print(f'\nДля улучшения необходимо: ({lvl_up_energy_max}).')

    def speed_skill_training(self):
        print(f'\nСкорость: {Fore.GREEN}{char_characteristic["speed_skill"]}{Style.RESET_ALL} уровень.')
        print(f'\nСкорость - каждый уровень добавляет + 1% к общей скорости персонажа. Влияет на работу, прокачку навыков, прохождение приключений.')
        print(f'\nДля улучшения необходимо: ({lvl_up_speed_skill}).')

    def luck_skill_training(self):
        print(f'\nУдача: {Fore.GREEN}{char_characteristic["luck_skill"]}{Style.RESET_ALL} уровень.')
        print(f'\nУдача - за каждый уровень улучшения, увеличивается удача персонажа на 1%. '
              f'\nУдача влияет на шанс выпадения предметов, а так же на их качество.'
              f'\nТак же, удача влияет и на другие игровые события.')
        print(f'\nДля улучшения необходимо: ({lvl_up_luck_skill}).')


Skill = Skill_Training(char_characteristic['skill_training'], char_characteristic['skill_training_name'],
                       char_characteristic['skill_training_timestamp'], char_characteristic['skill_training_time_end'],
                       datetime.now().timestamp())
