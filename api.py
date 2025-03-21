import requests
import json
from datetime import datetime
from settings import debug_mode

from get_token_fitnes_api import get_access_token


def steps_today_update():
    """Обновляет количество шагов за сегодня через Fitness API (Google Fit)."""
    global steps_today

    save_game_last_enter_date_file = open('save.txt', 'r')
    last_enter_date = save_game_last_enter_date_file.read()
    now_date = datetime.now().date()

    if str(now_date) != last_enter_date:  # Обновляем только если текущая дата отличается от сохраненной
        print('\nFitness API запрос на обновление данных о количестве шагов.')

        # Попытка загрузить токен из файла
        token = None
        try:
            token = load_token_from_file()
        except AttributeError:
            print("Токен отсутствует или недействителен. Обновляем токен...")
            token = get_access_token()

        if not token:
            print("Не удалось получить токен для Fitness API.")
            steps_today = 401  # Ошибка авторизации
            return steps_today

        # Временной диапазон для сегодняшнего дня
        now = datetime.now()
        start_time = int(datetime(now.year, now.month, now.day).timestamp() * 1e9)  # Полночь текущего дня в наносекундах
        end_time = int(now.timestamp() * 1e9)  # Текущее время в наносекундах

        url = "https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate"
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
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(url, headers=headers, json=body)

            if response.status_code == 401:  # Если токен истек
                print("Токен истек. Обновляем токен и повторяем запрос...")
                token = get_access_token()
                if not token:
                    print("Не удалось обновить токен.")
                    steps_today = 401
                    return steps_today
                headers["Authorization"] = f"Bearer {token}"
                response = requests.post(url, headers=headers, json=body)

            if response.status_code == 200:
                data = response.json()
                try:
                    # Извлекаем данные о количестве шагов
                    steps_today = data['bucket'][0]['dataset'][0]['point'][0]['value'][0]['intVal']
                    print(f"Steps Updated: {steps_today}")

                    # Сохраняем дату обновления
                    with open('save.txt', 'w') as save_file:
                        save_file.write(str(now_date))

                    # Сохраняем данные в файл в формате JSON
                    with open('characteristic.txt', 'w', encoding='utf-8') as f:
                        json.dump({'steps_today': steps_today}, f, ensure_ascii=False, indent=4)
                    print('Данные успешно сохранены.')

                    return steps_today
                except (IndexError, KeyError):
                    print("Нет данных за сегодняшний день.")
                    steps_today = 0
                    return steps_today
            else:
                print(f"Ошибка API Fitness: {response.status_code} - {response.json()}")
                steps_today = 404
                return steps_today
        except Exception as e:
            print(f"\n--- Ошибка API соединения: {e} ---\n")
            steps_today = 404
            return steps_today
    else:
        print('Дата совпадает с последним обновлением. Шаги не обновлялись.')
        # Загружаем шаги из файла в формате JSON
        try:
            with open('characteristic.txt', 'r', encoding='utf-8') as f:
                data = json.load(f)
                steps_today = data.get("steps_today", 0)
                print(f"Загружено из файла: {steps_today} шагов.")
        except Exception as e:
            print(f"Ошибка чтения characteristic.json: {e}")
            steps_today = 0
        return steps_today


def load_token_from_file(file_path="token.json"):
    """Загружает токен доступа из файла token.json."""
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
            return data.get('token')
    except FileNotFoundError:
        print(f"Файл {file_path} не найден.")
        return None
    except json.JSONDecodeError:
        print("Ошибка чтения JSON из файла.")
        return None
