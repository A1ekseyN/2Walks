from kivy.uix.screenmanager import Screen
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.popup import Popup
from kivy.metrics import dp
from widgets.character_info_widget import CharacterInfoWidget
from kivy.properties import ObjectProperty
from kivy.uix.label import Label

from characteristics import char_characteristic  # Импортируем данные о характеристиках персонажа
from functions import save_game_date_last_enter, energy_time_charge
from work import Work  # Импортируем класс Work из файла с логикой работы


class WorkScreen(Screen):
    character_info_widget = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(WorkScreen, self).__init__(**kwargs)

        # Основной AnchorLayout для размещения других Layout
        main_layout = AnchorLayout()

        # Создаем экземпляр класса Work для получения информации о работе
        self.work = Work(char_characteristic)

        # AnchorLayout для информации о персонаже в верхнем левом углу
        character_info_layout = AnchorLayout(anchor_x='left', anchor_y='top')
        character_info_box = BoxLayout(orientation='vertical', size_hint=(None, None), size=(dp(200), dp(150)))
        self.character_info_widget = CharacterInfoWidget()
        character_info_box.add_widget(self.character_info_widget)
        character_info_layout.add_widget(character_info_box)

        # AnchorLayout для кнопок меню в центре
        button_layout = AnchorLayout(anchor_x='center', anchor_y='center')
        button_box = BoxLayout(orientation='vertical', spacing=dp(5), size_hint=(None, None), size=(dp(200), dp(250)))

        button_info = [
            ('Сторож', 'watchman'),
            ('Завод', 'factory'),
            ('Курьер', 'courier_foot'),
            ('Экспедитор', 'forwarder'),
            ('Go Back', 'go_back')
        ]

        print(f"test: {self.work.work_requirements}")
        for button_text, action in button_info:
            if action in self.work.work_requirements:
                work_req = self.work.work_requirements[action]
                button_text = f'{button_text} \n(Steps: {work_req["steps"]}, Energy: {work_req["energy"]})'
            btn = Button(text=button_text,
                         size_hint=(None, None),
                         size=(dp(200), dp(50)),
                         background_normal='',
                         background_color=(0.4, 0.4, 0.8, 1),
                         border=(20, 20, 20, 20))
            if action == 'go_back':
                btn.bind(on_release=self.go_back)
            else:
                btn.bind(on_release=self.work_button_action(action))
            button_box.add_widget(btn)

        button_layout.add_widget(button_box)

        # Добавляем AnchorLayout для информации о персонаже и кнопок в основной AnchorLayout
        main_layout.add_widget(character_info_layout)
        main_layout.add_widget(button_layout)

        self.add_widget(main_layout)

        # Инициализация информации о персонаже
        self.update_character_info()

    def update_character_info(self):
        # Обновление информации о персонаже на основе данных из char_characteristic_info
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

    def work_button_action(self, work_type):
        def action(instance):
            self.show_hours_popup(work_type)
        return action

    def show_hours_popup(self, work_type):
        layout = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))

        for i in range(1, 6):
            btn = Button(text=str(i), size_hint_y=None, height=dp(40))
            btn.bind(on_release=lambda instance, hours=i: self.select_hours(work_type, hours))
            layout.add_widget(btn)

        self.popup = Popup(title='Выберите количество часов', content=layout, size_hint=(None, None), size=(dp(200), dp(400)))
        self.popup.open()

    def select_hours(self, work_type, hours):
        self.popup.dismiss()  # Закрыть всплывающее окно

        if self.work.check_requirements(work_type, hours):
            # Логика запуска работы, если требования выполнены
            print(f"Запуск работы: {work_type} на {hours} часов.")
            # Обновляем информацию о персонаже на главном экране
            self.update_character_info()
        else:
            # TODO: Добавить логику, которая отображает сколько не хватило steps, energy
            self.show_error_popup(f"Не удалось запустить работу: {work_type}. \n"
                                  f"Не достаточно Steps or Energy.")


#    def check_requirements(self, work, working_hours):
#        # Логика проверки требований работы и выполнения действий
#        print(f"Проверка требований для работы: {work} на {working_hours} часов")
#        # Добавьте вашу логику здесь

    def show_error_popup(self, message):
        """Отображение ошибки, если не достаточно steps, energy для запуска wokr"""
        layout = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))
        label = Label(text=message, size_hint_y=None, height=dp(100))
        btn = Button(text="OK", size_hint_y=None, height=dp(40))
        btn.bind(on_release=lambda instance: self.error_popup.dismiss())
        layout.add_widget(label)
        layout.add_widget(btn)

        self.error_popup = Popup(title='Ошибка', content=layout, size_hint=(None, None), size=(dp(300), dp(200)))
        self.error_popup.open()
