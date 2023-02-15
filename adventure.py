from adventure_data import adventure_data_table
from characteristics import char_characteristic
from colors import steps, energy
from datetime import datetime, timedelta
from drop import Drop_Item
from functions_02 import time
from skill_bonus import speed_skill_equipment_bonus_def
from colorama import Fore, Style


walk_easy = adventure_data_table['walk_easy']
walk_normal = adventure_data_table['walk_normal']
walk_hard = adventure_data_table['walk_hard']


walk_easy_requirements = f'🏃: {steps(walk_easy["steps"])} шагов, ' \
                         f'🔋: {energy(walk_easy["energy"])} энергии, ' \
                         f'🕑: {time(speed_skill_equipment_bonus_def(walk_easy["time"]))} '
walk_normal_requirements = f'🏃: {steps(walk_normal["steps"])} шагов, ' \
                           f'🔋: {energy(walk_normal["energy"])} энергии, ' \
                           f'🕑: {time(speed_skill_equipment_bonus_def(walk_normal["time"]))}'
walk_hard_requirements = f'🏃: {steps(walk_hard["steps"])} шагов, ' \
                         f'🔋: {energy(walk_hard["energy"])} энергии, ' \
                         f'🕑: {time(speed_skill_equipment_bonus_def(walk_hard["time"]))}'


class Adventure():
    # Класс для Adventure (Приключений).

    def adventure_check_done(self):
        # Проверка или начатое Приключение - закончилось.
        if char_characteristic['adventure'] == True:
            if char_characteristic['adventure_end_timestamp'] <= datetime.now().timestamp():
                print('\nПриключение пройдено.')
                char_characteristic['adventure'] = False
                char_characteristic['adventure_name'] = None
                char_characteristic['adventure_end_timestamp'] = None

                # Drop function
                Drop_Item.item_collect(self=None)

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
              f'\n\t1. Прогулка вокруг озера: {walk_easy_requirements} (Награда: C-Grade (Rings, Necklace))'
              f'\n\t2. Прогулка по району:    {walk_normal_requirements} - (Не работает)'
              f'\n\t3. Прогулка в лес:        {walk_hard_requirements} - (Не работает)'
              #          '\n\t4. хххххх прогулка - 20.000 шагов. (Пока не работает)'
              '\n\t0. Выход')
        Adventure.adventure_choice(self)

    def adventure_choice(self):
        # Выбор приключения
        try:
            ask = input('\nВыберите локацию, в которую хотите отправиться:\n>>> ')
            if ask == '1':
                adv_name = '🗺️ Прогулка вокруг озера 🗺️'
                adv_req = walk_easy_requirements
                adv_steps = walk_easy['steps']
                adv_energy = walk_easy['energy']
                adv_time = speed_skill_equipment_bonus_def(walk_easy['time'])
                Adventure.adventure_choice_confirmation(self, adv_name, adv_req, adv_steps, adv_energy, adv_time)
            elif ask == '2':
                adv_name = '🗺️ Прогулка про району 🗺️'
                adv_req = walk_normal_requirements
                adv_steps = walk_normal['steps']
                adv_energy = walk_normal['energy']
                adv_time = speed_skill_equipment_bonus_def(walk_normal['time'])
                Adventure.adventure_choice_confirmation(self, adv_name, adv_req, adv_steps, adv_energy, adv_time)
            elif ask == '3':
                adv_name = '🗺️ Прогулка в лес 🗺️'
                adv_req = walk_hard_requirements
                adv_steps = walk_hard['steps']
                adv_energy = walk_hard['energy']
                adv_time = speed_skill_equipment_bonus_def(walk_hard['time'])
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
#        if char_characteristic['steps_can_use'] >= 0 and char_characteristic['energy'] >= adv_energy:
            print('\nПроверка требований успешна.')
            Adventure.start_adventure(self, adv_name, adv_steps, adv_energy, adv_time)
        else:
            if char_characteristic['steps_can_use'] < adv_steps:
                print('\n- Не достаточно: 🏃 шагов.')
            if char_characteristic['energy'] < adv_energy:
                print('-Не достаточно: 🔋 энергии.')
            Adventure.adventure_menu(self)

    def start_adventure(self, adv_name, adv_steps, adv_energy, adv_time):
        # Начало приключения.
        print(f'\nНачало приключения: {adv_name}')
        char_characteristic['adventure'] = True
        char_characteristic['adventure_name'] = adv_name
        char_characteristic['adventure_end_timestamp'] = datetime.now().timestamp() + (adv_time * 60)
        char_characteristic['steps_today_used'] += adv_steps
        char_characteristic['energy'] -= adv_energy

        print(f'Steps_used_today: {char_characteristic["steps_today_used"]}')
        print(f'Energy Left: {char_characteristic["energy"]}')
        print(f'Время_now: {datetime.now().timestamp()}')
        print(f'Время прохождения Приключения: {char_characteristic["adventure_end_timestamp"]}')
        return char_characteristic

    def walk_easy(self):
        pass

    def walk_normal(self):
        pass

    def walk_hard(self):
        pass

#Adventure.adventure_menu(self=None)
