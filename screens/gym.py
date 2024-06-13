# screens/gym.py
from kivy.uix.screenmanager import Screen
from kivy.uix.button import Button

class GymScreen(Screen):
    def __init__(self, **kwargs):
        super(GymScreen, self).__init__(**kwargs)
        self.add_widget(Button(text='You are on Gym Screen', on_release=self.go_back))

    def go_back(self, instance):
        self.manager.current = 'main_kivy'
