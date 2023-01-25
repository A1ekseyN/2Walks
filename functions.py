from api import steps_today_update
from colorama import Fore, Style
from datetime import datetime
import requests
from adventure import Adventure
from characteristics import char_characteristic
from locations import icon_loc
from settings import debug_mode
from skill_bonus import stamina_skill_bonus_def, speed_skill_bonus_def


def energy_time_charge():
    # Функция для восстановления энергии со временем
    # Нужно перенести в файл functions.py
    global char_characteristic

    if char_characteristic['energy'] < char_characteristic['energy_max']:
        if timestamp_now() - char_characteristic['energy_time_stamp'] > 60:
            # Bug: Нужно добавить деление остатка и минусовать его от 'energy_time_stamp'
            # Bug: Поправить char_characteristic['energy'] += round (округление). Ошибка в округлении 1.6, округляет в большую сторону.
            char_characteristic['energy'] += round((timestamp_now() - char_characteristic['energy_time_stamp']) // 60)
            char_characteristic['energy_time_stamp'] = timestamp_now() - ((timestamp_now() - char_characteristic['energy_time_stamp']) % 60)
            if debug_mode:
                print('\n--- Energy Check!!! ---')
                print(f"Добавлено energy: {round((timestamp_now() - char_characteristic['energy_time_stamp']) // 60)}")
                print(f"Счётчик времени: {round(timestamp_now() - char_characteristic['energy_time_stamp'])} sec.")

    if char_characteristic['energy'] > char_characteristic['energy_max']:
        char_characteristic['energy'] = char_characteristic['energy_max']

    if (datetime.now().timestamp() - char_characteristic['energy_time_stamp']) >= 60:
        char_characteristic['energy_time_stamp'] = datetime.now().timestamp()


def status_bar():
    # Отображение переменных: шагов, энергии, денег.
    print(f'\nSteps 🏃: {Fore.LIGHTCYAN_EX}{steps():,.0f} / {char_characteristic["steps_today"] + stamina_skill_bonus_def():,.0f}{Style.RESET_ALL} (Stamina Bonus 🏃: + {Fore.LIGHTCYAN_EX}{stamina_skill_bonus_def()}{Style.RESET_ALL})'
          f'\nEnergy 🔋: {Fore.GREEN}{char_characteristic["energy"]} / {char_characteristic["energy_max"]}{Style.RESET_ALL} ', end='')
    if debug_mode:
        print(f'(+ 1 эн. через: {abs(60 - (timestamp_now() - char_characteristic["energy_time_stamp"])):,.0f} sec.)', end='')
    print(f'\nMoney 💰: {Fore.LIGHTYELLOW_EX}{char_characteristic["money"]:,.0f}{Style.RESET_ALL} $.')
    print(f'Вы находитесь в локации: {icon_loc()} {Fore.GREEN}{char_characteristic["loc"].title()}{Style.RESET_ALL}.')
    if char_characteristic['skill_training']:
        skill_end_time = char_characteristic["skill_training_time_end"] - datetime.fromtimestamp(datetime.now().timestamp())
        skill_end_time = str(skill_end_time).split('.')[0]
        print(f'\t🏋 Улучшаем навык - {char_characteristic["skill_training_name"].title()} до {Fore.LIGHTCYAN_EX}{char_characteristic[char_characteristic["skill_training_name"]] + 1}{Style.RESET_ALL} уровня.'
              f'\n\t🕑 Улучшение через: {Fore.LIGHTBLUE_EX}{skill_end_time}{Style.RESET_ALL}.')
    if char_characteristic['working']:
        work_end_time = char_characteristic["working_end"] - datetime.fromtimestamp(datetime.now().timestamp())
        work_end_time = str(work_end_time).split('.')[0]
        print(f'\t🏭 Место работы: {char_characteristic["work"].title()} (💰: + {Fore.LIGHTYELLOW_EX}{char_characteristic["work_salary"] * char_characteristic["working_hours"]}{Style.RESET_ALL} $).'
              f'\n\t🕑 Конец смены через: {Fore.LIGHTBLUE_EX}{work_end_time}{Style.RESET_ALL}.')
    if char_characteristic['adventure']:
        # Проверка или персонаж находится в Приключении.
        Adventure.adventure_check_done(self=None)


def load_game():
    # Функция для загрузки прогресса в игры при запуске программы.
    pass


def save_game():
    # Функция для сохранения игры.
    pass


def save_game_char_and_progress():
    # Функция для сохранения игровых характеристик и переменных
    pass


def save_game_date_last_enter():
    global char_characteristic
    # Функция для сохранения и проверки игровой даты.
    # Используется для обновления энергии и шагов на протяжении дня.
    # Если вход был выполнен не сегодня, то происходит обновление кол-ва шагов, через API.
    # Если последний вход был сегодня, то ничего не происходит.
    save_game_last_enter_date_file = open('save.txt', 'r')
    last_enter_date = save_game_last_enter_date_file.read()
    now_date = datetime.now().date()
    if str(now_date) != last_enter_date:
        print(f"\nПоследний вход в игру: {now_date}.")
        # Обновления даты последнего входа в игру.
        save_game_last_enter_date_file = open('save.txt', 'w')
        save_game_last_enter_date_file.write(f"{str(now_date)}")
        save_game_last_enter_date_file.close()

        # Обновление данных о кол-ве шагов за день.
        steps_today_update()

    elif str(now_date) == last_enter_date:
        # Текущая дата, и дата последнего входа в игру совпадает.
        char_characteristic['steps_can_use'] = char_characteristic['steps_today'] - char_characteristic['steps_today_used']
        char_characteristic['steps_can_use'] += stamina_skill_bonus_def()
    else:
        print('Error (save_game_date_last_enter).')


def steps_today_update_manual():
    # Функция для ручного обновления кол-ва шагов через NoCodeAPI
    global steps_today_api
    global steps_today
    global char_characteristic      # Нужно проверить или тут нужна эта переменная

    print('\nAPI запрос на обновление данных о кол-ве шагов.')

    try:
        url = "https://v1.nocodeapi.com/alexeyn/fit/kxgLPAuehlTGiEaC/aggregatesDatasets?dataTypeName=steps_count&timePeriod=today"
        params = {}
        r = requests.get(url=url, params=params)
        result_steps_today = r.json()
        steps_today = result_steps_today['steps_count'][0]['value']
        print('--- Запрос NoCodeApi успешный. ---\n')
        char_characteristic['steps_today'] = result_steps_today['steps_count'][0]['value']
        if debug_mode:
            print(f'Steps Update: {char_characteristic["steps_today"]}.')
        return char_characteristic['steps_today']
    except:
        print('\n--- Ошибка API соеднинения. Обновление данных о кол-ве шагов не произошло ---\n')
        # Скорее всего, Что переменная steps_today не нужна. И достаточно только оведомления о ошибке.
        steps_today = 404  # Если ошибка подключения к интернету, тогда указано число 404 для тестов.
        return steps_today


def char_info():
    # Функция отображения характеристик персонажа. Пока сюда буду добавлять все подряд, а дальше будет видно.
    print('\n####################################')
    print('### Характеристики персонажа ###')
    print('####################################')
    print(f'- Пройдено шагов за сегодня 🏃: {char_characteristic["steps_today"]:,.0f}')
    print(f'- Потрачено шагов за сегодня 🏃: {char_characteristic["steps_today_used"]:,.0f}')
    print(f'\n- Запас энергии 🔋: {char_characteristic["energy"]} эд.')
    print(f'- Макс. запас энергии 🔋: {char_characteristic["energy_max"]} эд.')
    print(f'\n- Выносливость: + {char_characteristic["stamina"]} % (+ {stamina_skill_bonus_def()} шагов).')
    print(f'- Максимальный запас энергии: + {char_characteristic["energy_max_skill"]} энергии.')
    print(f'- Скорость: + {char_characteristic["speed_skill"]} %.')
    print(f'- Удача: + {char_characteristic["luck_skill"]} %.')
    print('####################################')
    print('\nP.S. Сюда так же будут добавлены характеристики по мере их добавления в игру.')
    print('####################################')


# Нужно проверить или эта функция, вообще нужна
def steps():
    # Функция для определения кол-ва шагов, которые пройдено за сегодня.
    save_game_date_last_enter()
    return char_characteristic['steps_can_use']


def location_change_map():
    # Функция для перехода между локациями на глобальной карте.
    char_characteristic['energy'] -= 0              # 5 энергии на перемещение между локациями.
    char_characteristic['steps_today_used'] += 0    # 150 шагов, возможно.


def timestamp_now():
    # Возвращает TimeStamp в данный момент.
    timestamp_now = datetime.now().timestamp()
    return timestamp_now


def energy_timestamp():
    # Функция для возвращения времени последнего обновления энергии.
    global char_characteristic
    char_characteristic['energy_time_stamp'] = datetime.now().timestamp()
    print('Energy TimeStamp Update - Function')
    return char_characteristic['energy_time_stamp']
