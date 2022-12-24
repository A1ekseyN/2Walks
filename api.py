import requests
from datetime import datetime
import pickle
from settings import debug_mode


def steps_today_update():
    # Функция обновления кол-ва шагов за сегодня через API NoCodeAPI
    global steps_today
    global char_characteristic      # Нужно проверить или тут нужна эта переменная

    save_game_last_enter_date_file = open('save.txt', 'r')
    last_enter_date = save_game_last_enter_date_file.read()
    now_date = datetime.now().date()

    if str(now_date) != last_enter_date:
        print('\nAPI запрос на обновление данных о кол-ве шагов.')
        try:
            url = "https://v1.nocodeapi.com/alexeyn/fit/kxgLPAuehlTGiEaC/aggregatesDatasets?dataTypeName=steps_count&timePeriod=today"
            params = {}
            r = requests.get(url=url, params=params)
            result_steps_today = r.json()
            steps_today = result_steps_today['steps_count'][0]['value']
            print('--- Запрос NoCodeApi успешный. ---\n')
            print(f'Steps: {steps_today}')
            print(result_steps_today['steps_count'][0]['value'])
            return steps_today
        except:
            print('\n--- Ошибка API соеднинения. Обновление данных о кол-ве шагов не произошло ---\n')
            steps_today = 1555      # Если ошибка подключения к интернету, тогда указано число 1555 для тестов.
            return steps_today
    else:
        # Если дата не изменилась, то забирам данные о кол-ве загов из переменной.
        # Сделать, чтобы данные забирались из файла.
        # По сути эта часть функции не нужна, и ее можно перенести в characteristics.py
        print('-- Кол-во шагов не обновлялось.\n-- Шаги взяты из файла api.py + characteristic.txt')
        with open('characteristic.txt', 'rb') as f:
            data = pickle.load(f)
            if debug_mode:
                print(f'\nLoading Game Data: {data}')
            steps_today = data["steps_today"]
            print(f'\nLoad Steps Today Count - Successfully.')
        return steps_today
