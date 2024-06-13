# screens/home.py
from kivy.uix.screenmanager import Screen
from kivy.uix.button import Button

class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super(HomeScreen, self).__init__(**kwargs)
        self.add_widget(Button(text='You are on Home Screen', on_release=self.go_back))

    def go_back(self, instance):
        self.manager.current = 'main_kivy'
