#pyinstaller --onefile --icon=icons/2walks.ico game.py

import os
import sys

from colorama import init

from characteristics import (
    game_state,
    save_characteristic,
)
from adventure import Adventure
from adventure_data import adventure_data_table
from equipment import Equipment
from functions import (
    save_game_date_last_enter,
    char_info,
    location_change_map,
    steps,
    steps_today_manual_entry,
    steps_today_set,
    timestamp_now,
    energy_timestamp,
    energy_time_charge,
    status_bar,
)
from google_sheets_db import (
    save_char_characteristic_to_google_sheet,
    load_char_characteristic_from_google_sheet,
)
from gym import skill_training_check_done
from inventory import inventory_menu
from level import CharLevel
from locations import (
    icon_loc,
    home_location,
    gym_location,
    shop_location,
    work_location,
    adventure_location,
    garage_location,
    auto_dialer_location,
    bank_location,
)
from work import Work, work_check_done


def game():
    while True:
        # Adventure пересоздаётся каждый цикл, чтобы adventure_requirements увидели
        # актуальную прокачку move_optimization_adventure (см. TASKS.md 2.3).
        adventure_instance = Adventure(adventure_data_table, state=game_state)

        def location_selection():
            def enter_location(loc, enter_fn, can_reopen=False, call_map_on_switch=True):
                """Смена локации: если уже там — молчим либо повторно показываем меню."""
                if game_state.loc != loc:
                    game_state.loc = loc
                    enter_fn()
                    if call_map_on_switch:
                        location_change_map(game_state)
                elif can_reopen:
                    enter_fn()

            def save_game_local_and_cloud():
                save_characteristic()
                save_char_characteristic_to_google_sheet()

            def save_and_exit():
                save_characteristic()
                save_char_characteristic_to_google_sheet()
                print('🚪 Спасибо за игру. До встречи.')
                sys.exit()

            def load_from_cloud():
                # update_from_dict мутирует существующий game_state — все импортёры,
                # удерживающие ссылку, видят новые данные без rebind.
                game_state.update_from_dict(load_char_characteristic_from_google_sheet())

            def unknown_command():
                print('\nНеизвестная команда. Попробуй ещё раз.')

            COMMANDS = {
                # Локации
                '1': lambda: enter_location('home', lambda: home_location(game_state)),
                '2': lambda: enter_location('gym', lambda: gym_location(game_state), can_reopen=True),
                '3': lambda: enter_location('shop', lambda: shop_location(game_state)),
                '4': lambda: enter_location('work', lambda: work_location(game_state), can_reopen=True),
                '5': lambda: enter_location('adventure',
                                            lambda: adventure_location(adventure_instance),
                                            call_map_on_switch=False),
                '6': lambda: enter_location('garage', lambda: garage_location(game_state)),
                '7': lambda: enter_location('auto_dialer', lambda: auto_dialer_location(game_state)),
                '8': lambda: enter_location('bank', lambda: bank_location(game_state)),
                # Шаги
                '+': lambda: steps_today_manual_entry(game_state),
                # Меню персонажа
                'm': lambda: print('\nРаздел "Меню" - (Пока не работает).'),
                'i': lambda: inventory_menu(game_state),
                'e': lambda: Equipment.equipment_view(self=None, state=game_state),
                'c': lambda: char_info(game_state),
                'u': lambda: CharLevel(game_state).menu_skill_point_allocation(),
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
                energy_time_charge(game_state)
                work_check_done(game_state)
                skill_training_check_done(game_state)

                status_bar(game_state)

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
                        steps_today_manual_entry(game_state)
                    else:
                        try:
                            steps_today_set(int(rest), game_state)
                        except ValueError:
                            print('Неверный формат. Ожидается "+N", где N — целое число.')
                else:
                    COMMANDS.get(temp_number, unknown_command)()

        # Запуск функции, которая относится к локациям.
        loc_dispatch = {
            'home': lambda: home_location(game_state),
            'gym': lambda: gym_location(game_state),
            'shop': lambda: shop_location(game_state),
            'work': lambda: work_location(game_state),
            'adventure': lambda: adventure_location(adventure_instance),
            'garage': lambda: garage_location(game_state),
            'auto_dialer': lambda: auto_dialer_location(game_state),
            'bank': lambda: bank_location(game_state),
        }
        loc_handler = loc_dispatch.get(game_state.loc)
        if loc_handler is not None:
            loc_handler()
            location_selection()


if __name__ == "__main__":
    print(f"Version: 0.2.0b")
    os.system("chcp 65001")
    init()

    try:
        game()
    except (KeyboardInterrupt, EOFError):
        print('\n\nВыход без сохранения. Пока!')
