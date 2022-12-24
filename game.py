# Version - 0.0.1h


from colorama import Fore, Style
from functions import save_game_date_last_enter, char_info, location_change_map, steps, steps_today_update_manual, timestamp_now, energy_timestamp
from characteristics import *
from locations import *
from settings import debug_mode

def energy_time_charge():
    # Функция для восстановления энергии со временем
    # Нужно перенести в файл functions.py
    global char_characteristic

    if char_characteristic['energy'] < char_characteristic['energy_max']:
#        if time.time() - energy_time > 60:
#            char_characteristic['energy'] += round((time.time() - energy_time) / 60)
#            print(f"Добавлено energy: {round((time.time() - energy_time) / 60)}")
#            print(f"Счётчик времени: {time.time() - energy_time}")
#            energy_time = time.time() # - (((time.time() - energy_time) - 60))    # Вроде делитель можно подобрать. Или погуглить как time.time считает время, вроде эпохами. Получается в качестве делителя нужно использовать время эпохи.
        if timestamp_now() - char_characteristic['energy_time_stamp'] > 60:
            # Bug: Нужно добавить деление остатка и минусовать его от 'energy_time_stamp'
            # Bug: Поправить char_characteristic['energy'] += round (округление). Ошибка в округлении 1.6, округляет в большую сторону.
            char_characteristic['energy'] += round((timestamp_now() - char_characteristic['energy_time_stamp']) // 60)
            char_characteristic['energy_time_stamp'] = timestamp_now() - ((timestamp_now() - char_characteristic['energy_time_stamp']) % 60)
            if debug_mode:
                print('\n--- Energy Check!!! ---')
                print(f"Добавлено energy: {round((timestamp_now() - char_characteristic['energy_time_stamp']) // 60)}")
                print(f"Счётчик времени: {round(timestamp_now() - char_characteristic['energy_time_stamp'])} sec.")

    if char_characteristic['energy'] > char_characteristic['energy_max']:
        char_characteristic['energy'] = char_characteristic['energy_max']


def game():
    # Общая функция для игры

    while True:
        def location_selection():
            # Функция для выбора локации на карте
            global steps_today
            global char_characteristic

            while True:
                save_game_date_last_enter()     # Проверка даты последнего захода в игру.
                energy_time_charge()
                print(f'\nSteps 🏃: {Fore.LIGHTCYAN_EX}{steps()} / {char_characteristic["steps_today"]}{Style.RESET_ALL}; '
                      f'Energy 🔋: {Fore.GREEN}{char_characteristic["energy"]} / {char_characteristic["energy_max"]}{Style.RESET_ALL} (+ 1 эн. через: {abs(60 - (timestamp_now() - char_characteristic["energy_time_stamp"])):,.0f} sec.)')
                print(f'$: {char_characteristic["money"]}')
                print(f'Вы находитесь в локации {Fore.GREEN}{char_characteristic["loc"]}{Style.RESET_ALL}.')
                print(f'Вы можете пойти в локацию:'
                      f'\n\t1. 🏠 Домой (Не работает)'
                      f'\n\t2. 🏋️ Спортзал (Не работает)'
                      f'\n\t3. 🛒 Магазин (Не работает)'
                      f'\n\t4. 🏭 Работа (Не работает)'
                      f'\n\t5. 🗺️ Приключение (Не работает)'
                      f'\n\t6. 🚗 Гараж (Не работает)'
                      f'\n\t7. Авто-дилер (Не работает)'
                      f'\n\t8. Банк (Не работает)'
                      f'\n\t0. 🔄 Обновить кол-во шагов')
                print(f'\tm. Меню // i. Инвентарь // c. Характеристики'
                      f'\n\ts. 💾 Save Game')
#                      f'\n\te. Save & Exit')
                try:
                    temp_number = input('Куда вы хотите пойти?:\n>>> ')
                except:
                    print('\nPlease enter digit or letter.')
                    continue

                if temp_number == '1' and char_characteristic['loc'] != 'home':
                    char_characteristic['loc'] = 'home'
                    home_location()
                    location_change_map()
                elif temp_number == '2' and char_characteristic['loc'] != 'gym':
                    char_characteristic['loc'] = 'gym'
                    gym_location()
                    location_change_map()
                elif temp_number == '3' and char_characteristic['loc'] != 'shop':
                    char_characteristic['loc'] = 'shop'
                    shop_location()
                    location_change_map()
                elif temp_number == '4' and char_characteristic['loc'] != 'work':
                    char_characteristic['loc'] = 'work'
                    work_location()
                    location_change_map()
                elif temp_number == '5' and char_characteristic['loc'] != 'adventure':
                    char_characteristic['loc'] = 'adventure'
                    adventure_location()
                    location_change_map()
                elif temp_number == '6' and char_characteristic['loc'] != 'garage':
                    char_characteristic['loc'] = 'garage'
                    garage_location()
                    location_change_map()
                elif temp_number == '7' and char_characteristic['loc'] != 'auto_dialer':
                    char_characteristic['loc'] = 'auto_dialer'
                    auto_dialer_location()
                    location_change_map()
                elif temp_number == '8' and char_characteristic['loc'] != 'bank':
                    char_characteristic['loc'] = 'bank'
                    bank_location()
                    location_change_map()
                elif temp_number == '0':
                    # Обновление кол-ва шагов через API
                    steps_today_update_manual()

                # Меню персонажа, инвентаря.
                # Пока функционал не дописан
                elif temp_number == 'm' or temp_number == 'ь':
                    print('\nРаздел "Меню" - пока не работает.')
                elif temp_number == 'i' or temp_number == 'ш':
                    print('\nИнвентарь - Пока не работает.')
                elif temp_number == 'c' or temp_number == 'с':
                    char_info()
                elif temp_number == 's' or temp_number == 'ы':
                    save_characteristic()
#                elif temp_number == 'l' or temp_number == 'д':
#                    load_characteristic()
                # Дописать функционал по закрытию игры с кнопки 'e'.
                # Через break и global переменную не работает.
#                elif temp_number == 'e' or temp_number == 'у':
#                    save_characteristic()

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

game()
