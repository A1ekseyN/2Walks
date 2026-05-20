"""Gym — прокачка навыков. UI + старт/финализация тренировки."""

from datetime import datetime
from typing import Optional

from colorama import Fore, Style

from persistence import save_characteristic
from skill_training_data import skill_training_table, get_energy_training_data
from settings import debug_mode
from skill_bonus import stamina_skill_bonus_def
from functions_02 import format_money, time
from equipment_bonus import equipment_speed_skill_bonus
from bonus import apply_energy_optimization_gym, apply_money_saving, apply_move_optimization_gym
from inventory import Wear_Equipped_Items
from actions import try_spend, start_training as actions_start_training
from state import GameState


# ----- Чистые helper-функции расчёта (тестируются напрямую) -----

def _next_skill_level(state: GameState, skill_name: str) -> int:
    """Уровень, до которого мы прокачиваем навык. Все 8 навыков теперь
    единообразно — `state.gym.<skill_name> + 1` (после унификации в 0.2.1g
    ключ `'energy_max_skill'` тоже соответствует field-name)."""
    # cast(int) — mypy не умеет вывести тип через getattr(..., dynamic name).
    current: int = getattr(state.gym, skill_name)
    return current + 1


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
    money_cost = apply_money_saving(cost["money"], state)
    energy_cost = apply_energy_optimization_gym(cost["energy"], state)
    return (
        f'🏃: {Fore.LIGHTCYAN_EX}{apply_move_optimization_gym(cost["steps"], state):,.0f}{Style.RESET_ALL} / '
        f'🔋: {Fore.GREEN}{energy_cost}{Style.RESET_ALL} эн. / '
        f'💰: {Fore.LIGHTYELLOW_EX}{format_money(money_cost)}{Style.RESET_ALL} $ / '
        f'🕑: {time(round(_apply_speed_bonus(cost["time"], state)))}'
    )


def get_lvl_up_info(skill_name: str, level: int, state: GameState) -> str:
    """Описание стоимости конкретного уровня навыка (используется в меню)."""
    cost = skill_training_table[level]
    money_cost = apply_money_saving(cost["money"], state)
    energy_cost = apply_energy_optimization_gym(cost["energy"], state)
    return (
        f'🏃: {Fore.LIGHTCYAN_EX}{apply_move_optimization_gym(cost["steps"], state):,.0f}{Style.RESET_ALL} / '
        f'🔋: {Fore.GREEN}{energy_cost}{Style.RESET_ALL} эн. / '
        f'💰: {Fore.LIGHTYELLOW_EX}{format_money(money_cost)}{Style.RESET_ALL} $ / '
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
    'energy_regen_skill': (
        'Регенерация энергии',
        'energy_regen_skill',
        'Каждый уровень увеличивает скорость восстановления энергии на 1%. На длительность активностей (работа, тренировки, приключения) не влияет.',
    ),
    'speed_skill': (
        'Скорость',
        'speed_skill',
        'Каждый уровень добавляет + 1% к общей скорости персонажа. Влияет на работу, прокачку навыков, прохождение приключений. На скорость регенерации энергии не влияет (с 0.2.4i — отдельный навык).',
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
    'energy_optimization_adventure': (
        'Экономия энергии в Adventure',
        'energy_optimization_adventure',
        'Каждый уровень уменьшает на 1 % энергозатраты приключений. Минимум 1 эн. Помогает разблокировать высокоуровневые приключения при низком energy_max.',
    ),
    'energy_optimization_gym': (
        'Экономия энергии в Gym',
        'energy_optimization_gym',
        'Каждый уровень уменьшает на 1 % энергозатраты прокачки навыков в Спортзале. Минимум 1 эн. Помогает разблокировать высокоуровневые прокачки.',
    ),
    'energy_optimization_work': (
        'Экономия энергии в Work',
        'energy_optimization_work',
        'Каждый уровень уменьшает на 1 % энергозатраты смены (применяется к total = per_hour × hours). Минимум 1 эн. Позволяет ставить более длинные смены.',
    ),
    'neatness_in_using_things': (
        'Аккуратность при использовании вещей',
        'neatness_in_using_things',
        'Каждый уровень навыка уменьшает износ вещей на 1 %.',
    ),
    'banking_interest_rate': (
        'Банковская ставка',
        'banking_interest_rate',
        'Каждый уровень добавляет +1% к годовой ставке депозита в Банке.',
    ),
    'loan_capacity': (
        'Кредитный лимит',
        'loan_capacity',
        'Каждый уровень добавляет +100 $ к максимальной сумме кредита.',
    ),
    'loan_interest_reduction': (
        'Снижение ставки по кредиту',
        'loan_interest_reduction',
        'Каждый уровень снижает годовую ставку кредита на 1% (от базовых 100%).',
    ),
    'inspiration': (
        'Обучение',
        'inspiration',
        'Каждый уровень добавляет +1% к опыту персонажа за каждый потраченный шаг.',
    ),
    'money_saving': (
        'Экономия денег',
        'money_saving',
        'Каждый уровень снижает стоимость денежных трат на 1% (Спортзал, Магазин). На банковские операции и зарплату не влияет.',
    ),
    'earnings_boost': (
        'Бонус к зарплате',
        'earnings_boost',
        'Каждый уровень добавляет +1% к зарплате на работе. На другие источники денег (продажа предметов) не влияет.',
    ),
    'trader': (
        'Торговец',
        'trader',
        'Каждый уровень добавляет +1% к цене продажи предметов (в т.ч. еда / экипировка из Adventure). Без cap, на lvl=100 удвоение.',
    ),
    'backpack_skill': (
        'Размер инвентаря',
        'backpack_skill',
        'Каждый уровень добавляет +1 слот к рюкзаку. Базовая ёмкость: 10 слотов.',
    ),
}


def display_skill_description(skill_name: str, state: GameState) -> None:
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

def _render_gym_menu(state: GameState, skill_options: dict) -> None:
    """Печать меню Gym (1.5.6 — 0.2.1h, helper для loop'а в gym_menu)."""
    print('\n🏋 --- Вы находитесь в локации - Спортзал. --- 🏋')
    print(f"Steps 🏃: {state.steps.can_use}, Energy 🔋: {state.energy}, Money 💰: {format_money(state.money)} $.")
    print('На данный момент вы можете улучшить: ')
    for key, (skill, name, level) in skill_options.items():
        print(f'\t{key}. {name}{Fore.LIGHTCYAN_EX}{level}{Style.RESET_ALL} lvl ({get_lvl_up_info(skill, level, state)})')
    print('\n\t0. Назад.')


def gym_menu(state: GameState) -> None:
    if state.training.active:
        print('\n🏋 --- Вы находитесь в локации - Спортзал. --- 🏋')
        skill_lvl = getattr(state.gym, state.training.skill_name)
        print(f'\t🏋 Улучшаем навык - {state.training.skill_name.title()} до {Fore.LIGHTCYAN_EX}{skill_lvl + 1}{Style.RESET_ALL} уровня.'
              f'\n\t🕑 Улучшение через: {Fore.CYAN}{state.training.time_end - datetime.fromtimestamp(datetime.now().timestamp())}{Style.RESET_ALL}.')
        return

    skill_options = {
        '1': ('stamina', 'Stamina:                          ',
              state.gym.stamina + 1),
        '2': ('energy_max_skill', 'Energy Max:                       ',
              state.gym.energy_max_skill + 1),
        '3': ('energy_regen_skill', 'Регенерация энергии:              ',
              state.gym.energy_regen_skill + 1),
        '4': ('speed_skill', 'Speed:                            ',
              state.gym.speed_skill + 1),
        '5': ('luck_skill', 'Luck:                             ',
              state.gym.luck_skill + 1),
        '6': ('move_optimization_adventure', 'Оптимизация движений Adventure:   ',
              state.gym.move_optimization_adventure + 1),
        '7': ('move_optimization_gym', 'Оптимизация движений Gym:         ',
              state.gym.move_optimization_gym + 1),
        '8': ('move_optimization_work', 'Оптимизация движений Work:        ',
              state.gym.move_optimization_work + 1),
        '9': ('energy_optimization_adventure', 'Экономия энергии в Adventure:     ',
              state.gym.energy_optimization_adventure + 1),
        '10': ('energy_optimization_gym', 'Экономия энергии в Gym:           ',
               state.gym.energy_optimization_gym + 1),
        '11': ('energy_optimization_work', 'Экономия энергии в Work:          ',
               state.gym.energy_optimization_work + 1),
        '12': ('neatness_in_using_things', 'Аккуратность использования вещей: ',
               state.gym.neatness_in_using_things + 1),
        '13': ('money_saving', 'Экономия денег:                   ',
               state.gym.money_saving + 1),
        '14': ('earnings_boost', 'Бонус к зарплате:                 ',
               state.gym.earnings_boost + 1),
        '15': ('trader', 'Торговец:                         ',
               state.gym.trader + 1),
        '16': ('banking_interest_rate', 'Банковская ставка:                ',
               state.gym.banking_interest_rate + 1),
        '17': ('loan_capacity', 'Кредитный лимит:                  ',
               state.gym.loan_capacity + 1),
        '18': ('loan_interest_reduction', 'Снижение ставки по кредиту:       ',
               state.gym.loan_interest_reduction + 1),
        '19': ('inspiration', 'Обучение:                         ',
               state.gym.inspiration + 1),
        '20': ('backpack_skill', 'Размер инвентаря:                 ',
               state.gym.backpack_skill + 1),
    }

    # Цикл retry на невалиде / отказе от подтверждения (1.5.6 — 0.2.1h, было:
    # рекурсивные self-вызовы + широкий except Exception). Теперь except только
    # на ValueError (фактических ValueError источников нет, но оставлено как
    # narrow safety net на случай регрессии).
    while True:
        _render_gym_menu(state, skill_options)
        try:
            temp_number = input('\nВыберите какой навык улучшить: \n>>> ')
        except ValueError:
            continue

        if temp_number == '0':
            return
        if temp_number not in skill_options:
            continue

        skill_name, skill_display_name, _ = skill_options[temp_number]
        display_skill_description(skill_name, state)

        ask = input(f'\t1. Повысить {skill_display_name.strip()} + 1.'
                    f'\n\t0. Назад\n>>> ')
        if ask != '1':
            continue

        state.training.skill_name = skill_name
        skill_training = Skill_Training(state=state, name=skill_name)

        if skill_training.check_requirements():
            skill_training.start_skill_training()
            steps = apply_move_optimization_gym(skill_training_table[getattr(state.gym, skill_name) + 1]["steps"], state)
            Wear_Equipped_Items(state).decrease_durability(steps)
            return
        # Ресурсов не хватило — check_requirements уже напечатал детали,
        # просто перерисовываем меню (continue).


def skill_training_check_done(state: GameState) -> None:
    """Финализатор тренировки — если таймер истёк, повышает уровень навыка и чистит сессию."""
    if debug_mode and not state.training.active:
        print('\nНавыки не изучаются.')

    if not state.training.active:
        return
    if datetime.fromtimestamp(datetime.now().timestamp()) < state.training.time_end:
        return

    skill_name = state.training.skill_name
    # 4.49.1.2 / 4.49.2.3 (0.2.4z): retro-bonus exploit ОТКРЫТ намеренно —
    # симметрично earnings_boost (4.23). accrue срабатывает только на mutation
    # (top-up / withdraw / take_loan / repay), новая ставка применяется
    # ретроактивно к накопленному времени. Stimulus для прокачки скиллов:
    # «открыл депозит → прокачал → собрал с retro-процентами» / «взял кредит
    # → прокачал reduction → отдал меньше».
    old_level = getattr(state.gym, skill_name)
    new_level = old_level + 1

    # 4.48.5.1 (0.2.5a): atomic save-first pattern. Snapshot для rollback при STALE.
    snap = (
        getattr(state.gym, skill_name),
        state.training.active,
        state.training.skill_name,
        state.training.timestamp,
        state.training.time_end,
    )

    # Tentative mutate.
    setattr(state.gym, skill_name, new_level)
    state.training.active = False
    state.training.skill_name = None
    state.training.timestamp = None
    state.training.time_end = None
    stamina_skill_bonus_def(state)

    # Commit в Sheets.
    status = save_characteristic()
    if status == "STALE":
        # Rollback — skill-up не подтверждён. На reload state с Sheets
        # придёт с уже-прокачанным скиллом (если другой процесс успел) →
        # double-claim не произойдёт.
        setattr(state.gym, skill_name, snap[0])
        state.training.active = snap[1]
        state.training.skill_name = snap[2]
        state.training.timestamp = snap[3]
        state.training.time_end = snap[4]
        stamina_skill_bonus_def(state)
        state.finalize_stale = True
        print('[gym finalize] STALE — skill-up откатан, fresh reload подтянет state.')
        return

    # Commit подтверждён — log_event + печать.
    print(f'\n🏋 Навык {skill_name.title()} улучшен до {new_level}')
    # 4.6 — log_event значимого события прокачки навыка.
    from history import log_event
    log_event('skill_upgraded', skill=skill_name, from_level=old_level, to_level=new_level)


class Skill_Training:
    """Прокачка навыка в Gym — проверка ресурсов, старт сессии."""

    def __init__(self, state: GameState, name: Optional[str] = None) -> None:
        self._state = state
        self.name = name

    def check_requirements(self) -> bool:
        """Проверяет (без списания), хватает ли ресурсов на прокачку.

        Само списание происходит в `start_skill_training` через `try_spend`.
        """
        cost = skill_training_table[getattr(self._state.gym, self.name) + 1]
        steps_needed = apply_move_optimization_gym(cost['steps'], self._state)
        energy_needed = apply_energy_optimization_gym(cost['energy'], self._state)
        money_needed = apply_money_saving(cost['money'], self._state)
        if (self._state.steps.can_use >= steps_needed
                and self._state.energy >= energy_needed
                and self._state.money >= money_needed):
            print('\nПроверка кол-ва шагов, энергии и денег - успешна.')
            return True

        print(f'\n{Fore.RED}У вас не достаточно ресурсов: {Style.RESET_ALL}')
        if self._state.steps.can_use <= steps_needed:
            print(f'\t- 🏃: Не хватает - {steps_needed - self._state.steps.can_use} шагов.')
        if self._state.energy <= energy_needed:
            print(f'\t- 🔋: Не хватает - {energy_needed - self._state.energy} энергии.')
        if self._state.money <= money_needed:
            print(f'\t- 💰: Не хватает - {format_money(money_needed - self._state.money)} money.')
        # Удалён рекурсивный вызов gym_menu(self._state) (1.5.6 — 0.2.1h):
        # с while-loop в gym_menu вызывающий код сам перерисует меню через
        # `continue` при возврате False.
        return False

    def start_skill_training(self) -> GameState:
        state = self._state
        next_level = getattr(state.gym, self.name) + 1
        cost = skill_training_table[next_level]
        steps_needed = apply_move_optimization_gym(cost['steps'], state)
        energy_needed = apply_energy_optimization_gym(cost['energy'], state)
        money_needed = apply_money_saving(cost['money'], state)

        # Атомарное списание steps/energy/money через actions.try_spend.
        # money — float после money_saving discount; try_spend поддерживает float.
        # energy — int после energy_optimization_gym (0.2.4j / task 4.22).
        try_spend(state, steps=steps_needed, energy=energy_needed, money=money_needed)

        # Установка таймера тренировки.
        # base_seconds — int (round * 60), adjusted_seconds — float после
        # speed-бонуса. Разные имена чтобы mypy не ругался на int *= float.
        base_seconds = round(cost['time']) * 60
        adjusted_seconds = _apply_speed_bonus(base_seconds, state)
        time_end = datetime.fromtimestamp(datetime.now().timestamp() + adjusted_seconds)
        actions_start_training(state, skill_name=self.name, time_end=time_end,
                               timestamp=datetime.now().timestamp())
        # 4.6 — log_event старта тренировки.
        from history import log_event
        log_event('skill_train_start', skill=self.name, next_level=next_level,
                  cost_steps=steps_needed, cost_energy=energy_needed,
                  cost_money=money_needed, duration_seconds=int(adjusted_seconds))

        print(f'\n🏋️ {self.name.title()} - Начато улучшение навыка. 🏋')
        print(f'На улучшение навыка {self.name} потрачено:'
              f'\n- 🏃: {steps_needed:,.0f} steps'
              f'\n- 🔋: {energy_needed} эн.'
              f'\n- 💰: {format_money(money_needed)} $'
              f'\n- 🕑 Окончание тренировки навыка через: {Fore.LIGHTBLUE_EX}{time(round(_apply_speed_bonus(cost["time"], state)))}{Style.RESET_ALL}')
        return state
