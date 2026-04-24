from characteristics import char_characteristic, save_characteristic
from datetime import datetime, timedelta
from settings import debug_mode
from colorama import Fore, Style
from functions_02 import time
from equipment_bonus import equipment_speed_skill_bonus
from bonus import apply_move_optimization_work
from inventory import Wear_Equipped_Items


class Work():
    """Класс для работы"""

    def __init__(self, char_characteristic):
        self.work_requirements = {
            'watchman': {'steps': apply_move_optimization_work(200), 'energy': 4, 'salary': 2},
            'factory': {'steps': apply_move_optimization_work(500), 'energy': 7, 'salary': 5},
            'courier_foot': {'steps': apply_move_optimization_work(1000), 'energy': 10, 'salary': 10},
            'forwarder': {'steps': apply_move_optimization_work(5000), 'energy': 30, 'salary': 50},
        }

    def work_choice(self):
        # Выбор места работы для персонажа.
        if not char_characteristic['working']:
            print('\n--- 🏭 Work Location 🏭 ---')
            print(f'\nSteps 🏃: {char_characteristic["steps_can_use"]}; Energy 🔋: {char_characteristic["energy"]}')
            print(f'В этой локации можно устроится на работу. '
                  f'\nОплата почасовая 🕑: '
                  f'1 час = {time(round(60 - ((60 / 100) * char_characteristic["speed_skill"] + equipment_speed_skill_bonus() + char_characteristic["lvl_up_skill_speed"])))}')
            print('\nНа данный момент доступны вакансии:'
                  f'\n\t1. Сторож     - 💰: {Fore.LIGHTYELLOW_EX}2{Style.RESET_ALL} $ (🏃: {self.work_requirements["watchman"]["steps"]} + 🔋: 4)'
                  f'\n\t2. Завод      - 💰: {Fore.LIGHTYELLOW_EX}5{Style.RESET_ALL} $ (🏃: {self.work_requirements["factory"]["steps"]} + 🔋: 7)'
                  f'\n\t3. Курьер     - 💰: {Fore.LIGHTYELLOW_EX}10{Style.RESET_ALL} $ (🏃: {self.work_requirements["courier_foot"]["steps"]} + 🔋: 10)'
                  f'\n\t4. Экспедитор - 💰: {Fore.LIGHTYELLOW_EX}50{Style.RESET_ALL} $ (🏃: {self.work_requirements["forwarder"]["steps"]} + 🔋: 50)'
                  '\n\t0. Вернуться назад.')
            working = input('\nВыберите вакансию, или вернитесь обратно:\n>>> ')
            if working == '1':
                # Вакансия - Сторож
                self.ask_hours('watchman')
            elif working == '2':
                # Вакансия - Завод
                self.ask_hours('factory')
            elif working == '3':
                # Вакансия - Курьер
                self.ask_hours('courier_foot')
            elif working == '4':
                # Вакансия - Экспедитор
                self.ask_hours('forwarder')
            elif working == '0':
                # Выход в меню.
                pass
            else:
                print('\nВы ввели не правильные данные. Попробуйте еще раз.')
                self.work_choice()
            return working
        elif char_characteristic['working']:
            # Если персонаж уже на работе, можно добавить рабочие часы.
            self.add_working_hours(char_characteristic['work'])

    def ask_hours(self, work):
        # Сколько рабочих часов
        try:
#            print(f'char: {char_characteristic}')
            print(f'\nSteps 🏃: {char_characteristic["steps_can_use"]}; Energy 🔋: {char_characteristic["energy"]}')
            print(f'Вы выбрали вакансию: {Fore.GREEN}{work.title()}{Style.RESET_ALL} c зарплатой: {Fore.LIGHTYELLOW_EX}{self.work_requirements[work]["salary"]}{Style.RESET_ALL} $ в час.')

            # Оплата почасовая 🕑
            work_time_per_hour = round(60 - (
                    (60 / 100) * char_characteristic["speed_skill"] + equipment_speed_skill_bonus() +
                    char_characteristic["lvl_up_skill_speed"]))
            print(f'Оплата почасовая 🕑: 1 час = {time(work_time_per_hour)}')

            # Расчёт максимального доступного количества рабочих часов
            max_hours_by_steps = char_characteristic["steps_can_use"] // self.work_requirements[work]["steps"]
            max_hours_by_energy = char_characteristic["energy"] // self.work_requirements[work]["energy"]
            max_available_hours = min(max_hours_by_steps, max_hours_by_energy, 8)  # Ограничиваем максимум 8 часами

            print(f'Max work hours: {Fore.LIGHTBLUE_EX}{max_available_hours}{Style.RESET_ALL} '
                  f'({Fore.LIGHTCYAN_EX}{max_available_hours * self.work_requirements[work]["steps"]}{Style.RESET_ALL} шагов, '
                  f'{Fore.LIGHTGREEN_EX}{max_available_hours * self.work_requirements[work]["energy"]}{Style.RESET_ALL} энергии, '
                  f'{Fore.LIGHTYELLOW_EX}{max_available_hours * self.work_requirements[work]["salary"]}{Style.RESET_ALL} $ заработка).')

            working_hours = abs(int(input('\nВведите количество рабочих часов: 1 - 8.\n0. Выход.\n>>> ')))
            if working_hours >= 1 and working_hours <= max_available_hours:
                self.check_requirements(work, working_hours)

                # Износ Экипировки
                steps = working_hours * self.work_requirements[work]["steps"]
                equipped_items_manager = Wear_Equipped_Items()
                equipped_items_manager.decrease_durability(steps)

            elif working_hours == 0:
                self.work_choice()
            else:
                print(f'\nНужно ввести число рабочих часов в диапазоне 1 - {max_available_hours}.')
                self.ask_hours(work)
        except ValueError:
            print('\nВы ввели неправильные данные. Попробуйте ещё раз.')
            self.ask_hours(work)

    def add_working_hours(self, work):
        # Если персонаж находится на работе, то можно добавить несколько рабочих часов. От 1 до 8 часов.
        print(f'\nПерсонаж на работе. Вы можете добавить несколько рабочих часов.'
              f'\nМесто работы: {Fore.GREEN}{char_characteristic["work"].title()}{Style.RESET_ALL}, в час - {Fore.LIGHTYELLOW_EX}{char_characteristic["work_salary"]}{Style.RESET_ALL} $ (💰: + {Fore.LIGHTYELLOW_EX}{char_characteristic["work_salary"] * char_characteristic["working_hours"]}{Style.RESET_ALL} $).'
              '\n1. Добавить рабочие часы.'
              '\n0. Назад')
        ask = input('\nДобавить рабочие часы или вернуться обратно? \n>>> ')
        if ask == '1':
            self.ask_hours(work)
        elif ask == '0':
            pass
        else:
            self.work_choice()

    def check_requirements(self, work, working_hours):
        # Проверка требований для устройства на работу.
        if working_hours >= 1:
            if (char_characteristic['steps_can_use'] >= working_hours * self.work_requirements[work]["steps"] and
                char_characteristic['energy'] >= working_hours * self.work_requirements[work]["energy"]):

                char_characteristic['steps_today_used'] += working_hours * self.work_requirements[work]["steps"]
                char_characteristic['steps_total_used'] += working_hours * self.work_requirements[work]["steps"]
                char_characteristic['energy'] -= working_hours * self.work_requirements[work]["energy"]
                char_characteristic['work'] = work
                char_characteristic['working'] = True

                # Обновление времени работы с учетом уже оставшегося времени.
                now = datetime.now()
                if char_characteristic.get('working_end'):
                    current_end = char_characteristic['working_end']
                    if isinstance(current_end, (int, float)):
                        current_end = datetime.fromtimestamp(current_end)
                    remaining_time = current_end - now
                    if remaining_time < timedelta(0):
                        remaining_time = timedelta(0)
                else:
                    remaining_time = timedelta(0)

                # Вычисляем дополнительное время для новых рабочих часов
                raw_duration = timedelta(minutes=working_hours * 60)
                bonus_percent = char_characteristic['speed_skill'] + equipment_speed_skill_bonus() + \
                                char_characteristic["lvl_up_skill_speed"]
                adjusted_duration = raw_duration - (raw_duration * bonus_percent / 100)

                new_working_end = now + remaining_time + adjusted_duration
                char_characteristic['working_end'] = new_working_end

                char_characteristic['work_salary'] = self.work_requirements[work]['salary']
                char_characteristic['working_hours'] += working_hours

                print(f'\nИспользовано 🏃: {Fore.LIGHTCYAN_EX}{working_hours * self.work_requirements[work]["steps"]}{Style.RESET_ALL} + '
                    f'🔋: {Fore.GREEN}{working_hours * self.work_requirements[work]["energy"]}{Style.RESET_ALL}.')
                print(f'Время работы 🕑: {time(working_hours * (round(60 - ((60 / 100) * char_characteristic["speed_skill"] + equipment_speed_skill_bonus()))))}')
                print(f'Зарплата 💰: {Fore.LIGHTYELLOW_EX}{working_hours * char_characteristic["work_salary"]}{Style.RESET_ALL} $.')
                return True
            else:
                print('\nДописать функционал, который показывает, чего именно не хватило. Можно использовать метод класса.')
                print('Не достаточно: 🏃 или 🔋')
                return False


def work_check_done():
    # Функция, которая проверяет окончание таймера работы.
    global char_characteristic

    if char_characteristic['working_end'] != None:
        if debug_mode:
            if char_characteristic['working_end'] >= datetime.fromtimestamp(datetime.now().timestamp()):
                print('\n--- Персонаж на работе ---.')

        if char_characteristic['working_end'] <= datetime.fromtimestamp(datetime.now().timestamp()):
            # Когда прошел кулдаун на работу. Добавить деньги, обнулить таймеры, и статусы связанные с работой.
            char_characteristic['money'] += char_characteristic["work_salary"] * char_characteristic["working_hours"]
            print(f'\n🏭 Вы закончили работу и заработали: {Fore.LIGHTYELLOW_EX}{char_characteristic["work_salary"] * char_characteristic["working_hours"]}{Style.RESET_ALL} $.')
            # Обнуление переменных и статусов связанных с работой. (Возможно стоит сделать отдельной функцией).
            char_characteristic['work'] = None
            char_characteristic['work_salary'] = 0
            char_characteristic['working'] = False
            char_characteristic['working_hours'] = 0
            char_characteristic['working_start'] = None
            char_characteristic['working_end'] = None
            save_characteristic()       # Сохранение прогресса при завершении работы
    return char_characteristic
