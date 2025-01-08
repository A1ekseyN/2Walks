from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.uix.image import Image
from kivy.uix.label import Label

from screens.home import HomeScreen
from screens.adventure import AdventureScreen
from screens.gym import GymScreen
from screens.shop import ShopScreen
from screens.work import WorkScreen
from screens.inventory import InventoryScreen
from screens.character_info import CharacterInfoScreen
from widgets.character_info_widget import CharacterInfoWidget

from characteristics import char_characteristic, save_characteristic
from functions import save_game_date_last_enter, energy_time_charge, steps_today_update_manual
from work import work_check_done
from google_sheets_db import save_char_characteristic_to_google_sheet


class MainScreen(Screen):
    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)
        self.energy_update(char_characteristic)             # Обновление количества энергии во время запуска игры
        self.work_check_done()                              # Проверка окончания работы

        self.steps = save_game_date_last_enter()
        self.energy = char_characteristic["energy"]
        self.energy_max = char_characteristic["energy_max"]
        self.money = char_characteristic["money"]
        self.level = char_characteristic["char_level"]

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
            ('Home', "Home (Don't work)"),
            ('Gym', 'Gym'),
#            ('Shop', "Shop (Don't work)"),
            ('Work', 'Work'),
            ('Adventure', 'Adventure'),
            ('Inventory', 'Inventory'),
            ('character_info', 'Character Info'),
            ('save', 'Save'),
            ('update_steps', "Update Steps")
        ]

        for screen_name, button_text in button_info:
            btn = Button(text=button_text,
                         size_hint=(None, None),
                         size=(dp(200), dp(50)),
                         background_normal='',
                         background_color=(0.4, 0.4, 0.8, 1),
                         border=(20, 20, 20, 20))
            if screen_name.lower() == 'save':
                btn.bind(on_release=self.save_characteristics)
            elif screen_name.lower() == 'update_steps':
                btn.bind(on_release=self.update_steps_api)
            else:
                btn.bind(on_release=self.change_screen)
            btn.screen_name = screen_name.lower()
            button_box.add_widget(btn)

        button_layout.add_widget(button_box)

        # Вызываем метод для добавления фона
        self.add_background_main(main_layout)

        # Вызываем метод для добавления версии игры
        self.version_view(main_layout)

        # Добавляем AnchorLayout для информации о персонаже и кнопок в основной AnchorLayout
        main_layout.add_widget(character_info_layout)
        main_layout.add_widget(button_layout)

        self.add_widget(main_layout)

        # Инициализация информации о персонаже
        self.character_info_widget.update_info(steps=self.steps, energy=self.energy, max_energy=self.energy_max,
                                               money=self.money, level=self.level, exp=7500, max_exp=10000)

    def change_screen(self, instance):
        self.manager.current = instance.screen_name

    def update_character_info(self, instance):
        # Обновление информации о персонаже на основе данных из char_characteristic
        self.steps = save_game_date_last_enter()
        self.energy = char_characteristic["energy"]
        self.energy_max = char_characteristic["energy_max"]
        self.money = char_characteristic["money"]
        self.level = char_characteristic["char_level"]

        self.character_info_widget.update_info(steps=self.steps, energy=self.energy, max_energy=self.energy_max,
                                               money=self.money, level=self.level, exp=7500, max_exp=10000)

    def on_enter(self, *args):
        # Метод on_enter вызывается каждый раз при показе экрана WorkScreen
        self.update_character_info(char_characteristic)
        self.energy_update(char_characteristic)

    def save_characteristics(self, instance):
        """Метод для сохранения прогресса в игре. Сохраняет переменную char_characteristic в cvs, txt"""
        save_characteristic()                           # Сохраняем данные в CSV
        save_char_characteristic_to_google_sheet()      # Сохраняем данные в Google Sheets

    def energy_update(self, instance):
        """Метод для обновления количества энергии"""
        energy_time_charge()

    def work_check_done(self):
        """Метод для проверки или закончилась Work"""
        work_check_done()

    def update_steps_api(self, instance):
        """Метод для обновления количество шагов через API"""
        steps_today_update_manual()
        self.on_enter()

    def add_background_main(self, layout):
        """Метод для добавления фона"""
        background_image = Image(
            source='screens/background/background_main.png',
            allow_stretch=False,  # Отключаем растяжение картинки
            keep_ratio=True,  # Сохраняем пропорции картинки
            size_hint=(None, None)  # Отключаем автоматическое изменение размера
        )

        # Устанавливаем исходный размер картинки
        background_image.size = (768, 1366)

        # Центрируем картинку на экране
        background_image.pos_hint = {'center_x': 0.5, 'center_y': 0.5}
        layout.add_widget(background_image)

    def version_view(self, layout):
        """Метод для добавления информации о версии игры внизу справа"""
        version = "Version: 0.0.5c "
        version_layout = AnchorLayout(anchor_x='right', anchor_y='bottom')
        version_label = Label(text=version,
                              size_hint=(None, None),
                              size=(dp(100), dp(30)),
                              color=(0, 0, 0, 1))  # Черный цвет текста
        version_layout.add_widget(version_label)

        # Добавляем Layout с версией в основной макет
        layout.add_widget(version_layout)


class MyGameApp(App):
    def build(self):
        # Устанавливаем серый цвет фона для всего окна приложения
        Window.clearcolor = (0.8, 0.8, 0.8, 1)  # серый цвет фона
        sm = ScreenManager()

#        Window.size = (2340 // 2, 1080 // 2)

        # Добавляем экраны
        sm.add_widget(MainScreen(name='main_kivy'))
        sm.add_widget(HomeScreen(name='home'))
        sm.add_widget(GymScreen(name='gym'))
        sm.add_widget(ShopScreen(name='shop'))
        sm.add_widget(WorkScreen(name='work'))
        sm.add_widget(AdventureScreen(name='adventure'))
        sm.add_widget(InventoryScreen(name='inventory'))
        sm.add_widget(CharacterInfoScreen(name='character_info'))
        return sm


if __name__ == '__main__':
    MyGameApp().run()
