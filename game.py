#pyinstaller --onefile --icon=icons/2walks.ico game.py

import os
import sys
import time
from colorama import init

from functions import save_game_date_last_enter, char_info, location_change_map, steps, steps_today_update_manual, steps_today_manual_entry, timestamp_now, energy_timestamp, energy_time_charge, status_bar
from characteristics import *
from equipment import Equipment
from locations import *
from gym import skill_training_check_done
from work import Work, work_check_done
from inventory import inventory_menu
from level import CharLevel
from google_sheets_db import save_char_characteristic_to_google_sheet, load_char_characteristic_from_google_sheet


def game():
    # Общая функция для игры
    while True:
        # Создаем класс для Приключений.
        # В этом месте у на заранее просчитываются бонусы навыков для прохождения приключений.
        adventure_instance = Adventure(adventure_data_table)

        def location_selection():
            # Функция для выбора локации на карте
            global char_characteristic

            # --- Helpers ---
            def enter_location(loc, enter_fn, can_reopen=False, call_map_on_switch=True):
                """Смена локации: если уже там — молчим либо повторно показываем меню (can_reopen=True)."""
                current = char_characteristic['loc']
                if current != loc:
                    char_characteristic['loc'] = loc
                    enter_fn()
                    if call_map_on_switch:
                        location_change_map()
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
                # .update() мутирует существующий dict — все импортёры видят новые данные.
                char_characteristic.update(load_char_characteristic_from_google_sheet())

            def unknown_command():
                print('\nНеизвестная команда. Попробуй ещё раз.')

            # --- Command dispatch table ---
            COMMANDS = {
                # Локации
                '1': lambda: enter_location('home', home_location),
                '2': lambda: enter_location('gym', gym_location, can_reopen=True),
                '3': lambda: enter_location('shop', shop_location),
                '4': lambda: enter_location('work', work_location, can_reopen=True),
                '5': lambda: enter_location('adventure',
                                            lambda: adventure_location(adventure_instance),
                                            call_map_on_switch=False),
                '6': lambda: enter_location('garage', garage_location),
                '7': lambda: enter_location('auto_dialer', auto_dialer_location),
                '8': lambda: enter_location('bank', bank_location),
                # Шаги
                '0': steps_today_update_manual,
                '+': steps_today_manual_entry,
                # Меню персонажа
                'm': lambda: print('\nРаздел "Меню" - (Пока не работает).'),
                'i': inventory_menu,
                'e': lambda: Equipment.equipment_view(self=None),
                'c': char_info,
                'u': lambda: CharLevel(char_characteristic).menu_skill_point_allocation(),
                # Сохранение / загрузка
                'l': load_from_cloud,
                's': save_game_local_and_cloud,
                'q': save_and_exit,
            }

            # --- Авто-маппинг русской раскладки на Latin-команды ---
            LAYOUT_RU_TO_EN = {
                'ь': 'm', 'ш': 'i', 'у': 'e', 'с': 'c', 'г': 'u',
                'д': 'l', 'ы': 's', 'й': 'q',
            }
            for cyr, lat in LAYOUT_RU_TO_EN.items():
                if lat in COMMANDS:
                    COMMANDS[cyr] = COMMANDS[lat]

            while True:
                energy_time_charge()            # Проверка и восстановление игровой энергии.
                work_check_done()               # Проверка работает ли персонаж, и закончил ли он работу по таймауту.
                skill_training_check_done()     # Проверка или закончилось улучшение навыка и повышение lvl навыка.

                status_bar()                    # Отображение переменных: Шаги, Энергия, Деньги, работа, изучение навыков.

                print(f'Вы можете пройти в локацию:'
                      f'\n\t1. 🏠 Домой (Не работает)'
                      f'\n\t2. 🏋️ Спортзал'
                      f'\n\t3. 🛒 Магазин (В тестовом режиме)'
                      f'\n\t4. 🏭 Работа'
                      f'\n\t5. 🗺️ Приключение (В тестовом режиме)'
#                      f'\n\t6. 🚗 Гараж (Не работает)'
#                      f'\n\t7. 🚗 Авто-дилер (Не работает)'
#                      f'\n\t8. 🏛 Банк (Не работает)'
                      f'\n\t0. 🔄 Обновить кол-во шагов (API)'
                      f'\n\t+. Ввести шаги вручную')
                print(f'\tm. Меню // '
                      f'i. 🎒 Инвентарь // '
                      f'e. 🎒 Экипировка // '
                      f'c. Характеристики // '
                      f'u. Level'
                      f'\n\tl. ☁ Load from Cloud'
                      f'\n\ts. 💾 Save Game'
                      f'\n\tq/e. 💾 + 🚪 Save & Exit')
                try:
                    temp_number = input('Куда вы хотите пойти?:\n>>> ')
                except:
                    print('\n\nPlease enter digit or letter.')
                    continue

                COMMANDS.get(temp_number, unknown_command)()

        # Запуск функции, которая относится к локациям
        if char_characteristic['loc'] == 'home':
            home_location()
            location_selection()
        elif char_characteristic['loc'] == 'gym':
            gym_location()
            location_selection()
        elif char_characteristic['loc'] == 'shop':
            shop_location()
            location_selection()
        elif char_characteristic['loc'] == 'work':
            work_location()
            location_selection()
        elif char_characteristic['loc'] == 'adventure':
            adventure_location()
            location_selection()
        elif char_characteristic['loc'] == 'garage':
            garage_location()
            location_selection()
        elif char_characteristic['loc'] == 'auto_dialer':
            auto_dialer_location()
            location_selection()
        elif char_characteristic['loc'] == 'bank':
            bank_location()
            location_selection()


if __name__ == "__main__":
    print(f"Version: 0.1.0")
    os.system("chcp 65001")         # Включение Unicode для консоли. Все равно это не работает

    game()
