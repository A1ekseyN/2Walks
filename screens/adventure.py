from kivy.uix.screenmanager import Screen
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.metrics import dp
from widgets.character_info_widget import CharacterInfoWidget
from kivy.properties import ObjectProperty

from characteristics import char_characteristic  # Импортируем данные о характеристиках персонажа
from functions import save_game_date_last_enter, energy_time_charge
from skill_bonus import speed_skill_equipment_and_level_bonus
from adventure_data import adventure_data_table
from adventure import Adventure


class AdventureScreen(Screen):
    character_info_widget = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(AdventureScreen, self).__init__(**kwargs)
        self.adventure = Adventure(adventure_data_table)
        self.buttons = {}  # Словарь для хранения кнопок и их действий

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
        button_box = BoxLayout(orientation='vertical', spacing=dp(5), size_hint=(None, None), size=(dp(200), dp(350)))

        button_info = [
            ('Прогулка: 2500 шагов', '1'),
            ('Прогулка: 5000 шагов', '2'),
            ('Прогулка: 10к шагов', '3'),
            ('Прогулка: 15к шагов', '4'),
            ('Прогулка: 20к шагов', '5'),
            ('Прогулка: 25к шагов', '6'),
            ('Прогулка: 30к шагов', '7'),
            ('Go Back', 'go_back')
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
                btn.bind(on_release=lambda instance, act=action: self.show_confirmation_popup(act))
            button_box.add_widget(btn)
            self.buttons[action] = btn  # Сохраняем кнопку в словарь

        button_layout.add_widget(button_box)

        # Добавляем AnchorLayout для информации о персонаже и кнопок в основной AnchorLayout
        main_layout.add_widget(character_info_layout)
        main_layout.add_widget(button_layout)

        self.add_widget(main_layout)

        # Инициализация информации о персонаже и счётчиков
        self.update_character_info()
        self.update_character_counters()

        self.popup = Popup(title='Подтверждение приключения',
                           size_hint=(None, None), size=(400, 200),
                           auto_dismiss=False,
                           title_color=(1, 1, 1, 1),  # цвет текста заголовка (белый)
                           background_color=(0.9, 0.9, 0.9, 1),  # цвет фона Popup (светло-серый)
                           separator_color=(1, 1, 1, 1))  # цвет полоски (белый)

        # Контент внутри Popup
        content = BoxLayout(orientation='vertical', spacing=10)
        self.popup_content_label = Label(text='Вы уверены, что хотите начать приключение?')
        buttons_layout = BoxLayout(spacing=10)

        btn_ok = Button(text='Ок', size_hint=(None, None), size=(100, 50))
        btn_ok.bind(on_release=self.on_ok_pressed)
        btn_cancel = Button(text='Отмена', size_hint=(None, None), size=(100, 50))
        btn_cancel.bind(on_release=self.popup.dismiss)

        buttons_layout.add_widget(btn_ok)
        buttons_layout.add_widget(btn_cancel)

        content.add_widget(self.popup_content_label)
        content.add_widget(buttons_layout)

        self.popup.content = content

    def update_character_info(self):
        # Обновление информации о персонаже на основе данных из char_characteristic_info
        steps = save_game_date_last_enter()
        energy = char_characteristic.get('energy', 0)
        max_energy = char_characteristic.get('energy_max', 0)
        money = char_characteristic.get('money', 0)
        level = char_characteristic.get('char_level', 0)

        self.character_info_widget.update_info(steps=steps, energy=energy, max_energy=max_energy,
                                               money=money, level=level, exp=7500, max_exp=10000)

    def update_character_counters(self):
        # Обновление счётчиков приключений из char_characteristic
        key_map = {
            '1': 'adventure_walk_easy_counter',
            '2': 'adventure_walk_normal_counter',
            '3': 'adventure_walk_hard_counter',
            '4': 'adventure_walk_15k_counter',
            '5': 'adventure_walk_20k_counter',
            '6': 'adventure_walk_25k_counter',
            '7': 'adventure_walk_30k_counter'
        }

        # Обновление счётчиков приключений из char_characteristic
        for action, btn in self.buttons.items():
            if action != 'go_back':
                counter_key = key_map.get(action)
                if counter_key in char_characteristic:
                    counter_value = char_characteristic[counter_key]
#                    print(f"Ключ: {counter_key}, Значение: {counter_value}")  # Отладка
                    btn.disabled = counter_value < 3
                else:
#                    print(f"Ключ {counter_key} не найден в char_characteristic")  # Отладка
                    btn.disabled = True

    def on_enter(self, *args):
        # Метод on_enter вызывается каждый раз при показе экрана WorkScreen
        self.update_character_info()
        self.update_character_counters()  # Обновляем счётчики при входе на экран
        self.energy_update(char_characteristic)

    def energy_update(self, instance):
        """Метод для обновления количества энергии"""
        energy_time_charge()

    def go_back(self, instance):
        self.manager.current = 'main_kivy'

    def show_confirmation_popup(self, adventure_id):
        # Отображение Popup для подтверждения начала приключения
        self.current_adventure_id = adventure_id  # сохраняем adventure_id для последующего использования в методе on_ok_pressed
        self.popup.open()

    def on_ok_pressed(self, instance):
        # Логика при нажатии на кнопку Ок в Popup
        self.popup.dismiss()
        adventure_id = self.current_adventure_id
        if adventure_id in self.adventure.adventures:
            adv = self.adventure.adventures[adventure_id]
            adv_name = adv['name']
            adv_data = adv['data']
            adv_steps = adv_data['steps']
            adv_energy = adv_data['energy']
            adv_time = speed_skill_equipment_and_level_bonus(adv_data['time'])

            if self.adventure.check_requirements(adv_name, adv_steps, adv_energy, adv_time):
                self.on_enter()
                pass
#                self.adventure.start_adventure(adv_name, adv_steps, adv_energy, adv_time)
            else:
                print('Не выполнены требования для начала приключения.')

    def check_and_start_adventure(self, adventure_id):
        # Проверяем и запускаем приключение
        if adventure_id in self.adventure.adventures:
            adv = self.adventure.adventures[adventure_id]
            adv_name = adv['name']
            adv_data = adv['data']
            adv_steps = adv_data['steps']
            adv_energy = adv_data['energy']
            adv_time = speed_skill_equipment_and_level_bonus(adv_data['time'])

            if self.adventure.check_requirements(adv_name, adv_steps, adv_energy, adv_time):
                pass
#                self.adventure.start_adventure(adv_name, adv_steps, adv_energy, adv_time)
            else:
                print('Не выполнены требования для начала приключения.')
