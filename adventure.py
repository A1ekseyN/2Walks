from adventure_data import adventure_data_table
from characteristics import char_characteristic
from colors import steps_color, energy_color
from datetime import datetime, timedelta
from drop import Drop_Item
from functions_02 import time
from skill_bonus import speed_skill_equipment_and_level_bonus
from colorama import Fore, Style
from settings import debug_mode
from bonus import apply_move_optimization_adventure
from inventory import Wear_Equipped_Items


class Adventure():
    # Класс для Adventure (Приключений).
    def __init__(self, adventure_data_table):
        self.adventures = {
            '1': {'name': 'walk_easy', 'data': apply_move_optimization_adventure(adventure_data_table['walk_easy'])},
            '2': {'name': 'walk_normal', 'data': apply_move_optimization_adventure(adventure_data_table['walk_normal'])},
            '3': {'name': 'walk_hard', 'data': apply_move_optimization_adventure(adventure_data_table['walk_hard'])},
            '4': {'name': 'walk_15k', 'data': apply_move_optimization_adventure(adventure_data_table['walk_15k'])},
            '5': {'name': 'walk_20k', 'data': apply_move_optimization_adventure(adventure_data_table['walk_20k'])},
            '6': {'name': 'walk_25k', 'data': apply_move_optimization_adventure(adventure_data_table['walk_25k'])},
            '7': {'name': 'walk_30k', 'data': apply_move_optimization_adventure(adventure_data_table['walk_30k'])},
        }
        self.adventure_requirements = {}
        for key, adventure in self.adventures.items():
            self.adventure_requirements[key] = f'🏃: {steps_color(adventure["data"]["steps"])} шагов, ' \
                                               f'🔋: {energy_color(adventure["data"]["energy"])} энергии, ' \
                                               f'🕑: {time(speed_skill_equipment_and_level_bonus(adventure["data"]["time"]))}'

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
                elif char_characteristic['adventure_name'] == 'walk_25k':
                    Drop_Item.item_collect(self=None, hard='walk_25k')
                    char_characteristic['adventure_walk_25k_counter'] += 1
                elif char_characteristic['adventure_name'] == 'walk_30k':
                    Drop_Item.item_collect(self=None, hard='walk_30k')
                    char_characteristic['adventure_walk_30k_counter'] += 1

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
        print(f"Steps 🏃: {char_characteristic['steps_can_use']}, "
              f"Energy 🔋: {char_characteristic['energy']}, "
              f"Money 💰: {char_characteristic['money']} $,")
        print('Вы можете отправить персонажа в приключение.'
              '\nВ приключении, персонаж может получить полезные предметы.')

        print('\nДоступные приключения: '
              f'\n\t1. Прогулка вокруг озера: {self.adventure_requirements["1"]} - (Награда: C-Grade (Ring, Necklace))')

        if char_characteristic['adventure_walk_easy_counter'] >= 3:
            print(f'\t2. Прогулка по району:    {self.adventure_requirements["2"]} - (Награда: C-Grade, B-Grade (Ring, Necklace))')
        else:
            print(f'\t- Пройдите - "Прогулку вокруг озера": {3 - char_characteristic["adventure_walk_easy_counter"]} раз.')

        if char_characteristic['adventure_walk_normal_counter'] >= 3:
            print(f'\t3. Прогулка в лес:        {self.adventure_requirements["3"]} - (Награда: C-Grade, B-Grade, A-Grade (Ring, Necklace))')
        else:
            print(f'\t- Пройдите - "Прогулку по району" еще: {3 - char_characteristic["adventure_walk_normal_counter"]} раз.')

        # Пункт 4 – новый: unlock для walk_15k (например, после 3 раз прохождения walk_hard)
        if char_characteristic.get('adventure_walk_hard_counter', 0) >= 3:
            print(f'\t4. Прогулка 15к шагов:    {self.adventure_requirements["4"]} - (Need to Test) (Награда: B-Grade, A-Grade, S-Grade)')
        else:
            print(f'\t- Пройдите "Прогулку в лес" еще: {3 - char_characteristic.get("adventure_walk_hard_counter", 0)} раз.')

        if char_characteristic['adventure_walk_15k_counter'] >= 3:
            print(f'\t5. Прогулка 20к шагов:    {self.adventure_requirements["5"]} - (Награда: A-Grade, S-Grade, S+Grade (Ring, Necklace))')
        else:
            print(f'\t- Пройдите прогулку на 15к еще: {3 - char_characteristic["adventure_walk_15k_counter"]} раз.')

        if char_characteristic['adventure_walk_20k_counter'] >= 3:
            print(f'\t6. Прогулка 25к шагов:    {self.adventure_requirements["6"]} - (Награда: S-Grade, S+Grade (Ring, Necklace))')
        else:
            print(f'\t- Пройдите прогулку на 20к еще: {3 - char_characteristic["adventure_walk_20k_counter"]} раз.')

        if char_characteristic['adventure_walk_25k_counter'] >= 3:
            print(f'\t7. Прогулка 30к шагов:    {self.adventure_requirements["7"]} - (Награда: S+Grade (Ring, Necklace))')
        else:
            print(f'\t- Пройдите прогулку на 25к еще: {3 - char_characteristic["adventure_walk_25k_counter"]} раз.')

        print('\t0. Выход')
        self.adventure_choice()

    def adventure_choice(self):
        # Выбор приключения
        try:
            ask = input('\nВыберите локацию, в которую хотите отправиться:\n>>> ')
            if ask in self.adventures:
                adv = self.adventures[ask]
                adv_name = adv['name']
                adv_data = adv['data']
                adv_req = self.adventure_requirements[ask]
                adv_steps = adv_data['steps']
                adv_energy = adv_data['energy']
                adv_time = speed_skill_equipment_and_level_bonus(adv_data['time'])
                self.adventure_choice_confirmation(adv_name, adv_req, adv_steps, adv_energy, adv_time)
            elif ask == '0':
                pass
            else:
                self.adventure_menu()
        except:
            self.adventure_menu()

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
                if self.check_requirements(adv_name, adv_steps, adv_energy, adv_time):
                    pass
                else:
                    self.adventure_menu()
            elif ask == '0':
                self.adventure_menu()
            else:
                self.adventure_choice_confirmation(adv_name, adv_req, adv_steps, adv_energy, adv_time)
        except Exception as error:
            print(f'Ошибка подтверждения выбора Приключения: {error}')
#            self.adventure_choice_confirmation(adv_name, adv_req, adv_steps, adv_energy, adv_time)

    def check_requirements(self, adv_name, adv_steps, adv_energy, adv_time):
        # Проверка требований для Приключения.
        if char_characteristic['steps_can_use'] >= adv_steps and char_characteristic['energy'] >= adv_energy:
            print('\nПроверка требований успешна.')
            self.start_adventure(adv_name, adv_steps, adv_energy, adv_time)

            # Износ Экипировки
            steps = adv_steps
            equipped_items_manager = Wear_Equipped_Items()
            equipped_items_manager.decrease_durability(steps)

            return True
        else:
            if char_characteristic['steps_can_use'] < adv_steps:
                print('\n- Не достаточно: 🏃 шагов.')
            if char_characteristic['energy'] < adv_energy:
                print('- Не достаточно: 🔋 энергии.')
#            self.adventure_menu()
            return False

    def start_adventure(self, adv_name, adv_steps, adv_energy, adv_time):
        # Начало приключения.
        print(f'\nНачало приключения: {adv_name}')
        char_characteristic['adventure'] = True
        char_characteristic['adventure_name'] = adv_name
        char_characteristic['adventure_start_timestamp'] = int(datetime.now().timestamp())
        char_characteristic['adventure_end_timestamp'] = int(datetime.now().timestamp()) + (adv_time * 60)
        char_characteristic['steps_today_used'] += adv_steps
        char_characteristic['steps_total_used'] += adv_steps
        char_characteristic['energy'] -= adv_energy

        print(f'Steps_used_today 🏃: {char_characteristic["steps_today_used"]}')
        print(f'Energy used 🔋: {adv_energy}')
        if debug_mode:
            print(f'Energy Left: {char_characteristic["energy"]}')
            print(f'Время_now: {datetime.now().timestamp()}')
            print(f'Время прохождения Приключения: {char_characteristic["adventure_end_timestamp"] - datetime.now().timestamp()}')
        return char_characteristic
