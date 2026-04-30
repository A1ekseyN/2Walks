import time
from datetime import datetime
import csv
import json
import ast

from settings import debug_mode
from google_sheets_db import load_char_characteristic_from_google_sheet
from state import GameState, CharCharacteristicProxy


# Шаги за сегодня — читаются из сейва. Источник обновления — ручной ввод (команда `+`).
def steps_today():
    return loaded_data_char_characteristic.get('steps_today', 0)


def load_characteristic():
    """Функция для считывания сохранения из csv файла"""
    char_characteristic = {}

    with open("characteristic.csv", mode='r', encoding='utf-8') as file:
        csv_reader = csv.reader(file)
        headers = next(csv_reader)
        data_row = next(csv_reader)

        for key, value in zip(headers, data_row):
            # Преобразование значений в соответствующие типы данных
            if value.isdigit():
                char_characteristic[key] = int(value)
            elif value.replace('.', '', 1).isdigit():
                char_characteristic[key] = float(value)
            elif value.lower() in ['true', 'false']:
                char_characteristic[key] = value.lower() == 'true'
            elif value == '':
                char_characteristic[key] = None
            else:
                # Преобразование строковых представлений словарей и списков обратно в объекты Python
                try:
                    char_characteristic[key] = ast.literal_eval(value)
                except (ValueError, SyntaxError):
                    char_characteristic[key] = value

            if key in ['skill_training_time_end', 'working_end', 'adventure_end_timestamp'] \
                and isinstance(char_characteristic[key], str):
                try:
                    char_characteristic[key] = datetime.strptime(
                        char_characteristic[key], '%Y-%m-%d %H:%M:%S.%f'
                    )
                except ValueError:
                    pass

    return char_characteristic


def date_check_steps_today_used():
    # Функция проверки последнего входа в игру.
    # Если дата последнего входа в игру не сегодня - обнуление счётчика steps_today_used
    date_today_check = open('save.txt', 'r')
    last_enter_date = date_today_check.read()
    now_date = datetime.now().date()
    if str(now_date) != last_enter_date:
        return 0
    elif str(now_date) == last_enter_date:
        return load_characteristic()['steps_today_used']


def load_data_from_google_sheet_or_csv():
    """
    Сначала пытается загрузить данные из Google Sheets.
    Если это не удастся или данные пусты, загружает данные из CSV файла.

    :return: Словарь данных.
    """
    try:
        # Попытка загрузить данные из Google Sheets
        loaded_data_char_characteristic = load_char_characteristic_from_google_sheet()

        if loaded_data_char_characteristic:
            return loaded_data_char_characteristic
        else:
            # Если Google Sheets пуст, загружаем данные из CSV
            print("Google Sheets пуст. Загружаем данные из CSV файла.")
            loaded_data_char_characteristic = load_characteristic()
            print("Loaded Data from CSV.")
            return loaded_data_char_characteristic

    except Exception as error:
        print(f"Ошибка при загрузке данных из Google Sheets: {error}. Загружаем данные из CSV файла.")
        # В случае ошибки загрузки из Google Sheets, загружаем данные из CSV файла
        loaded_data_char_characteristic = load_characteristic()
        print("Loaded Data from CSV.")
        return loaded_data_char_characteristic


# Загружаем данные из Google Sheets / CSV (legacy flat-dict).
loaded_data_char_characteristic = load_data_from_google_sheet_or_csv()
#print(f"loaded_data_char_characteristic: {loaded_data_char_characteristic}")


# Phase 2 задачи 1.1: переход с module-level dict на GameState + backward-compat proxy.
# Все легаси-модули продолжают делать `from characteristics import char_characteristic`
# и обращаться к нему как к dict — proxy транслирует это в nested-поля GameState.
# proxy будет удалён в Phase 5 после полной миграции.
game_state = GameState.from_dict(loaded_data_char_characteristic)

# Поведение, сохранённое от legacy-кода:
# - timestamp_last_enter всегда обновляется до текущего момента при загрузке.
# - loc всегда сбрасывается в 'home' (загруженное значение игнорируется).
# - steps_today_used пересчитывается через date_check_steps_today_used() (зависит от save.txt).
# - energy_max начинается с 50, потом добавляются бонусы (см. ниже).
game_state.timestamp_last_enter = datetime.now().timestamp()
game_state.loc = 'home'
game_state.steps.used = date_check_steps_today_used()
game_state.energy_max = 50  # сброс перед добавлением бонусов

# Список слотов экипировки (для расчёта бонуса energy_max ниже).
equipment_list = [
    game_state.equipment.head, game_state.equipment.neck,
    game_state.equipment.torso, game_state.equipment.finger_01,
    game_state.equipment.finger_02, game_state.equipment.legs,
    game_state.equipment.foots,
]


def equipment_energy_max_bonus_for_char_characteristics():
    # Бонус Energy Max. Функция для вычисления бонуса экипировки.
    # Архитектурно неверно реализованное решение — рефакторинг отложен (см. equipment_bonus.py).
    bonus = 0
    for item in equipment_list:
        if item is not None:
            if item['characteristic'][0] == 'energy_max':
                bonus += item['bonus'][0]
    return bonus


# Просчёт Energy Max в зависимости от навыков, скиллов, уровня.
game_state.energy_max += (
    game_state.gym.energy_max_skill
    + equipment_energy_max_bonus_for_char_characteristics()
    + game_state.steps.daily_bonus
    + game_state.char_level.skill_energy_max
)

# Backward-compat: legacy-модули обращаются к char_characteristic как к dict.
char_characteristic = CharCharacteristicProxy(game_state)


skill_training_table = {
    # Таблица стоимости изучения навыков.
    1: {
        'steps': 1000,
        'energy': 5,
        'money': 10,
        'time': 5,
    },
    2: {
        'steps': 2000,
        'energy': 10,
        'money': 20,
        'time': 15,
    },
    3: {
        'steps': 3000,
        'energy': 15,
        'money': 30,
        'time': 30,
    },
    4: {
        'steps': 4000,
        'energy': 20,
        'money': 40,
        'time': 60,
    },
    5: {
        'steps': 5000,
        'energy': 25,
        'money': 50,
        'time': 120,
    },
    6: {
        'steps': 6000,
        'energy': 30,
        'money': 100,
        'time': 240,
    },
    7: {
        'steps': 7000,
        'energy': 35,
        'money': 150,
        'time': 480,
    },
    8: {
        'steps': 8000,
        'energy': 40,
        'money': 200,
        'time': 720,
    },
    9: {
        'steps': 9000,
        'energy': 45,
        'money': 250,
        'time': 960,
    },
    10: {
        'steps': 10000,
        'energy': 50,
        'money': 300,
        'time': 1200,
    },
    11: {
        'steps': 11000,
        'energy': 55,
        'money': 350,
        'time': 1440,
    },
    12: {
        'steps': 12000,
        'energy': 60,
        'money': 400,
        'time': 1680,
    },
    13: {
        'steps': 13000,
        'energy': 65,
        'money': 450,
        'time': 1920,
    },
    14: {
        'steps': 14000,
        'energy': 70,
        'money': 500,
        'time': 2160,
    },
    15: {
        'steps': 15000,
        'energy': 75,
        'money': 550,
        'time': 2400,
    },
    16: {
        'steps': 16000,
        'energy': 80,
        'money': 600,
        'time': 2640,
    },
    17: {
        'steps': 17000,
        'energy': 85,
        'money': 650,
        'time': 2880,
    },
    18: {
        'steps': 18000,
        'energy': 90,
        'money': 700,
        'time': 3120,       # 52 часа
    },
    19: {
        'steps': 19000,
        'energy': 95,
        'money': 750,
        'time': 3360,       # 56 часов
    },
    20: {
        'steps': 20000,
        'energy': 100,
        'money': 800,
        'time': 3600,       # 60 часов
    },
    21: {
        'steps': 21000,
        'energy': 105,
        'money': 850,
        'time': 3840,       # 64 часов
    },
    22: {
        'steps': 22000,
        'energy': 110,
        'money': 900,
        'time': 4080,       # 68 часов
    },
    23: {
        'steps': 23000,
        'energy': 115,
        'money': 950,
        'time': 4320,       # 72 часов
    },
    24: {
        'steps': 24000,
        'energy': 120,
        'money': 1000,
        'time': 4560,       # 76 часов
    },
    25: {
        'steps': 25000,
        'energy': 125,
        'money': 1050,
        'time': 4800,       # 80 часов
    },
    26: {
        'steps': 26000,
        'energy': 130,
        'money': 1100,
        'time': 5040,       # 84 часов
    },
    27: {
        'steps': 27000,
        'energy': 135,
        'money': 1150,
        'time': 5280,       # 88 часов
    },
    28: {
        'steps': 28000,
        'energy': 140,
        'money': 1200,
        'time': 5520,       # 92 часов
    },
    29: {
        'steps': 29000,
        'energy': 145,
        'money': 1250,
        'time': 5760,       # 96 часов
    },
    30: {
        'steps': 30000,
        'energy': 150,
        'money': 1300,
        'time': 6000,       # 100 часов
    },
}


def get_skill_training(level):
    """
    Возвращает параметры обучения для заданного уровня.
    Для уровней 1–30 используется статическая таблица (skill_training_table),
    для уровней > 30 значения вычисляются по формуле:
      - steps = level * 1000
      - energy = базовое значение уровня 30 (150) + (level - 30) * 5
      - money = базовое значение уровня 30 (1300) + (level - 30) * 50
      - time = базовое значение уровня 30 (6000) + (level - 30) * 240
    """
    if level in skill_training_table:
        return skill_training_table[level]
    else:
        base = {
            'steps': 30000,
            'energy': 150,
            'money': 1300,
            'time': 6000
        }
        return {
            'steps': level * 1000,
            'energy': base['energy'] + (level - 30) * 5,
            'money': base['money'] + (level - 30) * 50,
            'time': base['time'] + (level - 30) * 240
        }


def get_energy_training_data(level):
    """
    Функция для расчёта необходимого уровня для прокачки.
    Данные берутся из переменной: skill_training_table, в которой есть таблица по прокачке.
    Если нужного уровня нет в таблице, то рассчитываем нужные данные исходя из base параметров.

    Функция нужна для того, чтобы корректно рассчитывать Daily Bonus, который может выходить за пределы прокачки персонажа

    Возвращает данные об обучении для указанного уровня.
    Если уровень есть в таблице, берет данные оттуда, иначе вычисляет через get_skill_training().
    """
    if level in skill_training_table:
        return skill_training_table[level]
    return get_skill_training(level)


# Список ключей, для которых ожидается дата/время (настройте по необходимости)
DATE_KEYS = [
    "date_last_enter",
    "energy_time_stamp",
    "working_start",
    "working_end",
    "skill_training_time_end",
    "adventure_end_timestamp"
]


def json_serial(obj):
    """
    Функция для преобразования str() -> datetime.
    Функция нужна для нормальной работы времени в игре.
    """
    if isinstance(obj, datetime):
        return obj.strftime('%Y-%m-%d %H:%M:%S.%f')
    raise TypeError("Type not serializable")


def save_characteristic():
    """Записывает характеристики в файл в формате JSON и CSV."""
    # Phase 2 задачи 1.1: source of truth — game_state, не proxy.
    # to_dict() даёт legacy flat-формат, совместимый с прежней структурой CSV/JSON.
    state_dict = game_state.to_dict()
    if debug_mode:
        print(f'Сохраняем данные: {state_dict}')
    try:
        with open('characteristic.txt', 'w', encoding='utf-8') as f:
            json.dump(state_dict, f, ensure_ascii=False, indent=4, default=json_serial)
    except Exception as e:
        print(f"Ошибка записи в characteristic.txt: {e}")
    # Сохранение в CSV без изменений структуры, но с источником state_dict.
    try:
        with open('characteristic.csv', 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=state_dict.keys())
            writer.writeheader()
            processed_char = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
                              for k, v in state_dict.items()}
            writer.writerow(processed_char)
    except PermissionError:
        print("\nОшибка записи в файл 'characteristic.csv'. "
              "\nЗакройте файл и повторите попытку. Задержка 30 сек и повторный запуск.")
        time.sleep(30)
        save_characteristic()
    print('\n💾 Save Successfully.')


# Основные характеристики
energy = 50                 # Кол-во энергии
energy_max = 50             # Max кол-во энергии

stamina = 0                 # Выносливость
mechanics = 0               # Механика
it_technologies = 0          # ИТ Технологии

# Навыки ходьбы по разному типу местности
flat_walking = 0            # Ходьба по ровной местности
up_walking = 0              # Ходьба вверх
down_walking = 0            # Ходьба вниз
mountain_walking = 0        # Ходьба по горной местности
terrain_walking = 0         # Ходьба по земле местности
grass_walking = 0           # Ходьба по траве
grass_high_walking = 0      # Ходьба по высокой траве
forest_walking = 0          # Ходьба по лесу
marshland_walking = 0       # Ходьба по болотистой местности
snow_walking = 0            # Ходьба по снегу
ice_walking = 0             # Ходьба по льду
sand_walking = 0            # Ходьба по песку
stone_walking = 0           # Ходьба по камням
# Навык лазить по горам и камням (Нужен для преодоления определеннйо местности)

# Сопротивляемость природным явлениям
resistance_cold = 0         # Сопротивляемость холоду
resistance_heat = 0         # Сопротивляемость теплу
