from colorama import Fore, Style

from characteristics import char_characteristic


class CharLevel():
    """Класс для вывода информации о level персонажа на основе общего кол-ва потраченных шагов"""
    LEVEL_THRESHOLDS = {
        0: 10000,
        1: 20000,
        2: 50000
    }

    def __init__(self, char_characteristic):
        self.total_used_steps = char_characteristic['steps_total_used']
        self.level = char_characteristic['char_level']

    def view_total_used_steps(self):
        """Отображение общего количества потраченных шагов"""
        print(f"total_used_steps: {self.total_used_steps}")

    def view_char_level(self):
        """Отображение Level персонажа, который он получил на основе общего количества пройденных шагов"""
        print(f"level: {self.level}")

    def update_level_char_characteristic(self):
        """Update переменную char_characteristic['char_level']"""
        global char_characteristic
        char_characteristic['char_level'] = self.level

    def update_level_up_skills_char_characteristic(self, level_up_difference):
        """
        Update количество очков навыков, которые мы можем распределить
        При повышении уровня персонажа нам дается + 1 очко для распределения навыков за + 1 level_up
        """
        global char_characteristic
        char_characteristic['char_level_up_skills'] += level_up_difference

    def calculate_level_from_total_used_steps(self):
        """Просчёт level персонажа на основе общего количества потраченных шагов"""
        used_steps = self.total_used_steps
        new_level = 0

        for level, threshold in sorted(self.LEVEL_THRESHOLDS.items()):
            if used_steps > threshold:
                new_level = level + 1
            else:
                break

        return new_level

    def update_level(self):
        """Update level, если мы переходим на следующий уровень"""
        new_level = self.calculate_level_from_total_used_steps()
        if new_level != self.level:
            level_up_difference = new_level - self.level
            self.level = new_level
            self.update_level_up_skills_char_characteristic(level_up_difference)
            self.update_level_char_characteristic()
            print(f"Персонаж повысил свой уровень до {self.level} уровня.")

    def progress_to_next_level(self):
        """Отображение прогресса до следующего уровня в процентах"""
        current_threshold = 0 if self.level == 0 else self.LEVEL_THRESHOLDS[self.level - 1]
        next_threshold = self.LEVEL_THRESHOLDS.get(self.level, float('inf'))

        steps_into_level = self.total_used_steps - current_threshold
        steps_needed = next_threshold - current_threshold

        progress_percentage = (steps_into_level / steps_needed) * 100 if steps_needed > 0 else 100

        return progress_percentage

    def progress_bar(self, length=33):
        """Возвращает текстовый прогресс-бар"""
        progress_percentage = self.progress_to_next_level()
        filled_length = int(length * progress_percentage // 100)
        bar = '#' * filled_length + '-' * (length - filled_length)
        return f"[{bar}] {Fore.GREEN}{progress_percentage:.2f}{Style.RESET_ALL} %"

    def progress_bar_lvl_up_message(self):
        """Отображение сообщения о том, что у персонажа есть не распределенные очки навыков"""
        if char_characteristic['char_level_up_skills'] != 0:
            return f"[+ {char_characteristic['char_level_up_skills']} Skill points]"
        else:
            return f""

    def menu_skill_point_allocation(self):
        """Меню для повышения уровня навыков персонажа, после lvl up"""
        global char_characteristic
        if char_characteristic['char_level_up_skills'] > 0:
            print(f"\nВам доступно: + {char_characteristic['char_level_up_skills']} очков навыков."
                  f" Текущие навыки от уровня персонажа:"
                  f"\n\t1. Stamina: + {char_characteristic['lvl_up_skill_stamina']} Добавляет + 1 % к общему количеству шагов"
                  f"\n\t2. Energy: + {char_characteristic['lvl_up_skill_energy_max']}  Добавляет + 1 ед. к общему запасу энергии "
                  f"\n\t3. Speed: + {char_characteristic['lvl_up_skill_speed']}   Добавляет + 1 % к скорости выполнения активностей"
                  f"\n\t4. Luck: + {char_characteristic['lvl_up_skill_luck']}    Добавляет + 1 % к удаче."
                  f"\n\t0. Назад")
            try:
                ask = int(input(f"\nВведите навык, который хотите улучшить: \n>>> "))
                if ask == 1:
                    char_characteristic['lvl_up_skill_stamina'] += 1
                    char_characteristic['char_level_up_skills'] -= 1
                    print(f"\nНавык Stamina повышен до {char_characteristic['lvl_up_skill_stamina']}.")
                elif ask == 2:
                    char_characteristic['lvl_up_skill_energy_max'] += 1
                    char_characteristic['char_level_up_skills'] -= 1
                    print(f"\nНавык Energy повышен до {char_characteristic['lvl_up_skill_energy_max']}.")
                elif ask == 3:
                    char_characteristic['lvl_up_skill_speed'] += 1
                    char_characteristic['char_level_up_skills'] -= 1
                    print(f"\nНавык Speed Skill повышен до {char_characteristic['lvl_up_skill_speed']}.")
                elif ask == 4:
                    char_characteristic['lvl_up_skill_luck'] += 1
                    char_characteristic['char_level_up_skills'] -= 1
                    print(f"\nНавык Luck повышен до {char_characteristic['lvl_up_skill_luck']}.")
                elif ask == 0:
                    return
                else:
                    print("\nНеверный ввод. Попробуйте снова.")
                    self.menu_skill_point_allocation()
            except ValueError:
                print("\nНеверный ввод. Пожалуйста, введите число.")
                self.menu_skill_point_allocation()
        else:
            print("\nУ вас нет очков навыков для распределения.")
            print(f"\nНавыки: "
                  f"\n\t1. Stamina: + {char_characteristic['lvl_up_skill_stamina']} Добавляет + 1 % к общему количеству шагов"
                  f"\n\t2. Energy: + {char_characteristic['lvl_up_skill_energy_max']}  Добавляет + 1 ед. к общему запасу энергии "
                  f"\n\t3. Speed: + {char_characteristic['lvl_up_skill_speed']}   Добавляет + 1 % к скорости выполнения активностей"
                  f"\n\t4. Luck: + {char_characteristic['lvl_up_skill_luck']}    Добавляет + 1 % к удаче.")

    def level_status_bar(self):
        """Отображение информации об Level персонажа, Прогресс бар, lvl-up"""
        self.update_level()  # Проверка и обновление уровня персонажа
        progress_bar = self.progress_bar()
        print(f"Уровень: {self.level} {progress_bar} {self.progress_bar_lvl_up_message()}")


if __name__ == "__main__":
    print()
    char_level_view = CharLevel(char_characteristic)
    char_level_view.view_total_used_steps()
    char_level_view.view_char_level()
    char_level_view.level_status_bar()
