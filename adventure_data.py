# Таблица с приключениями, и параметрами
adventure_data_table = {
    'walk_easy': {
        'steps': 2500,
        'energy': 10,
        'time': 30,
        'drop_grade': {'c'},
        'drop_items': {'Ring', 'Necklace'},
    },
    'walk_normal': {
        'steps': 5000,
        'energy': 20,
        'time': 60,
        'drop_grade': {'c', 'b'},
        'drop_items': {'ring', 'necklace'},
    },
    'walk_hard': {
        'steps': 10000,
        'energy': 30,
        'time': 120,
        'drop_grade': {'c', 'b', 'a'},
        'drop_items': {'ring', 'necklace'},
    },
    'walk_15k': {
        'steps': 15000,
        'energy': 40,
        'time': 180,
        'drop_grade': {'b', 'a', 's'},
        'drop_items': {'ring', 'necklace'},
    },
    'walk_20k': {
        'steps': 20000,
        'energy': 50,
        'time': 240,
        'drop_grade': {'a', 's', 's+'},
        'drop_items': {'ring', 'necklace'},
    },
    'walk_25k': {
        'steps': 25000,
        'energy': 60,
        'time': 300,
        'drop_grade': {'s', 's+'},
        'drop_items': {'ring', 'necklace'},
    },
    'walk_30k': {
        'steps': 30000,
        'energy': 70,
        'time': 360,
        'drop_grade': {'s+'},
        'drop_items': {'ring', 'necklace'},
    },
}