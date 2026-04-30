"""Work — рабочая смена. Выбор вакансии, расчёт часов, финализация по таймеру.

Phase 4 задачи 1.1: всё через `state: GameState` (default `state=None` →
characteristics.game_state). Work() принимает state (или дефолт), а не legacy
char_characteristic.
"""

from datetime import datetime, timedelta
from colorama import Fore, Style

from characteristics import save_characteristic
from settings import debug_mode
from functions_02 import time
from equipment_bonus import equipment_speed_skill_bonus
from bonus import apply_move_optimization_work
from inventory import Wear_Equipped_Items
from actions import try_spend, start_work
from state import GameState


def _resolve_state(state):
    if state is None:
        from characteristics import game_state
        return game_state
    # Legacy callers (locations.py) могут передать proxy.
    if hasattr(state, '_get_state'):
        return state._get_state()
    return state


def _speed_bonus_pct(state: GameState) -> int:
    """Сумма speed-бонусов в процентах: skill + equipment + level."""
    return state.gym.speed_skill + equipment_speed_skill_bonus(state) + state.char_level.skill_speed


class Work:
    """Класс для работы — UI выбора + старт сессии."""

    def __init__(self, state=None):
        self._state = _resolve_state(state)
        self.work_requirements = {
            'watchman': {'steps': apply_move_optimization_work(200, self._state), 'energy': 4, 'salary': 2},
            'factory': {'steps': apply_move_optimization_work(500, self._state), 'energy': 7, 'salary': 5},
            'courier_foot': {'steps': apply_move_optimization_work(1000, self._state), 'energy': 10, 'salary': 10},
            'forwarder': {'steps': apply_move_optimization_work(5000, self._state), 'energy': 30, 'salary': 50},
        }

    def work_choice(self):
        state = self._state
        if not state.work.active:
            print('\n--- 🏭 Work Location 🏭 ---')
            print(f'\nSteps 🏃: {state.steps.can_use}; Energy 🔋: {state.energy}')
            hour_time = round(60 - ((60 / 100) * state.gym.speed_skill + equipment_speed_skill_bonus(state) + state.char_level.skill_speed))
            print(f'В этой локации можно устроится на работу. '
                  f'\nОплата почасовая 🕑: 1 час = {time(hour_time)}')
            print('\nНа данный момент доступны вакансии:'
                  f'\n\t1. Сторож     - 💰: {Fore.LIGHTYELLOW_EX}2{Style.RESET_ALL} $ (🏃: {self.work_requirements["watchman"]["steps"]} + 🔋: 4)'
                  f'\n\t2. Завод      - 💰: {Fore.LIGHTYELLOW_EX}5{Style.RESET_ALL} $ (🏃: {self.work_requirements["factory"]["steps"]} + 🔋: 7)'
                  f'\n\t3. Курьер     - 💰: {Fore.LIGHTYELLOW_EX}10{Style.RESET_ALL} $ (🏃: {self.work_requirements["courier_foot"]["steps"]} + 🔋: 10)'
                  f'\n\t4. Экспедитор - 💰: {Fore.LIGHTYELLOW_EX}50{Style.RESET_ALL} $ (🏃: {self.work_requirements["forwarder"]["steps"]} + 🔋: 50)'
                  '\n\t0. Вернуться назад.')
            working = input('\nВыберите вакансию, или вернитесь обратно:\n>>> ')
            choices = {'1': 'watchman', '2': 'factory', '3': 'courier_foot', '4': 'forwarder'}
            if working in choices:
                self.ask_hours(choices[working])
            elif working == '0':
                pass
            else:
                print('\nВы ввели не правильные данные. Попробуйте еще раз.')
                self.work_choice()
            return working
        else:
            self.add_working_hours(state.work.work_type)

    def ask_hours(self, work):
        state = self._state
        try:
            print(f'\nSteps 🏃: {state.steps.can_use}; Energy 🔋: {state.energy}')
            print(f'Вы выбрали вакансию: {Fore.GREEN}{work.title()}{Style.RESET_ALL} c зарплатой: {Fore.LIGHTYELLOW_EX}{self.work_requirements[work]["salary"]}{Style.RESET_ALL} $ в час.')

            work_time_per_hour = round(60 - ((60 / 100) * state.gym.speed_skill + equipment_speed_skill_bonus(state) + state.char_level.skill_speed))
            print(f'Оплата почасовая 🕑: 1 час = {time(work_time_per_hour)}')

            max_hours_by_steps = state.steps.can_use // self.work_requirements[work]['steps']
            max_hours_by_energy = state.energy // self.work_requirements[work]['energy']
            max_available_hours = min(max_hours_by_steps, max_hours_by_energy, 8)

            print(f'Max work hours: {Fore.LIGHTBLUE_EX}{max_available_hours}{Style.RESET_ALL} '
                  f'({Fore.LIGHTCYAN_EX}{max_available_hours * self.work_requirements[work]["steps"]}{Style.RESET_ALL} шагов, '
                  f'{Fore.LIGHTGREEN_EX}{max_available_hours * self.work_requirements[work]["energy"]}{Style.RESET_ALL} энергии, '
                  f'{Fore.LIGHTYELLOW_EX}{max_available_hours * self.work_requirements[work]["salary"]}{Style.RESET_ALL} $ заработка).')

            working_hours = abs(int(input('\nВведите количество рабочих часов: 1 - 8.\n0. Выход.\n>>> ')))
            if 1 <= working_hours <= max_available_hours:
                self.check_requirements(work, working_hours)
                steps = working_hours * self.work_requirements[work]['steps']
                Wear_Equipped_Items(state).decrease_durability(steps)
            elif working_hours == 0:
                self.work_choice()
            else:
                print(f'\nНужно ввести число рабочих часов в диапазоне 1 - {max_available_hours}.')
                self.ask_hours(work)
        except ValueError:
            print('\nВы ввели неправильные данные. Попробуйте ещё раз.')
            self.ask_hours(work)

    def add_working_hours(self, work):
        state = self._state
        print(f'\nПерсонаж на работе. Вы можете добавить несколько рабочих часов.'
              f'\nМесто работы: {Fore.GREEN}{state.work.work_type.title()}{Style.RESET_ALL}, '
              f'в час - {Fore.LIGHTYELLOW_EX}{state.work.salary}{Style.RESET_ALL} $ '
              f'(💰: + {Fore.LIGHTYELLOW_EX}{state.work.salary * state.work.hours}{Style.RESET_ALL} $).'
              '\n1. Добавить рабочие часы.'
              '\n0. Назад')
        ask = input('\nДобавить рабочие часы или вернуться обратно? \n>>> ')
        if ask == '1':
            self.ask_hours(work)
        elif ask == '0':
            pass
        else:
            self.work_choice()

    def check_requirements(self, work, working_hours):
        """Атомарно проверяет ресурсы и стартует/продлевает рабочую сессию."""
        state = self._state
        if working_hours < 1:
            return False

        steps_cost = working_hours * self.work_requirements[work]['steps']
        energy_cost = working_hours * self.work_requirements[work]['energy']

        if not try_spend(state, steps=steps_cost, energy=energy_cost):
            print('\nДописать функционал, который показывает, чего именно не хватило. Можно использовать метод класса.')
            print('Не достаточно: 🏃 или 🔋')
            return False

        # Подсчёт нового времени окончания смены с учётом уже накопленного.
        now = datetime.now()
        current_end = state.work.end
        if current_end is not None:
            if isinstance(current_end, (int, float)):
                current_end = datetime.fromtimestamp(current_end)
            remaining = current_end - now
            if remaining < timedelta(0):
                remaining = timedelta(0)
        else:
            remaining = timedelta(0)

        raw_duration = timedelta(minutes=working_hours * 60)
        bonus_pct = _speed_bonus_pct(state)
        adjusted_duration = raw_duration - (raw_duration * bonus_pct / 100)
        new_end = now + remaining + adjusted_duration

        # state.work уже могла быть активна — сохраняем накопленные hours.
        prev_hours = state.work.hours if state.work.active else 0
        start_work(
            state,
            work_type=work,
            salary=self.work_requirements[work]['salary'],
            hours=prev_hours + working_hours,
            start=state.work.start if state.work.active else now,
            end=new_end,
        )

        print(f'\nИспользовано 🏃: {Fore.LIGHTCYAN_EX}{steps_cost}{Style.RESET_ALL} + '
              f'🔋: {Fore.GREEN}{energy_cost}{Style.RESET_ALL}.')
        print(f'Время работы 🕑: {time(working_hours * (round(60 - ((60 / 100) * state.gym.speed_skill + equipment_speed_skill_bonus(state)))))}')
        print(f'Зарплата 💰: {Fore.LIGHTYELLOW_EX}{working_hours * state.work.salary}{Style.RESET_ALL} $.')
        return True


def work_check_done(state: GameState = None):
    """Финализатор работы по таймеру: начислить зарплату, обнулить смену, save."""
    state = _resolve_state(state)

    if state.work.end is None:
        return state

    now = datetime.fromtimestamp(datetime.now().timestamp())
    if debug_mode and state.work.end >= now:
        print('\n--- Персонаж на работе ---.')

    if state.work.end <= now:
        earned = state.work.salary * state.work.hours
        state.money += earned
        print(f'\n🏭 Вы закончили работу и заработали: {Fore.LIGHTYELLOW_EX}{earned}{Style.RESET_ALL} $.')
        state.work.work_type = None
        state.work.salary = 0
        state.work.active = False
        state.work.hours = 0
        state.work.start = None
        state.work.end = None
        save_characteristic()
    return state
