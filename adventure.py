from adventure_data import adventure_data_table
from characteristics import char_characteristic
from colors import steps, energy
from datetime import datetime, timedelta
from drop import Drop_Item
from functions_02 import time
from skill_bonus import speed_skill_equipment_bonus_def
from colorama import Fore, Style
from settings import debug_mode


walk_easy = adventure_data_table['walk_easy']
walk_normal = adventure_data_table['walk_normal']
walk_hard = adventure_data_table['walk_hard']
walk_15k = adventure_data_table['walk_15k']
walk_20k = adventure_data_table['walk_20k']


walk_easy_requirements = f'🏃: {steps(walk_easy["steps"])} шагов, ' \
                         f'🔋: {energy(walk_easy["energy"])} энергии, ' \
                         f'🕑: {time(speed_skill_equipment_bonus_def(walk_easy["time"]))} '
walk_normal_requirements = f'🏃: {steps(walk_normal["steps"])} шагов, ' \
                           f'🔋: {energy(walk_normal["energy"])} энергии, ' \
                           f'🕑: {time(speed_skill_equipment_bonus_def(walk_normal["time"]))}'
walk_hard_requirements = f'🏃: {steps(walk_hard["steps"])} шагов, ' \
                         f'🔋: {energy(walk_hard["energy"])} энергии, ' \
                         f'🕑: {time(speed_skill_equipment_bonus_def(walk_15k["time"]))}'
walk_15k_requirements = f'🏃: {steps(walk_15k["steps"])} шагов, ' \
                         f'🔋: {energy(walk_15k["energy"])} энергии, ' \
                         f'🕑: {time(speed_skill_equipment_bonus_def(walk_20k["time"]))}'
walk_20k_requirements = f'🏃: {steps(walk_20k["steps"])} шагов, ' \
                         f'🔋: {energy(walk_20k["energy"])} энергии, ' \
                         f'🕑: {time(speed_skill_equipment_bonus_def(walk_20k["time"]))}'


class Adventure():
    # Класс для Adventure (Приключений).

    def adventure_check_done(self):
        # Проверка или начатое Приключение - закончилось.
        if char_characteristic['adventure'] == True:
            if char_characteristic['adventure_end_timestamp'] <= datetime.now().timestamp():
                print('\n🗺 Приключение пройдено. 🗺')

                # Drop function
                if char_characteristic['adventure_name'] == 'walk_easy':
                    Drop_Item.item_collect(self=None, hard='walk_easy')
                    char_characteristic['adventure_walk_easy_counter'] += 1
                elif char_characteristic['adventure_name'] == 'walk_normal':
                    Drop_Item.item_collect(self=None, hard='walk_normal')
                    char_characteristic['adventure_walk_normal_counter'] += 1
                elif char_characteristic['adventure_name'] == 'walk_hard':
                    Drop_Item.item_collect(self=None, hard='walk_hard')
                    char_characteristic['adventure_walk_hard_counter'] += 1
                elif char_characteristic['adventure_name'] == 'walk_15k':
                    Drop_Item.item_collect(self=None, hard='walk_15k')
                    char_characteristic['adventure_walk_15k_counter'] += 1
                elif char_characteristic['adventure_name'] == 'walk_20k':
                    Drop_Item.item_collect(self=None, hard='walk_20k')
                    char_characteristic['adventure_walk_20k_counter'] += 1

                char_characteristic['adventure'] = False
                char_characteristic['adventure_name'] = None
                char_characteristic['adventure_end_timestamp'] = None

            elif char_characteristic['adventure_end_timestamp'] > datetime.now().timestamp():
                adv_end = datetime.fromtimestamp(char_characteristic["adventure_end_timestamp"]) - datetime.fromtimestamp(datetime.now().timestamp())
                adv_end = str(adv_end).split('.')[0]
                print(f'\t🗺️ Персонаж находится в Приключении: {char_characteristic["adventure_name"].title()}.')
                print(f'\t🕑 Персонаж вернется через: {Fore.LIGHTBLUE_EX}{adv_end}{Style.RESET_ALL}')

    def adventure_menu(self):
        # Меню раздела приключение.
        print('\n ️🗺 ️--- Меню Приключения --- 🗺️')
        print('\nВы можете отправить персонажа в приключение.'
              '\nВ приключении, персонаж может получить полезные предметы.')

        print('\nДоступные приключения: '
              f'\n\t1. Прогулка вокруг озера: {walk_easy_requirements}- (Награда: C-Grade (Ring, Necklace))')

        if char_characteristic['adventure_walk_easy_counter'] >= 3:
            print(f'\t2. Прогулка по району:    {walk_normal_requirements} - (Награда: C-Grade, B-Grade (Ring, Necklace))')
        elif char_characteristic['adventure_walk_easy_counter'] < 3:
            print(f'\t- Пройдите - "Прогулку вокруг озера": {3 - char_characteristic["adventure_walk_easy_counter"]} раз.')

        if char_characteristic['adventure_walk_normal_counter'] >= 3:
            print(f'\t3. Прогулка в лес:        {walk_hard_requirements} - (Награда: C-Grade, B-Grade, A-Grade (Ring, Necklace))')
        elif char_characteristic['adventure_walk_normal_counter'] < 3:
            print(f'\t- Пройдите - "Прогулку по районе еще": {3 - char_characteristic["adventure_walk_normal_counter"]} раз.')

        if char_characteristic['adventure_walk_hard_counter'] >= 3:
            print(f'\t4. Прогулка на 15к шагов: {walk_15k_requirements} - (Награда: B-Grade, A-Grade, S-Grade (Ring, Necklace))')
        elif char_characteristic['adventure_walk_hard_counter'] < 3:
            print(f'\t- Пройдите прогулку в лесу еще: {3 - char_characteristic["adventure_walk_hard_counter"]} раз.')

        if char_characteristic['adventure_walk_15k_counter'] >= 3:
            print(f'\t5. Прогулка на 20к шагов: {walk_20k_requirements} - (Награда: A-Grade, S-Grade, S+Grade (Ring, Necklace))')
        elif char_characteristic['adventure_walk_15k_counter'] < 3 and char_characteristic['adventure_walk_hard_counter'] >= 3:
            print(f'\t- Пройдите прогулку на 15к еще: {3 - char_characteristic["adventure_walk_15k_counter"]} раз.')

        print('\t0. Выход')
        Adventure.adventure_choice(self)

    def adventure_choice(self):
        # Выбор приключения
        try:
            ask = input('\nВыберите локацию, в которую хотите отправиться:\n>>> ')
            if ask == '1':
                adv_name = 'walk_easy'
                adv_req = walk_easy_requirements
                adv_steps = walk_easy['steps']
                adv_energy = walk_easy['energy']
                adv_time = speed_skill_equipment_bonus_def(walk_easy['time'])
                Adventure.adventure_choice_confirmation(self, adv_name, adv_req, adv_steps, adv_energy, adv_time)
            elif ask == '2':
                adv_name = 'walk_normal'
                adv_req = walk_normal_requirements
                adv_steps = walk_normal['steps']
                adv_energy = walk_normal['energy']
                adv_time = speed_skill_equipment_bonus_def(walk_normal['time'])
                Adventure.adventure_choice_confirmation(self, adv_name, adv_req, adv_steps, adv_energy, adv_time)
            elif ask == '3':
                adv_name = 'walk_hard'
                adv_req = walk_hard_requirements
                adv_steps = walk_hard['steps']
                adv_energy = walk_hard['energy']
                adv_time = speed_skill_equipment_bonus_def(walk_hard['time'])
                Adventure.adventure_choice_confirmation(self, adv_name, adv_req, adv_steps, adv_energy, adv_time)
            elif ask == '4':
                adv_name = 'walk_15k'
                adv_req = walk_15k_requirements
                adv_steps = walk_15k['steps']
                adv_energy =walk_15k['energy']
                adv_time = speed_skill_equipment_bonus_def(walk_15k['time'])
                Adventure.adventure_choice_confirmation(self, adv_name, adv_req, adv_steps, adv_energy, adv_time)
            elif ask == '5':
                adv_name = 'walk_20k'
                adv_req = walk_20k_requirements
                adv_steps = walk_20k['steps']
                adv_energy = walk_20k['energy']
                adv_time = speed_skill_equipment_bonus_def(walk_20k['time'])
                Adventure.adventure_choice_confirmation(self, adv_name, adv_req, adv_steps, adv_energy, adv_time)
            elif ask == '0':
                pass
            else:
                Adventure.adventure_menu(self)
        except:
            print('Choice - Error.')
            Adventure.adventure_menu(self)

    def adventure_choice_confirmation(self, adv_name, adv_req, adv_steps, adv_energy, adv_time):
        # Подтверждение выбора Приключения. + Описание Приключения и возможный дроп с него.
        print(f'\nВы выбрали приключение: {adv_name}.'
              f'\nДля прохождения приключения необходимо: {adv_req}'
              '\n\t1. Пройти Приключение.'
              '\n\t0. Назад.')
        try:
            ask = input('\n>>> ')
            if ask == '1':
                # Проверка требований для приключения.
                Adventure.check_requirements(self, adv_name, adv_steps, adv_energy, adv_time)
            elif ask == '0':
                Adventure.adventure_menu(self)
            else:
                Adventure.adventure_choice_confirmation(self, adv_name, adv_req, adv_steps, adv_energy, adv_time)
        except:
            print('Ошибка подтверждения выбора Приключения.')
            Adventure.adventure_choice_confirmation(self, adv_name, adv_req, adv_steps, adv_energy, adv_time)

    def check_requirements(self, adv_name, adv_steps, adv_energy, adv_time):
        # Проверка требований для Приключения.
#        print(f'\nПроверка требований для прохождения приключения.')
#        print(f'Steps can use: {char_characteristic["steps_can_use"]}')
#        print(f'Steps: {adv_steps}')
#        print(f'Energy: {adv_energy}')
#        print(f'Time: {adv_time}')
#        print(f'adv_name: {adv_name}')

        if char_characteristic['steps_can_use'] >= adv_steps and char_characteristic['energy'] >= adv_energy:
            print('\nПроверка требований успешна.')
            Adventure.start_adventure(self, adv_name, adv_steps, adv_energy, adv_time)
        else:
            if char_characteristic['steps_can_use'] < adv_steps:
                print('\n- Не достаточно: 🏃 шагов.')
            if char_characteristic['energy'] < adv_energy:
                print('- Не достаточно: 🔋 энергии.')
            Adventure.adventure_menu(self)

    def start_adventure(self, adv_name, adv_steps, adv_energy, adv_time):
        # Начало приключения.
        print(f'\nНачало приключения: {adv_name}')
        char_characteristic['adventure'] = True
        char_characteristic['adventure_name'] = adv_name
        char_characteristic['adventure_end_timestamp'] = datetime.now().timestamp() + (adv_time * 60)
        char_characteristic['steps_today_used'] += adv_steps
        char_characteristic['energy'] -= adv_energy

        print(f'Steps_used_today 🏃: {char_characteristic["steps_today_used"]}')
        print(f'Energy used 🔋: {adv_energy}')
        if debug_mode:
            print(f'Energy Left: {char_characteristic["energy"]}')
            print(f'Время_now: {datetime.now().timestamp()}')
            print(f'Время прохождения Приключения: {char_characteristic["adventure_end_timestamp"] - datetime.now().timestamp()}')
        return char_characteristic

    def walk_easy(self):
        pass

    def walk_normal(self):
        pass

    def walk_hard(self):
        pass

#Adventure.adventure_menu(self=None)
