# Version - 0.0.1d


from colorama import Fore, Style
from api import steps_today_update
import time
from functions import save_game_date_last_enter, char_info, location_change_map, steps, steps_today_update_manual
from characteristics import *


loc = char_characteristic['loc']
en = char_characteristic['energy']
stp_can_use = char_characteristic['steps_can_use']
print(loc)
print(en)
print(stp_can_use)
#loc = 'home', 'gym', 'shop', 'work', 'adventure', 'garage', 'auto_dialer, 'bank'


def energy_time_charge():
    # Функция для восстановления энергии со временем
#    global energy
    global energy_time

    ### !!!! Похоже, что функция, как-то не правильно работает.
    # Вроде ошибка в формуле расчёта (там где / 30 / 10)
    if char_characteristic['energy'] < char_characteristic['energy_max']:
        if time.time() - energy_time > 60:
            char_characteristic['energy'] += round((time.time() - energy_time) / 60)

            print('--- Energy Check!!! ---')
            print(f"Добавлено energy: {round((time.time() - energy_time) / 60)}")
            print(f"Счётчик времени: {time.time() - energy_time}")

            energy_time = time.time() # - (((time.time() - energy_time) - 60))    # Вроде делитель можно подобрать. Или погуглить как time.time считает время, вроде эпохами. Получается в качестве делителя нужно использовать время эпохи.
    if char_characteristic['energy'] > char_characteristic['energy_max']:
        char_characteristic['energy'] = char_characteristic['energy_max']


def game():
    # Общая функция для игры
    global loc
#    global steps_today_api
#    global steps_today
    global energy

    while True:
        def location_selection():
            # Функция для выбора локации на карте
            global loc
            global steps_today
            global energy

            while True:
                save_game_date_last_enter()     # Проверка даты последнего захода в игру.
                energy_time_charge()
                load_characteristic()
                print(f'\nSteps: {Fore.LIGHTCYAN_EX}{steps()}{Style.RESET_ALL}; '
                      f'Energy: {Fore.GREEN}{char_characteristic["energy"]} / {char_characteristic["energy_max"]}{Style.RESET_ALL} (+ 1 эн. через: {60 - (time.time() - energy_time):,.0f} sec.)')
                print(f'Вы находитесь в локации {Fore.GREEN}{loc}{Style.RESET_ALL}.')
                print(f'Вы можете пойти в локацию:'
                      f'\n\t1. Домой (Не работает)'
                      f'\n\t2. Спортзал (Не работает)'
                      f'\n\t3. Магазин (Не работает)'
                      f'\n\t4. Работа (Не работает)'
                      f'\n\t5. Приключение (Не работает)'
                      f'\n\t6. Гараж (Не работает)'
                      f'\n\t7. Авто-дилер (Не работает)'
                      f'\n\t8. Банк (Не работает)'
                      f'\n\t0. Обновить кол-во шагов')
                print(f'\tm. Меню // i. Инвентарь // c. Характеристики'
                      f'\n\ts. Save Game'
                      f'\n\tl. Load Game')
                try:
                    temp_number = input('Введите цифры куда вы хотите пойти: ')
                except:
                    print('\nPlease enter digit or letter.')
                    continue

                if temp_number == '1' and loc != 'home':
                    loc = 'home'
                    location_change_map()
                elif temp_number == '2' and loc != 'gym':
                    loc = 'gym'
                    location_change_map()
                elif temp_number == '3' and loc != 'shop':
                    loc = 'shop'
                    location_change_map()
                elif temp_number == '4' and loc != 'work':
                    loc = 'work'
                    location_change_map()
                elif temp_number == '5' and loc != 'adventure':
                    loc = 'adventure'
                    location_change_map()
                elif temp_number == '6' and loc != 'garage':
                    loc = 'garage'
                    location_change_map()
                elif temp_number == '7' and loc != 'auto_dialer':
                    loc = 'auto_dialer'
                    location_change_map()
                elif temp_number == '8' and loc != 'bank':
                    loc = 'bank'
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
                elif temp_number == 'l' or temp_number == 'д':
                    load_characteristic()

        if loc == 'home':
            print('-- Home Location.')
            location_selection()
        elif loc == 'shop':
            print('-- Shop Location.')
            location_selection()
        elif loc == 'work':
            print('-- Work Location.')
            location_selection()
        elif loc == 'adventure':
            print('-- Adventure Location.')
            location_selection()
        elif loc == 'garage':
            print('-- Garage Location.')
            location_selection()
        elif loc == 'auto_dialer':
            print('-- Auto Dialer Location.')
            location_selection()
        elif loc == 'bank':
            print('-- Bank Location.')
            location_selection()

game()
