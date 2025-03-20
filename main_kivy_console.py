import sys
from threading import Thread
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.clock import Clock
from kivy.uix.button import Button
from game import game


class ConsoleApp(App):
    def build(self):
        self.layout = BoxLayout(orientation='vertical')

        self.console_output = TextInput(readonly=True, size_hint_y=0.9, font_name='Roboto', font_size=14)
        self.layout.add_widget(self.console_output)

        self.console_input = TextInput(hint_text='Введите команду', multiline=False, size_hint_y=0.1)
        self.console_input.bind(on_text_validate=self.send_command)
        self.layout.add_widget(self.console_input)

        self.console_thread = Thread(target=self.run_game, daemon=True)
        self.console_thread.start()

        return self.layout

    def run_game(self):
        sys.stdout = self
        game()

    def send_command(self, instance):
        command = self.console_input.text.strip()
        if command:
            print(command)  # Вывод команды в консоль
            self.console_input.text = ""

    def write(self, message):
        Clock.schedule_once(lambda dt: self.update_console_output(message))

    def update_console_output(self, message):
        self.console_output.text += message
        self.console_output.cursor = (0, len(self.console_output.text))  # Прокрутка вниз

    def flush(self):
        pass  # Метод flush нужен для совместимости с sys.stdout


if __name__ == '__main__':
    ConsoleApp().run()
