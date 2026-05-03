#pyinstaller --onefile --icon=icons/2walks.ico game.py

import os
import sys
from datetime import datetime

from colorama import init

from characteristics import (
    game,
    init_game_state,
    save_characteristic,
)
from adventure import Adventure
from adventure_data import adventure_data_table
from equipment import Equipment
from functions import (
    char_info,
    location_change_map,
    steps_today_manual_entry,
    steps_today_set,
    energy_time_charge,
    status_bar,
)
from google_sheets_db import GameStateRepo, StepsLogRepo
from gym import skill_training_check_done
from inventory import inventory_menu
from level import CharLevel
from locations import (
    home_location,
    gym_location,
    shop_location,
    work_location,
    adventure_location,
    garage_location,
    auto_dialer_location,
    bank_location,
)
from work import work_check_done


def play():
    """Главный игровой цикл. Требует, чтобы game.state был инициализирован
    через init_game_state() — обычно из __main__."""
    state = game.state
    if state is None:
        raise RuntimeError("game.state не инициализирован — вызови init_game_state() до play().")

    while True:
        # Adventure пересоздаётся каждый цикл, чтобы adventure_requirements увидели
        # актуальную прокачку move_optimization_adventure (см. TASKS.md 2.3).
        adventure_instance = Adventure(adventure_data_table, state=state)

        def location_selection():
            def enter_location(loc, enter_fn, can_reopen=False, call_map_on_switch=True):
                """Смена локации: если уже там — молчим либо повторно показываем меню."""
                if state.loc != loc:
                    state.loc = loc
                    enter_fn()
                    if call_map_on_switch:
                        location_change_map(state)
                elif can_reopen:
                    enter_fn()

            def _sync_to_cloud():
                """Save game_state в Sheets + лог замера шагов в steps_log.

                Локальное сохранение (CSV/JSON) делаем всегда первым — оно гарантировано,
                даже если Sheets-вызов ниже упадёт сетевой ошибкой. Это даёт offline-mode:
                игрок может играть без сети, а синк в Sheets произойдёт в следующий save.
                """
                save_characteristic()  # local CSV/JSON всегда
                GameStateRepo().save(state.to_dict())
                # Append текущего snapshot шагов в steps_log с источником 'manual'
                # (CLI — единственный канал ввода в этой задаче; web/auto канал
                # будет писать сам в 4.48.2 / 4.13).
                StepsLogRepo().append(
                    ts=datetime.now().timestamp(),
                    steps=state.steps.today,
                    source='manual',
                )

            def save_game_local_and_cloud():
                _sync_to_cloud()

            def save_and_exit():
                _sync_to_cloud()
                print('🚪 Спасибо за игру. До встречи.')
                sys.exit()

            def load_from_cloud():
                # update_from_dict мутирует существующий state — все импортёры,
                # удерживающие ссылку, видят новые данные без rebind.
                state.update_from_dict(GameStateRepo().load())

            def unknown_command():
                print('\nНеизвестная команда. Попробуй ещё раз.')

            COMMANDS = {
                # Локации
                '1': lambda: enter_location('home', lambda: home_location(state)),
                '2': lambda: enter_location('gym', lambda: gym_location(state), can_reopen=True),
                '3': lambda: enter_location('shop', lambda: shop_location(state)),
                '4': lambda: enter_location('work', lambda: work_location(state), can_reopen=True),
                '5': lambda: enter_location('adventure',
                                            lambda: adventure_location(adventure_instance),
                                            call_map_on_switch=False),
                '6': lambda: enter_location('garage', lambda: garage_location(state)),
                '7': lambda: enter_location('auto_dialer', lambda: auto_dialer_location(state)),
                '8': lambda: enter_location('bank', lambda: bank_location(state)),
                # Шаги
                '+': lambda: steps_today_manual_entry(state),
                # Меню персонажа
                'm': lambda: print('\nРаздел "Меню" - (Пока не работает).'),
                'i': lambda: inventory_menu(state),
                'e': lambda: Equipment.equipment_view(self=None, state=state),
                'c': lambda: char_info(state),
                'u': lambda: CharLevel(state).menu_skill_point_allocation(),
                # Сохранение / загрузка
                'l': load_from_cloud,
                's': save_game_local_and_cloud,
                'q': save_and_exit,
            }

            LAYOUT_RU_TO_EN = {
                'ь': 'm', 'ш': 'i', 'у': 'e', 'с': 'c', 'г': 'u',
                'д': 'l', 'ы': 's', 'й': 'q',
            }
            for cyr, lat in LAYOUT_RU_TO_EN.items():
                if lat in COMMANDS:
                    COMMANDS[cyr] = COMMANDS[lat]

            while True:
                energy_time_charge(state)
                work_check_done(state)
                skill_training_check_done(state)

                status_bar(state)

                print(f'Вы можете пройти в локацию:'
                      f'\n\t1. 🏠 Домой (Не работает)'
                      f'\n\t2. 🏋️ Спортзал'
                      f'\n\t3. 🛒 Магазин (В тестовом режиме)'
                      f'\n\t4. 🏭 Работа'
                      f'\n\t5. 🗺️ Приключение (В тестовом режиме)'
                      f'\n\t+. Ввести шаги вручную')
                print(f'\tm. Меню // '
                      f'i. 🎒 Инвентарь // '
                      f'e. 🎒 Экипировка // '
                      f'c. Характеристики // '
                      f'u. Level'
                      f'\n\tl. ☁ Load from Cloud'
                      f'\n\ts. 💾 Save Game'
                      f'\n\tq/e. 💾 + 🚪 Save & Exit')
                temp_number = input('Куда вы хотите пойти?:\n>>> ')

                # Inline-команда: "+1232" или "+ 1312" применяет шаги сразу.
                if temp_number.startswith('+') and temp_number != '+':
                    rest = temp_number[1:].strip()
                    if not rest:
                        steps_today_manual_entry(state)
                    else:
                        try:
                            steps_today_set(int(rest), state)
                        except ValueError:
                            print('Неверный формат. Ожидается "+N", где N — целое число.')
                else:
                    COMMANDS.get(temp_number, unknown_command)()

        # Запуск функции, которая относится к локациям.
        loc_dispatch = {
            'home': lambda: home_location(state),
            'gym': lambda: gym_location(state),
            'shop': lambda: shop_location(state),
            'work': lambda: work_location(state),
            'adventure': lambda: adventure_location(adventure_instance),
            'garage': lambda: garage_location(state),
            'auto_dialer': lambda: auto_dialer_location(state),
            'bank': lambda: bank_location(state),
        }
        loc_handler = loc_dispatch.get(state.loc)
        if loc_handler is not None:
            loc_handler()
            location_selection()


if __name__ == "__main__":
    print(f"Version: 0.2.1b")
    os.system("chcp 65001")
    init()

    init_game_state()  # Загрузка из Sheets / CSV — отложена с импорта (1.2).

    try:
        play()
    except (KeyboardInterrupt, EOFError):
        print('\n\nВыход без сохранения. Пока!')
