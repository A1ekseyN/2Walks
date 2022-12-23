import time
from datetime import datetime
import pickle
from api import steps_today_update

# Переменная для текущего времени. Используется в подсчёте timestamp_last_enter.
# Пока не используется
now_timestamp = datetime.now().timestamp()

######## Game Ballance ########
# Настройки игрового балланса #
###############################

# Шаги за сегодня
steps_today = steps_today_update()

### Character characteristics ###
### Характеристики персонажа ####

def load_characteristic():
    # Функция загрузки характеристик из файла
    global char_characteristic
    with open('characteristic.txt', 'rb') as f:
        char_characteristic = pickle.load(f)
        print(f'Чтение сохранения: {char_characteristic}')
        return char_characteristic


def date_check_steps_today_used():
    # Функция проверки последнего входа в игру.
    # Если дата последнего входа в игру не сегодня - обнуление счётчика steps_today_used
    date_today_check = open('save.txt', 'r')
    last_enter_date = date_today_check.read()
    now_date = datetime.now().date()
    if str(now_date) != last_enter_date:
        print('Данные обновлены: steps_today_used.')
        return 0
    elif str(now_date) == last_enter_date:
        return load_characteristic()['steps_today_used']


char_characteristic = {
    'date_last_enter': None,    # Добавить дату последнего входа в игру
    'timestamp_last_enter': now_timestamp,    # TimeStamp для расчёта игрового времени
    'steps_today' : steps_today,
    'steps_can_use': 60,
    'steps_today_used': date_check_steps_today_used(),  # Шаги потреченные за сегодня
    'loc' : load_characteristic()['loc'],
    'energy' : load_characteristic()['energy'],
    'energy_max' : 50,
    'energy_time_stamp': load_characteristic()['energy_time_stamp'],      # Данные берутся из functions.py
    'stamina' : 0,
    'mechanics' : 0,
    'it_technologies' : 0,
}


def save_characteristic():
    # Функция записи характеристик в файл
    print(f'Сохраняем данные: {char_characteristic}')
    with open('characteristic.txt', 'wb') as f:
        pickle.dump(char_characteristic, f)
    print('\nSave Successfully.')



#save_characteristic()
#load_characteristic()


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
