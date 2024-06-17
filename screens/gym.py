from kivy.uix.screenmanager import Screen
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.metrics import dp
from kivy.properties import ObjectProperty

from widgets.character_info_widget import CharacterInfoWidget

from characteristics import char_characteristic
from functions import save_game_date_last_enter, energy_time_charge


class GymScreen(Screen):
    character_info_widget = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(GymScreen, self).__init__(**kwargs)

        # Основной AnchorLayout для размещения других Layout
        main_layout = AnchorLayout()

        # AnchorLayout для информации о персонаже в верхнем левом углу
        character_info_layout = AnchorLayout(anchor_x='left', anchor_y='top')
        character_info_box = BoxLayout(orientation='vertical', size_hint=(None, None), size=(dp(200), dp(150)))
        self.character_info_widget = CharacterInfoWidget()
        character_info_box.add_widget(self.character_info_widget)
        character_info_layout.add_widget(character_info_box)

        # AnchorLayout для кнопок меню в центре
        button_layout = AnchorLayout(anchor_x='center', anchor_y='center')
        button_box = BoxLayout(orientation='vertical', spacing=dp(5), size_hint=(None, None), size=(dp(200), dp(400)))

        button_info = [
            ('Stamina', 'stamina'),
            ('Energy Max', 'energy_max'),
            ('Speed', 'speed_skill'),
            ('Luck', 'luck_skill'),
            ('Opt. move Adventure', 'move_optimization_adventure'),
            ('Opt. move Gym', 'move_optimization_gym'),
            ('Opt. move Work', 'move_optimization_work'),
            ('go_back', 'go_back')
        ]

        for button_text, action in button_info:
            btn = Button(text=button_text,
                         size_hint=(None, None),
                         size=(dp(200), dp(50)),
                         background_normal='',
                         background_color=(0.4, 0.4, 0.8, 1),
                         border=(20, 20, 20, 20))
            if action == 'go_back':
                btn.bind(on_release=self.go_back)
            else:
                btn.action = action
                btn.bind(on_release=self.show_confirmation_popup)
            button_box.add_widget(btn)

        button_layout.add_widget(button_box)

        # Добавляем AnchorLayout для информации о персонаже и кнопок в основной AnchorLayout
        main_layout.add_widget(character_info_layout)
        main_layout.add_widget(button_layout)

        self.add_widget(main_layout)

        # Инициализация информации о персонаже
        self.update_character_info()

    def update_character_info(self):
        # Обновление информации о персонаже на основе данных из char_characteristic
        steps = save_game_date_last_enter()
        energy = char_characteristic.get('energy', 0)
        max_energy = char_characteristic.get('energy_max', 0)
        money = char_characteristic.get('money', 0)
        level = char_characteristic.get('char_level', 0)

        self.character_info_widget.update_info(steps=steps, energy=energy, max_energy=max_energy,
                                               money=money, level=level, exp=7500, max_exp=10000)

    def on_enter(self, *args):
        # Метод on_enter вызывается каждый раз при показе экрана WorkScreen
        self.update_character_info()
        self.energy_update(char_characteristic)

    def energy_update(self, instance):
        """Метод для обновления количества энергии"""
        energy_time_charge()

    def go_back(self, instance):
        self.manager.current = 'main_kivy'

    def show_confirmation_popup(self, instance):
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))

        message = Label(text=f'Are you sure you want to {instance.text}?')
        confirm_button = Button(text='Confirm', size_hint_y=None, height=dp(40))
        cancel_button = Button(text='Cancel', size_hint_y=None, height=dp(40))

        content.add_widget(message)
        content.add_widget(confirm_button)
        content.add_widget(cancel_button)

        popup = Popup(title='Confirmation',
                      content=content,
                      size_hint=(None, None),
                      size=(dp(300), dp(200)),
                      auto_dismiss=False)

        confirm_button.bind(on_release=lambda x: self.perform_action(instance.action, popup))
        cancel_button.bind(on_release=popup.dismiss)

        popup.open()

    def perform_action(self, action, popup):
        # Здесь должна быть логика выполнения действия в зависимости от нажатой кнопки
        print(f'Action confirmed: {action}')
        popup.dismiss()
