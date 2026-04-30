"""CharLevel — отображение и управление уровнем персонажа.

Имя `CharLevel` существует и в `state.py` (dataclass для nested-полей уровня) —
коллизия не реальная, классы живут в разных модулях и не пересекаются по импортам.
"""

from colorama import Fore, Style

from state import GameState


class CharLevel:
    """Отображение / обновление уровня персонажа на основе общего кол-ва потраченных шагов."""

    LEVEL_THRESHOLDS = {
        0: 10000,
        1: 20000,
        2: 50000,
        3: 100000,
        4: 250000,
        5: 500000,
        6: 750000,
        7: 1000000,     # + 250к
        8: 1300000,     # + 300к
        9: 1650000,     # + 350к
        10: 2050000,    # + 400к
        11: 2500000,    # + 450к
    }

    def __init__(self, state: GameState):
        self._state = state

    @property
    def total_used_steps(self):
        return self._state.steps.total_used

    @property
    def level(self):
        return self._state.char_level.level

    @level.setter
    def level(self, value):
        self._state.char_level.level = value

    def view_total_used_steps(self):
        print(f"total_used_steps: {self.total_used_steps}")

    def view_char_level(self):
        print(f"level: {self.level}")

    def update_level_char_characteristic(self):
        # Уровень синхронизируется через property setter — метод оставлен для совместимости вызовов.
        self._state.char_level.level = self.level

    def update_level_up_skills_char_characteristic(self, level_up_difference):
        """+ N очков навыков за каждый level-up."""
        self._state.char_level.up_skills += level_up_difference

    def calculate_level_from_total_used_steps(self):
        """Просчёт level персонажа на основе общего количества потраченных шагов."""
        used_steps = self.total_used_steps
        new_level = 0
        for level, threshold in sorted(self.LEVEL_THRESHOLDS.items()):
            if used_steps >= threshold:
                new_level = level + 1
            else:
                break
        return new_level

    def update_level(self):
        """Update level, если мы переходим на следующий уровень."""
        new_level = self.calculate_level_from_total_used_steps()
        if new_level != self.level:
            level_up_difference = new_level - self.level
            self.level = new_level
            self.update_level_up_skills_char_characteristic(level_up_difference)
            print(f"Персонаж повысил свой уровень до {self.level} уровня.")

    def progress_to_next_level(self):
        """Отображение прогресса до следующего уровня в процентах."""
        current_threshold = 0 if self.level == 0 else self.LEVEL_THRESHOLDS[self.level - 1]
        next_threshold = self.LEVEL_THRESHOLDS.get(self.level, float('inf'))

        steps_into_level = self.total_used_steps - current_threshold
        steps_needed = next_threshold - current_threshold

        progress_percentage = (steps_into_level / steps_needed) * 100 if steps_needed > 0 else 100
        return progress_percentage

    def progress_bar(self, length=33):
        progress_percentage = self.progress_to_next_level()
        filled_length = int(length * progress_percentage // 100)
        bar = '#' * filled_length + '-' * (length - filled_length)
        return f"[{bar}] {Fore.GREEN}{progress_percentage:.2f}{Style.RESET_ALL} %"

    def progress_bar_lvl_up_message(self):
        if self._state.char_level.up_skills != 0:
            return f"[+ {self._state.char_level.up_skills} Skill points]"
        return ""

    def menu_skill_point_allocation(self):
        """Меню распределения очков навыков после lvl up."""
        cl = self._state.char_level
        if cl.up_skills > 0:
            print(f"\nВам доступно: + {cl.up_skills} очков навыков."
                  f" Текущие навыки от уровня персонажа:"
                  f"\n\t1. Stamina: + {cl.skill_stamina} Добавляет + 1 % к общему количеству шагов"
                  f"\n\t2. Energy: + {cl.skill_energy_max}  Добавляет + 1 ед. к общему запасу энергии "
                  f"\n\t3. Speed: + {cl.skill_speed}   Добавляет + 1 % к скорости выполнения активностей"
                  f"\n\t4. Luck: + {cl.skill_luck}    Добавляет + 1 % к удаче."
                  f"\n\t0. Назад")
            try:
                ask = int(input(f"\nВведите навык, который хотите улучшить: \n>>> "))
                if ask == 1:
                    cl.skill_stamina += 1
                    cl.up_skills -= 1
                    print(f"\nНавык Stamina повышен до {cl.skill_stamina}.")
                elif ask == 2:
                    cl.skill_energy_max += 1
                    cl.up_skills -= 1
                    print(f"\nНавык Energy повышен до {cl.skill_energy_max}.")
                elif ask == 3:
                    cl.skill_speed += 1
                    cl.up_skills -= 1
                    print(f"\nНавык Speed Skill повышен до {cl.skill_speed}.")
                elif ask == 4:
                    cl.skill_luck += 1
                    cl.up_skills -= 1
                    print(f"\nНавык Luck повышен до {cl.skill_luck}.")
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
                  f"\n\t1. Stamina: + {cl.skill_stamina} Добавляет + 1 % к общему количеству шагов"
                  f"\n\t2. Energy: + {cl.skill_energy_max}  Добавляет + 1 ед. к общему запасу энергии "
                  f"\n\t3. Speed: + {cl.skill_speed}   Добавляет + 1 % к скорости выполнения активностей"
                  f"\n\t4. Luck: + {cl.skill_luck}    Добавляет + 1 % к удаче.")

    def level_status_bar(self):
        """Отображение информации об Level персонажа, Прогресс бар, lvl-up."""
        self.update_level()
        progress_bar = self.progress_bar()
        print(f"Уровень: {self.level} {progress_bar} {self.progress_bar_lvl_up_message()}")


if __name__ == "__main__":
    from characteristics import game_state
    print()
    char_level_view = CharLevel(game_state)
    char_level_view.view_total_used_steps()
    char_level_view.view_char_level()
    char_level_view.level_status_bar()
