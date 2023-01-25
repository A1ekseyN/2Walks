from characteristics import char_characteristic, save_characteristic
from datetime import datetime, timedelta
from settings import debug_mode
from colorama import Fore, Style
from functions_02 import time


work_requirements = {
    'watchman': {'steps': 200, 'energy': 4, 'salary': 2},
    'factory': {'steps': 500, 'energy': 7, 'salary': 5},
    'courier_foot': {'steps': 1000, 'energy': 10, 'salary': 10},
}


class Work():
    # Класс инициализации работы

    def __init__(self, work, salary, working, working_hours, working_end, steps_can_use):
        self.work = work
        self.work_salary = salary
        self.working = working
        self.working_hours = working_hours
        self.working_end = working_end
        self.steps_can_use = steps_can_use

    def work_choise(self):
        print('\n--- 🏭 Work Location 🏭 ---')
        print(f'В этой локации можно устроится на работу. '
              f'\nОплата почасовая 🕑: 1 час = {time(round(60 - ((60 / 100) * char_characteristic["speed_skill"])))}')
        print('\nНа данный момент доступны вакансии:'
              f'\n\t1. Сторож - 💰: {Fore.LIGHTYELLOW_EX}2{Style.RESET_ALL} $ (🏃: 200 + 🔋: 4).'
              f'\n\t2. Завод  - 💰: {Fore.LIGHTYELLOW_EX}5{Style.RESET_ALL} $ (🏃: 500 + 🔋: 7).'
              f'\n\t3. Курьер - 💰: {Fore.LIGHTYELLOW_EX}10{Style.RESET_ALL} $ (🏃: 1000 + 🔋: 10).'
              '\n\t0. Вернуться назад.')
        try:
            working = input('\nВыберите вакансию, или вернитесь обратно:\n>>> ')
            if working == '1':
                work = 'watchman'
                Work.work_watchman(self)
                Work.ask_hours(self, work)
            elif working == '2':
                # Вакансия - Завод
                work = 'factory'
                Work.ask_hours(self, work)
            elif working == '3':
                # Вакансия - Курьер
                work = 'courier_foot'
                Work.ask_hours(self, work)
            elif working == '0':
                # Выход в меню.
                pass
            else:
                print('\nВы ввели не правильные данные. Попробуйте еще раз.')
                Work.work_choise(self)
        except:
            print('\nВы ввели не правильные данные. Попробуйте еще раз.')
            Work.work_choise(self)
        return working

    def ask_hours(self, work):
        # Сколько рабочих часов
        try:
            print(f'\nВы выбрали вакансию: {Fore.GREEN}{work.title()}{Style.RESET_ALL} c зарплатой: {Fore.LIGHTYELLOW_EX}{work_requirements[work]["salary"]}{Style.RESET_ALL} $ в час.')
            print(f'Оплата почасовая 🕑: 1 час = {time(round(60 - ((60 / 100) * char_characteristic["speed_skill"])))}')
            working_hours = abs(int(input('\nВведите количество рабочих часов: 1 - 8.\n0. Выход.\n>>> ')))
            if working_hours >= 1 and working_hours <= 8:
                Work.check_requirements(self, work, working_hours)
            elif working_hours == 0:
                Work.work_choise(self)
            else:
                print('\nНужно ввести число рабочих часов в диапазоне 1 - 8.')
                Work.ask_hours(self, work)
        except:
            print('\nВы ввели не правильные данные. Попробуйте еще раз.')
            Work.ask_hours(self, work)

    def check_requirements(self, work, working_hours):
        # Проверка требований для устройства на работу.
        if working_hours >= 1:
            if char_characteristic['steps_can_use'] >= working_hours * work_requirements[work]["steps"] and char_characteristic['energy'] >= working_hours * work_requirements[work]["energy"]:
                char_characteristic['steps_today_used'] = char_characteristic['steps_today_used'] + (working_hours * work_requirements[work]["steps"])
                char_characteristic['energy'] = char_characteristic['energy'] - (working_hours * work_requirements[work]["energy"])
                char_characteristic['work'] = work
                char_characteristic['working'] = True
                char_characteristic['working_start'] = datetime.now().timestamp()
                char_characteristic['working_end'] = datetime.fromtimestamp(datetime.now().timestamp()) + (timedelta(minutes=working_hours * 60) - ((timedelta(minutes=working_hours * 60) / 100) * char_characteristic['speed_skill']))
                char_characteristic['work_salary'] = work_requirements[work]['salary']
                char_characteristic['working_hours'] = working_hours

                print(f'\nИспользовано 🏃: {Fore.LIGHTCYAN_EX}{working_hours * work_requirements[work]["steps"]}{Style.RESET_ALL} + '
                      f'🔋: {Fore.GREEN}{working_hours * work_requirements[work]["energy"]}{Style.RESET_ALL}.')
                print(f'Время работы 🕑: {time(working_hours * (round(60 - ((60 / 100) * char_characteristic["speed_skill"]))))}')
                print(f'Зарплата 💰: {Fore.LIGHTYELLOW_EX}{working_hours * char_characteristic["work_salary"]}{Style.RESET_ALL} $.')
            else:
                print('Дописать функционал, который показывает, чего именно не хватило. Можно использовать метод класса.')
                print('Не достаточно: 🏃 или 🔋')

    def work_watchman(self):
        # Работа сторожем
        pass

    def work_factory(self):
        # Работа на заводе
        pass

    def work_courier_foot(self):
        # Работа пешим курьером
        pass


def work_check_done():
    # Функция, которая проверяет отончание таймера работы.
    global char_characteristic

    if char_characteristic['working_end'] != None:
        if debug_mode:
            if char_characteristic['working_end'] >= datetime.fromtimestamp(datetime.now().timestamp()):
                print('\n--- Персонаж на работе ---.')

        if char_characteristic['working_end'] <= datetime.fromtimestamp(datetime.now().timestamp()):
            # Когда прошел кулдаун на работу. Дабавляются деньги и обнуляются таймеры и статусы связанные с работой.
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


"""
def work_choice():
    # Глобальная функция для выбора работы.
    start_work_status()
    print(f'\nВ этой локации можно устроится на работу. '
          f'\nОплата почасовая 🕑: 1 час = {time(round(60 - ((60 / 100) * char_characteristic["speed_skill"])))}')
    print('На данный момент доступны вакансии:'
          f'\n\t1. Сторож - 💰: {Fore.LIGHTYELLOW_EX}2{Style.RESET_ALL} $ (🏃: 200 + 🔋: 4).'
          f'\n\t2. Завод  - 💰: {Fore.LIGHTYELLOW_EX}5{Style.RESET_ALL} $ (🏃: 500 + 🔋: 7).'
          f'\n\t3. Курьер - 💰: {Fore.LIGHTYELLOW_EX}10{Style.RESET_ALL} $ (🏃: 1000 + 🔋: 10).'
          '\n\t0. Вернуться назад.')
    try:
        temp_number_work = input('\nВыберите вакансию, или вернитесь обратно:\n>>> ')
    except:
        print('\nВы ввели не правильные данные. Попробуйте еще раз.')
        work_choice()

    if temp_number_work == '1':         # Сторож
        work_watchman()
    elif temp_number_work == '2':       # Завод
        work_factory()
    elif temp_number_work == '3':       # Курьер
        work_courier_foot()
    elif temp_number_work == '0':       # Вернуться назад
        # Тут нужно вставить функцию, которая отвечает за возврат в меню. Хз, или нужно.
        pass




def start_work_status():
    # Старт работы. Функция, которая отображает текущюю работу и ее статус.
    if char_characteristic['working'] and debug_mode:
        print('\n🏭 --- Тут описание текущей работы и ее статуса ---')
        print(f'Работа: {char_characteristic["work"].title()}.')
        print(f'Начало: {char_characteristic["working_start"]}.')
        print(f'Окончание: {char_characteristic["working_end"]}.')
        print(f'Рабочие часы: {char_characteristic["working_hours"]}.')


def work_watchman():
    # Работа - Сторож
    print('\n--- Сторож ---\nЗарплата в час: 2$. '
          '\nДля 1 часа работы требуется: (🏃: 200 + 🔋: 4).')
    if char_characteristic['working_hours'] == 0:
        try:
            char_characteristic['working_hours'] = abs(int(input('\nВведите количество рабочих часов: 1 - 8.'
                                  '\n0. Выход.\n>>> ')))
        except:
            print('\nВы ввели не правильные данные. Попробуйте еще раз.')
            work_watchman()

        if char_characteristic['working_hours'] >= 1:
            if char_characteristic['steps_can_use'] >= char_characteristic['working_hours'] * 200 and char_characteristic['energy'] >= char_characteristic['working_hours'] * 4:
                char_characteristic['steps_today_used'] = char_characteristic['steps_today_used'] + (char_characteristic['working_hours'] * 200)
                char_characteristic['energy'] = char_characteristic['energy'] - (char_characteristic['working_hours'] * 4)
                char_characteristic['work'] = 'watchman'
                char_characteristic['working'] = True
                char_characteristic['working_start'] = datetime.now().timestamp()
                # char_characteristic['working_end'] = datetime.fromtimestamp(datetime.now().timestamp()) + timedelta(hours=char_characteristic['working_hours'])
                char_characteristic['working_end'] = datetime.fromtimestamp(datetime.now().timestamp()) + (timedelta(minutes=char_characteristic['working_hours'] * 60) - ((timedelta(minutes=char_characteristic['working_hours'] * 60) / 100) * char_characteristic['speed_skill']))
                char_characteristic['work_salary'] = 2
                print(f'\nИспользовано: 🏃: {char_characteristic["working_hours"] * 200}; 🔋: {char_characteristic["working_hours"] * 4}.')
                print(f'Время работы: {char_characteristic["working_hours"]} часа.')
                print(f'Время окончания: {char_characteristic["working_end"]}.')

                start_work_status()
                return char_characteristic
            else:
                print('\nУ нас не достаточно 🏃 или 🔋.')
        elif char_characteristic['working_hours'] == 0:
            # Выход в меню.
            pass
#        else:
#            work_watchman()
    else:
        print(f'\nВ данный моменты, вы уже работаете: {char_characteristic["work"]}.')
        print(f'Конец смены через: {char_characteristic["working_end"] - datetime.fromtimestamp(datetime.now().timestamp())}.')
        print('Можно добавить часы работы. (Функционал появится немного позже).')


def work_factory():
    # Работа - Завод
    print('\n--- Завод ---\nЗарплата в час: 5 $. '
          '\nДля 1 часа работы требуется: (🏃: 500 + 🔋: 7).')
    try:
        char_characteristic['working_hours'] = abs(int(input('\nВведите количество рабочих часов: 1 - 8.'
                              '\n0. Выход.\n>>> ')))
    except:
        print('\nВы ввели не правильные данные. Попробуйте еще раз.')
        work_factory()

    if char_characteristic['working_hours'] >= 1:
        if char_characteristic['steps_can_use'] >= char_characteristic['working_hours'] * 500 and char_characteristic['energy'] >= char_characteristic['working_hours'] * 7:
            char_characteristic['steps_today_used'] = char_characteristic['steps_today_used'] + (char_characteristic['working_hours'] * 500)
            char_characteristic['energy'] = char_characteristic['energy'] - (char_characteristic['working_hours'] * 7)
            char_characteristic['work'] = 'factory'
            char_characteristic['working'] = True
            char_characteristic['working_start'] = datetime.now().timestamp()
#            char_characteristic['working_end'] = datetime.fromtimestamp(datetime.now().timestamp()) + timedelta(hours=char_characteristic['working_hours'])
            char_characteristic['working_end'] = datetime.fromtimestamp(datetime.now().timestamp()) + (timedelta(minutes=char_characteristic['working_hours'] * 60) - ((timedelta(minutes=char_characteristic['working_hours'] * 60) / 100) * char_characteristic['speed_skill']))
            char_characteristic['work_salary'] = 5
            print(f'\nИспользовано: 🏃: {char_characteristic["working_hours"] * 500}; 🔋: {char_characteristic["working_hours"] * 7}.')
            print(f'Время работы: {char_characteristic["working_hours"]} часа.')
            print(f'Время окончания: {char_characteristic["working_end"]}.')

            start_work_status()
            return char_characteristic
        else:
            print('\nУ нас не достаточно 🏃 или 🔋.')
    elif char_characteristic['working_hours'] == 0:
        pass
    else:
        work_factory()


def work_courier_foot():
    # Работа - Курьер (пешком)
    print('\n--- Курьер ---\nЗарплата в час: 10 $. '
          '\nДля 1 часа работы требуется: (🏃: 1000 + 🔋: 10).')
    try:
        char_characteristic['working_hours'] = abs(int(input('\nВведите количество рабочих часов: 1 - 8.'
                              '\n0. Выход.\n>>> ')))
    except:
        print('\nВы ввели не правильные данные. Попробуйте еще раз.')
        work_courier_foot()

    if char_characteristic['working_hours'] >= 1:
        if char_characteristic['steps_can_use'] >= char_characteristic['working_hours'] * 1000 and char_characteristic['energy'] >= char_characteristic['working_hours'] * 10:
            char_characteristic['steps_today_used'] = char_characteristic['steps_today_used'] + (char_characteristic['working_hours'] * 1000)
            char_characteristic['energy'] = char_characteristic['energy'] - (char_characteristic['working_hours'] * 10)
            char_characteristic['work'] = 'courier_foot'
            char_characteristic['working'] = True
            char_characteristic['working_start'] = datetime.now().timestamp()
#            char_characteristic['working_end'] = datetime.fromtimestamp(datetime.now().timestamp()) + timedelta(hours=char_characteristic['working_hours'])
            char_characteristic['working_end'] = datetime.fromtimestamp(datetime.now().timestamp()) + (timedelta(minutes=char_characteristic['working_hours'] * 60) - ((timedelta(minutes=char_characteristic['working_hours'] * 60) / 100) * char_characteristic['speed_skill']))
            char_characteristic['work_salary'] = 10
            print(f'\nИспользовано: 🏃: {char_characteristic["working_hours"] * 1000}; 🔋: {char_characteristic["working_hours"] * 10}.')
            print(f'Время работы: {char_characteristic["working_hours"]} часа.')
            print(f'Время окончания: {char_characteristic["working_end"]}.')

            start_work_status()
            return char_characteristic
        else:
            print('\nУ нас не достаточно 🏃 или 🔋.')
    elif char_characteristic['working_hours'] == 0:
        pass
    else:
        work_courier_foot()
"""