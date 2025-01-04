import json
import time
import pickle
import ast
from datetime import datetime

import gspread
from oauth2client.service_account import ServiceAccountCredentials


def save_char_characteristic_to_google_sheet(file_path='characteristic.txt',
                                             spreadsheet_id='1l1SfzodtHAAIVsmsQjZPK2YEltilVzu5psv0_2p4MLM',
                                             sheet_name='Sheet1',
                                             credentials="credentials/2walks_service_account.json"):
    ping_time = time.time()

    # Чтение данных из файла с использованием pickle
    with open(file_path, 'rb') as file:
        data = pickle.load(file)

    # Установка соединения с Google Sheets
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials, scope)
    client = gspread.authorize(creds)

    # Открытие таблицы и листа
    sheet = client.open_by_key(spreadsheet_id).worksheet(sheet_name)

    # Формируем данные для записи: плоская структура + JSON строка для вложенных данных
    rows = [["Key", "Value"]]

    for key, value in data.items():
        if isinstance(value, list) or isinstance(value, dict):
            # Сохранение списков и словарей как JSON строки
            rows.append([key, json.dumps(value)])
        else:
            rows.append([key, value])

    # Очистка листа перед записью новых данных
    sheet.clear()

    # Запись данных в таблицу
    sheet.update(rows)

    print(f"Save Data to Google Sheets. [{time.time() - ping_time:,.2f} sec]")


def load_char_characteristic_from_google_sheet(spreadsheet_id='1l1SfzodtHAAIVsmsQjZPK2YEltilVzu5psv0_2p4MLM',
                                               sheet_name='Sheet1',
                                               credentials="credentials/2walks_service_account.json"):
    ping_time = time.time()
    print(f"Loading...")

    # Установка соединения с Google Sheets
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials, scope)
    client = gspread.authorize(creds)

    # Открытие таблицы и листа
    sheet = client.open_by_key(spreadsheet_id).worksheet(sheet_name)

    # Получение всех данных с листа (пропускаем заголовок)
    rows = sheet.get_all_values()[1:]  # [1:] пропускает заголовок ("Key", "Value")

    # Восстановление структуры данных
    data = {}
    for key, value in rows:
        try:
            # Попытка преобразовать строку в список или словарь (если это JSON)
            data[key] = json.loads(value)
        except json.JSONDecodeError:
            # Если это не JSON, сохраняем как строку или число
            data[key] = value if not value.isdigit() else int(value)

        # Дополнительная обработка значений, как в функции load_characteristic
        if isinstance(data[key], str):
            value = data[key]

            # Преобразование строковых представлений словарей и списков обратно в объекты Python
            try:
                data[key] = ast.literal_eval(value)
            except (ValueError, SyntaxError):
                # Если не удается преобразовать, оставляем строку
                pass

            # Преобразование значений в соответствующие типы данных
            if value.isdigit():
                data[key] = int(value)
            elif value.replace('.', '', 1).isdigit():
                data[key] = float(value)
            elif value.lower() in ['true', 'false']:
                data[key] = value.lower() == 'true'
            elif value == '':
                data[key] = None

            # Преобразование дат
            if key in ['skill_training_time_end', 'working_end', 'adventure_end_timestamp'] \
                and isinstance(data[key], str):
                try:
                    data[key] = datetime.strptime(
                        data[key], '%Y-%m-%d %H:%M:%S.%f'
                    )
                except ValueError:
                    pass

    print(f"Data Loaded from Google Sheets. [{time.time() - ping_time:,.2f} sec]")
    return data


if __name__ == "__main__":
    # Save Data to Google Sheets
    save_char_characteristic_to_google_sheet()

    # Load Data (char_characteristic) from Google Sheets
    char_characteristic = load_char_characteristic_from_google_sheet()
    print(f"char: {char_characteristic}")
