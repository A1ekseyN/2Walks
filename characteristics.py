from datetime import datetime
import pickle
from api import steps_today_update
from settings import debug_mode

# Переменная для текущего времени. Используется в подсчёте timestamp_last_enter.
# Пока не используется
now_timestamp = datetime.now().timestamp()

######## Game Ballance ########
# Настройки игрового балланса #
###############################

# Шаги за сегодня
steps_today = steps_today_update()


def load_characteristic():
    # Функция загрузки характеристик из файла
    global char_characteristic
    with open('characteristic.txt', 'rb') as f:
        char_characteristic = pickle.load(f)
        if debug_mode:
            print(f'Чтение сохранения: {char_characteristic}')
        return char_characteristic


def date_check_steps_today_used():
    # Функция проверки последнего входа в игру.
    # Если дата последнего входа в игру не сегодня - обнуление счётчика steps_today_used
    date_today_check = open('save.txt', 'r')
    last_enter_date = date_today_check.read()
    now_date = datetime.now().date()
    if str(now_date) != last_enter_date:
        if debug_mode:
            print('Данные обновлены: [steps_today_used] - 0.')
            return 0
        return 0
    elif str(now_date) == last_enter_date:
        return load_characteristic()['steps_today_used']


char_characteristic = {
    'date_last_enter': None,    # Добавить дату последнего входа в игру
    'timestamp_last_enter': now_timestamp,    # TimeStamp для расчёта игрового времени
    'steps_today' : steps_today,                                        # Default: 0
    'steps_can_use': 0,                                                 # Default: 0
    'steps_today_used': date_check_steps_today_used(),                  # Default: 0
    'loc' : load_characteristic()['loc'],                               # Default: 'home'
    'energy' : load_characteristic()['energy'],                         # Default: 50
    'energy_max' : 50,                                                  # Default: 50
    'energy_time_stamp': load_characteristic()['energy_time_stamp'],    # Default: timestamp() (Возможно)
    'money': load_characteristic()['money'],                            # Default: 50 $

    'skill_training': load_characteristic()['skill_training'],                          # Default: False
    'skill_training_name': load_characteristic()['skill_training_name'],                # Default: None
    'skill_training_timestamp': load_characteristic()['skill_training_timestamp'],      # Default: None
    'skill_training_time_end': load_characteristic()['skill_training_time_end'],        # Default: None

    'stamina' : load_characteristic()['stamina'],  # Выносливость: +1 % к общему кол-ву пройденых шагов        # Default: 0
    'energy_max_skill': load_characteristic()['energy_max_skill'], # Навык для прокачки макс. энергии. (Нужен еще одна переменная, для прокачки.       # Default: 0
    'mechanics' : 0,
    'it_technologies' : 0,

    'work': load_characteristic()['work'],                              # Default: None
    'work_salary': load_characteristic()['work_salary'],                # Default: 0
    'working': load_characteristic()['working'],                        # Default: False (Вроде)
    'working_hours': load_characteristic()['working_hours'],            # Default: 0
    'working_start': load_characteristic()['working_start'],
    'working_end': load_characteristic()['working_end'],
}

char_characteristic['energy_max'] = char_characteristic['energy_max'] + char_characteristic['energy_max_skill']

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
        'money': 500,
        'time': 1440,
    },
    12: {
        'steps': 12000,
        'energy': 60,
        'money': 750,
        'time': 1680,
    },
}


def save_characteristic():
    # Функция записи характеристик в файл
    if debug_mode:
        print(f'Сохраняем данные: {char_characteristic}')
    with open('characteristic.txt', 'wb') as f:
        pickle.dump(char_characteristic, f)
    print('\n💾 Save Successfully.')


# Основные характеристики
energy = 50                 # Кол-во энергии
energy_max = 50             # Max кол-во энергии
#energy_time = time.time()   # Переменная для отпечатка времени

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

# Сопротевляемость природным явлениям
resistance_cold = 0         # Сопротивляемость холоду
resistance_heat = 0         # Сопротивляемость теплу
