"""Cross-cutting helpers — energy regen, status_bar, date helpers, ввод шагов.

Phase 4 задачи 1.1: все функции принимают `state: GameState` (default `state=None`
→ fallback на characteristics.game_state для пока-не-мигрированных вызовов из
gym/work/adventure/etc). Шим уйдёт в Phase 5.

UI-функции (status_bar, char_info) тестируются через capsys.
"""

import json
from colorama import Fore, Style
from datetime import datetime, timedelta

from adventure import Adventure
from bonus import equipment_bonus_stamina_steps, daily_steps_bonus, level_steps_bonus
from locations import icon_loc
from settings import debug_mode
from skill_bonus import stamina_skill_bonus_def, speed_skill_equipment_and_level_bonus
from equipment_bonus import equipment_stamina_bonus, equipment_energy_max_bonus, equipment_speed_skill_bonus, equipment_luck_bonus
from level import CharLevel
from state import GameState


def _resolve_state(state):
    if state is None:
        from characteristics import game_state
        return game_state
    return state


def timestamp_now():
    """Возвращает TimeStamp в данный момент. Pure utility, state не требуется."""
    return datetime.now().timestamp()


def energy_time_charge(state: GameState = None):
    """Регенерация энергии во времени. Одна единица каждые
    speed_skill_equipment_and_level_bonus(60) секунд. При достижении
    energy_max регенерация приостанавливается, стамп синкается к now."""
    state = _resolve_state(state)

    now = timestamp_now()
    energy = state.energy
    energy_max = state.energy_max
    interval = speed_skill_equipment_and_level_bonus(60, state)

    if energy >= energy_max:
        # Клэмп излишка (например, после снятия экипировки energy_max уменьшился).
        state.energy = energy_max
        state.energy_time_stamp = now
        return

    elapsed = now - state.energy_time_stamp
    if elapsed < interval:
        return

    points = int(elapsed // interval)
    remainder = elapsed - points * interval
    new_energy = min(energy + points, energy_max)
    state.energy = new_energy

    if new_energy >= energy_max:
        # Добрали до максимума — остаток времени не копим.
        state.energy_time_stamp = now
    else:
        state.energy_time_stamp = now - remainder

    if debug_mode:
        print('\n--- Energy Check ---')
        print(f'Добавлено energy: {new_energy - energy}')
        if new_energy < energy_max:
            print(f'До следующей +1: {interval - remainder:.1f} sec.')


def status_bar(state: GameState = None):
    """Отображение переменных: шагов, энергии, денег."""
    state = _resolve_state(state)
    save_game_date_last_enter(state)  # детект смены дня + пересчёт steps_can_use до любых чтений (см. 2.12)

    char_level_view = CharLevel(state)

    total_bonus = total_bonus_steps(state)
    max_steps = state.steps.today + total_bonus
    bonus_percent = bonus_percentage(state)

    print(f'\nSteps 🏃: {Fore.LIGHTCYAN_EX}{steps(state):,.0f} / {max_steps:,.0f}{Style.RESET_ALL} '
          f'(Bonus: Stamina 🏃: + {Fore.LIGHTCYAN_EX}{stamina_skill_bonus_def(state):,.0f}{Style.RESET_ALL} '
          f'/ Equipment 🏃: + {Fore.LIGHTCYAN_EX}{equipment_bonus_stamina_steps(state):,.0f}{Style.RESET_ALL} '
          f'/ Daily 🏃: {Fore.LIGHTCYAN_EX}{daily_steps_bonus(state)}{Style.RESET_ALL} '
          f'/ Level: {Fore.LIGHTCYAN_EX}{level_steps_bonus(state)}{Style.RESET_ALL}. '
          f'[🏃: {total_bonus:,.0f}, {bonus_percent:.2f} %]) '
          f'(Total steps used 🏃: {Fore.LIGHTCYAN_EX}{format_steps(state.steps.total_used)}{Style.RESET_ALL})'
          f'\nEnergy 🔋: {Fore.GREEN}{state.energy} / {state.energy_max}{Style.RESET_ALL} '
          f'(Bonus: Equipment 🔋: + {Fore.GREEN}{equipment_energy_max_bonus(state)}{Style.RESET_ALL} / '
          f'Daily 🔋: + {Fore.GREEN}{state.steps.daily_bonus}{Style.RESET_ALL} / '
          f'Level: + {Fore.GREEN}{state.char_level.skill_energy_max}{Style.RESET_ALL})', end='')
    if debug_mode:
        print(f'(+ 1 эн. через: {abs(speed_skill_equipment_and_level_bonus(60, state) - (timestamp_now() - state.energy_time_stamp)):,.0f} sec.)', end='')
    print(f'\nMoney 💰: {Fore.LIGHTYELLOW_EX}{state.money:,.0f}{Style.RESET_ALL} $.')

    char_level_view.level_status_bar()

    print(f'Вы находитесь в локации: {icon_loc()} {Fore.GREEN}{state.loc.title()}{Style.RESET_ALL}.')
    if state.training.active:
        skill_end_time = state.training.time_end - datetime.fromtimestamp(datetime.now().timestamp())
        skill_end_time = str(skill_end_time).split('.')[0]
        # Уровень изучаемого скилла читается динамически: имя в state.training.skill_name
        # совпадает с атрибутом state.gym (stamina, energy_max_skill, speed_skill, ...).
        current_level = getattr(state.gym, state.training.skill_name)
        print(f'\t🏋 Улучшаем навык - {state.training.skill_name.title()} до {Fore.LIGHTCYAN_EX}{current_level + 1}{Style.RESET_ALL} уровня.'
              f'\n\t🕑 Улучшение через: {Fore.LIGHTBLUE_EX}{skill_end_time}{Style.RESET_ALL}.')
    if state.work.active:
        work_end_time = state.work.end - datetime.fromtimestamp(datetime.now().timestamp())
        work_end_time = str(work_end_time).split('.')[0]
        print(f'\t🏭 Место работы: {state.work.work_type.title()} (💰: + {Fore.LIGHTYELLOW_EX}{state.work.salary * state.work.hours}{Style.RESET_ALL} $).'
              f'\n\t🕑 Конец смены через: {Fore.LIGHTBLUE_EX}{work_end_time}{Style.RESET_ALL}.')
    if state.adventure.active:
        Adventure.adventure_check_done(self=None)


def save_game_date_last_enter(state: GameState = None):
    """Проверка смены игрового дня. На новый день — сброс счётчиков и перенос
    steps_today в steps_yesterday. В обоих случаях — пересчёт steps_can_use."""
    state = _resolve_state(state)

    now_date = datetime.now().date()
    last_enter_date_char = state.date_last_enter or None

    if str(now_date) != str(last_enter_date_char):
        print(f"\nNew Day: {now_date}. Обновляем шаги и бонусы.")

        with open('save.txt', 'w') as save_file:
            save_file.write(str(now_date))

        today_steps_to_yesterday_steps(state)

        # Сброс шагов на новый день. Игрок вводит фактическое значение через команду `+`.
        state.steps.today = 0
        state.steps.used = 0
        state.date_last_enter = str(now_date)

    # Пересчёт steps_can_use в обеих ветках — иначе статус-бар покажет stale значение
    # из сейва после смены даты (см. 2.12).
    state.steps.can_use = state.steps.today - state.steps.used
    state.steps.can_use += stamina_skill_bonus_def(state)
    state.steps.can_use += equipment_bonus_stamina_steps(state)
    state.steps.can_use += daily_steps_bonus(state)
    state.steps.can_use += level_steps_bonus(state)
    return state.steps.can_use


def steps_today_set(entered, state: GameState = None):
    """Применяет max(текущий, введённый) к steps_today. Общая логика для
    интерактивного ввода и inline-команды `+N`. Mi Fitness -> Apple Health
    синхронизируется с задержкой, поэтому показания на браслете часто свежее
    того, что доехало автоматически — поэтому max(), а не replace."""
    state = _resolve_state(state)

    if entered < 0:
        print('Отрицательное число. Ввод отменён.')
        return

    old = state.steps.today
    new = max(old, entered)
    state.steps.today = new

    if new == old:
        print(f'Текущее значение ({old:,}) больше или равно введённому ({entered:,}). Оставлено как было.')
    else:
        print(f'Обновлено: {old:,} -> {new:,}.')


def steps_today_manual_entry(state: GameState = None):
    """Интерактивный ручной ввод количества шагов через подменю."""
    state = _resolve_state(state)
    try:
        entered = int(input('Введите текущее количество шагов с браслета:\n>>> '))
    except ValueError:
        print('Нужно целое число. Ввод отменён.')
        return
    steps_today_set(entered, state)


def char_info(state: GameState = None):
    """Отображение характеристик персонажа."""
    state = _resolve_state(state)
    print('\n################################')
    print('### Характеристики персонажа ###')
    print('################################')
    print(f'- Пройдено шагов за сегодня 🏃: {state.steps.today:,.0f}')
    print(f'- Потрачено шагов за сегодня 🏃: {state.steps.used:,.0f}')

    print('\n### Бонусы за навыки: ###')
    print(f'- Запас энергии 🔋: {state.energy} эд.')
    print(f'- Макс. запас энергии 🔋: {state.energy_max} эд.')
    print(f'\n- Выносливость: + {state.gym.stamina} % (+ {stamina_skill_bonus_def(state)} шагов).')
    print(f'- Максимальный запас энергии: + {state.gym.energy_max_skill} энергии.')
    print(f'- Скорость: + {state.gym.speed_skill} %.')
    print(f'- Удача: + {state.gym.luck_skill} %.')

    print('\n### Бонусы экипировки: ###')
    print(f'\t- Stamina: + {equipment_stamina_bonus(state)} %'
          f'\n\t- Energy Max: + {equipment_energy_max_bonus(state)} эд.'
          f'\n\t- Speed: + {equipment_speed_skill_bonus(state)} %'
          f'\n\t- Luck: + {equipment_luck_bonus(state)} %')

    print(f'\n### Бонусы за прохождение каждый день 10к+ шагов:'
          f'\n\t- Steps: + {state.steps.daily_bonus} %'
          f'\n\t- Energy Max: + {state.steps.daily_bonus} эд.')

    print(f"\n### Прокачка навыков от уровня персонажа ###"
          f"\n\t- Stamina: {state.char_level.skill_stamina}"
          f"\n\t- Energy Max: {state.char_level.skill_energy_max}"
          f"\n\t- Speed Skill: {state.char_level.skill_speed}"
          f"\n\t- Luck: {state.char_level.skill_luck}")

    print('\n####################################')
    print('P.S. Сюда так же будут добавлены характеристики по мере их добавления в игру.')
    print('####################################')


def steps(state: GameState = None):
    """Возвращает кол-во шагов, доступных для траты сегодня (после пересчёта)."""
    state = _resolve_state(state)
    save_game_date_last_enter(state)
    return state.steps.can_use


def location_change_map(state: GameState = None):
    """Перемещение между локациями на глобальной карте.

    Сейчас стоимость нулевая (placeholder для будущей механики 5/150)."""
    state = _resolve_state(state)
    state.energy -= 0
    state.steps.used += 0


def energy_timestamp(state: GameState = None):
    """Обновляет timestamp последней регенерации энергии до now."""
    state = _resolve_state(state)
    state.energy_time_stamp = datetime.now().timestamp()
    print('Energy TimeStamp Update - Function')
    return state.energy_time_stamp


def today_steps_to_yesterday_steps(state: GameState = None):
    """На новый день переносит steps_today → steps_yesterday и обновляет daily_bonus.

    Если за вчера >= 10k шагов — daily_bonus += 1, иначе сбрасывается в 0.
    """
    state = _resolve_state(state)
    state.steps.yesterday = state.steps.today

    if state.steps.yesterday >= 10000:
        state.steps.daily_bonus += 1
    else:
        state.steps.daily_bonus = 0
    return state.steps.yesterday, state.steps.daily_bonus


def total_bonus_steps(state: GameState = None):
    """Сумма бонусных шагов из всех источников."""
    state = _resolve_state(state)
    return (stamina_skill_bonus_def(state) +
            equipment_bonus_stamina_steps(state) +
            daily_steps_bonus(state) +
            level_steps_bonus(state))


def bonus_percentage(state: GameState = None):
    """Процент бонусных шагов относительно базового количества шагов."""
    state = _resolve_state(state)
    total_bonus = total_bonus_steps(state)
    base_steps = state.steps.today
    if base_steps:
        return (total_bonus / base_steps) * 100
    return 0


def format_steps(steps):
    """Форматирует количество шагов:
    - < 10 000 → без изменений
    - >= 10 000 и < 1 000 000 → округление до тысяч с "k"
    - >= 1 000 000 → округление до сотен тысяч с "kk"
    """
    if steps < 10_000:
        return f"{steps}"
    elif steps < 1_000_000:
        return f"{steps // 1_000}k"
    else:
        return f"{steps / 1_000_000:.1f}kk"
