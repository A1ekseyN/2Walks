# Version - 0.0.1q


from functions import save_game_date_last_enter, char_info, location_change_map, steps, steps_today_update_manual, timestamp_now, energy_timestamp, energy_time_charge, status_bar
from characteristics import *
from locations import *
from gym import skill_training_check_done
from work import Work, work_check_done
from inventory import inventory_menu
#from work import work_check_done


def game():
    # Общая функция для игры
    while True:
        def location_selection():
            # Функция для выбора локации на карте
            global char_characteristic

            while True:
                if debug_mode:
                    print(char_characteristic)

                save_game_date_last_enter()     # Проверка даты последнего захода в игру.
                energy_time_charge()            # Проверка и восстановление игровой энергии.
                work_check_done()               # Проверка работает ли персонаж, и закончил ли он работу по таймауту.
                skill_training_check_done()     # Проверка или закончилось улучшение навыка и повышение lvl навыка.

                status_bar()                    # Отображение переменных: Шаги, Энергия, Деньги, работа, изучение навыков.
                print(f'Вы можете пройти в локацию:'
                      f'\n\t1. 🏠 Домой (Не работает)'
                      f'\n\t2. 🏋️ Спортзал'
                      f'\n\t3. 🛒 Магазин (Не работает)'
                      f'\n\t4. 🏭 Работа'
                      f'\n\t5. 🗺️ Приключение (Не работает)'
#                      f'\n\t6. 🚗 Гараж (Не работает)'
#                      f'\n\t7. 🚗 Авто-дилер (Не работает)'
#                      f'\n\t8. 🏛 Банк (Не работает)'
                      f'\n\t0. 🔄 Обновить кол-во шагов')
                print(f'\tm. Меню // i. 🎒 Инвентарь // c. Характеристики'
                      f'\n\ts. 💾 Save Game'
                      f'\n\tq/e. 💾 + 🚪 Save & Exit')
                try:
                    temp_number = input('Куда вы хотите пойти?:\n>>> ')
                except:
                    print('\n\nPlease enter digit or letter.')
                    continue

                if temp_number == '1' and char_characteristic['loc'] != 'home':
                    char_characteristic['loc'] = 'home'
                    home_location()
                    location_change_map()
                elif temp_number == '2' and char_characteristic['loc'] != 'gym':
                    char_characteristic['loc'] = 'gym'
                    gym_location()
                    location_change_map()
                elif temp_number == '2' and char_characteristic['loc'] == 'gym':
                    gym_location()
                elif temp_number == '3' and char_characteristic['loc'] != 'shop':
                    char_characteristic['loc'] = 'shop'
                    shop_location()
                    location_change_map()
                elif temp_number == '4' and char_characteristic['loc'] != 'work':
                    char_characteristic['loc'] = 'work'
                    work_location()
                    location_change_map()
                elif temp_number == '4' and char_characteristic['loc'] == 'work':
                    work_location()
                elif temp_number == '5' and char_characteristic['loc'] != 'adventure':
                    char_characteristic['loc'] = 'adventure'
                    adventure_location()
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
                    # Обновление кол-ва шагов через API.
                    steps_today_update_manual()

                # Меню персонажа, инвентаря.
                elif temp_number == 'm' or temp_number == 'ь':
                    print('\nРаздел "Меню" - (Пока не работает).')
                elif temp_number == 'i' or temp_number == 'ш':
                    inventory_menu()
                elif temp_number == 'c' or temp_number == 'с':
                    char_info()
                elif temp_number == 's' or temp_number == 'ы':
                    # Сохранение игры.
                    save_characteristic()
                elif temp_number == 'e' or temp_number == 'у' or temp_number == 'q' or temp_number == 'й':
                    # Сохранение игры, и выход.
                    save_characteristic()
                    print('🚪 Спасибо за игру. До встречи.')
                    quit()

#                elif temp_number == 'l' or temp_number == 'д':
#                    load_characteristic()

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
