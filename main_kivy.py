# main_kivy.py

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.metrics import dp
from kivy.core.window import Window

from screens.home import HomeScreen
from screens.adventure import AdventureScreen
from screens.gym import GymScreen
from screens.shop import ShopScreen
from screens.work import WorkScreen
from widgets.character_info_widget import CharacterInfoWidget


class MainScreen(Screen):
    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)

        # Основной Layout для размещения двух вертикальных BoxLayout: один для информации о персонаже, другой для кнопок
        main_layout = BoxLayout(orientation='horizontal', padding=(dp(20), dp(20)), spacing=dp(10))

        # BoxLayout для информации о персонаже в верхнем левом углу
        character_info_layout = BoxLayout(orientation='vertical', size_hint=(None, None), size=(dp(200), dp(150)))
        self.character_info_widget = CharacterInfoWidget()
        character_info_layout.add_widget(self.character_info_widget)
        character_info_layout.pos_hint = {'x': 0, 'top': 1}

        # Layout для кнопок меню
        button_layout = BoxLayout(orientation='vertical', spacing=dp(10))
        button_layout.size_hint_y = None
        button_layout.height = dp(300)
        button_layout.pos_hint = {'center_x': 0.5, 'center_y': 0.5}

        button_info = [
            ('Home', 'Go to Home'),
            ('Gym', 'Go to Gym'),
            ('Shop', 'Go to Shop'),
            ('Work', 'Go to Work'),
            ('Adventure', 'Go to Adventure'),
        ]

        for screen_name, button_text in button_info:
            btn = Button(text=button_text,
                         on_release=self.change_screen,
                         size_hint=(None, None),
                         size=(dp(200), dp(50)),
                         background_normal='',
                         background_color=(0.4, 0.4, 0.8, 1),
                         border=(20, 20, 20, 20))
            btn.screen_name = screen_name.lower()
            button_layout.add_widget(btn)

        # Добавляем BoxLayout для информации о персонаже и кнопок в основной Layout
        main_layout.add_widget(character_info_layout)
        main_layout.add_widget(button_layout)

        self.add_widget(main_layout)

        # Инициализация информации о персонаже
        self.character_info_widget.update_info(steps=0, energy=50, max_energy=100, money=200, level=1, exp=7500, max_exp=10000)

    def change_screen(self, instance):
        self.manager.current = instance.screen_name


class MyGameApp(App):
    def build(self):
        # Устанавливаем серый цвет фона для всего окна приложения
        Window.clearcolor = (0.8, 0.8, 0.8, 1)  # RGBA цвет (серый с полной прозрачностью)

        sm = ScreenManager()
        sm.add_widget(MainScreen(name='main_kivy'))
        sm.add_widget(HomeScreen(name='home'))
        sm.add_widget(GymScreen(name='gym'))
        sm.add_widget(ShopScreen(name='shop'))
        sm.add_widget(WorkScreen(name='work'))
        sm.add_widget(AdventureScreen(name='adventure'))
        return sm


if __name__ == '__main__':
    MyGameApp().run()
