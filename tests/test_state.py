"""Round-trip и базовые тесты для GameState (Phase 1 задачи 1.1)."""

from datetime import datetime

from state import (
    GameState,
    StepsState,
    CharLevel,
    GymSkills,
    TrainingSession,
    WorkSession,
    AdventureSession,
    Equipment,
)


def test_default_new_game_has_expected_defaults():
    s = GameState.default_new_game()
    assert s.energy == 50
    assert s.energy_max == 50
    assert s.money == 0
    assert s.loc == 'home'
    assert s.date_last_enter == ''
    assert s.steps.today == 0
    assert s.steps.daily_bonus == 0
    assert s.char_level.level == 0
    assert s.gym.stamina == 0
    assert s.training.active is False
    assert s.work.active is False
    assert s.adventure.active is False
    assert s.adventure.counters['walk_easy'] == 0
    assert s.adventure.counters['walk_30k'] == 0
    assert s.equipment.head is None
    assert s.equipment.foots is None
    assert s.inventory == []


def test_round_trip_default_state():
    """default_new_game() → to_dict() → from_dict() → identity."""
    s1 = GameState.default_new_game()
    d = s1.to_dict()
    s2 = GameState.from_dict(d)
    assert s1 == s2


def test_round_trip_state_with_data():
    """Заполненный state переживает round-trip без потерь."""
    s1 = GameState(
        date_last_enter='2026-04-29',
        timestamp_last_enter=1714398000.0,
        energy=42,
        energy_max=75,
        money=1000,
        energy_time_stamp=1714398000.0,
        loc='gym',
        steps=StepsState(today=5000, used=200, yesterday=15000, total_used=1500000,
                         can_use=4800, daily_bonus=3),
        char_level=CharLevel(level=10, up_skills=2, skill_stamina=15, skill_energy_max=5,
                             skill_speed=8, skill_luck=3),
        gym=GymSkills(stamina=20, energy_max_skill=10, speed_skill=7, luck_skill=5,
                      neatness_in_using_things=4, move_optimization_adventure=3,
                      move_optimization_gym=2, move_optimization_work=6,
                      mechanics=0, it_technologies=0),
        training=TrainingSession(active=True, skill_name='stamina',
                                 timestamp=1714398000.0,
                                 time_end=datetime(2026, 4, 29, 14, 0, 0)),
        work=WorkSession(work_type='watchman', active=True, hours=4, salary=2,
                         start=datetime(2026, 4, 29, 10, 0, 0),
                         end=datetime(2026, 4, 29, 14, 0, 0)),
        adventure=AdventureSession(
            active=True, name='walk_easy', start_ts=1714398000.0,
            end_ts=datetime(2026, 4, 29, 16, 0, 0),
            counters={
                'walk_easy': 5, 'walk_normal': 3, 'walk_hard': 1,
                'walk_15k': 0, 'walk_20k': 0, 'walk_25k': 0, 'walk_30k': 0,
            },
        ),
        equipment=Equipment(
            head={'item_name': ['cap']},
            neck=None,
            torso={'item_name': ['t-shirt']},
            finger_01=None,
            finger_02=None,
            legs=None,
            foots={'item_name': ['shoes']},
        ),
        inventory=[
            {'item_name': ['ring'], 'grade': ['c-grade'], 'bonus': [1]},
            {'item_name': ['necklace'], 'grade': ['b-grade'], 'bonus': [2]},
        ],
    )
    d = s1.to_dict()
    s2 = GameState.from_dict(d)
    assert s1 == s2


def test_legacy_flat_dict_loads():
    """Имитация загрузки реального legacy save: плоский dict без nested → GameState."""
    legacy = {
        'date_last_enter': '2026-04-29',
        'timestamp_last_enter': 1714398000.0,
        'steps_today': 8000, 'steps_today_used': 200,
        'steps_yesterday': 12000, 'steps_total_used': 1600000,
        'steps_can_use': 7800, 'steps_daily_bonus': 3,
        'char_level': 9, 'char_level_up_skills': 1,
        'lvl_up_skill_stamina': 9, 'lvl_up_skill_energy_max': 0,
        'lvl_up_skill_speed': 0, 'lvl_up_skill_luck': 0,
        'loc': 'home', 'energy': 50, 'energy_max': 65,
        'energy_time_stamp': 1714398000.0, 'money': 1500,
        'skill_training': False, 'skill_training_name': None,
        'skill_training_timestamp': None, 'skill_training_time_end': None,
        'stamina': 18, 'energy_max_skill': 13, 'speed_skill': 7,
        'luck_skill': 3, 'neatness_in_using_things': 4,
        'mechanics': 0, 'it_technologies': 0,
        'move_optimization_adventure': 5, 'move_optimization_gym': 4,
        'move_optimization_work': 6,
        'work': None, 'work_salary': 0, 'working': False,
        'working_hours': 0, 'working_start': None, 'working_end': None,
        'inventory': [],
        'equipment_head': None, 'equipment_neck': None,
        'equipment_torso': None, 'equipment_finger_01': None,
        'equipment_finger_02': None, 'equipment_legs': None,
        'equipment_foots': None,
        'adventure': False, 'adventure_name': None,
        'adventure_start_timestamp': None, 'adventure_end_timestamp': None,
        'adventure_walk_easy_counter': 50, 'adventure_walk_normal_counter': 30,
        'adventure_walk_hard_counter': 20, 'adventure_walk_15k_counter': 10,
        'adventure_walk_20k_counter': 5, 'adventure_walk_25k_counter': 2,
        'adventure_walk_30k_counter': 0,
    }
    s = GameState.from_dict(legacy)
    # Проверяем разные углы nested-структуры:
    assert s.energy == 50
    assert s.energy_max == 65
    assert s.steps.today == 8000
    assert s.steps.daily_bonus == 3
    assert s.char_level.level == 9
    assert s.char_level.skill_stamina == 9
    assert s.gym.stamina == 18
    assert s.gym.energy_max_skill == 13
    assert s.gym.move_optimization_work == 6
    assert s.adventure.counters['walk_easy'] == 50
    assert s.adventure.counters['walk_30k'] == 0

    # Round-trip identity на boundary CSV format.
    d2 = s.to_dict()
    assert d2 == legacy


def test_datetime_fields_preserved_round_trip():
    """datetime-поля (training/work/adventure end times) не теряются."""
    dt = datetime(2026, 4, 29, 14, 30, 0)
    s1 = GameState(
        training=TrainingSession(active=True, skill_name='stamina', time_end=dt),
        work=WorkSession(work_type='watchman', active=True, end=dt),
        adventure=AdventureSession(active=True, end_ts=dt),
    )
    d = s1.to_dict()
    s2 = GameState.from_dict(d)
    assert s2.training.time_end == dt
    assert s2.work.end == dt
    assert s2.adventure.end_ts == dt


def test_datetime_string_parsed_on_load():
    """Если datetime приходит как строка (legacy CSV format) — парсится в datetime."""
    legacy = {
        'skill_training_time_end': '2026-04-29 14:00:00.000000',
        'working_end': '2026-04-29 16:00:00.000000',
        'adventure_end_timestamp': '2026-04-29 18:00:00.000000',
    }
    s = GameState.from_dict(legacy)
    assert isinstance(s.training.time_end, datetime)
    assert s.training.time_end == datetime(2026, 4, 29, 14, 0, 0)
    assert isinstance(s.work.end, datetime)
    assert s.work.end == datetime(2026, 4, 29, 16, 0, 0)
    assert isinstance(s.adventure.end_ts, datetime)
    assert s.adventure.end_ts == datetime(2026, 4, 29, 18, 0, 0)


def test_partial_dict_uses_defaults_for_missing():
    """from_dict толерантен к отсутствующим ключам — берутся дефолты подклассов."""
    minimal = {'energy': 30, 'money': 500}
    s = GameState.from_dict(minimal)
    assert s.energy == 30
    assert s.money == 500
    # Дефолты подклассов:
    assert s.steps.today == 0
    assert s.char_level.level == 0
    assert s.adventure.counters['walk_easy'] == 0
    assert s.equipment.head is None


def test_datetime_invalid_string_returns_none():
    """Невалидная строка datetime → None (не падаем)."""
    legacy = {'working_end': 'not-a-date'}
    s = GameState.from_dict(legacy)
    assert s.work.end is None


def test_inventory_round_trip():
    """Вложенная структура inventory (list of dicts) переживает round-trip."""
    inv = [
        {'item_name': ['ring'], 'grade': ['c-grade'], 'bonus': [1], 'quality': [85.5]},
        {'item_name': ['necklace'], 'grade': ['s-grade'], 'bonus': [4], 'quality': [99.0]},
    ]
    s1 = GameState(inventory=inv)
    d = s1.to_dict()
    s2 = GameState.from_dict(d)
    assert s2.inventory == inv


def test_equipment_with_item_round_trip():
    """Equipment с надетым item — round-trip без потерь."""
    item = {'item_name': ['ring'], 'grade': ['s-grade'], 'bonus': [4], 'quality': [99.0]}
    s1 = GameState(equipment=Equipment(finger_01=item))
    d = s1.to_dict()
    s2 = GameState.from_dict(d)
    assert s2.equipment.finger_01 == item
    assert s2.equipment.finger_02 is None


def test_default_state_to_dict_has_all_legacy_keys():
    """to_dict() возвращает все 58 ключей legacy save format."""
    s = GameState.default_new_game()
    d = s.to_dict()
    expected_keys = {
        # Time / day
        'date_last_enter', 'timestamp_last_enter',
        # Steps
        'steps_today', 'steps_can_use', 'steps_today_used',
        'steps_yesterday', 'steps_daily_bonus', 'steps_total_used',
        # Char level
        'char_level', 'char_level_up_skills',
        'lvl_up_skill_stamina', 'lvl_up_skill_energy_max',
        'lvl_up_skill_speed', 'lvl_up_skill_luck',
        # Resources
        'loc', 'energy', 'energy_max', 'energy_time_stamp', 'money',
        # Training
        'skill_training', 'skill_training_name',
        'skill_training_timestamp', 'skill_training_time_end',
        # Gym skills
        'stamina', 'energy_max_skill', 'speed_skill', 'luck_skill',
        'neatness_in_using_things', 'mechanics', 'it_technologies',
        'move_optimization_adventure', 'move_optimization_gym',
        'move_optimization_work',
        # Work
        'work', 'work_salary', 'working', 'working_hours',
        'working_start', 'working_end',
        # Inventory
        'inventory',
        # Equipment
        'equipment_head', 'equipment_neck', 'equipment_torso',
        'equipment_finger_01', 'equipment_finger_02',
        'equipment_legs', 'equipment_foots',
        # Adventure
        'adventure', 'adventure_name',
        'adventure_start_timestamp', 'adventure_end_timestamp',
        # Adventure counters
        'adventure_walk_easy_counter', 'adventure_walk_normal_counter',
        'adventure_walk_hard_counter', 'adventure_walk_15k_counter',
        'adventure_walk_20k_counter', 'adventure_walk_25k_counter',
        'adventure_walk_30k_counter',
    }
    assert set(d.keys()) == expected_keys
