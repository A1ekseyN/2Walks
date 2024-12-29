import pickle
import gspread
from oauth2client.service_account import ServiceAccountCredentials


def flatten_data(data, parent_key='', sep='__'):
    """
    Преобразует вложенные структуры (словари и списки) в плоский словарь.
    """
    items = []
    for k, v in data.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_data(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            for i, item in enumerate(v):
                items.extend(flatten_data({f"{k}[{i}]": item}, parent_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def upload_char_characteristic_to_google_sheet(file_path: str, spreadsheet_id: str, sheet_name: str):
    """
    Загружает данные из pickle файла в Google Sheets.

    :param file_path: Путь к файлу characteristic.txt.
    :param spreadsheet_id: ID Google Sheets документа.
    :param sheet_name: Имя листа в таблице.
    """
    try:
        # 1. Чтение данных из файла
        with open(file_path, 'rb') as f:
            data = pickle.load(f)

        # 2. Преобразование данных
        flattened_data = flatten_data(data)

        # 3. Установка соединения с Google Sheets
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials/2walks_service_account.json', scope)
        client = gspread.authorize(creds)

        # 4. Открытие таблицы и листа
        sheet = client.open_by_key(spreadsheet_id).worksheet(sheet_name)

        # 5. Подготовка данных к записи
        rows = [[key, value] for key, value in flattened_data.items()]

        # 6. Очистка текущих данных и запись новых
        sheet.clear()
        sheet.update(rows, "A1")

        print("Data successfully uploaded to Google Sheets.")

    except FileNotFoundError:
        print(f"Файл {file_path} не найден.")
    except pickle.UnpicklingError:
        print("Ошибка декодирования файла. Проверьте формат данных.")
    except Exception as e:
        print(f"Произошла ошибка: {e}")


def read_char_characteristic_from_google_sheet(spreadsheet_id: str, sheet_name: str):
    """
    Читает данные из Google Sheets и преобразует их в словарь.

    :param spreadsheet_id: ID Google Sheets документа.
    :param sheet_name: Имя листа в таблице.
    :return: Словарь данных из таблицы.
    """
    try:
        # 1. Установка соединения с Google Sheets
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials/2walks_service_account.json', scope)
        client = gspread.authorize(creds)

        # 2. Открытие таблицы и листа
        sheet = client.open_by_key(spreadsheet_id).worksheet(sheet_name)

        # 3. Чтение всех данных из таблицы
        rows = sheet.get_all_values()

        # 4. Преобразование данных в словарь
        char_characteristic = {}
        for row in rows:
            if len(row) >= 2:  # Проверка на наличие ключа и значения
                key, value = row[0], row[1]
                try:
                    # Попытка преобразовать значение в его реальный тип
                    if value.lower() == 'none':
                        value = None
                    elif value.isdigit():
                        value = int(value)
                    else:
                        try:
                            value = float(value)
                        except ValueError:
                            pass  # Оставить строкой, если преобразование не удалось
                except AttributeError:
                    pass
                char_characteristic[key] = value

        return char_characteristic

    except Exception as e:
        print(f"Произошла ошибка: {e}")
        return None


if __name__ == "__main__":
    file_path = 'characteristic.txt'
    spreadsheet_id = '1l1SfzodtHAAIVsmsQjZPK2YEltilVzu5psv0_2p4MLM'
    sheet_name = 'Sheet1'

    # Загрузка characteristic в Google Sheets
    upload_char_characteristic_to_google_sheet(file_path, spreadsheet_id, sheet_name)

    # Load char_characteristic data from Google Sheets
    char_characteristic = read_char_characteristic_from_google_sheet(spreadsheet_id, sheet_name)
    print("load_char_pickle:", char_characteristic)
