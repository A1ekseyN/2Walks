"""Static lookup-таблица стоимости прокачки Gym-навыков (1.3.2, 0.2.3e).

Вынесено из `characteristics.py` для разделения lookup-данных и state-логики
(по аналогии с `adventure_data.py`). Содержит:
- `skill_training_table` — dict уровни 1..30 со стоимостью {steps, energy, money, time}.
- `get_skill_training(level)` — для уровней > 30 экстраполирует по формуле.
- `get_energy_training_data(level)` — wrapper над skill_training_table + get_skill_training.

Импортёры: `gym.py`, `web/main.py`. Без зависимостей от state — pure data + pure helpers.
"""


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


def get_skill_training(level: int) -> dict:
    """Возвращает параметры обучения для заданного уровня.

    Для уровней 1..30 используется статическая `skill_training_table`,
    для уровней > 30 значения вычисляются по формуле:
      - steps = level * 1000
      - energy = базовое (150) + (level - 30) * 5
      - money = базовое (1300) + (level - 30) * 50
      - time = базовое (6000) + (level - 30) * 240
    """
    if level in skill_training_table:
        return skill_training_table[level]
    base = {
        'steps': 30000,
        'energy': 150,
        'money': 1300,
        'time': 6000,
    }
    return {
        'steps': level * 1000,
        'energy': base['energy'] + (level - 30) * 5,
        'money': base['money'] + (level - 30) * 50,
        'time': base['time'] + (level - 30) * 240,
    }


def get_energy_training_data(level: int) -> dict:
    """Wrapper для расчёта необходимого уровня прокачки. Используется в Daily
    Bonus где уровень может выйти за пределы прокачки персонажа.

    Если уровень есть в таблице — берет данные оттуда, иначе вычисляет через
    `get_skill_training()`.
    """
    if level in skill_training_table:
        return skill_training_table[level]
    return get_skill_training(level)
