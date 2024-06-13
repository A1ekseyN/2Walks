# character_info_widget.py
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.metrics import dp


class CharacterInfoWidget(BoxLayout):
    def __init__(self, **kwargs):
        super(CharacterInfoWidget, self).__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = dp(10)
        self.spacing = dp(5)

        self.steps_label = Label(text='Steps: 0')
        self.energy_label = Label(text='Energy: 50/100')
        self.energy_bar = ProgressBar(max=100, value=50)  # Прогресс-бар для энергии
        self.money_label = Label(text='Money: $200')
        self.level_label = Label(text='Level: 1')
        self.exp_bar = ProgressBar(max=10000, value=7500)  # Прогресс-бар для опыта

        self.add_widget(self.steps_label)
        self.add_widget(self.energy_label)
        self.add_widget(self.energy_bar)
        self.add_widget(self.money_label)
        self.add_widget(self.level_label)
        self.add_widget(self.exp_bar)

    def update_info(self, steps, energy, max_energy, money, level, exp, max_exp):
        self.steps_label.text = f'Steps: {steps}'
        self.energy_label.text = f'Energy: {energy}/{max_energy}'
        self.energy_bar.max = max_energy
        self.energy_bar.value = energy
        self.money_label.text = f'Money: ${money}'
        self.level_label.text = f'Level: {level}'
        self.exp_bar.max = max_exp
        self.exp_bar.value = exp
