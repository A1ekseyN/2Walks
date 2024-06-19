# character_info.py
from kivy.uix.screenmanager import Screen
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.utils import get_color_from_hex

from characteristics import char_characteristic

# Список ключей для фильтрации
DISPLAY_KEYS = [
    'steps_can_use', 'char_level', 'energy_max', 'money',
    'stamina', 'energy_max_skill', 'speed_skill', 'luck_skill',
    'move_optimization_adventure', 'move_optimization_gym', 'move_optimization_work'
]

class CharacterInfoScreen(Screen):
    def __init__(self, **kwargs):
        super(CharacterInfoScreen, self).__init__(**kwargs)

        # Вертикальный BoxLayout для размещения информации и кнопки
        vertical_layout = BoxLayout(orientation='vertical', spacing=10, padding=10)

        # GridLayout для отображения информации о характеристиках
        self.layout = GridLayout(cols=2, spacing=10, padding=10)
        vertical_layout.add_widget(self.layout)

        # Добавляем информацию о характеристиках персонажа
        self.add_characteristics_info()

        # Кнопка для возврата на главный экран
        btn_back = Button(text='Go Back', size_hint_y=None, height=40, on_release=self.go_back)
        vertical_layout.add_widget(btn_back)

        self.add_widget(vertical_layout)

    def go_back(self, instance):
        self.manager.current = 'main_kivy'

    def add_characteristics_info(self):
        # Фильтруем только ключи из DISPLAY_KEYS
        for key in DISPLAY_KEYS:
            if key in char_characteristic:
                label_key = Label(text=f"{key}:", halign='right', size_hint=(None, None), height=30,
                                  color=get_color_from_hex('#000000'))  # Черный цвет текста
                label_value = Label(text=str(char_characteristic[key]), size_hint=(None, None), height=30,
                                    color=get_color_from_hex('#000000'))  # Черный цвет текста

                self.layout.add_widget(label_key)
                self.layout.add_widget(label_value)
