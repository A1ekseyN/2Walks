"""Work — рабочая смена. Выбор вакансии, расчёт часов, финализация по таймеру."""

from datetime import datetime, timedelta
from typing import Optional

from colorama import Fore, Style

from persistence import save_characteristic
from settings import debug_mode
from functions_02 import format_money, time
from equipment_bonus import equipment_speed_skill_bonus
from bonus import apply_earnings_boost, apply_energy_optimization_work, apply_move_optimization_work
from inventory import Wear_Equipped_Items
from actions import try_spend, start_work
from state import GameState


def _speed_bonus_pct(state: GameState) -> int:
    """Сумма speed-бонусов в процентах: skill + equipment + level."""
    return state.gym.speed_skill + equipment_speed_skill_bonus(state) + state.char_level.skill_speed


def _max_work_hours_by_energy(state: GameState, per_hour: int, cap: int = 8) -> int:
    """4.22 (0.2.4j) — Максимальное кол-во часов которое игрок может позволить
    себе по энергии С УЧЁТОМ `apply_energy_optimization_work` (total approach).

    Без этой логики `max_hours = state.energy // per_hour` был бы слишком
    консервативным — игрок не видит что с оптимизацией мог бы взять больше
    часов. Loop по убыванию h от cap до 1, возвращает первое h при котором
    optimized total ≤ state.energy. Дёшево (cap=8 итераций).
    """
    for h in range(cap, 0, -1):
        if apply_energy_optimization_work(per_hour * h, state) <= state.energy:
            return h
    return 0


class Work:
    """Класс для работы — UI выбора + старт сессии."""

    def __init__(self, state: GameState) -> None:
        self._state = state
        self.work_requirements = {
            'watchman': {'steps': apply_move_optimization_work(200, self._state), 'energy': 4, 'salary': 2},
            'factory': {'steps': apply_move_optimization_work(500, self._state), 'energy': 7, 'salary': 5},
            'courier_foot': {'steps': apply_move_optimization_work(1000, self._state), 'energy': 10, 'salary': 10},
            'forwarder': {'steps': apply_move_optimization_work(5000, self._state), 'energy': 30, 'salary': 50},
        }

    def work_choice(self) -> Optional[str]:
        state = self._state
        if state.work.active:
            self.add_working_hours(state.work.work_type)
            return None
        # Цикл retry на невалиде (1.5.1 — 0.2.1h, было: рекурсивный self-call).
        choices = {'1': 'watchman', '2': 'factory', '3': 'courier_foot', '4': 'forwarder'}
        while True:
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
            if working in choices:
                self.ask_hours(choices[working])
                return working
            if working == '0':
                return working
            print('\nВы ввели не правильные данные. Попробуйте еще раз.')

    def ask_hours(self, work: str) -> None:
        state = self._state
        # Цикл retry на невалиде / ValueError (1.5.1 — 0.2.1h).
        while True:
            print(f'\nSteps 🏃: {state.steps.can_use}; Energy 🔋: {state.energy}')
            # 4.23 — apply_earnings_boost для display (state.work.salary остаётся базовой).
            base_salary = self.work_requirements[work]["salary"]
            effective_salary = apply_earnings_boost(base_salary, state)
            print(f'Вы выбрали вакансию: {Fore.GREEN}{work.title()}{Style.RESET_ALL} c зарплатой: {Fore.LIGHTYELLOW_EX}{format_money(effective_salary)}{Style.RESET_ALL} $ в час.')

            work_time_per_hour = round(60 - ((60 / 100) * state.gym.speed_skill + equipment_speed_skill_bonus(state) + state.char_level.skill_speed))
            print(f'Оплата почасовая 🕑: 1 час = {time(work_time_per_hour)}')

            max_hours_by_steps = state.steps.can_use // self.work_requirements[work]['steps']
            # 4.22 (0.2.4j) — max_hours_by_energy теперь учитывает energy_optimization_work
            # (total approach). Loop helper — без него max_hours был бы слишком консервативным.
            per_hour_energy = self.work_requirements[work]['energy']
            max_hours_by_energy = _max_work_hours_by_energy(state, per_hour_energy)
            max_available_hours = min(max_hours_by_steps, max_hours_by_energy, 8)

            # 4.22 — отображение optimized total energy за max_available_hours.
            max_total_energy = apply_energy_optimization_work(max_available_hours * per_hour_energy, state)
            print(f'Max work hours: {Fore.LIGHTBLUE_EX}{max_available_hours}{Style.RESET_ALL} '
                  f'({Fore.LIGHTCYAN_EX}{max_available_hours * self.work_requirements[work]["steps"]}{Style.RESET_ALL} шагов, '
                  f'{Fore.LIGHTGREEN_EX}{max_total_energy}{Style.RESET_ALL} энергии, '
                  f'{Fore.LIGHTYELLOW_EX}{format_money(max_available_hours * effective_salary)}{Style.RESET_ALL} $ заработка).')

            try:
                working_hours = abs(int(input('\nВведите количество рабочих часов: 1 - 8.\n0. Выход.\n>>> ')))
            except ValueError:
                print('\nВы ввели неправильные данные. Попробуйте ещё раз.')
                continue

            if 1 <= working_hours <= max_available_hours:
                self.check_requirements(work, working_hours)
                steps = working_hours * self.work_requirements[work]['steps']
                Wear_Equipped_Items(state).decrease_durability(steps)
                return
            if working_hours == 0:
                self.work_choice()
                return
            print(f'\nНужно ввести число рабочих часов в диапазоне 1 - {max_available_hours}.')

    def add_working_hours(self, work: str) -> None:
        state = self._state
        # 4.23 — apply_earnings_boost для display активной смены.
        effective_salary = apply_earnings_boost(state.work.salary, state)
        print(f'\nПерсонаж на работе. Вы можете добавить несколько рабочих часов.'
              f'\nМесто работы: {Fore.GREEN}{state.work.work_type.title()}{Style.RESET_ALL}, '
              f'в час - {Fore.LIGHTYELLOW_EX}{format_money(effective_salary)}{Style.RESET_ALL} $ '
              f'(💰: + {Fore.LIGHTYELLOW_EX}{format_money(effective_salary * state.work.hours)}{Style.RESET_ALL} $).'
              '\n1. Добавить рабочие часы.'
              '\n0. Назад')
        ask = input('\nДобавить рабочие часы или вернуться обратно? \n>>> ')
        if ask == '1':
            self.ask_hours(work)
        elif ask == '0':
            pass
        else:
            self.work_choice()

    def check_requirements(self, work: str, working_hours: int) -> bool:
        """Атомарно проверяет ресурсы и стартует/продлевает рабочую сессию."""
        state = self._state
        if working_hours < 1:
            return False

        steps_cost = working_hours * self.work_requirements[work]['steps']
        # 4.22 (0.2.4j) — apply_energy_optimization_work на TOTAL (per_hour × hours).
        # Это важно — total approach убирает плато при low-base активностях
        # (watchman 4 эн/ч: per-hour rounding давал бы saving=1 на skill 1-25,
        # total approach даёт линейный saving).
        energy_cost = apply_energy_optimization_work(
            working_hours * self.work_requirements[work]['energy'], state
        )

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
        is_resume = state.work.active
        start_work(
            state,
            work_type=work,
            salary=self.work_requirements[work]['salary'],
            hours=prev_hours + working_hours,
            start=state.work.start if state.work.active else now,
            end=new_end,
        )
        # 4.6 — log_event старт смены / добавление часов.
        from history import log_event
        log_event(
            'work_extend' if is_resume else 'work_start',
            vacancy=work,
            added_hours=working_hours,
            total_hours=prev_hours + working_hours,
            salary_per_hour=self.work_requirements[work]['salary'],
            cost_steps=steps_cost,
            cost_energy=energy_cost,
        )

        print(f'\nИспользовано 🏃: {Fore.LIGHTCYAN_EX}{steps_cost}{Style.RESET_ALL} + '
              f'🔋: {Fore.GREEN}{energy_cost}{Style.RESET_ALL}.')
        print(f'Время работы 🕑: {time(working_hours * (round(60 - ((60 / 100) * state.gym.speed_skill + equipment_speed_skill_bonus(state)))))}')
        # 4.23 — preview зарплаты с earnings_boost.
        effective_salary = apply_earnings_boost(state.work.salary, state)
        print(f'Зарплата 💰: {Fore.LIGHTYELLOW_EX}{format_money(working_hours * effective_salary)}{Style.RESET_ALL} $.')
        return True


def work_check_done(state: GameState) -> GameState:
    """Финализатор работы по таймеру: атомарно начислить зарплату + save.

    4.48.5.1 (0.2.5a): atomic save-first pattern. Tentative mutate в RAM →
    save_characteristic → если STALE → rollback RAM (claim отменён, фрешный
    state придёт с Sheets через STALE response в web / handle_stale_prompt
    в CLI). Если save OK → claim подтверждён, log_event фаерится.

    Закрывает double-claim race: claim попадает в money ТОЛЬКО если Sheets
    save прошёл успешно. Web restart до сохранения = в Sheets state.work
    остаётся active → на reload web попробует финализировать заново, но это
    будет ПЕРВЫЙ commit (никакого double).

    Возвращает state (мутированный или нет) — для удобной chain-композиции.
    """
    if state.work.end is None:
        return state

    now = datetime.fromtimestamp(datetime.now().timestamp())
    if debug_mode and state.work.end >= now:
        print('\n--- Персонаж на работе ---.')

    if state.work.end <= now:
        # 4.23 — earnings_boost: state.work.salary базовая, итог считается через
        # apply_earnings_boost (recompute — учитывает текущий уровень skill,
        # даже если он был прокачан во время смены).
        base_salary = state.work.salary
        effective_salary = apply_earnings_boost(base_salary, state)
        earned = effective_salary * state.work.hours
        finished_vacancy = state.work.work_type
        finished_hours = state.work.hours

        # 4.48.5.1: snapshot для rollback при STALE.
        snap = (
            state.money,
            state.work.work_type,
            state.work.salary,
            state.work.active,
            state.work.hours,
            state.work.start,
            state.work.end,
        )

        # Tentative mutate.
        state.money += earned
        state.work.work_type = None
        state.work.salary = 0
        state.work.active = False
        state.work.hours = 0
        state.work.start = None
        state.work.end = None

        # Commit в Sheets.
        status = save_characteristic()
        if status == "STALE":
            # Rollback — claim не подтверждён. На следующем reload (через
            # STALE response в web или handle_stale_prompt в CLI) фрешный
            # state с Sheets придёт с уже-финализированной сменой (если
            # CLI/другой web успел) — там money уже зачислен другим финализатором.
            (state.money, state.work.work_type, state.work.salary,
             state.work.active, state.work.hours, state.work.start,
             state.work.end) = snap
            state.finalize_stale = True
            print('[work finalize] STALE — claim откатан, fresh reload подтянет state.')
            return state

        # Commit подтверждён — фаерим log_event + печатаем для CLI.
        print(f'\n🏭 Вы закончили работу и заработали: {Fore.LIGHTYELLOW_EX}{format_money(earned)}{Style.RESET_ALL} $.')
        # 4.62.1.5.1 — Iron Worker triumph (metric-based). Обновляем
        # state.work.longest_shift_hours = max(current, this shift) ПЕРЕД
        # log_event чтобы register_event auto-hook увидел свежее значение и
        # unlock'нул tier сразу (а не на следующем event'е).
        if finished_hours > state.work.longest_shift_hours:
            state.work.longest_shift_hours = finished_hours
        # 4.6 — log_event завершения смены. salary = итоговая (с bonus),
        # salary_base = базовая (без bonus) — для отладки.
        from history import log_event
        log_event('work_done', vacancy=finished_vacancy, hours=finished_hours,
                  salary=round(earned, 2), salary_base=base_salary,
                  earnings_boost_pct=state.gym.earnings_boost)
        # 4.48.12 — web-уведомление о завершении смены (после OK commit'а).
        state.push_session_event('work_done', vacancy=finished_vacancy,
                                 hours=finished_hours, earned=round(earned, 2))
    return state
