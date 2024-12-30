import requests
import json
from colorama import Fore, Style
from datetime import datetime, timedelta

from api import steps_today_update, load_token_from_file
from adventure import Adventure
from bonus import equipment_bonus_stamina_steps, daily_steps_bonus, level_steps_bonus
from characteristics import char_characteristic
from locations import icon_loc
from settings import debug_mode
from skill_bonus import stamina_skill_bonus_def, speed_skill_equipment_and_level_bonus
from equipment_bonus import equipment_stamina_bonus, equipment_energy_max_bonus, equipment_speed_skill_bonus, equipment_luck_bonus
from level import CharLevel
from get_token_fitnes_api import get_access_token


def energy_time_charge():
    # Функция для восстановления энергии со временем
    # Нужно перенести в файл functions.py
    global char_characteristic

    if char_characteristic['energy'] < char_characteristic['energy_max']:
        if timestamp_now() - char_characteristic['energy_time_stamp'] > speed_skill_equipment_and_level_bonus(60):
            # (Тестируем): Нужно добавить Speed bonus + Speed Equipment bonus
            # Bug: Нужно добавить деление остатка и минусовать его от 'energy_time_stamp'
            # Bug: Поправить char_characteristic['energy'] += round (округление). Ошибка в округлении 1.6, округляет в большую сторону.
            char_characteristic['energy'] += round((timestamp_now() - char_characteristic['energy_time_stamp']) // speed_skill_equipment_and_level_bonus(60))
            char_characteristic['energy_time_stamp'] = timestamp_now() - ((timestamp_now() - char_characteristic['energy_time_stamp']) % speed_skill_equipment_and_level_bonus(60))
            if debug_mode:
                print('\n--- Energy Check!!! ---')
                print(f"Добавлено energy: {round((timestamp_now() - char_characteristic['energy_time_stamp']) // speed_skill_equipment_and_level_bonus(60))}")
                print(f"Счётчик времени: {round(timestamp_now() - char_characteristic['energy_time_stamp'])} sec.")

    if char_characteristic['energy'] > char_characteristic['energy_max']:
        char_characteristic['energy'] = char_characteristic['energy_max']

    if datetime.now().timestamp() - char_characteristic['energy_time_stamp'] >= speed_skill_equipment_and_level_bonus(60):
        char_characteristic['energy_time_stamp'] = datetime.now().timestamp()


def status_bar():
    # Отображение переменных: шагов, энергии, денег.
    char_level_view = CharLevel(char_characteristic)  # Инициализация уровня персонажа, прогресса, и lvl up

    print(f'\nSteps 🏃: {Fore.LIGHTCYAN_EX}{steps():,.0f} / {char_characteristic["steps_today"] + stamina_skill_bonus_def() + equipment_bonus_stamina_steps() + daily_steps_bonus() + level_steps_bonus():,.0f}{Style.RESET_ALL} '
          f'(Bonus: Stamina 🏃: + {Fore.LIGHTCYAN_EX}{stamina_skill_bonus_def():,.0f}{Style.RESET_ALL} '
          f'/ Equipment 🏃: + {Fore.LIGHTCYAN_EX}{equipment_bonus_stamina_steps():,.0f}{Style.RESET_ALL} '
          f'/ Daily 🏃: {Fore.LIGHTCYAN_EX}{daily_steps_bonus()}{Style.RESET_ALL} '
          f'/ Level: {Fore.LIGHTCYAN_EX}{level_steps_bonus()}{Style.RESET_ALL}) '
          f'(Total steps used 🏃: {Fore.LIGHTCYAN_EX}{char_characteristic["steps_total_used"]}{Style.RESET_ALL})'
          
          f'\nEnergy 🔋: {Fore.GREEN}{char_characteristic["energy"]} / {char_characteristic["energy_max"]}{Style.RESET_ALL} '
          f'(Bonus: Equipment 🔋: + {Fore.GREEN}{equipment_energy_max_bonus()}{Style.RESET_ALL} / '
          f'Daily 🔋: + {Fore.GREEN}{char_characteristic["steps_daily_bonus"]}{Style.RESET_ALL} / '
          f'Level: + {Fore.GREEN}{char_characteristic["lvl_up_skill_energy_max"]}{Style.RESET_ALL})', end='')
    if debug_mode:
        print(f'(+ 1 эн. через: {abs(speed_skill_equipment_and_level_bonus(60) - (timestamp_now() - char_characteristic["energy_time_stamp"])):,.0f} sec.)', end='')
    print(f'\nMoney 💰: {Fore.LIGHTYELLOW_EX}{char_characteristic["money"]:,.0f}{Style.RESET_ALL} $.')

    # Отображение Level персонажа, прогресс и lvl up
    char_level_view.level_status_bar()

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


def save_game_date_last_enter():
    global char_characteristic
    # Функция для сохранения и проверки игровой даты.
    # Используется для обновления энергии и шагов на протяжении дня.
    # Если вход был выполнен не сегодня, то происходит обновление кол-ва шагов, через API.
    # Если последний вход был сегодня, то ничего не происходит.

    # Текущая дата
    now_date = datetime.now().date()

    # Считываем дату последнего входа
    with open('save.txt', 'r') as save_file:
        last_enter_date = save_file.read()

    # Проверяем дату последнего входа через ключ 'date_last_enter'
    last_enter_date_char = char_characteristic.get('date_last_enter', None)
#    print(f"now_date: {now_date}, last_date_txt: {last_enter_date}, last_date_char_characteristic: {last_enter_date_char}")
#    print(f"char: {char_characteristic}")

    # Новый день
    if str(now_date) != str(last_enter_date_char):
#    if str(now_date) != last_enter_date:
        print(f"\nNew Day: {now_date}. Обновляем шаги и бонусы.")

        # Обновляем дату последнего входа
        with open('save.txt', 'w') as save_file:
            save_file.write(str(now_date))

        # Обновление числа шагов, пройденных за вчера.
        # Если более 10к, то дается бонус.
        today_steps_to_yesterday_steps()

        # Обновление данных о кол-ве шагов за день.
        steps_today_update()

        # Обновляем количество потраченных шагов за сегодня
        char_characteristic['steps_today_used'] = 0

        # Обновляем дату последнего входа в ключе 'date_last_enter'
        char_characteristic['date_last_enter'] = str(now_date)

    # Текущий день
    elif str(now_date) == str(last_enter_date_char):
    #    elif str(now_date) == last_enter_date:
        # Текущая дата, и дата последнего входа в игру совпадает.
        # Похоже, что это место, гда высчитывается общее количество шагов, которое может потратить игрок
        # Но, это нужно проверить
        char_characteristic['steps_can_use'] = char_characteristic['steps_today'] - char_characteristic['steps_today_used']
        char_characteristic['steps_can_use'] += stamina_skill_bonus_def()                   # Бонус от навыка
        char_characteristic['steps_can_use'] += equipment_bonus_stamina_steps()             # Бонус от экипировки
        char_characteristic['steps_can_use'] += daily_steps_bonus()                         # Бонус за пройденные шаги, более 10к+ в день.
        char_characteristic['steps_can_use'] += level_steps_bonus()                         # Бонус за прокаченный уровень
    else:
        print('Error (save_game_date_last_enter).')
    return char_characteristic['steps_can_use']


def steps_today_update_manual():
    """Получает данные о количестве шагов за сегодня через Fitness API (Google Fit)."""
    global steps_today_api
    global steps_today
    global char_characteristic

    # Получение токена через Fitness API
    token = None
    try:
        token = load_token_from_file()  # Попытка загрузить токен из файла
    except AttributeError:
        print("Токен отсутствует или недействителен. Попробуем обновить его.")
        token = get_access_token()

    if not token:
        print("Не удалось получить токен для Fitness API.")
        steps_today = 401  # Ошибка авторизации
        char_characteristic['steps_today'] = 401
        return None

    # URL для запроса Fitness API
    url = "https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate"

    # Временной диапазон (с полуночи текущего дня до текущего времени)
    now = datetime.now()
    start_time = int(datetime(now.year, now.month, now.day).timestamp() * 1e9)  # Полночь текущего дня в наносекундах
    end_time = int(now.timestamp() * 1e9)  # Текущее время в наносекундах

    body = {
        "aggregateBy": [{
            "dataTypeName": "com.google.step_count.delta",
            "dataSourceId": "derived:com.google.step_count.delta:com.google.android.gms:estimated_steps"
        }],
        "bucketByTime": {"durationMillis": 86400000},  # 1 день
        "startTimeMillis": start_time // 1e6,  # Преобразуем в миллисекунды
        "endTimeMillis": end_time // 1e6  # Преобразуем в миллисекунды
    }

    headers = {
        "Authorization": f"Bearer {token}",  # Используем токен
        "Content-Type": "application/json"
    }

    print('\nFitness API запрос на Steps Update.')

    try:
        response = requests.post(url, headers=headers, json=body)

        if response.status_code == 401:  # Ошибка авторизации, возможно, токен истек
            print("Токен истек. Обновляем токен и повторяем запрос...")
            token = get_access_token()
            if not token:
                print("Не удалось обновить токен.")
                steps_today = 401  # Ошибка авторизации
                char_characteristic['steps_today'] = 401
                return None
            headers["Authorization"] = f"Bearer {token}"
            response = requests.post(url, headers=headers, json=body)  # Повторяем запрос

        if response.status_code == 200:
            try:
                data = response.json()
                # Извлекаем количество шагов
                steps = data['bucket'][0]['dataset'][0]['point'][0]['value'][0]['intVal']
                steps_today = steps  # Обновляем глобальную переменную
                char_characteristic['steps_today'] = steps  # Сохраняем в структуру
                print(f"Steps Updated: {steps}")
                return steps
            except (IndexError, KeyError):
                print("Нет данных за сегодняшний день.")
                steps_today = 0  # Если нет данных, сохраняем 0
                char_characteristic['steps_today'] = 0
                return steps_today
        else:
            print("Ошибка:", response.json())
            steps_today = 404  # Обновляем переменную при ошибке соединения
            return None
    except Exception as e:
        print('\n--- Ошибка API соединения. Обновление данных о кол-ве шагов не произошло ---\n')
        steps_today = 404  # Если ошибка подключения к интернету
        char_characteristic['steps_today'] = 404
        return None


def steps_today_update_manual_nocodeapi_old():
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
    print('\n################################')
    print('### Характеристики персонажа ###')
    print('################################')
    print(f'- Пройдено шагов за сегодня 🏃: {char_characteristic["steps_today"]:,.0f}')
    print(f'- Потрачено шагов за сегодня 🏃: {char_characteristic["steps_today_used"]:,.0f}')

    print('\n### Бонусы за навыки: ###')
    print(f'- Запас энергии 🔋: {char_characteristic["energy"]} эд.')
    print(f'- Макс. запас энергии 🔋: {char_characteristic["energy_max"]} эд.')
    print(f'\n- Выносливость: + {char_characteristic["stamina"]} % (+ {stamina_skill_bonus_def()} шагов).')
    print(f'- Максимальный запас энергии: + {char_characteristic["energy_max_skill"]} энергии.')
    print(f'- Скорость: + {char_characteristic["speed_skill"]} %.')
    print(f'- Удача: + {char_characteristic["luck_skill"]} %.')

    print('\n### Бонусы экипировки: ###')
    print(f'\t- Stamina: + {equipment_stamina_bonus()} %'
          f'\n\t- Energy Max: + {equipment_energy_max_bonus()} эд.'
          f'\n\t- Speed: + {equipment_speed_skill_bonus()} %'
          f'\n\t- Luck: + {equipment_luck_bonus()} %')

    print(f'\n### Бонусы за прохождение каждый день 10к+ шагов:'
          f'\n\t- Steps: + {char_characteristic["steps_daily_bonus"]} %'
          f'\n\t- Energy Max: + {char_characteristic["steps_daily_bonus"]} эд.')

    print(f"\n### Прокачка навыков от уровня персонажа ###"
          f"\n\t- Stamina: {char_characteristic['lvl_up_skill_stamina']}"
          f"\n\t- Energy Max: {char_characteristic['lvl_up_skill_energy_max']}"
          f"\n\t- Speed Skill: {char_characteristic['lvl_up_skill_speed']}"
          f"\n\t- Luck: { char_characteristic['lvl_up_skill_luck']}")

    print('\n####################################')
    print('P.S. Сюда так же будут добавлены характеристики по мере их добавления в игру.')
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


def today_steps_to_yesterday_steps():
    # Запись шагов, которые пройдены за вчера в переменную.
    # Увеличение бонуса, если шагов более 10к за вчера. Если шагов меньше 10к, то обнуление бонуса.
    # Bug: Кол-во шагов обновляется раньше, чем шаги за вчера записываются в переменную.
    # Hot To Fix: В файле characteristics.py переменная шагов запускатеся во время инициализации файла.
    char_characteristic['steps_yesterday'] = char_characteristic['steps_today']

    if char_characteristic['steps_yesterday'] >= 10000:
        char_characteristic['steps_daily_bonus'] += 1
    else:
        char_characteristic['steps_daily_bonus'] = 0
    return char_characteristic['steps_yesterday'], char_characteristic['steps_daily_bonus']


#def load_token_from_file(file_path="token.json"):
#    """Загружает токен доступа из файла token.json."""
#    try:
#        with open(file_path, 'r') as file:
#            data = json.load(file)
#            return data.get('token')
#    except FileNotFoundError:
#        print(f"Файл {file_path} не найден.")
#        return None
#    except json.JSONDecodeError:
#        print("Ошибка чтения JSON из файла.")
#        return None


if __name__ == "__main__":
    print(steps_today_update_manual())
    pass
