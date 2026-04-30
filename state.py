"""GameState — типизированное игровое состояние.

Часть задачи 1.1 — заменить module-level dict `char_characteristic`
на структурированный dataclass с nested подклассами.

В Phase 1 (29.04.2026) — только определение классов, маппинг старых ключей
и round-trip конвертация. Существующий код игры пока ничего не использует —
параллельная структура. Миграция модулей идёт отдельными фазами (см. TASKS.md 1.1).

Save format CSV / Google Sheets остаётся неизменным: `to_dict()` возвращает
плоский dict с прежними именами ключей. `from_dict()` принимает такой же
плоский dict и собирает в nested структуру.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# Формат datetime в CSV save (тот же, что в characteristics.py:load_characteristic).
_DATETIME_FMT = '%Y-%m-%d %H:%M:%S.%f'


def _deser_datetime(v):
    """Толерантная конвертация в datetime.

    Принимает datetime / str (legacy CSV format) / None. Возвращает datetime или None.
    """
    if v is None or v == '' or v == 'None':
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        try:
            return datetime.strptime(v, _DATETIME_FMT)
        except ValueError:
            return None
    return None


@dataclass
class StepsState:
    today: int = 0
    used: int = 0           # was steps_today_used
    yesterday: int = 0
    total_used: int = 0
    can_use: int = 0
    daily_bonus: int = 0    # was steps_daily_bonus


@dataclass
class CharLevel:
    level: int = 0              # was char_level
    up_skills: int = 0          # was char_level_up_skills
    skill_stamina: int = 0      # was lvl_up_skill_stamina
    skill_energy_max: int = 0   # was lvl_up_skill_energy_max
    skill_speed: int = 0        # was lvl_up_skill_speed
    skill_luck: int = 0         # was lvl_up_skill_luck


@dataclass
class GymSkills:
    stamina: int = 0
    energy_max_skill: int = 0
    speed_skill: int = 0
    luck_skill: int = 0
    neatness_in_using_things: int = 0
    move_optimization_adventure: int = 0
    move_optimization_gym: int = 0
    move_optimization_work: int = 0
    mechanics: int = 0
    it_technologies: int = 0


@dataclass
class TrainingSession:
    active: bool = False                    # was skill_training
    skill_name: Optional[str] = None        # was skill_training_name
    timestamp: Optional[float] = None       # was skill_training_timestamp
    time_end: Optional[datetime] = None     # was skill_training_time_end


@dataclass
class WorkSession:
    work_type: Optional[str] = None         # was 'work'
    active: bool = False                    # was 'working'
    hours: int = 0                          # was working_hours
    salary: int = 0                         # was work_salary
    start: Optional[datetime] = None        # was working_start
    end: Optional[datetime] = None          # was working_end


@dataclass
class AdventureSession:
    active: bool = False                    # was 'adventure'
    name: Optional[str] = None              # was adventure_name
    start_ts: Optional[float] = None        # was adventure_start_timestamp
    end_ts: Optional[datetime] = None       # was adventure_end_timestamp
    counters: dict = field(default_factory=lambda: {
        'walk_easy': 0,
        'walk_normal': 0,
        'walk_hard': 0,
        'walk_15k': 0,
        'walk_20k': 0,
        'walk_25k': 0,
        'walk_30k': 0,
    })


@dataclass
class Equipment:
    head: Optional[dict] = None
    neck: Optional[dict] = None
    torso: Optional[dict] = None
    finger_01: Optional[dict] = None
    finger_02: Optional[dict] = None
    legs: Optional[dict] = None
    foots: Optional[dict] = None


@dataclass
class GameState:
    # Time / day
    date_last_enter: str = ''
    timestamp_last_enter: float = 0.0

    # Resources
    energy: int = 50
    energy_max: int = 50
    money: int = 0
    energy_time_stamp: float = 0.0
    loc: str = 'home'

    # Composed (nested)
    steps: StepsState = field(default_factory=StepsState)
    char_level: CharLevel = field(default_factory=CharLevel)
    gym: GymSkills = field(default_factory=GymSkills)
    training: TrainingSession = field(default_factory=TrainingSession)
    work: WorkSession = field(default_factory=WorkSession)
    adventure: AdventureSession = field(default_factory=AdventureSession)
    equipment: Equipment = field(default_factory=Equipment)
    inventory: list = field(default_factory=list)

    @classmethod
    def default_new_game(cls) -> "GameState":
        """Дефолтное состояние нового персонажа (energy=50, money=0, location=home)."""
        return cls()

    @classmethod
    def from_dict(cls, d: dict) -> "GameState":
        """Конструктор из плоского dict (legacy save format).

        Толерантен к отсутствующим ключам — для них берутся дефолты подклассов.
        Datetime поля принимаются как datetime или str (формат `%Y-%m-%d %H:%M:%S.%f`).
        """
        return cls(
            date_last_enter=d.get('date_last_enter', '') or '',
            timestamp_last_enter=float(d.get('timestamp_last_enter') or 0.0),
            energy=int(d.get('energy', 50)),
            energy_max=int(d.get('energy_max', 50)),
            money=int(d.get('money', 0)),
            energy_time_stamp=float(d.get('energy_time_stamp') or 0.0),
            loc=d.get('loc', 'home') or 'home',

            steps=StepsState(
                today=int(d.get('steps_today', 0)),
                used=int(d.get('steps_today_used', 0)),
                yesterday=int(d.get('steps_yesterday', 0)),
                total_used=int(d.get('steps_total_used', 0)),
                can_use=int(d.get('steps_can_use', 0)),
                daily_bonus=int(d.get('steps_daily_bonus', 0)),
            ),

            char_level=CharLevel(
                level=int(d.get('char_level', 0)),
                up_skills=int(d.get('char_level_up_skills', 0)),
                skill_stamina=int(d.get('lvl_up_skill_stamina', 0)),
                skill_energy_max=int(d.get('lvl_up_skill_energy_max', 0)),
                skill_speed=int(d.get('lvl_up_skill_speed', 0)),
                skill_luck=int(d.get('lvl_up_skill_luck', 0)),
            ),

            gym=GymSkills(
                stamina=int(d.get('stamina', 0)),
                energy_max_skill=int(d.get('energy_max_skill', 0)),
                speed_skill=int(d.get('speed_skill', 0)),
                luck_skill=int(d.get('luck_skill', 0)),
                neatness_in_using_things=int(d.get('neatness_in_using_things', 0)),
                move_optimization_adventure=int(d.get('move_optimization_adventure', 0)),
                move_optimization_gym=int(d.get('move_optimization_gym', 0)),
                move_optimization_work=int(d.get('move_optimization_work', 0)),
                mechanics=int(d.get('mechanics', 0)),
                it_technologies=int(d.get('it_technologies', 0)),
            ),

            training=TrainingSession(
                active=bool(d.get('skill_training', False)),
                skill_name=d.get('skill_training_name'),
                timestamp=d.get('skill_training_timestamp'),
                time_end=_deser_datetime(d.get('skill_training_time_end')),
            ),

            work=WorkSession(
                work_type=d.get('work'),
                active=bool(d.get('working', False)),
                hours=int(d.get('working_hours', 0)),
                salary=int(d.get('work_salary', 0)),
                start=_deser_datetime(d.get('working_start')),
                end=_deser_datetime(d.get('working_end')),
            ),

            adventure=AdventureSession(
                active=bool(d.get('adventure', False)),
                name=d.get('adventure_name'),
                start_ts=d.get('adventure_start_timestamp'),
                end_ts=_deser_datetime(d.get('adventure_end_timestamp')),
                counters={
                    'walk_easy': int(d.get('adventure_walk_easy_counter', 0)),
                    'walk_normal': int(d.get('adventure_walk_normal_counter', 0)),
                    'walk_hard': int(d.get('adventure_walk_hard_counter', 0)),
                    'walk_15k': int(d.get('adventure_walk_15k_counter', 0)),
                    'walk_20k': int(d.get('adventure_walk_20k_counter', 0)),
                    'walk_25k': int(d.get('adventure_walk_25k_counter', 0)),
                    'walk_30k': int(d.get('adventure_walk_30k_counter', 0)),
                },
            ),

            equipment=Equipment(
                head=d.get('equipment_head'),
                neck=d.get('equipment_neck'),
                torso=d.get('equipment_torso'),
                finger_01=d.get('equipment_finger_01'),
                finger_02=d.get('equipment_finger_02'),
                legs=d.get('equipment_legs'),
                foots=d.get('equipment_foots'),
            ),

            inventory=list(d.get('inventory') or []),
        )

    def to_dict(self) -> dict:
        """Сериализация в плоский dict (legacy save format).

        Backward compat: тот же набор ключей, что в текущем `char_characteristic`,
        чтобы CSV / Google Sheets продолжали работать без изменений.
        """
        return {
            # Time / day
            'date_last_enter': self.date_last_enter,
            'timestamp_last_enter': self.timestamp_last_enter,

            # Steps
            'steps_today': self.steps.today,
            'steps_can_use': self.steps.can_use,
            'steps_today_used': self.steps.used,
            'steps_yesterday': self.steps.yesterday,
            'steps_daily_bonus': self.steps.daily_bonus,
            'steps_total_used': self.steps.total_used,

            # Char level
            'char_level': self.char_level.level,
            'char_level_up_skills': self.char_level.up_skills,
            'lvl_up_skill_stamina': self.char_level.skill_stamina,
            'lvl_up_skill_energy_max': self.char_level.skill_energy_max,
            'lvl_up_skill_speed': self.char_level.skill_speed,
            'lvl_up_skill_luck': self.char_level.skill_luck,

            # Resources
            'loc': self.loc,
            'energy': self.energy,
            'energy_max': self.energy_max,
            'energy_time_stamp': self.energy_time_stamp,
            'money': self.money,

            # Training session
            'skill_training': self.training.active,
            'skill_training_name': self.training.skill_name,
            'skill_training_timestamp': self.training.timestamp,
            'skill_training_time_end': self.training.time_end,

            # Gym skills
            'stamina': self.gym.stamina,
            'energy_max_skill': self.gym.energy_max_skill,
            'speed_skill': self.gym.speed_skill,
            'luck_skill': self.gym.luck_skill,
            'neatness_in_using_things': self.gym.neatness_in_using_things,
            'mechanics': self.gym.mechanics,
            'it_technologies': self.gym.it_technologies,

            # Move optimization
            'move_optimization_adventure': self.gym.move_optimization_adventure,
            'move_optimization_gym': self.gym.move_optimization_gym,
            'move_optimization_work': self.gym.move_optimization_work,

            # Work session
            'work': self.work.work_type,
            'work_salary': self.work.salary,
            'working': self.work.active,
            'working_hours': self.work.hours,
            'working_start': self.work.start,
            'working_end': self.work.end,

            # Inventory
            'inventory': self.inventory,

            # Equipment
            'equipment_head': self.equipment.head,
            'equipment_neck': self.equipment.neck,
            'equipment_torso': self.equipment.torso,
            'equipment_finger_01': self.equipment.finger_01,
            'equipment_finger_02': self.equipment.finger_02,
            'equipment_legs': self.equipment.legs,
            'equipment_foots': self.equipment.foots,

            # Adventure session
            'adventure': self.adventure.active,
            'adventure_name': self.adventure.name,
            'adventure_start_timestamp': self.adventure.start_ts,
            'adventure_end_timestamp': self.adventure.end_ts,

            # Adventure counters
            'adventure_walk_easy_counter': self.adventure.counters.get('walk_easy', 0),
            'adventure_walk_normal_counter': self.adventure.counters.get('walk_normal', 0),
            'adventure_walk_hard_counter': self.adventure.counters.get('walk_hard', 0),
            'adventure_walk_15k_counter': self.adventure.counters.get('walk_15k', 0),
            'adventure_walk_20k_counter': self.adventure.counters.get('walk_20k', 0),
            'adventure_walk_25k_counter': self.adventure.counters.get('walk_25k', 0),
            'adventure_walk_30k_counter': self.adventure.counters.get('walk_30k', 0),
        }


# ----------------------------------------------------------------------------
# CharCharacteristicProxy — backward-compat proxy для legacy кода.
#
# Во время миграции (Phase 2-4 задачи 1.1) старые модули продолжают делать
# `from characteristics import char_characteristic` и обращаться к нему как
# к dict (`char_characteristic['energy']`). Прокси преобразует такие обращения
# в чтение/запись соответствующих nested-полей `GameState`.
#
# Удаляется в Phase 5, когда все модули мигрированы на прямой доступ к state.
# ----------------------------------------------------------------------------


# Маппинг legacy flat-ключей → путь в nested GameState.
# Каждый путь — кортеж имён атрибутов от корня state до листа.
_KEY_MAP: dict[str, tuple[str, ...]] = {
    # Time / day
    'date_last_enter': ('date_last_enter',),
    'timestamp_last_enter': ('timestamp_last_enter',),

    # Steps
    'steps_today': ('steps', 'today'),
    'steps_today_used': ('steps', 'used'),
    'steps_yesterday': ('steps', 'yesterday'),
    'steps_total_used': ('steps', 'total_used'),
    'steps_can_use': ('steps', 'can_use'),
    'steps_daily_bonus': ('steps', 'daily_bonus'),

    # Char level
    'char_level': ('char_level', 'level'),
    'char_level_up_skills': ('char_level', 'up_skills'),
    'lvl_up_skill_stamina': ('char_level', 'skill_stamina'),
    'lvl_up_skill_energy_max': ('char_level', 'skill_energy_max'),
    'lvl_up_skill_speed': ('char_level', 'skill_speed'),
    'lvl_up_skill_luck': ('char_level', 'skill_luck'),

    # Resources
    'loc': ('loc',),
    'energy': ('energy',),
    'energy_max': ('energy_max',),
    'energy_time_stamp': ('energy_time_stamp',),
    'money': ('money',),

    # Training session
    'skill_training': ('training', 'active'),
    'skill_training_name': ('training', 'skill_name'),
    'skill_training_timestamp': ('training', 'timestamp'),
    'skill_training_time_end': ('training', 'time_end'),

    # Gym skills
    'stamina': ('gym', 'stamina'),
    'energy_max_skill': ('gym', 'energy_max_skill'),
    'speed_skill': ('gym', 'speed_skill'),
    'luck_skill': ('gym', 'luck_skill'),
    'neatness_in_using_things': ('gym', 'neatness_in_using_things'),
    'mechanics': ('gym', 'mechanics'),
    'it_technologies': ('gym', 'it_technologies'),
    'move_optimization_adventure': ('gym', 'move_optimization_adventure'),
    'move_optimization_gym': ('gym', 'move_optimization_gym'),
    'move_optimization_work': ('gym', 'move_optimization_work'),

    # Work session
    'work': ('work', 'work_type'),
    'work_salary': ('work', 'salary'),
    'working': ('work', 'active'),
    'working_hours': ('work', 'hours'),
    'working_start': ('work', 'start'),
    'working_end': ('work', 'end'),

    # Inventory
    'inventory': ('inventory',),

    # Equipment
    'equipment_head': ('equipment', 'head'),
    'equipment_neck': ('equipment', 'neck'),
    'equipment_torso': ('equipment', 'torso'),
    'equipment_finger_01': ('equipment', 'finger_01'),
    'equipment_finger_02': ('equipment', 'finger_02'),
    'equipment_legs': ('equipment', 'legs'),
    'equipment_foots': ('equipment', 'foots'),

    # Adventure session
    'adventure': ('adventure', 'active'),
    'adventure_name': ('adventure', 'name'),
    'adventure_start_timestamp': ('adventure', 'start_ts'),
    'adventure_end_timestamp': ('adventure', 'end_ts'),
}

# Adventure counters живут в dict внутри AdventureSession — отдельный mapping
# через 'counters' атрибут + ключ counters dict.
_ADVENTURE_COUNTER_KEYS: dict[str, str] = {
    'adventure_walk_easy_counter': 'walk_easy',
    'adventure_walk_normal_counter': 'walk_normal',
    'adventure_walk_hard_counter': 'walk_hard',
    'adventure_walk_15k_counter': 'walk_15k',
    'adventure_walk_20k_counter': 'walk_20k',
    'adventure_walk_25k_counter': 'walk_25k',
    'adventure_walk_30k_counter': 'walk_30k',
}


class CharCharacteristicProxy:
    """Прокси-обёртка над `GameState`, имитирующая старый dict.

    Поддерживает chunk legacy-операций: `proxy[key]`, `proxy[key] = value`,
    `key in proxy`, `proxy.get(key, default)`, `proxy.update(d)`, `proxy.keys()`.

    Внутри обращения транслируются в чтение/запись nested-полей через `_KEY_MAP`.
    """

    def __init__(self, state: GameState):
        self._state = state

    # ----- Read access -----

    def __getitem__(self, key):
        if key in _KEY_MAP:
            path = _KEY_MAP[key]
            obj = self._state
            for attr in path:
                obj = getattr(obj, attr)
            return obj
        if key in _ADVENTURE_COUNTER_KEYS:
            counter_key = _ADVENTURE_COUNTER_KEYS[key]
            return self._state.adventure.counters.get(counter_key, 0)
        raise KeyError(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key) -> bool:
        return key in _KEY_MAP or key in _ADVENTURE_COUNTER_KEYS

    def keys(self):
        return list(_KEY_MAP.keys()) + list(_ADVENTURE_COUNTER_KEYS.keys())

    def items(self):
        for k in self.keys():
            yield k, self[k]

    def values(self):
        for k in self.keys():
            yield self[k]

    # ----- Write access -----

    def __setitem__(self, key, value):
        if key in _KEY_MAP:
            path = _KEY_MAP[key]
            # path всегда имеет хотя бы 1 элемент
            obj = self._state
            for attr in path[:-1]:
                obj = getattr(obj, attr)
            setattr(obj, path[-1], value)
            return
        if key in _ADVENTURE_COUNTER_KEYS:
            counter_key = _ADVENTURE_COUNTER_KEYS[key]
            self._state.adventure.counters[counter_key] = value
            return
        raise KeyError(key)

    def update(self, other):
        """Поддерживает proxy.update({'energy': 30, 'money': 100})
        и proxy.update(other_proxy) — для команды `l` (Load from Cloud)."""
        if hasattr(other, 'items'):
            for k, v in other.items():
                self[k] = v
        else:
            for k, v in other:
                self[k] = v

    def setdefault(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            self[key] = default
            return default

    # ----- Internal access -----

    def _get_state(self) -> GameState:
        """Доступ к underlying GameState (для внутренних модулей во время миграции)."""
        return self._state
