import requests
from datetime import datetime, timedelta


def get_steps(token):
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
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Запрос к API
    response = requests.post(url, headers=headers, json=body)

    if response.status_code == 200:
        try:
            data = response.json()
            # Извлекаем количество шагов
            steps = data['bucket'][0]['dataset'][0]['point'][0]['value'][0]['intVal']
            print(f"steps: {steps}")
            return steps
        except (IndexError, KeyError):
            print("Нет данных за сегодняшний день.")
            return 0
    else:
        print("Ошибка:", response.json())
        return None


get_steps(token)
