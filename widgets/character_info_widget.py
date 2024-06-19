from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.metrics import dp
from datetime import datetime

from characteristics import char_characteristic
from functions import save_game_date_last_enter


class CharacterInfoWidget(BoxLayout):
    def __init__(self, **kwargs):
        super(CharacterInfoWidget, self).__init__(**kwargs)
        self.steps = save_game_date_last_enter()
        self.energy = char_characteristic["energy"]
        self.energy_max = char_characteristic["energy_max"]
        self.money = char_characteristic["money"]
        self.level = char_characteristic["char_level"]
        self.level_up_skills = char_characteristic["char_level_up_skills"]

        self.work = char_characteristic["working"]                      # Проверка Work
        self.work_salary = char_characteristic["work_salary"]

        self.adventure = char_characteristic["adventure"]               # Проверка Adventure
        self.adventure_start_time = char_characteristic["adventure_start_timestamp"]
        self.adventure_end_time = char_characteristic["adventure_end_timestamp"]
        self.adventure_name = char_characteristic["adventure_name"]

        self.skill_training = char_characteristic["skill_training"]
        self.skill_training_name = char_characteristic["skill_training_name"]
        self.skill_start_timestamp = char_characteristic["skill_training_timestamp"]
        self.skill_end_timestamp = char_characteristic["skill_training_time_end"]

        self.orientation = 'vertical'
        self.padding = dp(10)
        self.spacing = dp(2)

        self.steps_label = Label(text=f'Steps: {self.steps}', halign='left', valign='middle', text_size=(dp(200), None), padding=(dp(10), 0))
        self.energy_label = Label(text=f'Energy: {self.energy}/{self.energy_max}', halign='left', valign='middle', text_size=(dp(200), None), padding=(dp(10), 0))
        self.energy_bar = ProgressBar(max=100, value=50, size_hint=(None, None), size=(dp(100), dp(10)))
        self.money_label = Label(text=f'Money: ${self.money}', halign='left', valign='middle', text_size=(dp(200), None), padding=(dp(10), 0))
        self.level_label = Label(text=f'Level: {self.level}', halign='left', valign='middle', text_size=(dp(200), None), padding=(dp(10), 0))
        self.exp_bar = ProgressBar(max=10000, value=7500, size_hint=(None, None), size=(dp(100), dp(10)))

        # Добавляем widget
        self.add_widget(self.steps_label)
        self.add_widget(self.money_label)
        self.add_widget(self.energy_label)
        self.add_widget(self.energy_bar)
        self.add_widget(self.level_label)
        self.add_widget(self.exp_bar)

        # Добавляем Widgets & ProgressBar: Work, Adventure, Skill Training
        self.view_work_widget()
        self.view_adventure_widget()
        self.view_skill_training_widget()

    def update_info(self, steps, energy, max_energy, money, level, exp, max_exp):
        self.steps_label.text = f'Steps: {steps}'
        self.energy_label.text = f'Energy: {energy}/{max_energy}'
        self.energy_bar.max = max_energy
        self.energy_bar.value = energy
        self.money_label.text = f'Money: ${money}'
        self.level_label.text = f'Level: {level} ' + (f'(+ {self.level_up_skills} skills)' if self.level_up_skills > 0 else '')
        self.exp_bar.max = max_exp
        self.exp_bar.value = exp

    def view_work_widget(self):
        """Метод для отображения виджета с Work"""
        if self.work:
            self.update_work_progressbar()
            salary = self.work_salary * char_characteristic['working_hours']
            self.work_bar = ProgressBar(max=self.work_time_total, value=self.work_time_seconds, size_hint=(None, None),
                                        size=(dp(100), dp(10)))
            self.working_label = Label(text=f'Working: {salary} $', halign='left', valign='middle', text_size=(dp(200), None),
                                       padding=(dp(10), 0))
            self.add_widget(self.working_label)
            self.add_widget(self.work_bar)

    def view_adventure_widget(self):
        """Метод для отображения виджета с Adventure"""
        if self.adventure:
            self.update_adventure_progressbar()
            total_time = self.adventure_end_time - self.adventure_start_time
            time_left = self.adventure_time_left

            self.adventure_bar = ProgressBar(max=total_time, value=total_time - time_left, size_hint=(None, None),
                                             size=(dp(100), dp(10)))
            self.adventure_label = Label(text=f'Adventure: {self.adventure_name}',
                                         halign='left', valign='middle', text_size=(dp(200), None), padding=(dp(10), 0))
            self.add_widget(self.adventure_label)
            self.add_widget(self.adventure_bar)

    def view_skill_training_widget(self):
        """Метод для отображения виджета с Gym Skill Training"""
        if self.skill_training:
            self.update_skill_training_progressbar()
            self.skill_training_bar = ProgressBar(max=self.skill_training_total_time, value=self.skill_training_time_left,
                                                  size_hint=(None, None), size=(dp(100), dp(10)))
            self.skill_training_label = Label(text=f'Skill Training: True, Time Left: {100000}',
                                         halign='left', valign='middle', text_size=(dp(200), None), padding=(dp(10), 0))
            self.add_widget(self.skill_training_label)
            self.add_widget(self.skill_training_bar)

    def update_work_progressbar(self):
        """Обновление ProgressBar для Work"""
        if self.work:
            working_end = char_characteristic['working_end']
            working_end_timestamp = working_end.timestamp()
            current_timestamp = datetime.now().timestamp()

            self.work_time_total = int(working_end_timestamp - char_characteristic['working_start'])
            self.work_time_seconds = int(current_timestamp - char_characteristic['working_start'])

    def update_adventure_progressbar(self):
        """Обновление ProgressBar для Adventure"""
        if self.adventure:
            self.adventure_time_total = self.adventure_end_time - self.adventure_start_time
            self.adventure_time_left = self.adventure_end_time - datetime.now().timestamp()

    def update_skill_training_progressbar(self):
        """Обновление ProgressBar для Gym - Skill Training"""
        if self.skill_training:
            self.skill_training_total_time = self.skill_end_timestamp - self.skill_start_timestamp
            self.skill_training_time_left = self.skill_end_timestamp - datetime.now().timestamp()
