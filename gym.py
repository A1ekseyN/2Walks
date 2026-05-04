"""Gym — прокачка навыков. UI + старт/финализация тренировки."""

from datetime import datetime
from colorama import Fore, Style

from characteristics import skill_training_table, save_characteristic, get_energy_training_data
from settings import debug_mode
from skill_bonus import stamina_skill_bonus_def
from functions_02 import time
from equipment_bonus import equipment_speed_skill_bonus
from bonus import apply_move_optimization_gym
from inventory import Wear_Equipped_Items
from actions import try_spend, start_training as actions_start_training
from state import GameState


# ----- Чистые helper-функции расчёта (тестируются напрямую) -----

def _next_skill_level(state: GameState, skill_name: str) -> int:
    """Уровень, до которого мы прокачиваем навык. Все 8 навыков теперь
    единообразно — `state.gym.<skill_name> + 1` (после унификации в 0.2.1g
    ключ `'energy_max_skill'` тоже соответствует field-name)."""
    return getattr(state.gym, skill_name) + 1


def _training_cost(state: GameState, skill_name: str) -> dict:
    """Возвращает запись из skill_training_table для следующего уровня навыка.
    `energy_max_skill` тоже идёт через общий путь — `get_energy_training_data`
    оставлен на случай level > 30, но для уровней 1-30 совпадает с
    `skill_training_table`."""
    level = _next_skill_level(state, skill_name)
    if skill_name == 'energy_max_skill':
        return get_energy_training_data(level)
    return skill_training_table[level]


def _apply_speed_bonus(base_minutes: int, state: GameState) -> float:
    """Уменьшает длительность на сумму speed-бонусов (skill + equipment + level), %."""
    speed_pct = (
        state.gym.speed_skill
        + equipment_speed_skill_bonus(state)
        + state.char_level.skill_speed
    )
    return base_minutes - (base_minutes / 100) * speed_pct


# ----- Форматирование описаний навыков (заменяет module-level f-строки) -----

def format_lvl_up_info(state: GameState, skill_name: str) -> str:
    """Описание стоимости прокачки одного навыка для меню Gym.

    Заменяет 8 stale module-level f-строк lvl_up_* — теперь вычисляется в
    момент отображения, видит актуальный state.
    """
    cost = _training_cost(state, skill_name)
    return (
        f'🏃: {Fore.LIGHTCYAN_EX}{apply_move_optimization_gym(cost["steps"], state):,.0f}{Style.RESET_ALL} / '
        f'🔋: {Fore.GREEN}{cost["energy"]}{Style.RESET_ALL} эн. / '
        f'💰: {Fore.LIGHTYELLOW_EX}{cost["money"]}{Style.RESET_ALL} $ / '
        f'🕑: {time(round(_apply_speed_bonus(cost["time"], state)))}'
    )


def get_lvl_up_info(skill_name, level, state: GameState):
    """Описание стоимости конкретного уровня навыка (используется в меню)."""
    cost = skill_training_table[level]
    return (
        f'🏃: {Fore.LIGHTCYAN_EX}{apply_move_optimization_gym(cost["steps"], state):,.0f}{Style.RESET_ALL} / '
        f'🔋: {Fore.GREEN}{cost["energy"]}{Style.RESET_ALL} эн. / '
        f'💰: {Fore.LIGHTYELLOW_EX}{cost["money"]}{Style.RESET_ALL} $ / '
        f'🕑: {time(round(_apply_speed_bonus(cost["time"], state)))}'
    )


_SKILL_DESCRIPTIONS = {
    'stamina': (
        'Выносливость',
        'stamina',
        'Каждый уровень, на 1 % повышает пройденное кол-во шагов на протяжении дня.',
    ),
    'energy_max_skill': (
        'Максимальный запас энергии',
        'energy_max_skill',
        'Каждый уровень, добавляет + 1 единицу к максимальному запасу энергии.',
    ),
    'speed_skill': (
        'Скорость',
        'speed_skill',
        'Каждый уровень добавляет + 1% к общей скорости персонажа. Влияет на работу, прокачку навыков, прохождение приключений.',
    ),
    'luck_skill': (
        'Удача',
        'luck_skill',
        'Каждый уровень улучшения, увеличивается удача персонажа на 1%.\n'
        'Удача влияет на шанс выпадения предметов, а так же на их качество.\n'
        'Так же, удача влияет и на другие игровые события.',
    ),
    'move_optimization_adventure': (
        'Оптимизация движений Adventure',
        'move_optimization_adventure',
        'Каждый уровень уменьшает на 1 % количество шагов необходимых для активности.',
    ),
    'move_optimization_gym': (
        'Оптимизация движений Gym',
        'move_optimization_gym',
        'Каждый уровень уменьшает на 1 % количество шагов необходимых для активности.',
    ),
    'move_optimization_work': (
        'Оптимизация движений Work',
        'move_optimization_work',
        'Каждый уровень уменьшает на 1 % количество шагов необходимых для активности.',
    ),
    'neatness_in_using_things': (
        'Аккуратность при использовании вещей',
        'neatness_in_using_things',
        'Каждый уровень навыка уменьшает износ вещей на 1 %.',
    ),
}


def display_skill_description(skill_name, state: GameState):
    """Печатает описание навыка + стоимость прокачки до следующего уровня."""
    if skill_name not in _SKILL_DESCRIPTIONS:
        return
    title, attr_name, body = _SKILL_DESCRIPTIONS[skill_name]
    current = getattr(state.gym, attr_name)
    cost_line = format_lvl_up_info(state, skill_name)
    print(f'\n{title}: {Fore.GREEN}{current}{Style.RESET_ALL} уровень.')
    print(body)
    if skill_name in ('stamina',):
        print(f'\nДля улучшения до {Fore.GREEN}{current + 1}{Style.RESET_ALL} уровня необходимо: ({cost_line}).')
    else:
        print(f'\nДля улучшения необходимо: ({cost_line}).')


# ----- Меню Gym -----

def gym_menu(state: GameState):
    print('\n🏋 --- Вы находитесь в локации - Спортзал. --- 🏋')

    if state.training.active:
        skill_lvl = getattr(state.gym, state.training.skill_name)
        print(f'\t🏋 Улучшаем навык - {state.training.skill_name.title()} до {Fore.LIGHTCYAN_EX}{skill_lvl + 1}{Style.RESET_ALL} уровня.'
              f'\n\t🕑 Улучшение через: {Fore.CYAN}{state.training.time_end - datetime.fromtimestamp(datetime.now().timestamp())}{Style.RESET_ALL}.')
        return

    skill_options = {
        '1': ('stamina', 'Stamina:    ', state.gym.stamina + 1),
        '2': ('energy_max_skill', 'Energy Max: ', state.gym.energy_max_skill + 1),
        '3': ('speed_skill', 'Speed:      ', state.gym.speed_skill + 1),
        '4': ('luck_skill', 'Luck:       ', state.gym.luck_skill + 1),
        '5': ('move_optimization_adventure', 'Оптимизация движений Adventure:   ',
              state.gym.move_optimization_adventure + 1),
        '6': ('move_optimization_gym', 'Оптимизация движений Gym:         ',
              state.gym.move_optimization_gym + 1),
        '7': ('move_optimization_work', 'Оптимизация движений Work:        ',
              state.gym.move_optimization_work + 1),
        '8': ('neatness_in_using_things', 'Аккуратность использования вещей: ',
              state.gym.neatness_in_using_things + 1),
    }

    print(f"Steps 🏃: {state.steps.can_use}, Energy 🔋: {state.energy}, Money 💰: {state.money} $.")
    print('На данный момент вы можете улучшить: ')
    for key, (skill, name, level) in skill_options.items():
        print(f'\t{key}. {name}{Fore.LIGHTCYAN_EX}{level}{Style.RESET_ALL} lvl ({get_lvl_up_info(skill, level, state)})')
    print('\n\t0. Назад.')

    try:
        temp_number = input('\nВыберите какой навык улучшить: \n>>> ')
        if temp_number == '0':
            return
        if temp_number not in skill_options:
            return gym_menu(state)

        skill_name, skill_display_name, _ = skill_options[temp_number]
        display_skill_description(skill_name, state)

        ask = input(f'\t1. Повысить {skill_display_name.strip()} + 1.'
                    f'\n\t0. Назад\n>>> ')
        if ask != '1':
            return gym_menu(state)

        state.training.skill_name = skill_name
        skill_training = Skill_Training(state=state, name=skill_name)

        if skill_training.check_requirements():
            skill_training.start_skill_training()
            steps = apply_move_optimization_gym(skill_training_table[getattr(state.gym, skill_name) + 1]["steps"], state)
            Wear_Equipped_Items(state).decrease_durability(steps)
        else:
            gym_menu(state)
    except Exception as error:
        print(f'\nОшибка Gym: {error}')
        gym_menu(state)


def skill_training_check_done(state: GameState):
    """Финализатор тренировки — если таймер истёк, повышает уровень навыка и чистит сессию."""
    if debug_mode and not state.training.active:
        print('\nНавыки не изучаются.')

    if not state.training.active:
        return
    if datetime.fromtimestamp(datetime.now().timestamp()) < state.training.time_end:
        return

    skill_name = state.training.skill_name
    new_level = getattr(state.gym, skill_name) + 1
    setattr(state.gym, skill_name, new_level)
    print(f'\n🏋 Навык {skill_name.title()} улучшен до {new_level}')

    state.training.active = False
    state.training.skill_name = None
    state.training.timestamp = None
    state.training.time_end = None
    stamina_skill_bonus_def(state)
    save_characteristic()


class Skill_Training:
    """Прокачка навыка в Gym — проверка ресурсов, старт сессии."""

    def __init__(self, state: GameState, name: str = None):
        self._state = state
        self.name = name

    def check_requirements(self) -> bool:
        """Проверяет (без списания), хватает ли ресурсов на прокачку.

        Само списание происходит в `start_skill_training` через `try_spend`.
        """
        cost = skill_training_table[getattr(self._state.gym, self.name) + 1]
        steps_needed = apply_move_optimization_gym(cost['steps'], self._state)
        if (self._state.steps.can_use >= steps_needed
                and self._state.energy >= cost['energy']
                and self._state.money >= cost['money']):
            print('\nПроверка кол-ва шагов, энергии и денег - успешна.')
            return True

        print(f'\n{Fore.RED}У вас не достаточно ресурсов: {Style.RESET_ALL}')
        if self._state.steps.can_use <= steps_needed:
            print(f'\t- 🏃: Не хватает - {cost["steps"] - self._state.steps.can_use} шагов.')
        if self._state.energy <= cost['energy']:
            print(f'\t- 🔋: Не хватает - {cost["energy"] - self._state.energy} энергии.')
        if self._state.money <= cost['money']:
            print(f'\t- 💰: Не хватает - {cost["money"] - self._state.money} money.')
        gym_menu(self._state)
        return False

    def start_skill_training(self):
        state = self._state
        cost = skill_training_table[getattr(state.gym, self.name) + 1]
        steps_needed = apply_move_optimization_gym(cost['steps'], state)

        # Атомарное списание steps/energy/money через actions.try_spend.
        try_spend(state, steps=steps_needed, energy=cost['energy'], money=cost['money'])

        # Установка таймера тренировки.
        skill_training_time = round(cost['time']) * 60
        skill_training_time = _apply_speed_bonus(skill_training_time, state)
        time_end = datetime.fromtimestamp(datetime.now().timestamp() + skill_training_time)
        actions_start_training(state, skill_name=self.name, time_end=time_end,
                               timestamp=datetime.now().timestamp())

        print(f'\n🏋️ {self.name.title()} - Начато улучшение навыка. 🏋')
        print(f'На улучшение навыка {self.name} потрачено:'
              f'\n- 🏃: {steps_needed:,.0f} steps'
              f'\n- 🔋: {cost["energy"]} эн.'
              f'\n- 💰: {cost["money"]} $'
              f'\n- 🕑 Окончание тренировки навыка через: {Fore.LIGHTBLUE_EX}{time(round(_apply_speed_bonus(cost["time"], state)))}{Style.RESET_ALL}')
        return state
