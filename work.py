from characteristics import char_characteristic, save_characteristic
from datetime import datetime, timedelta
from settings import debug_mode
from colorama import Fore, Style
from functions_02 import time


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
            print(f'\n🏭 Вы закончили работу и заработали: {char_characteristic["work_salary"] * char_characteristic["working_hours"]} $.')
            # Обнуление переменных и статусов связанных с работой. (Возможно стоит сделать отдельной функцией).
            char_characteristic['work'] = None
            char_characteristic['work_salary'] = 0
            char_characteristic['working'] = False
            char_characteristic['working_hours'] = 0
            char_characteristic['working_start'] = None
            char_characteristic['working_end'] = None
            save_characteristic()       # Сохранение прогресса при завершении работы
    return char_characteristic


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
            char_characteristic['work'] = 'factory'
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
