from characteristics import char_characteristic
from datetime import datetime, timedelta
from colorama import Fore, Style
from functions_02 import time


work_requirements = {
    'watchman': {'steps': 200, 'energy': 4, 'salary': 2},
    'factory': {'steps': 500, 'energy': 7, 'salary': 5},
    'courier_foot': {'steps': 1000, 'energy': 10, 'salary': 10},
}


print(work_requirements['watchman']['steps'])
print(work_requirements['watchman']['salary'])


class Work():
    # Класс инициализации работы

    def __init__(self, work, salary, working, working_hours, working_end, steps_can_use):
        self.work = work
        self.work_salary = salary
        self.working = working
        self.working_hours = working_hours
        self.working_end = working_end
        self.steps_can_use = steps_can_use

    def work_choise(self):
        print(f'\nВ этой локации можно устроится на работу. '
              f'\nОплата почасовая 🕑: 1 час = {time(round(60 - ((60 / 100) * char_characteristic["speed_skill"])))}')
        print('На данный момент доступны вакансии:'
              f'\n\t1. Сторож - 💰: {Fore.LIGHTYELLOW_EX}2{Style.RESET_ALL} $ (🏃: 200 + 🔋: 4).'
              f'\n\t2. Завод  - 💰: {Fore.LIGHTYELLOW_EX}5{Style.RESET_ALL} $ (🏃: 500 + 🔋: 7).'
              f'\n\t3. Курьер - 💰: {Fore.LIGHTYELLOW_EX}10{Style.RESET_ALL} $ (🏃: 1000 + 🔋: 10).'
              '\n\t0. Вернуться назад.')
        try:
            working = input('\nВыберите вакансию, или вернитесь обратно:\n>>> ')
            if working == '1':
                work = 'watchman'
                Work.ask_hours(self, work)
            elif working == '2':
                # Вакансия - Завод
                work = 'factory'
                Work.ask_hours(self, work)
            elif working == '3':
                # Вакансия - Курьер
                work = 'courier_foot'
                Work.ask_hours(self, work)
            elif working == '0':
                # Выход в меню.
                pass
        except:
            print('\nВы ввели не правильные данные. Попробуйте еще раз.')
            Work.work_choise(self)
        return working

    def ask_hours(self, work):
        # Сколько рабочих часов
        try:
            print(f'\nВы выбрали вакансию: {Fore.GREEN}{work.title()}{Style.RESET_ALL} c зарплатой: {Fore.LIGHTYELLOW_EX}{work_requirements[work]["salary"]}{Style.RESET_ALL} $ в час.')
            print(f'Оплата почасовая 🕑: 1 час = {time(round(60 - ((60 / 100) * char_characteristic["speed_skill"])))}.')
            working_hours = abs(int(input('\nВведите количество рабочих часов: 1 - 8.\n0. Выход.\n>>> ')))
            if working_hours >= 1 and working_hours <= 8:
                Work.check_requirements(self, work, working_hours)
            elif working_hours == 0:
                pass
            else:
                print('\nНужно ввести число рабочих часов в диапазоне 1 - 8.')
                Work.ask_hours(self, work)
        except:
            print('\nВы ввели не правильные данные. Попробуйте еще раз.')
            Work.ask_hours(self, work)

    def check_requirements(self, work, working_hours):
        # Проверка требований для устройства на работу.
        print('Check Requirements.')
        print(working_hours)
        if working_hours >= 1:
            print('Check #02.')
            print(f'Steps_can_use: {char_characteristic["steps_can_use"]}')
            print(f'Steps need: {working_hours * 200}')
            print(f'Energy: {char_characteristic["energy"]}')
            print(f'Energy Need: {working_hours * 4}')
            print(char_characteristic['steps_can_use'] >= working_hours * 200 and char_characteristic['energy'] >= working_hours * 4)

            if char_characteristic['steps_can_use'] >= working_hours * work_requirements[work]["steps"] and char_characteristic['energy'] >= working_hours * work_requirements[work]["energy"]:
                char_characteristic['steps_today_used'] = char_characteristic['steps_today_used'] + (working_hours * work_requirements[work]["steps"])
                char_characteristic['energy'] = char_characteristic['energy'] - (working_hours * work_requirements[work]["energy"])
                print('Check # 04')
                char_characteristic['work'] = work        # self.work
                print('Check # 05')
                char_characteristic['working'] = True
                char_characteristic['working_start'] = datetime.now().timestamp()
                char_characteristic['working_end'] = datetime.fromtimestamp(datetime.now().timestamp()) + (timedelta(minutes=working_hours * 60) - ((timedelta(minutes=working_hours * 60) / 100) * char_characteristic['speed_skill']))
                char_characteristic['work_salary'] = work_requirements[work]["salary"]
                print(f'\nИспользовано: 🏃: {working_hours * work_requirements[work]["steps"]}; 🔋: {working_hours * work_requirements[work]["energy"]}.')
                print(f'Время работы: {working_hours * (time(round(60 - ((60 / 100) * char_characteristic["speed_skill"]))))}')
                print(f'Время окончания: {char_characteristic["working_end"]}.')
                Work.start_working(self)
            else:
                print('\nCheck #03')
                print('Дописать функционал, который показывает, чего именно не хватило.')
                print('Не достаточно: 🏃 или 🔋')

    def start_working(self):
        # Начало работы
        print('Start Working')

    def work_watchman(self):
        # Работа сторожем
        print('\n🏭\n--- Сторож ---\nЗарплата в час: 2$. '
              '\nДля 1 часа работы требуется: (🏃: 200 + 🔋: 4).')

    def work_factory(self):
        # Работа на заводе
        pass

    def work_courier_foot(self):
        # Работа пешим курьером
        pass


Work.work_choise(self=None)

#char_characteristic['work'], char_characteristic['work_salary'], char_characteristic['working'],
#                 char_characteristic['working_hours'], char_characteristic['working_end'],
