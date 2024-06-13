# screens/shop.py
from kivy.uix.screenmanager import Screen
from kivy.uix.button import Button

class ShopScreen(Screen):
    def __init__(self, **kwargs):
        super(ShopScreen, self).__init__(**kwargs)
        self.add_widget(Button(text='You are on Shop Screen', on_release=self.go_back))

    def go_back(self, instance):
        self.manager.current = 'main_kivy'
