import time
from datetime import datetime
from typing import Optional
import csv
import json
import ast

from settings import debug_mode
from google_sheets_db import GameStateRepo
from state import GameState


# ----------------------------------------------------------------------------
# State container (задача 1.2 — убрать побочные эффекты импорта).
#
# Вместо module-level `game_state = ...` (который грузил Sheets при импорте)
# держим контейнер `game` с атрибутом `state`. Атрибут заполняется через
# `init_game_state()`, которую CLI вызывает в начале `__main__`, а FastAPI
# (когда появится) — в startup hook.
#
# Все callers получают живую ссылку через `from characteristics import game`
# и обращаются как `game.state.<field>` — без проблемы "from import None".
# ----------------------------------------------------------------------------


class _GameContainer:
    """Контейнер для активного `GameState`. Один игрок = один state.

    Расширение до multi-user (задача 4.53) — заменить `state` на `states[user_id]`.
    """
    state: Optional[GameState] = None


game = _GameContainer()


def init_game_state(state: Optional[GameState] = None) -> GameState:
    """Идемпотентная инициализация игрового состояния.

    Вызывается в начале `__main__` (CLI) или из FastAPI startup hook.
    Если state передан — используется как есть (для тестов/инжекта). Иначе
    подгружается из Google Sheets / CSV и применяются post-load fixups.

    Возвращает заполненный `game.state`.
    """
    if game.state is not None:
        return game.state

    if state is not None:
        game.state = state
        return game.state

    loaded = load_data_from_google_sheet_or_csv()
    s = GameState.from_dict(loaded)

    # Legacy fixups, которые делались на module-level до 1.2:
    # - timestamp_last_enter всегда обновляется до текущего момента при загрузке.
    # - loc всегда сбрасывается в 'home' (загруженное значение игнорируется).
    # - energy_max — обновляем кэш-поле через compute_energy_max (4.48.4.1 / 0.2.1g);
    #   логика игры читает значение через `bonus.compute_energy_max(state)`, поле
    #   `state.energy_max` остаётся в dataclass для save-format совместимости.
    # Day rollover detection — единственная точка в functions.save_game_date_last_enter()
    # на первом тике main loop, через state.date_last_enter (legacy save.txt
    # удалён в задаче 2.1, версия 0.2.0k).
    s.timestamp_last_enter = datetime.now().timestamp()
    s.loc = 'home'
    from bonus import compute_energy_max  # lazy — bonus импортирует equipment_bonus
    s.energy_max = compute_energy_max(s)

    # Max-merge с steps_log (задача 4.15) — поднимает state.steps.today до
    # максимума по записям лога за сегодня (web/iPhone/manual). Без этого CLI
    # не увидит ввод через web, если game_state лист ещё не обновлён.
    apply_steps_log_max_merge(s)

    game.state = s
    return game.state


def apply_steps_log_max_merge(state: GameState) -> None:
    """Поднимает `state.steps.today` до максимума по `steps_log` записям за
    сегодня. Также пересчитывает `state.steps.can_use` если today изменился.

    Используется после load (в init_game_state и web.sync.try_reload_state)
    чтобы свежий ввод через любой канал (CLI / Web / iPhone) применялся
    немедленно, независимо от того, обновлён ли `game_state` лист в Sheets.

    Silent-fail при сетевой ошибке: если steps_log недоступен — оставляем
    state как есть. Лучше показать чуть-старое значение, чем падать.
    """
    # Lazy imports — characteristics.py загружается до google_sheets_db в
    # некоторых сценариях, а functions.py имеет циклическую зависимость.
    from google_sheets_db import StepsLogRepo

    today_str = datetime.now().strftime('%Y-%m-%d')
    try:
        entries = StepsLogRepo().for_day(today_str)
    except Exception:
        return  # silent fail

    if not entries:
        return

    max_in_log = max(e['steps'] for e in entries)
    if max_in_log > state.steps.today:
        state.steps.today = max_in_log
        # Recompute can_use — lazy import чтобы избежать circular.
        from functions import total_bonus_steps
        state.steps.can_use = state.steps.today - state.steps.used + total_bonus_steps(state)


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


def load_data_from_google_sheet_or_csv():
    """Сначала пытается загрузить данные из Google Sheets, при неудаче — CSV."""
    try:
        loaded = GameStateRepo().load()
        if loaded:
            return loaded
        print("Google Sheets пуст. Загружаем данные из CSV файла.")
        loaded = load_characteristic()
        print("Loaded Data from CSV.")
        return loaded
    except Exception as error:
        print(f"Ошибка при загрузке данных из Google Sheets: {error}. Загружаем данные из CSV файла.")
        loaded = load_characteristic()
        print("Loaded Data from CSV.")
        return loaded

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
    if game.state is None:
        raise RuntimeError("game.state не инициализирован — вызови init_game_state() до save_characteristic().")
    state_dict = game.state.to_dict()
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
