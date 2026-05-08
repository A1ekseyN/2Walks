"""GameState — типизированное игровое состояние.

Корневая структура состояния игры. Заменила module-level dict `char_characteristic`
(задача 1.1, завершено в Phase 5). Связанные данные сгруппированы в nested
подклассы (StepsState, CharLevel, GymSkills, TrainingSession, WorkSession,
AdventureSession, Equipment).

Save format CSV / Google Sheets остаётся неизменным: `to_dict()` возвращает
плоский dict с прежними именами ключей. `from_dict()` принимает такой же
плоский dict и собирает в nested структуру. `update_from_dict()` мутирует
существующий instance (используется для Load from Cloud, чтобы импортёры,
держащие ссылку на game_state, видели свежие данные).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


# Формат datetime в CSV save (тот же, что в characteristics.py:load_characteristic).
_DATETIME_FMT = '%Y-%m-%d %H:%M:%S.%f'


def _deser_datetime(v: Any) -> Optional[datetime]:
    """Толерантная конвертация в datetime.

    Принимает datetime / str (legacy CSV format) / None / любой другой тип.
    Возвращает datetime или None при невалидном вводе.
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
    xp_bonus: float = 0.0   # 4.27 — bonus accumulator от skill 'inspiration' (forward-only)


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
    banking_interest_rate: int = 0       # 4.49 — bonus к ставке депозита (+1%/level)
    loan_capacity: int = 0               # 4.49 — +100 $ к максимальной сумме кредита (default 0 → нельзя взять)
    loan_interest_reduction: int = 0     # 4.49 — снижение ставки кредита (-1%/level от базовых 100%)
    inspiration: int = 0                 # 4.27 — +1%/level к XP за каждый потраченный шаг (forward-only multiplier)
    money_saving: int = 0                # 4.20 — -1%/level к денежным тратам (Gym training + Shop). Линейный, на lvl=100 цена становится 0
    earnings_boost: int = 0              # 4.23 — +1%/level к зарплате (только Work). Линейный без cap, на lvl=100 удвоение дохода
    backpack_skill: int = 0              # 4.50 — +1 слот к инвентарю за уровень. Base = 10, cap = 10 + skill


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
    end_ts: Optional[float] = None          # was adventure_end_timestamp — float Unix ts
    counters: dict[str, int] = field(default_factory=lambda: {
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
class BankState:
    """Состояние банковских операций (4.49).

    Депозит (Phase 0.1, 4.49.0.1):
      - `deposit_amount` — float (тело + капитализированные проценты).
      - `deposit_last_interest_ts` — Unix timestamp последней капитализации.
        Обнуляется в None при полном снятии депозита.

    Кредит (Phase 4, 4.49.2.1):
      - `loan_amount` — float (тело + капитализированные проценты).
      - `loan_last_interest_ts` — Unix timestamp последней капитализации
        долга. Обнуляется в None при полном погашении.

    Auto-repay toggle (Phase 5, 4.49.2.2) — будет добавлен позже.
    """
    deposit_amount: float = 0.0
    deposit_last_interest_ts: Optional[float] = None
    loan_amount: float = 0.0
    loan_last_interest_ts: Optional[float] = None


@dataclass
class GameState:
    # Time / day
    date_last_enter: str = ''
    timestamp_last_enter: float = 0.0

    # Resources
    energy: int = 50
    energy_max: int = 50
    money: float = 0.0    # 4.49 — float чтобы поддержать копейки на кошельке (после Снять всё)
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
    bank: BankState = field(default_factory=BankState)
    # Item dicts имеют структуру {item_name: [str], bonus: [int], ...} (списки в
    # полях — legacy decision). Полная типизация TypedDict откладывается до
    # задачи 1.6 (Items as dataclass) — сейчас только `list[dict]`.
    inventory: list[dict] = field(default_factory=list)
    # 4.50.1 — Если рюкзак был полон в момент Adventure drop'а, новая находка
    # перемещается сюда вместо потери. Игрок resolve'ит через `inventory_menu`:
    # продать существующий → положить новый, или продать новый, или skip
    # (pending остаётся). Auto-collect'ится при освобождении слота.
    # Всегда `Optional[dict]`, не list — одновременно может быть только ОДИН
    # pending; новые drop'ы при active pending уходят в forced-sale (money +=
    # base price). Round-trip через flat-key 'pending_drop' (None для legacy).
    pending_drop: Optional[dict] = None

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
            money=float(d.get('money', 0) or 0),
            energy_time_stamp=float(d.get('energy_time_stamp') or 0.0),
            loc=d.get('loc', 'home') or 'home',

            steps=StepsState(
                today=int(d.get('steps_today', 0)),
                used=int(d.get('steps_today_used', 0)),
                yesterday=int(d.get('steps_yesterday', 0)),
                total_used=int(d.get('steps_total_used', 0)),
                can_use=int(d.get('steps_can_use', 0)),
                daily_bonus=int(d.get('steps_daily_bonus', 0)),
                xp_bonus=float(d.get('steps_xp_bonus') or 0.0),
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
                banking_interest_rate=int(d.get('banking_interest_rate', 0)),
                loan_capacity=int(d.get('loan_capacity', 0)),
                loan_interest_reduction=int(d.get('loan_interest_reduction', 0)),
                inspiration=int(d.get('inspiration', 0)),
                money_saving=int(d.get('money_saving', 0)),
                earnings_boost=int(d.get('earnings_boost', 0)),
                backpack_skill=int(d.get('backpack_skill', 0)),
            ),

            training=TrainingSession(
                active=bool(d.get('skill_training', False)),
                # Legacy migration (4.48.4.1 / 0.2.1g): старый ключ 'energy_max'
                # заменён на 'energy_max_skill' для соответствия field-name в
                # state.gym. Если в сейве лежит старый ключ — конвертируем при
                # загрузке. Поломанный flow (AttributeError на старте/finalize)
                # не активен — никто не успел запустить тренировку с этим ключом.
                skill_name=('energy_max_skill' if d.get('skill_training_name') == 'energy_max'
                            else d.get('skill_training_name')),
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
                # 5.6.1 (0.2.1u): end_ts — Optional[float] Unix timestamp (раньше
                # был объявлен Optional[datetime] и через _deser_datetime, что
                # некорректно конвертировало float→None). Save format всегда был
                # float, теперь тип совпадает.
                end_ts=d.get('adventure_end_timestamp'),
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

            # Bank (4.49.0.0 / 4.49.2.1). Старые сейвы без bank-keys → defaults BankState().
            # `*_last_interest_ts` хранится как Optional[float] Unix ts — читаем
            # напрямую без _deser_datetime (по аналогии с adventure end_ts).
            bank=BankState(
                deposit_amount=float(d.get('bank_deposit_amount') or 0.0),
                deposit_last_interest_ts=d.get('bank_deposit_last_interest_ts'),
                loan_amount=float(d.get('bank_loan_amount') or 0.0),
                loan_last_interest_ts=d.get('bank_loan_last_interest_ts'),
            ),

            inventory=list(d.get('inventory') or []),
            # 4.50.1 — Pending drop. None для сейвов до 0.2.4c, dict иначе.
            pending_drop=d.get('pending_drop') or None,
        )

    def update_from_dict(self, d: dict) -> "GameState":
        """Обновляет nested-поля по flat dict, не создавая новый instance.

        Используется для Load from Cloud: импортёры удерживают ссылку на
        `game_state`, поэтому пересоздание объекта осиротит их. Этот метод
        мутирует self in-place. Возвращает self для удобства.
        """
        new = GameState.from_dict(d)
        self.date_last_enter = new.date_last_enter
        self.timestamp_last_enter = new.timestamp_last_enter
        self.energy = new.energy
        self.energy_max = new.energy_max
        self.money = new.money
        self.energy_time_stamp = new.energy_time_stamp
        self.loc = new.loc
        self.steps = new.steps
        self.char_level = new.char_level
        self.gym = new.gym
        self.training = new.training
        self.work = new.work
        self.adventure = new.adventure
        self.equipment = new.equipment
        self.bank = new.bank
        self.inventory = new.inventory
        self.pending_drop = new.pending_drop
        return self

    def to_dict(self) -> dict:
        """Сериализация в плоский dict (legacy save format).

        Тот же набор ключей, что у CSV / Google Sheets — формат сейва не меняется.
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
            'steps_xp_bonus': self.steps.xp_bonus,

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
            'banking_interest_rate': self.gym.banking_interest_rate,
            'loan_capacity': self.gym.loan_capacity,
            'loan_interest_reduction': self.gym.loan_interest_reduction,
            'inspiration': self.gym.inspiration,
            'money_saving': self.gym.money_saving,
            'earnings_boost': self.gym.earnings_boost,
            'backpack_skill': self.gym.backpack_skill,

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
            # 4.50.1 — Pending drop (full inventory at drop time). None если нет
            # активной находки на resolve. Сериализуется как dict (item-формат)
            # или None — round-trip-симметрично с from_dict.
            'pending_drop': self.pending_drop,

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

            # Bank (4.49.0.0 / 4.49.2.1)
            'bank_deposit_amount': self.bank.deposit_amount,
            'bank_deposit_last_interest_ts': self.bank.deposit_last_interest_ts,
            'bank_loan_amount': self.bank.loan_amount,
            'bank_loan_last_interest_ts': self.bank.loan_last_interest_ts,
        }
