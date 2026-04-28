import json
from colorama import Fore, Style
from datetime import datetime, timedelta

from adventure import Adventure
from bonus import equipment_bonus_stamina_steps, daily_steps_bonus, level_steps_bonus
from characteristics import char_characteristic
from locations import icon_loc
from settings import debug_mode
from skill_bonus import stamina_skill_bonus_def, speed_skill_equipment_and_level_bonus
from equipment_bonus import equipment_stamina_bonus, equipment_energy_max_bonus, equipment_speed_skill_bonus, equipment_luck_bonus
from level import CharLevel


def energy_time_charge():
    """Регенерация энергии во времени. Одна единица каждые
    speed_skill_equipment_and_level_bonus(60) секунд. При достижении
    energy_max регенерация приостанавливается, стамп синкается к now."""
    global char_characteristic

    now = timestamp_now()
    energy = char_characteristic['energy']
    energy_max = char_characteristic['energy_max']
    interval = speed_skill_equipment_and_level_bonus(60)

    if energy >= energy_max:
        # Клэмп излишка (например, после снятия экипировки energy_max уменьшился).
        char_characteristic['energy'] = energy_max
        char_characteristic['energy_time_stamp'] = now
        return

    elapsed = now - char_characteristic['energy_time_stamp']
    if elapsed < interval:
        return

    points = int(elapsed // interval)
    remainder = elapsed - points * interval
    new_energy = min(energy + points, energy_max)
    char_characteristic['energy'] = new_energy

    if new_energy >= energy_max:
        # Добрали до максимума — остаток времени не копим.
        char_characteristic['energy_time_stamp'] = now
    else:
        char_characteristic['energy_time_stamp'] = now - remainder

    if debug_mode:
        print('\n--- Energy Check ---')
        print(f'Добавлено energy: {new_energy - energy}')
        if new_energy < energy_max:
            print(f'До следующей +1: {interval - remainder:.1f} sec.')


def status_bar():
    # Отображение переменных: шагов, энергии, денег.
    save_game_date_last_enter()  # детект смены дня + пересчёт steps_can_use до любых чтений (см. 2.12)

    char_level_view = CharLevel(char_characteristic)  # Инициализация уровня персонажа, прогресса, и lvl up

    total_bonus = total_bonus_steps()
    max_steps = char_characteristic["steps_today"] + total_bonus
    bonus_percent = bonus_percentage()

    print(f'\nSteps 🏃: {Fore.LIGHTCYAN_EX}{steps():,.0f} / {max_steps:,.0f}{Style.RESET_ALL} '
          f'(Bonus: Stamina 🏃: + {Fore.LIGHTCYAN_EX}{stamina_skill_bonus_def():,.0f}{Style.RESET_ALL} '
          f'/ Equipment 🏃: + {Fore.LIGHTCYAN_EX}{equipment_bonus_stamina_steps():,.0f}{Style.RESET_ALL} '
          f'/ Daily 🏃: {Fore.LIGHTCYAN_EX}{daily_steps_bonus()}{Style.RESET_ALL} '
          f'/ Level: {Fore.LIGHTCYAN_EX}{level_steps_bonus()}{Style.RESET_ALL}. '
          f'[🏃: {total_bonus:,.0f}, {bonus_percent:.2f} %]) '
          f'(Total steps used 🏃: {Fore.LIGHTCYAN_EX}{format_steps(char_characteristic["steps_total_used"])}{Style.RESET_ALL})'
          f'\nEnergy 🔋: {Fore.GREEN}{char_characteristic["energy"]} / {char_characteristic["energy_max"]}{Style.RESET_ALL} '
          f'(Bonus: Equipment 🔋: + {Fore.GREEN}{equipment_energy_max_bonus()}{Style.RESET_ALL} / '
          f'Daily 🔋: + {Fore.GREEN}{char_characteristic["steps_daily_bonus"]}{Style.RESET_ALL} / '
          f'Level: + {Fore.GREEN}{char_characteristic["lvl_up_skill_energy_max"]}{Style.RESET_ALL})', end='')
    if debug_mode:
        print(f'(+ 1 эн. через: {abs(speed_skill_equipment_and_level_bonus(60) - (timestamp_now() - char_characteristic["energy_time_stamp"])):,.0f} sec.)', end='')
    print(f'\nMoney 💰: {Fore.LIGHTYELLOW_EX}{char_characteristic["money"]:,.0f}{Style.RESET_ALL} $.')

    # Отображение Level персонажа, прогресс и lvl up
    char_level_view.level_status_bar()

    print(f'Вы находитесь в локации: {icon_loc()} {Fore.GREEN}{char_characteristic["loc"].title()}{Style.RESET_ALL}.')
    if char_characteristic['skill_training']:
        skill_end_time = char_characteristic["skill_training_time_end"] - datetime.fromtimestamp(datetime.now().timestamp())
        skill_end_time = str(skill_end_time).split('.')[0]
        print(f'\t🏋 Улучшаем навык - {char_characteristic["skill_training_name"].title()} до {Fore.LIGHTCYAN_EX}{char_characteristic[char_characteristic["skill_training_name"]] + 1}{Style.RESET_ALL} уровня.'
              f'\n\t🕑 Улучшение через: {Fore.LIGHTBLUE_EX}{skill_end_time}{Style.RESET_ALL}.')
    if char_characteristic['working']:
        work_end_time = char_characteristic["working_end"] - datetime.fromtimestamp(datetime.now().timestamp())
        work_end_time = str(work_end_time).split('.')[0]
        print(f'\t🏭 Место работы: {char_characteristic["work"].title()} (💰: + {Fore.LIGHTYELLOW_EX}{char_characteristic["work_salary"] * char_characteristic["working_hours"]}{Style.RESET_ALL} $).'
              f'\n\t🕑 Конец смены через: {Fore.LIGHTBLUE_EX}{work_end_time}{Style.RESET_ALL}.')
    if char_characteristic['adventure']:
        # Проверка или персонаж находится в Приключении.
        Adventure.adventure_check_done(self=None)


def save_game_date_last_enter():
    global char_characteristic
    # Проверка смены игрового дня. На новый день — сброс счётчиков и перенос
    # steps_today в steps_yesterday. В обоих случаях — пересчёт steps_can_use.

    now_date = datetime.now().date()
    last_enter_date_char = char_characteristic.get('date_last_enter', None)

    # Новый день — сбрасываем дневные счётчики
    if str(now_date) != str(last_enter_date_char):
        print(f"\nNew Day: {now_date}. Обновляем шаги и бонусы.")

        with open('save.txt', 'w') as save_file:
            save_file.write(str(now_date))

        # Перенос шагов в steps_yesterday + обновление daily_bonus.
        today_steps_to_yesterday_steps()

        # Сброс шагов на новый день. Игрок вводит фактическое значение через команду `+`.
        char_characteristic['steps_today'] = 0
        char_characteristic['steps_today_used'] = 0
        char_characteristic['date_last_enter'] = str(now_date)

    # Пересчёт steps_can_use — выполняется в обеих ветках (новый день / тот же день),
    # чтобы статус-бар не показывал stale значение из сейва после смены даты.
    char_characteristic['steps_can_use'] = char_characteristic['steps_today'] - char_characteristic['steps_today_used']
    char_characteristic['steps_can_use'] += stamina_skill_bonus_def()
    char_characteristic['steps_can_use'] += equipment_bonus_stamina_steps()
    char_characteristic['steps_can_use'] += daily_steps_bonus()
    char_characteristic['steps_can_use'] += level_steps_bonus()
    return char_characteristic['steps_can_use']


def steps_today_set(entered):
    """Применяет max(текущий, введённый) к steps_today. Общая логика для
    интерактивного ввода и inline-команды `+N`. Mi Fitness -> Apple Health
    синхронизируется с задержкой, поэтому показания на браслете часто свежее
    того, что доехало автоматически — поэтому max(), а не replace."""
    global char_characteristic

    if entered < 0:
        print('Отрицательное число. Ввод отменён.')
        return

    old = char_characteristic['steps_today']
    new = max(old, entered)
    char_characteristic['steps_today'] = new

    if new == old:
        print(f'Текущее значение ({old:,}) больше или равно введённому ({entered:,}). Оставлено как было.')
    else:
        print(f'Обновлено: {old:,} -> {new:,}.')


def steps_today_manual_entry():
    """Интерактивный ручной ввод количества шагов через подменю."""
    try:
        entered = int(input('Введите текущее количество шагов с браслета:\n>>> '))
    except ValueError:
        print('Нужно целое число. Ввод отменён.')
        return
    steps_today_set(entered)


def char_info():
    # Функция отображения характеристик персонажа. Пока сюда буду добавлять все подряд, а дальше будет видно.
    print('\n################################')
    print('### Характеристики персонажа ###')
    print('################################')
    print(f'- Пройдено шагов за сегодня 🏃: {char_characteristic["steps_today"]:,.0f}')
    print(f'- Потрачено шагов за сегодня 🏃: {char_characteristic["steps_today_used"]:,.0f}')

    print('\n### Бонусы за навыки: ###')
    print(f'- Запас энергии 🔋: {char_characteristic["energy"]} эд.')
    print(f'- Макс. запас энергии 🔋: {char_characteristic["energy_max"]} эд.')
    print(f'\n- Выносливость: + {char_characteristic["stamina"]} % (+ {stamina_skill_bonus_def()} шагов).')
    print(f'- Максимальный запас энергии: + {char_characteristic["energy_max_skill"]} энергии.')
    print(f'- Скорость: + {char_characteristic["speed_skill"]} %.')
    print(f'- Удача: + {char_characteristic["luck_skill"]} %.')

    print('\n### Бонусы экипировки: ###')
    print(f'\t- Stamina: + {equipment_stamina_bonus()} %'
          f'\n\t- Energy Max: + {equipment_energy_max_bonus()} эд.'
          f'\n\t- Speed: + {equipment_speed_skill_bonus()} %'
          f'\n\t- Luck: + {equipment_luck_bonus()} %')

    print(f'\n### Бонусы за прохождение каждый день 10к+ шагов:'
          f'\n\t- Steps: + {char_characteristic["steps_daily_bonus"]} %'
          f'\n\t- Energy Max: + {char_characteristic["steps_daily_bonus"]} эд.')

    print(f"\n### Прокачка навыков от уровня персонажа ###"
          f"\n\t- Stamina: {char_characteristic['lvl_up_skill_stamina']}"
          f"\n\t- Energy Max: {char_characteristic['lvl_up_skill_energy_max']}"
          f"\n\t- Speed Skill: {char_characteristic['lvl_up_skill_speed']}"
          f"\n\t- Luck: { char_characteristic['lvl_up_skill_luck']}")

    print('\n####################################')
    print('P.S. Сюда так же будут добавлены характеристики по мере их добавления в игру.')
    print('####################################')


# Нужно проверить или эта функция, вообще нужна
def steps():
    # Функция для определения кол-ва шагов, которые пройдено за сегодня.
    save_game_date_last_enter()
    return char_characteristic['steps_can_use']


def location_change_map():
    # Функция для перехода между локациями на глобальной карте.
    char_characteristic['energy'] -= 0              # 5 энергии на перемещение между локациями.
    char_characteristic['steps_today_used'] += 0    # 150 шагов, возможно.


def timestamp_now():
    # Возвращает TimeStamp в данный момент.
    timestamp_now = datetime.now().timestamp()
    return timestamp_now


def energy_timestamp():
    # Функция для возвращения времени последнего обновления энергии.
    global char_characteristic
    char_characteristic['energy_time_stamp'] = datetime.now().timestamp()
    print('Energy TimeStamp Update - Function')
    return char_characteristic['energy_time_stamp']


def today_steps_to_yesterday_steps():
    # Запись шагов, которые пройдены за вчера в переменную.
    # Увеличение бонуса, если шагов более 10к за вчера. Если шагов меньше 10к, то обнуление бонуса.
    # Bug: Кол-во шагов обновляется раньше, чем шаги за вчера записываются в переменную.
    # Hot To Fix: В файле characteristics.py переменная шагов запускатеся во время инициализации файла.
    char_characteristic['steps_yesterday'] = char_characteristic['steps_today']

    if char_characteristic['steps_yesterday'] >= 10000:
        char_characteristic['steps_daily_bonus'] += 1
    else:
        char_characteristic['steps_daily_bonus'] = 0
    return char_characteristic['steps_yesterday'], char_characteristic['steps_daily_bonus']


def total_bonus_steps():
    """Возвращает общее количество бонусных шагов из всех источников."""
    return (stamina_skill_bonus_def() +
            equipment_bonus_stamina_steps() +
            daily_steps_bonus() +
            level_steps_bonus())

def bonus_percentage():
    """Возвращает процент бонусных шагов относительно базового количества шагов."""
    total_bonus = total_bonus_steps()
    base_steps = char_characteristic["steps_today"]
    if base_steps:
        return (total_bonus / base_steps) * 100
    return 0


def format_steps(steps):
    """
    Форматирует количество шагов:
    - Если < 10 000, то без изменений.
    - Если >= 10 000 и < 1 000 000, то округляет до тысяч с "k".
    - Если >= 1 000 000, то округляет до сотен тысяч с "kk".
    """
    if steps < 10_000:
        return f"{steps}"
    elif steps < 1_000_000:
        return f"{steps // 1_000}k"
    else:
        return f"{steps / 1_000_000:.1f}kk"
