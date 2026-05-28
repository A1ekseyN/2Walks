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
    BankState,
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
    # Bank поля появились в 4.49.0.0 — для legacy сейва без bank-keys defaults.
    assert s.bank.deposit_amount == 0.0
    assert s.bank.deposit_last_interest_ts is None

    # Round-trip identity на уровне state-объекта (через from_dict обратно).
    # to_dict() добавляет новые поля (bank_*), которых нет в legacy → strict
    # dict-равенство не работает; но отсутствующие поля при from_dict дают
    # defaults, которые записываются в d2 как defaults — поэтому объект
    # остаётся равен исходному при повторной загрузке.
    d2 = s.to_dict()
    assert GameState.from_dict(d2) == s
    # Legacy keys всё ещё подмножество (не пропадают).
    for k, v in legacy.items():
        assert d2[k] == v, f"legacy key '{k}' изменилось: {legacy[k]} → {d2[k]}"


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
    """Legacy CSV format: datetime-строки для training_time_end / working_end
    парсятся в datetime через _deser_datetime. adventure_end_timestamp после
    задачи 5.6.1 (0.2.1u) — float Unix timestamp, не datetime, проверка ниже
    в test_adventure_end_ts_is_float."""
    legacy = {
        'skill_training_time_end': '2026-04-29 14:00:00.000000',
        'working_end': '2026-04-29 16:00:00.000000',
    }
    s = GameState.from_dict(legacy)
    assert isinstance(s.training.time_end, datetime)
    assert s.training.time_end == datetime(2026, 4, 29, 14, 0, 0)
    assert isinstance(s.work.end, datetime)
    assert s.work.end == datetime(2026, 4, 29, 16, 0, 0)


def test_adventure_end_ts_is_float():
    """5.6.1 (0.2.1u): adventure_end_timestamp — Unix ts (float), не datetime.
    Раньше через _deser_datetime float-значение → None (баг типизации).
    Теперь читается напрямую как float."""
    save = {'adventure_end_timestamp': 1777900000.5}
    s = GameState.from_dict(save)
    assert s.adventure.end_ts == 1777900000.5
    assert isinstance(s.adventure.end_ts, float)


def test_adventure_end_ts_none_when_missing():
    """Без adventure_end_timestamp в save — end_ts = None (default)."""
    s = GameState.from_dict({})
    assert s.adventure.end_ts is None


# ---------------------------------------------------------------------------
# Bank (4.49.0.0) — депозит state inframgmt без бизнес-логики начисления.
# ---------------------------------------------------------------------------

def test_bank_state_default_in_new_game():
    """default_new_game() инициализирует BankState нулями."""
    s = GameState.default_new_game()
    assert isinstance(s.bank, BankState)
    assert s.bank.deposit_amount == 0.0
    assert s.bank.deposit_last_interest_ts is None


def test_bank_state_round_trip():
    """Деньги на депозите + timestamp переживают to_dict / from_dict."""
    s1 = GameState(
        bank=BankState(
            deposit_amount=1234.56,
            deposit_last_interest_ts=1700000000.0,
        ),
    )
    d = s1.to_dict()
    # Flat-keys корректно сериализуют BankState.
    assert d['bank_deposit_amount'] == 1234.56
    assert d['bank_deposit_last_interest_ts'] == 1700000000.0
    s2 = GameState.from_dict(d)
    assert s2.bank == s1.bank
    assert s2.bank.deposit_amount == 1234.56
    assert s2.bank.deposit_last_interest_ts == 1700000000.0


def test_bank_state_load_old_save_without_bank_keys():
    """Сейвы до 4.49.0.0 не содержат bank-ключей — defaults BankState() применяются."""
    legacy = {'energy': 50, 'money': 100}  # минимум, без bank_*
    s = GameState.from_dict(legacy)
    assert s.bank.deposit_amount == 0.0
    assert s.bank.deposit_last_interest_ts is None
    assert s.bank == BankState()


def test_bank_state_with_zero_amount_and_no_timestamp():
    """Корректно обрабатывается случай 'депозит закрыт' — amount=0 + ts=None."""
    s1 = GameState(bank=BankState(deposit_amount=0.0, deposit_last_interest_ts=None))
    d = s1.to_dict()
    s2 = GameState.from_dict(d)
    assert s2.bank.deposit_amount == 0.0
    assert s2.bank.deposit_last_interest_ts is None


def test_bank_state_preserves_float_precision():
    """deposit_amount хранится как float — копейки от accrue не теряются на round-trip."""
    s1 = GameState(bank=BankState(deposit_amount=999.99999, deposit_last_interest_ts=1.5))
    d = s1.to_dict()
    s2 = GameState.from_dict(d)
    assert s2.bank.deposit_amount == 999.99999
    assert s2.bank.deposit_last_interest_ts == 1.5


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
    """to_dict() возвращает все 73 ключа legacy save format (72 + last_modified)."""
    s = GameState.default_new_game()
    d = s.to_dict()
    expected_keys = {
        # Time / day
        'date_last_enter', 'timestamp_last_enter', 'days_played',
        # Steps
        'steps_today', 'steps_can_use', 'steps_today_used',
        'steps_yesterday', 'steps_daily_bonus', 'steps_total_used',
        'steps_total_walked', 'steps_daily_streak_record', 'steps_xp_bonus',
        # Char level
        'char_level', 'char_level_up_skills',
        'lvl_up_skill_stamina', 'lvl_up_skill_energy_max',
        'lvl_up_skill_speed', 'lvl_up_skill_luck',
        'lvl_up_skill_energy_regen',
        # Resources
        'loc', 'energy', 'energy_max', 'energy_time_stamp', 'money',
        # Training
        'skill_training', 'skill_training_name',
        'skill_training_timestamp', 'skill_training_time_end',
        # Gym skills
        'stamina', 'energy_max_skill', 'speed_skill', 'energy_regen_skill', 'luck_skill',
        'neatness_in_using_things', 'mechanics', 'it_technologies',
        'banking_interest_rate', 'loan_capacity', 'loan_interest_reduction',
        'inspiration', 'money_saving', 'earnings_boost', 'trader',
        'backpack_skill',
        # 4.60 — Forge resource-saving + quality skills
        'forge_steps_saving', 'forge_money_saving', 'forge_repair_quality',
        # 4.59.4 — Forge speed skill
        'forge_speed',
        'move_optimization_adventure', 'move_optimization_gym',
        'move_optimization_work',
        'energy_optimization_adventure', 'energy_optimization_gym',
        'energy_optimization_work',
        # Work
        'work', 'work_salary', 'working', 'working_hours',
        'working_start', 'working_end',
        # Inventory
        'inventory', 'pending_drop',
        # 4.63.2 — Equipment presets (именованные loadout'ы)
        'equipment_presets',
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
        # Bank (4.49.0.0 / 4.49.2.1)
        'bank_deposit_amount', 'bank_deposit_last_interest_ts',
        'bank_loan_amount', 'bank_loan_last_interest_ts',
        # 4.62.1.10 — Capitalist triumph accumulator
        'bank_total_interest_earned',
        # 4.62.0.1 — Triumphs system (Phase 1 foundation для зонтичной 4.62)
        'triumphs', 'pinned_triumphs', 'title',
        # 4.62.0.2 — Triumphs engine backfill dismiss flag
        'triumphs_backfill_dismissed',
        # 4.62.7.6 — день dismiss'а unclaimed-баннера (web)
        'unclaimed_banner_dismissed_date',
        # 4.62.4 — Unclaimed triumph unlocks (Destiny-2 claim queue)
        'unclaimed_unlocks',
        # 4.62.1.5.1 — Iron Worker longest single shift
        'work_longest_shift_hours',
        # 4.59.4 — Forge timer session (repair/craft)
        'forge_session',
        # 4.54.1 — Optimistic concurrency
        'last_modified',
    }
    assert set(d.keys()) == expected_keys


def test_backpack_skill_round_trip():
    """4.50.0 — backpack_skill сериализуется в to_dict() и читается обратно
    в from_dict()."""
    s1 = GameState.default_new_game()
    s1.gym.backpack_skill = 7

    d = s1.to_dict()
    assert d['backpack_skill'] == 7

    s2 = GameState.from_dict(d)
    assert s2.gym.backpack_skill == 7


def test_legacy_save_without_backpack_skill_defaults_to_zero():
    """4.50.0 — старый сейв без поля backpack_skill — поле получает default 0."""
    s1 = GameState.default_new_game()
    d = s1.to_dict()
    del d['backpack_skill']  # имитируем legacy save до 0.2.4b
    s2 = GameState.from_dict(d)
    assert s2.gym.backpack_skill == 0


# ----- 4.62.0.1 — Triumphs system schema + persistence -----

def test_triumphs_default_empty_dict():
    """Новая игра: triumphs = {} (нет unlocked)."""
    s = GameState.default_new_game()
    assert s.triumphs == {}


def test_pinned_triumphs_default_empty_list():
    """Новая игра: pinned_triumphs = []."""
    s = GameState.default_new_game()
    assert s.pinned_triumphs == []


def test_title_default_none():
    """Новая игра: title = None."""
    s = GameState.default_new_game()
    assert s.title is None


def test_triumphs_round_trip_basic():
    """Round-trip: triumphs dict survives to_dict → from_dict."""
    s1 = GameState.default_new_game()
    s1.triumphs = {
        'marathoner': {'tier': 2, 'unlocked_at': {'0': '2026-05-22 10:00:00', '1': '2026-05-22 11:00:00'}, 'count': 0},
        'adventurer': {'tier': 1, 'unlocked_at': {'0': '2026-05-22 12:00:00'}, 'count': 15},
    }
    d = s1.to_dict()
    assert d['triumphs'] == s1.triumphs

    s2 = GameState.from_dict(d)
    assert s2.triumphs == s1.triumphs
    assert s2.triumphs['marathoner']['tier'] == 2
    assert s2.triumphs['adventurer']['count'] == 15


def test_pinned_triumphs_round_trip():
    """Round-trip: pinned_triumphs list survives."""
    s1 = GameState.default_new_game()
    s1.pinned_triumphs = ['marathoner', 'adventurer', 'treasure_hunter']

    d = s1.to_dict()
    assert d['pinned_triumphs'] == ['marathoner', 'adventurer', 'treasure_hunter']

    s2 = GameState.from_dict(d)
    assert s2.pinned_triumphs == ['marathoner', 'adventurer', 'treasure_hunter']


def test_title_round_trip():
    """Round-trip: title string survives."""
    s1 = GameState.default_new_game()
    s1.title = 'Marathoner'

    d = s1.to_dict()
    assert d['title'] == 'Marathoner'

    s2 = GameState.from_dict(d)
    assert s2.title == 'Marathoner'


def test_legacy_save_without_triumphs_defaults_to_empty():
    """Старый сейв без полей triumphs / pinned_triumphs / title — default empty."""
    s1 = GameState.default_new_game()
    d = s1.to_dict()
    # Имитируем legacy save до 4.62.0.1.
    del d['triumphs']
    del d['pinned_triumphs']
    del d['title']

    s2 = GameState.from_dict(d)
    assert s2.triumphs == {}
    assert s2.pinned_triumphs == []
    assert s2.title is None


def test_triumphs_update_from_dict_in_place():
    """update_from_dict обновляет triumph-поля in-place (не создаёт новый instance)."""
    s = GameState.default_new_game()
    original_id = id(s)

    s.update_from_dict({
        'triumphs': {'marathoner': {'tier': 1, 'unlocked_at': {'0': '2026-05-22'}, 'count': 0}},
        'pinned_triumphs': ['marathoner'],
        'title': 'Marathoner',
    })

    assert id(s) == original_id  # same instance, in-place
    assert s.triumphs == {'marathoner': {'tier': 1, 'unlocked_at': {'0': '2026-05-22'}, 'count': 0}}
    assert s.pinned_triumphs == ['marathoner']
    assert s.title == 'Marathoner'


def test_triumphs_round_trip_through_state_json(tmp_path, monkeypatch):
    """Round-trip через state.json (persistence layer) — проверка JSON-сериализации
    nested dict + list (важно для blob layout 1.4.3)."""
    import json
    from persistence import STATE_JSON_PATH, _json_default, load_state_json

    monkeypatch.chdir(tmp_path)
    s1 = GameState.default_new_game()
    s1.triumphs = {
        'marathoner': {'tier': 3, 'unlocked_at': {'0': '2026-05-22 10:00:00', '1': '2026-05-22 11:00:00', '2': '2026-05-22 12:00:00'}, 'count': 0},
    }
    s1.pinned_triumphs = ['marathoner']
    s1.title = 'Marathoner'

    # Write via _json_default (same as save_characteristic).
    d = s1.to_dict()
    (tmp_path / STATE_JSON_PATH).write_text(
        json.dumps(d, ensure_ascii=False, default=_json_default),
        encoding='utf-8',
    )
    # Read via load_state_json.
    loaded = load_state_json()
    s2 = GameState.from_dict(loaded)

    assert s2.triumphs == s1.triumphs
    assert s2.pinned_triumphs == s1.pinned_triumphs
    assert s2.title == s1.title


def test_pending_drop_round_trip_none():
    """4.50.1 — default state: pending_drop=None survives round-trip."""
    s1 = GameState.default_new_game()
    d = s1.to_dict()
    assert d['pending_drop'] is None
    s2 = GameState.from_dict(d)
    assert s2.pending_drop is None


def test_pending_drop_round_trip_with_item():
    """4.50.1 — pending_drop с реальным item-dict переживает round-trip."""
    item = {
        'item_name': ['ring'], 'item_type': ['ring'], 'grade': ['a-grade'],
        'characteristic': ['luck'], 'bonus': [3], 'quality': [80.0], 'price': [120],
    }
    s1 = GameState.default_new_game()
    s1.pending_drop = item

    d = s1.to_dict()
    assert d['pending_drop'] == item

    s2 = GameState.from_dict(d)
    assert s2.pending_drop == item


def test_legacy_save_without_pending_drop_defaults_to_none():
    """4.50.1 — старый сейв без поля pending_drop — поле получает default None."""
    s1 = GameState.default_new_game()
    d = s1.to_dict()
    del d['pending_drop']  # имитируем legacy save до 0.2.4c
    s2 = GameState.from_dict(d)
    assert s2.pending_drop is None


# ----- 4.54.1: Optimistic concurrency timestamp + snapshot -----

def test_last_modified_default_is_zero():
    """Новый default-state имеет last_modified=0.0 (никогда не сохранялся)."""
    s = GameState.default_new_game()
    assert s.last_modified == 0.0


def test_last_modified_round_trip():
    """last_modified переживает to_dict → from_dict без потерь."""
    s1 = GameState.default_new_game()
    s1.last_modified = 1234567890.123
    d = s1.to_dict()
    assert d['last_modified'] == 1234567890.123
    s2 = GameState.from_dict(d)
    assert s2.last_modified == 1234567890.123


def test_legacy_save_without_last_modified_defaults_to_zero():
    """4.54.1 — старый сейв без last_modified — поле получает default 0.0.
    Это позволяет первому save_safe пройти проверку (0.0 ≤ current = 0.0)."""
    s1 = GameState.default_new_game()
    d = s1.to_dict()
    del d['last_modified']  # legacy save до 4.54
    s2 = GameState.from_dict(d)
    assert s2.last_modified == 0.0


def test_last_loaded_snapshot_default_is_none():
    """Без явного take_snapshot() — snapshot пустой (None)."""
    s = GameState.default_new_game()
    assert s.last_loaded_snapshot is None


def test_last_loaded_snapshot_not_in_to_dict():
    """4.54.1 — snapshot НЕ сериализуется (runtime-only)."""
    s = GameState.default_new_game()
    s.take_snapshot()
    d = s.to_dict()
    assert 'last_loaded_snapshot' not in d


def test_take_snapshot_captures_current_state():
    """take_snapshot() сохраняет deep-copy текущего to_dict()."""
    s = GameState.default_new_game()
    s.money = 123.45
    s.gym.stamina = 5

    s.take_snapshot()

    assert s.last_loaded_snapshot is not None
    assert s.last_loaded_snapshot['money'] == 123.45
    assert s.last_loaded_snapshot['stamina'] == 5


def test_take_snapshot_is_deep_copy_not_reference():
    """Snapshot должен быть deep copy — мутации live state НЕ должны менять snapshot."""
    s = GameState.default_new_game()
    s.inventory.append({'item_type': ['ring'], 'grade': ['a-grade'], 'quality': [80]})
    s.take_snapshot()

    # Мутируем live state ПОСЛЕ snapshot'а
    s.inventory.append({'item_type': ['helmet'], 'grade': ['s-grade'], 'quality': [50]})
    s.money = 9999
    s.inventory[0]['quality'][0] = 1  # мутируем item-dict, который был в snapshot

    # Snapshot должен остаться в исходном виде
    assert len(s.last_loaded_snapshot['inventory']) == 1
    assert s.last_loaded_snapshot['inventory'][0]['quality'][0] == 80
    assert s.last_loaded_snapshot['money'] == 0


def test_two_states_compare_equal_regardless_of_snapshot():
    """4.54.1 — last_loaded_snapshot НЕ участвует в __eq__ (compare=False).
    Две одинаковые state'ы с разными snapshot'ами должны быть equal."""
    s1 = GameState.default_new_game()
    s2 = GameState.default_new_game()
    s1.take_snapshot()
    # s2 без snapshot'а
    assert s1 == s2


def test_update_from_dict_propagates_last_modified():
    """update_from_dict подтягивает last_modified из fresh dict."""
    s = GameState.default_new_game()
    assert s.last_modified == 0.0

    fresh_dict = GameState.default_new_game().to_dict()
    fresh_dict['last_modified'] = 9999.99

    s.update_from_dict(fresh_dict)
    assert s.last_modified == 9999.99
