"""Cross-cutting helpers — energy regen, status_bar, date helpers, ввод шагов.

UI-функции (status_bar, char_info) тестируются через capsys.
"""

from colorama import Fore, Style
from datetime import datetime

from adventure import Adventure
from bonus import energy_regen_interval, equipment_bonus_stamina_steps, daily_steps_bonus, level_steps_bonus
from functions_02 import format_money, format_timedelta
from locations import icon_loc
from settings import debug_mode
from skill_bonus import stamina_skill_bonus_def, speed_skill_equipment_and_level_bonus
from equipment_bonus import equipment_energy_max_bonus, equipment_stamina_bonus, equipment_speed_skill_bonus, equipment_luck_bonus
from level import CharLevel
from state import GameState


def timestamp_now() -> float:
    """Возвращает TimeStamp в данный момент. Pure utility, state не требуется."""
    return datetime.now().timestamp()


def energy_time_charge(state: GameState) -> None:
    """Регенерация энергии во времени. Одна единица каждые
    energy_regen_interval(60, state) секунд. При достижении
    energy_max регенерация приостанавливается, стамп синкается к now.

    Since 0.2.4i (task 4.21): использует `energy_regen_interval` (зависит
    только от `gym.energy_regen_skill` + `char_level.skill_energy_regen`)
    вместо ранее `speed_skill_equipment_and_level_bonus`. Это разделяет
    регенерацию энергии от длительности активностей — Speed-прокачка
    больше не ускоряет regen, и наоборот."""
    from bonus import compute_energy_max  # lazy — избегаем циклов при импорте functions
    now = timestamp_now()
    energy = state.energy
    energy_max = compute_energy_max(state)
    interval = energy_regen_interval(60, state)

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


def status_bar(state: GameState) -> None:
    """Отображение переменных: шагов, энергии, денег."""
    save_game_date_last_enter(state)  # детект смены дня + пересчёт steps_can_use до любых чтений (см. 2.12)

    char_level_view = CharLevel(state)

    total_bonus = total_bonus_steps(state)
    max_steps = state.steps.today + total_bonus
    bonus_percent = bonus_percentage(state)

    from bonus import compute_energy_max  # lazy import
    energy_max_now = compute_energy_max(state)
    print(f'\nSteps 🏃: {Fore.LIGHTCYAN_EX}{steps(state):,.0f} / {max_steps:,.0f}{Style.RESET_ALL} '
          f'(Bonus: Stamina 🏃: + {Fore.LIGHTCYAN_EX}{stamina_skill_bonus_def(state):,.0f}{Style.RESET_ALL} '
          f'/ Equipment 🏃: + {Fore.LIGHTCYAN_EX}{equipment_bonus_stamina_steps(state):,.0f}{Style.RESET_ALL} '
          f'/ Daily 🏃: {Fore.LIGHTCYAN_EX}{daily_steps_bonus(state)}{Style.RESET_ALL} '
          f'/ Level: {Fore.LIGHTCYAN_EX}{level_steps_bonus(state)}{Style.RESET_ALL}. '
          f'[🏃: {Fore.LIGHTCYAN_EX}{total_bonus:,.0f}{Style.RESET_ALL}, {bonus_percent:.2f} %]) '
          f'(Total steps used 🏃: {Fore.LIGHTCYAN_EX}{format_steps(state.steps.total_used)}{Style.RESET_ALL})'
          f'\nEnergy 🔋: {Fore.GREEN}{state.energy} / {energy_max_now}{Style.RESET_ALL} '
          f'(Bonus: Equipment 🔋: + {Fore.GREEN}{equipment_energy_max_bonus(state)}{Style.RESET_ALL} / '
          f'Daily 🔋: + {Fore.GREEN}{state.steps.daily_bonus}{Style.RESET_ALL} / '
          f'Level: + {Fore.GREEN}{state.char_level.skill_energy_max}{Style.RESET_ALL})', end='')
    if debug_mode:
        print(f'(+ 1 эн. через: {abs(energy_regen_interval(60, state) - (timestamp_now() - state.energy_time_stamp)):,.0f} sec.)', end='')
    print(f'\nMoney 💰: {Fore.LIGHTYELLOW_EX}{format_money(state.money)}{Style.RESET_ALL} $.')

    # 4.61 — Warning о низком quality equipped items (< 20%) или broken (=0).
    # Broken items не дают bonus (4.61 binary cliff), low-quality скоро сломаются.
    from equipment_bonus import low_quality_equipped_items
    low_q = low_quality_equipped_items(state)
    if low_q:
        broken = [i for i in low_q if i.get('quality', [0])[0] == 0]
        if broken:
            print(f'{Fore.LIGHTRED_EX}🔨 Сломано: {len(broken)} '
                  f'предмет(ов) (0% quality, не даёт bonus). '
                  f'Отремонтируй в Кузнице (9 → 1).{Style.RESET_ALL}')
        warn_only = [i for i in low_q if i.get('quality', [0])[0] > 0]
        if warn_only:
            print(f'{Fore.LIGHTYELLOW_EX}⚠ Требует ремонта: {len(warn_only)} '
                  f'предмет(ов) (<20% quality).{Style.RESET_ALL}')

    char_level_view.level_status_bar()

    # 4.62.3 — Active title from Seals system. Печатается отдельной строкой
    # над локацией если игрок надел title в Triumphs → Seals view.
    if getattr(state, 'title', None):
        print(f'{Fore.LIGHTYELLOW_EX}👑 {state.title}{Style.RESET_ALL}')

    print(f'Вы находитесь в локации: {icon_loc(state)} {Fore.GREEN}{state.loc.title()}{Style.RESET_ALL}.')
    if state.training.active:
        skill_end_time = format_timedelta(state.training.time_end - datetime.fromtimestamp(datetime.now().timestamp()))
        # Уровень изучаемого скилла читается динамически: имя в state.training.skill_name
        # совпадает с атрибутом state.gym (stamina, energy_max_skill, speed_skill, ...).
        current_level = getattr(state.gym, state.training.skill_name)
        print(f'\t🏋 Улучшаем навык - {state.training.skill_name.title()} до {Fore.LIGHTCYAN_EX}{current_level + 1}{Style.RESET_ALL} уровня.'
              f'\n\t🕑 Улучшение через: {Fore.LIGHTBLUE_EX}{skill_end_time}{Style.RESET_ALL}.')
    if state.work.active:
        work_end_time = format_timedelta(state.work.end - datetime.fromtimestamp(datetime.now().timestamp()))
        print(f'\t🏭 Место работы: {state.work.work_type.title()} (💰: + {Fore.LIGHTYELLOW_EX}{state.work.salary * state.work.hours}{Style.RESET_ALL} $).'
              f'\n\t🕑 Конец смены через: {Fore.LIGHTBLUE_EX}{work_end_time}{Style.RESET_ALL}.')
    if state.adventure.active:
        Adventure.adventure_check_done(self=None, state=state)

    # 4.62.0.3 — Pinned triumphs (≤3). Empty string если нет pinned или catalog
    # пустой — печатать ничего не нужно. Lazy import — triumphs_menu тянет
    # colorama и не нужен в большинстве path'ов.
    try:
        from triumphs_menu import render_pinned_status_bar
        pinned = render_pinned_status_bar(state)
        if pinned:
            print(pinned)
    except Exception:  # noqa: BLE001 — status_bar не должен ломать game loop
        pass


def _max_merge_today_from_log(state: GameState, date_str: str) -> None:
    """Поднимает `state.steps.today` до максимума записей в `steps_log` за
    указанную дату. Используется в `save_game_date_last_enter` перед
    rollover'ом дня (задача 2.4) — гарантирует, что `yesterday` получит
    максимально полную информацию о пройденных шагах за тот день, даже если
    `state.steps.today` был stale (web/API ввод не зафиксирован в game_state
    snapshot перед rollover'ом).

    Silent-fail при сетевой ошибке: оставляем state как есть.
    """
    # Lazy import — google_sheets_db тянет gspread, не нужен в большинстве
    # тестов functions.py.
    from google_sheets_db import StepsLogRepo
    try:
        entries = StepsLogRepo().for_day(date_str)
    except Exception:
        return
    if not entries:
        return
    max_in_log = max(e['steps'] for e in entries)
    if max_in_log > state.steps.today:
        state.steps.today = max_in_log


def save_game_date_last_enter(state: GameState) -> int:
    """Проверка смены игрового дня. На новый день — сброс счётчиков и перенос
    steps_today в steps_yesterday. В обоих случаях — пересчёт steps_can_use.

    Возвращает обновлённое значение `state.steps.can_use`."""
    now_date = datetime.now().date()
    last_enter_date_char = state.date_last_enter or None

    if str(now_date) != str(last_enter_date_char):
        print(f"\nNew Day: {now_date}. Обновляем шаги и бонусы.")

        # 2.4: max-merge state.steps.today из steps_log за день, который "уходит"
        # перед переносом в yesterday. Защита от случая "stale state.steps.today
        # на момент rollover" — если игрок ввёл шаги через web/API но не сохранил
        # game_state в Sheets, лог был обновлён, а snapshot — нет. Без max-merge
        # daily_bonus незаслуженно сбрасывался.
        if last_enter_date_char:
            _max_merge_today_from_log(state, str(last_enter_date_char))

        today_steps_to_yesterday_steps(state)

        # Сброс шагов на новый день. Игрок вводит фактическое значение через команду `+`.
        state.steps.today = 0
        state.steps.used = 0
        state.date_last_enter = str(now_date)
        # 4.6 — log_event смены игрового дня.
        from history import log_event
        log_event('new_day', new_date=str(now_date), prev_date=str(last_enter_date_char))

    # Пересчёт steps_can_use в обеих ветках — иначе статус-бар покажет stale значение
    # из сейва после смены даты (см. 2.12).
    state.steps.can_use = state.steps.today - state.steps.used
    state.steps.can_use += stamina_skill_bonus_def(state)
    state.steps.can_use += equipment_bonus_stamina_steps(state)
    state.steps.can_use += daily_steps_bonus(state)
    state.steps.can_use += level_steps_bonus(state)
    return state.steps.can_use


def steps_today_set(entered: int, state: GameState) -> None:
    """Применяет max(текущий, введённый) к steps_today. Общая логика для
    интерактивного ввода и inline-команды `+N`. Mi Fitness -> Apple Health
    синхронизируется с задержкой, поэтому показания на браслете часто свежее
    того, что доехало автоматически — поэтому max(), а не replace."""
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
        # 4.6 — log_event ввода шагов из CLI (только если значение реально обновилось).
        from history import log_event
        log_event('steps_set', source='manual', value=new, previous=old)


def steps_today_manual_entry(state: GameState) -> None:
    """Интерактивный ручной ввод количества шагов через подменю."""
    try:
        entered = int(input('Введите текущее количество шагов с браслета:\n>>> '))
    except ValueError:
        print('Нужно целое число. Ввод отменён.')
        return
    steps_today_set(entered, state)


def char_info(state: GameState) -> None:
    """Отображение характеристик персонажа."""
    print('\n################################')
    print('### Характеристики персонажа ###')
    print('################################')
    print(f'- Пройдено шагов за сегодня 🏃: {state.steps.today:,.0f}')
    print(f'- Потрачено шагов за сегодня 🏃: {state.steps.used:,.0f}')

    from bonus import compute_energy_max  # lazy
    print('\n### Бонусы за навыки: ###')
    print(f'- Запас энергии 🔋: {state.energy} эд.')
    print(f'- Макс. запас энергии 🔋: {compute_energy_max(state)} эд.')
    print(f'\n- Выносливость: + {state.gym.stamina} % (+ {stamina_skill_bonus_def(state)} шагов).')
    print(f'- Максимальный запас энергии: + {state.gym.energy_max_skill} энергии.')
    print(f'- Скорость: + {state.gym.speed_skill} %.')
    print(f'- Регенерация энергии: + {state.gym.energy_regen_skill} %.')
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
          f"\n\t- Energy Regen: {state.char_level.skill_energy_regen}"
          f"\n\t- Luck: {state.char_level.skill_luck}")

    print('\n####################################')
    print('P.S. Сюда так же будут добавлены характеристики по мере их добавления в игру.')
    print('####################################')


def steps(state: GameState) -> int:
    """Возвращает кол-во шагов, доступных для траты сегодня (после пересчёта)."""
    save_game_date_last_enter(state)
    return state.steps.can_use


def location_change_map(state: GameState) -> None:
    """Перемещение между локациями на глобальной карте.

    Сейчас стоимость нулевая (placeholder для будущей механики 5/150)."""
    state.energy -= 0
    state.steps.used += 0


def energy_timestamp(state: GameState) -> float:
    """Обновляет timestamp последней регенерации энергии до now."""
    state.energy_time_stamp = datetime.now().timestamp()
    print('Energy TimeStamp Update - Function')
    return state.energy_time_stamp


def today_steps_to_yesterday_steps(state: GameState) -> tuple[int, int]:
    """На новый день переносит steps_today → steps_yesterday и обновляет daily_bonus.

    Если за вчера >= 10k шагов — daily_bonus += 1, иначе сбрасывается в 0.
    Возвращает (yesterday, daily_bonus) — кортеж новых значений.
    """
    state.steps.yesterday = state.steps.today
    # 4.62.1.1.1 — накапливаем реально пройденные шаги (показание завершившегося
    # дня) в forward-only accumulator total_walked. Единственная точка — rollover,
    # без двойного счёта; current-day шаги попадут на следующем rollover'е.
    state.steps.total_walked += state.steps.yesterday
    # 4.62.1.9 (Total days played) — завершившийся день с активностью (≥1 шаг)
    # = +1 уникальный день игры. Forward-only, дедуп естественный (раз на день).
    if state.steps.yesterday >= 1:
        state.days_played += 1
    if state.steps.yesterday >= 10000:
        state.steps.daily_bonus += 1
    else:
        state.steps.daily_bonus = 0
    return state.steps.yesterday, state.steps.daily_bonus


def total_bonus_steps(state: GameState) -> int:
    """Сумма бонусных шагов из всех источников."""
    return (stamina_skill_bonus_def(state) +
            equipment_bonus_stamina_steps(state) +
            daily_steps_bonus(state) +
            level_steps_bonus(state))


def bonus_percentage(state: GameState) -> float:
    """Процент бонусных шагов относительно базового количества шагов."""
    total_bonus = total_bonus_steps(state)
    base_steps = state.steps.today
    if base_steps:
        return (total_bonus / base_steps) * 100
    return 0


def format_steps(steps: int) -> str:
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
