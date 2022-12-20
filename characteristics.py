import time
import pickle
from api import steps_today_update


######## Game Ballance ########
# Настройки игрового балланса #
###############################

# Шаги за сегодня
steps_today = steps_today_update()

### Character characteristics ###
### Характеристики персонажа ####

char_characteristic = {
    'date_last_enter': None,    # Добавить дату последнего входа в игру
    'steps_today' : steps_today,
    'steps_can_use': 60,
    'steps_today_used': 0,
    'loc' : 'home',
    'energy' : 50,
    'energy_max' : 50,
    'stamina' : 0,
    'mechanics' : 0,
    'it_technologies' : 0,
}


def save_characteristic():
    # Функция записи характеристик в файл
    print(char_characteristic)
    with open('characteristic.txt', 'wb') as f:
        pickle.dump(char_characteristic, f)
    print('\nSave Successfully.')


def load_characteristic():
    # Функция загрузки характеристик из файла
#    global data
    with open('characteristic.txt', 'rb') as f:
        char_characteristic = pickle.load(f)
#        data = pickle.load(f)
#        char_characteristic = data
        return char_characteristic

#save_characteristic()
load_characteristic()




# Основные характеристики
energy = 50                 # Кол-во энергии
energy_max = 50             # Max кол-во энергии
energy_time = time.time()   # Переменная для отпечатка времени

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
