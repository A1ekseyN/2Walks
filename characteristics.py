from datetime import datetime
import pickle
from api import steps_today_update
from settings import debug_mode

# Переменная для текущего времени. Используется в подсчёте timestamp_last_enter.
# Пока не используется
now_timestamp = datetime.now().timestamp()

######## Game Ballance ########
# Настройки игрового баланса #
###############################


# Шаги за сегодня
# Изначально это переменная, сделал ее функцией.
# Пытаюсь починить обновление кол-ва шагов за вчера. Чтобы в новый день шаги, не обновлялись раньше записи переменной steps_yesterday.
# Если этот метод не заработает, то можно будет откатиться.
def steps_today():
    steps_today = steps_today_update()
    return steps_today

# Шаги за сегодня
#steps_today = steps_today_update()


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
    'steps_today' : steps_today(),    # steps_today,                                                        # Default: 0
    'steps_can_use': 0,                                                                 # Default: 0
    'steps_today_used': date_check_steps_today_used(),                                  # Default: 0
    'steps_yesterday': load_characteristic()['steps_yesterday'],                        # Default: 0
    'steps_daily_bonus': load_characteristic()['steps_daily_bonus'],    ### Daily Bonus                # Default: 0            # Бонус за прохождение каждый день более 10к шагов. (Yesterday)
    'loc' : 'home',      #load_characteristic()['loc'],                                               # Default: 'home'
    'energy' : load_characteristic()['energy'],                                         # Default: 50
    'energy_max' : 50,                                                                  # Default: 50
    'energy_time_stamp': load_characteristic()['energy_time_stamp'],                    # Default: timestamp() (Возможно)
    'money': load_characteristic()['money'],                                            # Default: 50 $

    'skill_training': load_characteristic()['skill_training'],                          # Default: False
    'skill_training_name': load_characteristic()['skill_training_name'],                # Default: None
    'skill_training_timestamp': load_characteristic()['skill_training_timestamp'],      # Default: None
    'skill_training_time_end': load_characteristic()['skill_training_time_end'],        # Default: None

    'stamina': load_characteristic()['stamina'],  # Выносливость: + 1 % к общему кол-ву пройденых шагов                                                     # Default: 0
    'energy_max_skill': load_characteristic()['energy_max_skill'], # Навык для прокачки макс. энергии. (Нужен еще одна переменная, для прокачки.            # Default: 0
    'speed_skill': load_characteristic()['speed_skill'],           # Скорость: + 1% к скорости действий игрока на 1 %.                                      # Default: 0
    'luck_skill': load_characteristic()['luck_skill'],            # Удача: + 1% к удаче в игре. Влияет на шанс выпадения лута, на качество самого лута.     # Default: 0
    'mechanics': 0,
    'it_technologies' : 0,

    'work': load_characteristic()['work'],   # Название работы          # Default: None
    'work_salary': load_characteristic()['work_salary'],                # Default: 0
    'working': load_characteristic()['working'],                        # Default: False
    'working_hours': load_characteristic()['working_hours'],            # Default: 0
    'working_start': load_characteristic()['working_start'],
    'working_end': load_characteristic()['working_end'],

    # Инвентарь / Inventory
    'inventory': load_characteristic()['inventory'],                                                    # Default: []

    # Equipment / Экипировка
    'equipment_head': load_characteristic()['equipment_head'],                              # Default: None
    'equipment_neck': load_characteristic()['equipment_neck'],                              # Default: None
    'equipment_torso': load_characteristic()['equipment_torso'],                            # Default: None
    'equipment_finger_01': load_characteristic()['equipment_finger_01'],                    # Default: None
    'equipment_finger_02': load_characteristic()['equipment_finger_02'],                    # Default: None
    'equipment_legs': load_characteristic()['equipment_legs'],                              # Default: None
    'equipment_foots': load_characteristic()['equipment_foots'],                            # Default: None

    # Adventure / Приключения
    'adventure': load_characteristic()['adventure'],
    'adventure_name': load_characteristic()['adventure_name'],
    'adventure_end_timestamp': load_characteristic()['adventure_end_timestamp'],

    # Adventure Counters
    'adventure_walk_easy_counter': load_characteristic()['adventure_walk_easy_counter'],                  # Default: 0
    'adventure_walk_normal_counter': load_characteristic()['adventure_walk_normal_counter'],              # Default: 0
    'adventure_walk_hard_counter': load_characteristic()['adventure_walk_hard_counter'],                  # Default: 0
    'adventure_walk_15k_counter': load_characteristic()['adventure_walk_15k_counter'],                    # Default: 0
    'adventure_walk_20k_counter': load_characteristic()['adventure_walk_20k_counter'],                    # Default: 0
    'adventure_walk_30k_counter': load_characteristic()['adventure_walk_30k_counter'],                    # Default: 0
}


# Список Слотов куда можно вставить item экипировки.
equipment_list = [char_characteristic['equipment_head'], char_characteristic['equipment_neck'],
                  char_characteristic['equipment_torso'], char_characteristic['equipment_finger_01'],
                  char_characteristic['equipment_finger_02'], char_characteristic['equipment_legs'],
                  char_characteristic['equipment_foots']]


def equipment_energy_max_bonus_for_char_characteristics():
    # Бонус Energy Max. Функция для вычисления бонуса экипировки
    # Архитектурно неверно реализованное решение. Пока не знаю как его переделать.
    bonus = 0
    for item in equipment_list:
        if item is not None:
            if item['characteristic'][0] == 'energy_max':
                bonus += item['bonus'][0]
    return bonus


char_characteristic['energy_max'] += char_characteristic['energy_max_skill'] + equipment_energy_max_bonus_for_char_characteristics()
char_characteristic['energy_max'] += char_characteristic['steps_daily_bonus']


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
        'time': 4800,       # 8000 часов
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
