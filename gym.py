from datetime import datetime, timedelta
from characteristics import char_characteristic, skill_training_table, save_characteristic, get_energy_training_data
from settings import debug_mode
from colorama import Fore, Style
from skill_bonus import stamina_skill_bonus_def
from functions_02 import time
from equipment_bonus import equipment_speed_skill_bonus, equipment_energy_max_bonus
from bonus import apply_move_optimization_gym
from inventory import Wear_Equipped_Items


lvl_up_stamina = f'🏃: {Fore.LIGHTCYAN_EX}{apply_move_optimization_gym(skill_training_table[char_characteristic["stamina"] + 1]["steps"]):,.0f}{Style.RESET_ALL} / ' \
                 f'🔋: {Fore.GREEN}{skill_training_table[char_characteristic["stamina"] + 1]["energy"]}{Style.RESET_ALL} эн. / ' \
                 f'💰: {Fore.LIGHTYELLOW_EX}{skill_training_table[char_characteristic["stamina"] + 1]["money"]}{Style.RESET_ALL} $ / ' \
                 f'🕑: {time(round(skill_training_table[char_characteristic["stamina"] + 1]["time"] - ((skill_training_table[char_characteristic["stamina"] + 1]["time"] / 100) * (char_characteristic["speed_skill"] + equipment_speed_skill_bonus() + char_characteristic["lvl_up_skill_speed"]))))}'
lvl_up_energy_max = f'🏃: {Fore.LIGHTCYAN_EX}{apply_move_optimization_gym(get_energy_training_data(char_characteristic["energy_max"] - 49 - equipment_energy_max_bonus() - char_characteristic["steps_daily_bonus"])["steps"]):,.0f}{Style.RESET_ALL} / ' \
                    f'🔋: {Fore.GREEN}{get_energy_training_data(char_characteristic["energy_max"] - 49 - equipment_energy_max_bonus() - char_characteristic["steps_daily_bonus"])["energy"]}{Style.RESET_ALL} эн. / ' \
                    f'💰: {Fore.LIGHTYELLOW_EX}{get_energy_training_data(char_characteristic["energy_max"] - 49 - equipment_energy_max_bonus() - char_characteristic["steps_daily_bonus"])["money"]}{Style.RESET_ALL} $ / ' \
                    f'🕑: {time(round(get_energy_training_data(char_characteristic["energy_max"] - 49 - equipment_energy_max_bonus() - char_characteristic["steps_daily_bonus"])["time"] - ((get_energy_training_data(char_characteristic["energy_max"] - 49 - equipment_energy_max_bonus() - char_characteristic["steps_daily_bonus"])["time"] / 100) * (char_characteristic["speed_skill"] + equipment_speed_skill_bonus() + char_characteristic["lvl_up_skill_speed"]))))}'
lvl_up_speed_skill = f'🏃: {Fore.LIGHTCYAN_EX}{apply_move_optimization_gym(skill_training_table[char_characteristic["speed_skill"] + 1]["steps"]):,.0f}{Style.RESET_ALL} / ' \
                     f'🔋: {Fore.GREEN}{skill_training_table[char_characteristic["speed_skill"] + 1]["energy"]}{Style.RESET_ALL} эн. / ' \
                     f'💰: {Fore.LIGHTYELLOW_EX}{skill_training_table[char_characteristic["speed_skill"] + 1]["money"]}{Style.RESET_ALL} $ / ' \
                     f'🕑: {time(round(skill_training_table[char_characteristic["speed_skill"] + 1]["time"] - ((skill_training_table[char_characteristic["speed_skill"] + 1]["time"] / 100) * (char_characteristic["speed_skill"] + equipment_speed_skill_bonus() + char_characteristic["lvl_up_skill_speed"]))))}'
lvl_up_luck_skill = f'🏃: {Fore.LIGHTCYAN_EX}{apply_move_optimization_gym(skill_training_table[char_characteristic["luck_skill"] + 1]["steps"]):,.0f}{Style.RESET_ALL} / ' \
                     f'🔋: {Fore.GREEN}{skill_training_table[char_characteristic["luck_skill"] + 1]["energy"]}{Style.RESET_ALL} эн. / ' \
                     f'💰: {Fore.LIGHTYELLOW_EX}{skill_training_table[char_characteristic["luck_skill"] + 1]["money"]}{Style.RESET_ALL} $ / ' \
                     f'🕑: {time(round(skill_training_table[char_characteristic["luck_skill"] + 1]["time"] - ((skill_training_table[char_characteristic["luck_skill"] + 1]["time"] / 100) * (char_characteristic["speed_skill"] + equipment_speed_skill_bonus() + char_characteristic["lvl_up_skill_speed"]))))}'

lvl_up_move_optimization_adventure = f'🏃: {Fore.LIGHTCYAN_EX}{apply_move_optimization_gym(skill_training_table[char_characteristic["move_optimization_adventure"] + 1]["steps"]):,.0f}{Style.RESET_ALL} / ' \
                                     f'🔋: {Fore.GREEN}{skill_training_table[char_characteristic["move_optimization_adventure"] + 1]["energy"]}{Style.RESET_ALL} эн. / ' \
                                     f'💰: {Fore.LIGHTYELLOW_EX}{skill_training_table[char_characteristic["move_optimization_adventure"] + 1]["money"]}{Style.RESET_ALL} $ / ' \
                                     f'🕑: {time(round(skill_training_table[char_characteristic["move_optimization_adventure"] + 1]["time"] - ((skill_training_table[char_characteristic["move_optimization_adventure"] + 1]["time"] / 100) * (char_characteristic["speed_skill"] + equipment_speed_skill_bonus() + char_characteristic["lvl_up_skill_speed"]))))}'
lvl_up_move_optimization_gym = f'🏃: {Fore.LIGHTCYAN_EX}{apply_move_optimization_gym(skill_training_table[char_characteristic["move_optimization_gym"] + 1]["steps"]):,.0f}{Style.RESET_ALL} / ' \
                               f'🔋: {Fore.GREEN}{skill_training_table[char_characteristic["move_optimization_gym"] + 1]["energy"]}{Style.RESET_ALL} эн. / ' \
                               f'💰: {Fore.LIGHTYELLOW_EX}{skill_training_table[char_characteristic["move_optimization_gym"] + 1]["money"]}{Style.RESET_ALL} $ / ' \
                               f'🕑: {time(round(skill_training_table[char_characteristic["move_optimization_gym"] + 1]["time"] - ((skill_training_table[char_characteristic["move_optimization_gym"] + 1]["time"] / 100) * (char_characteristic["speed_skill"] + equipment_speed_skill_bonus() + char_characteristic["lvl_up_skill_speed"]))))}'
lvl_up_move_optimization_work = f'🏃: {Fore.LIGHTCYAN_EX}{apply_move_optimization_gym(skill_training_table[char_characteristic["move_optimization_work"] + 1]["steps"]):,.0f}{Style.RESET_ALL} / ' \
                                f'🔋: {Fore.GREEN}{skill_training_table[char_characteristic["move_optimization_work"] + 1]["energy"]}{Style.RESET_ALL} эн. / ' \
                                f'💰: {Fore.LIGHTYELLOW_EX}{skill_training_table[char_characteristic["move_optimization_work"] + 1]["money"]}{Style.RESET_ALL} $ / ' \
                                f'🕑: {time(round(skill_training_table[char_characteristic["move_optimization_work"] + 1]["time"] - ((skill_training_table[char_characteristic["move_optimization_work"] + 1]["time"] / 100) * (char_characteristic["speed_skill"] + equipment_speed_skill_bonus() + char_characteristic["lvl_up_skill_speed"]))))}'

lvl_up_neatness_in_using_things = f'🏃: {Fore.LIGHTCYAN_EX}{apply_move_optimization_gym(skill_training_table[char_characteristic["neatness_in_using_things"] + 1]["steps"]):,.0f}{Style.RESET_ALL} / ' \
                                 f'🔋: {Fore.GREEN}{skill_training_table[char_characteristic["neatness_in_using_things"] + 1]["energy"]}{Style.RESET_ALL} эн. / ' \
                                 f'💰: {Fore.LIGHTYELLOW_EX}{skill_training_table[char_characteristic["neatness_in_using_things"] + 1]["money"]}{Style.RESET_ALL} $ / ' \
                                 f'🕑: {time(round(skill_training_table[char_characteristic["neatness_in_using_things"] + 1]["time"] - ((skill_training_table[char_characteristic["neatness_in_using_things"] + 1]["time"] / 100) * (char_characteristic["speed_skill"] + equipment_speed_skill_bonus() + char_characteristic["lvl_up_skill_speed"]))))}'


description_stamina = f'\nВыносливость: {Fore.GREEN}{char_characteristic["stamina"]}{Style.RESET_ALL} уровень.' \
                      f'\nКаждый уровень, на 1 % повышает пройденное кол-во шагов на протяжении дня.' \
                      f'\n\nДля улучшения до {Fore.GREEN}{char_characteristic["stamina"] + 1}{Style.RESET_ALL} уровня необходимо: ({lvl_up_stamina}).'

description_energy_max = f'\nМаксимальный запас энергии: {Fore.GREEN}{char_characteristic["energy_max_skill"]}{Style.RESET_ALL} уровень.' \
                         f'\nКаждый уровень, добавляет + 1 единицу к максимальному запасу энергии.' \
                         f'\n\nДля улучшения необходимо: ({lvl_up_energy_max}).'

description_speed = f'\nСкорость: {Fore.GREEN}{char_characteristic["speed_skill"]}{Style.RESET_ALL} уровень.' \
                    f'\nКаждый уровень добавляет + 1% к общей скорости персонажа. Влияет на работу, прокачку навыков, прохождение приключений.' \
                    f'\n\nДля улучшения необходимо: ({lvl_up_speed_skill}).'

description_luck = f'\nУдача: {Fore.GREEN}{char_characteristic["luck_skill"]}{Style.RESET_ALL} уровень.' \
                   f'\nКаждый уровень улучшения, увеличивается удача персонажа на 1%.' \
                   f'\nУдача влияет на шанс выпадения предметов, а так же на их качество.' \
                   f'\nТак же, удача влияет и на другие игровые события.' \
                   f'\n\nДля улучшения необходимо: ({lvl_up_luck_skill}).'

description_move_optimization_adventure = f'\nОптимизация движений Adventure: {Fore.GREEN}{char_characteristic["move_optimization_adventure"]}{Style.RESET_ALL} уровень.' \
                                          f'\nКаждый уровень уменьшает на 1 % количество шагов необходимых для активности.' \
                                          f'\n\nДля улучшения необходимо: ({lvl_up_move_optimization_adventure})'

description_move_optimization_gym = f"\nОптимизация движений Gym: {Fore.GREEN}{char_characteristic['move_optimization_gym']}{Style.RESET_ALL} уровень." \
                                    f"\nКаждый уровень уменьшает на 1 % количество шагов необходимых для активности." \
                                    f"\n\nДля улучшения необходимо: ({lvl_up_move_optimization_gym})"

description_move_optimization_work = f"\nОптимизация движений Work: {Fore.GREEN}{char_characteristic['move_optimization_work']}{Style.RESET_ALL} уровень." \
                                     f"\nКаждый уровень уменьшает на 1 % количество шагов необходимых для активности." \
                                     f"\n\nДля улучшения необходимо: ({lvl_up_move_optimization_work})"

description_neatness_in_using_things = f"\nАккуратность при использовании вещей: {Fore.GREEN}{char_characteristic['neatness_in_using_things']}{Style.RESET_ALL}. " \
                                       f"\nКаждый уровень навыка уменьшает износ вещей на 1 %. " \
                                       f"\n\nДля улучшения необходимо: ({lvl_up_neatness_in_using_things})" \


def gym_menu():
    # Меню выбора навыка для прокачки.
    global char_characteristic
    print('\n🏋 --- Вы находитесь в локации - Спортзал. --- 🏋')

    if char_characteristic['skill_training']:
        print(f'\t🏋 Улучшаем навык - {char_characteristic["skill_training_name"].title()} до {Fore.LIGHTCYAN_EX}{char_characteristic[char_characteristic["skill_training_name"]] + 1}{Style.RESET_ALL} уровня.'
              f'\n\t🕑 Улучшение через: {Fore.CYAN}{char_characteristic["skill_training_time_end"] - datetime.fromtimestamp(datetime.now().timestamp())}{Style.RESET_ALL}.')
    else:
        skill_options = {
            '1': ('stamina', 'Stamina:    ', char_characteristic['stamina'] + 1),
            '2': ('energy_max', 'Energy Max: ',
                  char_characteristic['energy_max'] - 49 - equipment_energy_max_bonus() - char_characteristic[
                      'steps_daily_bonus']),
            '3': ('speed_skill', 'Speed:      ', char_characteristic['speed_skill'] + 1),
            '4': ('luck_skill', 'Luck:       ', char_characteristic['luck_skill'] + 1),
            '5': ('move_optimization_adventure', 'Оптимизация движений Adventure:   ', char_characteristic['move_optimization_adventure'] + 1),
            '6': ('move_optimization_gym', 'Оптимизация движений Gym:         ', char_characteristic['move_optimization_gym'] + 1),
            '7': ('move_optimization_work', 'Оптимизация движений Work:        ', char_characteristic['move_optimization_work'] + 1),
            '8': ('neatness_in_using_things', 'Аккуратность использования вещей: ', char_characteristic['neatness_in_using_things'] + 1)
        }

        print(f"Steps 🏃: {char_characteristic['steps_can_use']}, "
              f"Energy 🔋: {char_characteristic['energy']}, "
              f"Money 💰: {char_characteristic['money']} $.")
        print('На данный момент вы можете улучшить: ')
        for key, (skill, name, level) in skill_options.items():
            print(f'\t{key}. {name}{Fore.LIGHTCYAN_EX}{level}{Style.RESET_ALL} lvl ({get_lvl_up_info(skill, level)})')
        print('\n\t0. Назад.')

        try:
            temp_number = input('\nВыберите какой навык улучшить: \n>>> ')
            if temp_number == '0':
                return
            elif temp_number in skill_options:
                skill_name, skill_display_name, level = skill_options[temp_number]

                # Вывод описания выбранного навыка
                display_skill_description(skill_name)

                ask = input(f'\t1. Повысить {skill_display_name.strip()} + 1.'
                            f'\n\t0. Назад\n>>> ')
                if ask == '1':
                    char_characteristic['skill_training_name'] = skill_name
                    skill_training = Skill_Training(training=True, name=skill_name, timestamp=None, time_end=None,
                                                    time_stamp_now=None)

                    # Проверка наличия достаточных ресурсов
                    if skill_training.check_requirements():
                        # Запуск прокачки навыка
                        skill_training.start_skill_training()

                        # Износ Экипировки
                        steps = apply_move_optimization_gym(skill_training_table[char_characteristic[skill_name] + 1]["steps"])
                        equipped_items_manager = Wear_Equipped_Items()
                        equipped_items_manager.decrease_durability(steps)


                    else:
                        gym_menu()
                else:
                    gym_menu()
            else:
                gym_menu()
        except Exception as error:
            print(f'\nОшибка Gym: {error}')
            gym_menu()


def get_lvl_up_info(skill_name, level):
    return f'🏃: {Fore.LIGHTCYAN_EX}{apply_move_optimization_gym(skill_training_table[level]["steps"]):,.0f}{Style.RESET_ALL} / ' \
           f'🔋: {Fore.GREEN}{skill_training_table[level]["energy"]}{Style.RESET_ALL} эн. / ' \
           f'💰: {Fore.LIGHTYELLOW_EX}{skill_training_table[level]["money"]}{Style.RESET_ALL} $ / ' \
           f'🕑: {time(round(skill_training_table[level]["time"] - ((skill_training_table[level]["time"] / 100) * (char_characteristic["speed_skill"] + equipment_speed_skill_bonus() + char_characteristic["lvl_up_skill_speed"]))))}'


def display_skill_description(skill_name):
    # Вывод описания выбранного навыка
    if skill_name == 'stamina':
        print(description_stamina)
    elif skill_name == 'energy_max':
        print(description_energy_max)
    elif skill_name == 'speed_skill':
        print(description_speed)
    elif skill_name == 'luck_skill':
        print(description_luck)
    elif skill_name == 'move_optimization_adventure':
        print(description_move_optimization_adventure)
    elif skill_name == 'move_optimization_gym':
        print(description_move_optimization_gym)
    elif skill_name == 'move_optimization_work':
        print(description_move_optimization_work)
    elif skill_name == 'neatness_in_using_things':
        print(description_neatness_in_using_things)


def start_training():
    char_characteristic['skill_training'] = True
    char_characteristic['skill_training_timestamp'] = datetime.now().timestamp()
    skill_name = char_characteristic['skill_training_name']
    level = char_characteristic[skill_name] + 1
    skill_training_time = round(skill_training_table[level]['time']) * 60
    skill_training_speed_skill = skill_training_time - ((skill_training_time / 100) * (char_characteristic[skill_name] + equipment_speed_skill_bonus() + char_characteristic["lvl_up_skill_speed"]))
    skill_training_time_with_bonus = datetime.fromtimestamp(datetime.now().timestamp() + skill_training_speed_skill)
    char_characteristic['skill_training_time_end'] = skill_training_time_with_bonus
    char_characteristic['steps_today_used'] += apply_move_optimization_gym(skill_training_table[level]['steps'])
    char_characteristic['steps_total_used'] += apply_move_optimization_gym(skill_training_table[level]['steps'])
    char_characteristic['energy'] -= skill_training_table[level]['energy']
    char_characteristic['money'] -= skill_training_table[level]['money']

    print(f'\n🏋️ {skill_name.title()} - Начато улучшение навыка. 🏋')
    print(f'На улучшение навыка {skill_name} потрачено:'
          f'\n- 🏃: {apply_move_optimization_gym(skill_training_table[level]["steps"]):,.0f} steps'
          f'\n- 🔋: {skill_training_table[level]["energy"]} эн.'
          f'\n- 💰: {skill_training_table[level]["money"]} $'
          f'\n- 🕑 Окончание тренировки навыка через: {Fore.LIGHTBLUE_EX}{time(round(skill_training_table[level]["time"] - ((skill_training_table[level]["time"] / 100) * (char_characteristic["speed_skill"] + equipment_speed_skill_bonus() + char_characteristic["lvl_up_skill_speed"]))))}{Style.RESET_ALL}')


def skill_training_check_done():
    # Проверка или закончилось изучение навыка
    global char_characteristic
    if debug_mode:
        if not char_characteristic['skill_training']:
            print('\nНавыки не изучаются.')

    if char_characteristic['skill_training']:
        if datetime.fromtimestamp(datetime.now().timestamp()) >= char_characteristic['skill_training_time_end']:
            skill_name = char_characteristic['skill_training_name']
            char_characteristic[skill_name] += 1
            print(f'\n🏋 Навык {skill_name.title()} улучшен до {char_characteristic[skill_name]}')
            char_characteristic['skill_training'] = False
            char_characteristic['skill_training_name'] = None
            char_characteristic['skill_training_timestamp'] = None
            char_characteristic['skill_training_time_end'] = None
            stamina_skill_bonus_def()
            save_characteristic()


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
        # Проверка или достаточно кол-ва шагов, энергии, и денег для запуска прокачки навыка
        if char_characteristic['steps_can_use'] >= apply_move_optimization_gym(skill_training_table[char_characteristic[self.name] + 1]["steps"]) \
            and char_characteristic['energy'] >= skill_training_table[char_characteristic[self.name] + 1]["energy"]\
            and char_characteristic['money'] >= skill_training_table[char_characteristic[self.name] + 1]["money"]:
            print('\nПроверка кол-ва шагов, энергии и денег - успешна.')

            ### Проверить или здесь все нормально работает. И все ли хорошо с переменными.
#            Skill_Training.start_skill_training(self)       # Начало прокачки навыка, если выполнены требования.

            return True

        else:
            print(f'\n{Fore.RED}У вас не достаточно ресурсов: {Style.RESET_ALL}')
            if char_characteristic['steps_can_use'] <= apply_move_optimization_gym(skill_training_table[char_characteristic[self.name] + 1]["steps"]):
                print(f'\t- 🏃: Не хватает - {skill_training_table[char_characteristic[self.name] + 1]["steps"] - char_characteristic["steps_can_use"]} шагов.')
            if char_characteristic['energy'] <= skill_training_table[char_characteristic[self.name] + 1]["energy"]:
                print(f'\t- 🔋: Не хватает - {skill_training_table[char_characteristic[self.name] + 1]["energy"] - char_characteristic["energy"]} энергии.')
            if char_characteristic['money'] <= skill_training_table[char_characteristic[self.name] + 1]["money"]:
                print(f'\t- 💰: Не хватает - {skill_training_table[char_characteristic[self.name] + 1]["money"] - char_characteristic["money"]} money.')
            gym_menu()
            return False

    def start_skill_training(self):
        # Начало обучения навыка
        skill_training_time = round(skill_training_table[char_characteristic[self.name] + 1]['time']) * 60
        skill_training_speed_skill = skill_training_time - ((skill_training_time / 100) * (char_characteristic[self.name] + equipment_speed_skill_bonus() + char_characteristic["lvl_up_skill_speed"]))
        skill_training_time_with_bonus = datetime.fromtimestamp(datetime.now().timestamp() + skill_training_speed_skill)

        char_characteristic['skill_training'] = True
        char_characteristic['skill_training_name'] = self.name
        char_characteristic['skill_training_timestamp'] = datetime.now().timestamp()
        char_characteristic['skill_training_time_end'] = skill_training_time_with_bonus
        char_characteristic['steps_today_used'] += apply_move_optimization_gym(skill_training_table[char_characteristic[self.name] + 1]['steps'])
        char_characteristic['steps_total_used'] += apply_move_optimization_gym(skill_training_table[char_characteristic[self.name] + 1]['steps'])
        char_characteristic['energy'] -= skill_training_table[char_characteristic[self.name] + 1]['energy']
        char_characteristic['money'] -= skill_training_table[char_characteristic[self.name] + 1]['money']

        print(f'\n🏋️ {self.name.title()} - Начато улучшение навыка. 🏋')
        print(f'На улучшение навыка {self.name} потрачено:'
              f'\n- 🏃: {apply_move_optimization_gym(skill_training_table[char_characteristic[self.name] + 1]["steps"]):,.0f} steps'
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

    def move_optimization_adventure_skill_training(self):
        print(f'\nОптимизация движений Adventure: {Fore.GREEN}{char_characteristic["move_optimization_adventure"]}{Style.RESET_ALL} уровень.'
              f'\nОптимизация движений Adventure - Каждый уровень уменьшает на 1 % количество шагов необходимых для активности.'
              f'\nДля улучшения необходимо: ({lvl_up_move_optimization_adventure})')

    def move_optimization_gym_skill_training(self):
        print(f"\nОптимизация движений Gym: {Fore.GREEN}{char_characteristic['move_optimization_gym']}{Style.RESET_ALL} уровень."
              f"\nОптимизация движений Gym - Каждый уровень уменьшает на 1 % количество шагов необходимых для активности."
              f"\nДля улучшения необходимо: ({lvl_up_move_optimization_gym})")

    def move_optimization_work_skill_training(self):
        print(f"\nОптимизация движений Work: {Fore.GREEN}{char_characteristic['move_optimization_work']}{Style.RESET_ALL} уровень."
            f"\nОптимизация движений Work - Каждый уровень уменьшает на 1 % количество шагов необходимых для активности."
            f"\nДля улучшения необходимо: ({lvl_up_move_optimization_work})")


Skill = Skill_Training(char_characteristic['skill_training'], char_characteristic['skill_training_name'],
                       char_characteristic['skill_training_timestamp'], char_characteristic['skill_training_time_end'],
                       datetime.now().timestamp())
