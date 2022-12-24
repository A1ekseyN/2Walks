from characteristics import char_characteristic
from datetime import datetime, timedelta
from settings import debug_mode


vacancy = []        # Переменная для вакансий на будущее.
working_hours = 0   # Нужно проверить или эта функция нужна
time_stamp_now = datetime.now().timestamp()


def work_choice():
    # Глобальная функция для работы.
    # work и job - одно и тоже.
    print('\nВы находитесь в локации 🏭 Work.\nЗдесь можно устроится на работу. Оплата почасовая.')
    print('На данный момент доступны вакансии:'
          '\n\t1. Сторож - (1 час - 2 $ (🏃: 200 + 🔋: 4)).'
          '\n\t2. Завод - (1 час - 4 $ (🏃: 500 + 🔋: 10)).'
          '\n\t3. Курьер - (1 час - 10 $ (🏃: 1000 + 🔋: 10)).'
          '\n\t0. Вернуться назад.'
          )
    try:
        temp_number_work = input('\nВыберите вакансию, или вернитесь обратно:\n>>> ')
    except:
        print('\nВы ввели не правильные данные. Попробуйте еще раз.')
        work_choice()

    if temp_number_work == '1':
        # Сторож
        work_watchman()
    elif temp_number_work == '2':
        print('\nЗавод')
        work_factory()
    elif temp_number_work == '3':
        print('\nКурьер')
        work_courier_foot()
    elif temp_number_work == '0':
        # Тут нужно вставить функцию, которая отвечает за меню. Хз, или нужно.
        pass


def working_timer():
    # Функция для выбора кол-ва рабочих часов.
    pass


def work_status():
    # Функция, которая отображает текущюю работу и ее статус.
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
    return char_characteristic


def start_work_status():
    # Старт работы. Функция, которая отображает текущюю работу и ее статус.
    print('\nТут описание текущей работы и ее статуса.')
    print(f'Работа: {char_characteristic["work"]}.')
    print(f'Начало: {char_characteristic["working_start"]}.')
    print(f'Окончание: {char_characteristic["working_end"]}.')
    print(f'Рабочие часы: {char_characteristic["working_hours"]}.')


def work_watchman():
    # Работа - Сторож
    global working_hours

    print('\n--- Сторож ---\nЗарплата в час: 2$. '
          '\nДля 1 часа работы требуется: (🏃: 200 + 🔋: 4).')
    try:
        char_characteristic['working_hours'] = int(input('\nВведите количество рабочих часов: 1 - 8.'
                              '\n0. Выход.'
                              '\n>>> '))
        if char_characteristic['working_hours']:
            char_characteristic['steps_today_used'] = char_characteristic['steps_today_used'] + (char_characteristic['working_hours'] * 200)
            char_characteristic['energy'] = char_characteristic['energy'] - (char_characteristic['working_hours'] * 4)
            char_characteristic['work'] = 'watchman'
            char_characteristic['working'] = True
            char_characteristic['working_start'] = datetime.now().timestamp()
            char_characteristic['working_end'] = datetime.fromtimestamp(datetime.now().timestamp()) + timedelta(hours=char_characteristic['working_hours'])
            char_characteristic['work_salary'] = 2
            print(f'Использовано: 🏃: {char_characteristic["working_hours"] * 200}; 🔋: {char_characteristic["working_hours"] * 4}.')
            print(f'\nВремя работы: {char_characteristic["working_hours"]} часа.')
            print(f'Время начала: {datetime.fromtimestamp(datetime.now().timestamp())}.')
            print(f'Время окончания: {char_characteristic["working_end"]}.')

            start_work_status()
            return char_characteristic
    except:
        print('Except')
        print('\nВы ввели не правильные данные. Попробуйте еще раз.')
        work_watchman()


def work_factory():
    # Работа - Завод
    pass


def work_courier_foot():
    # Работа - Курьер (пешком)
    pass


#work_choice()
