from kivy.uix.screenmanager import Screen
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.metrics import dp
from kivy.uix.scrollview import ScrollView

from characteristics import char_characteristic

class InventoryScreen(Screen):
    def __init__(self, **kwargs):
        super(InventoryScreen, self).__init__(**kwargs)
        self.buttons = {}  # Словарь для хранения кнопок и их действий

        # Основной AnchorLayout для размещения других Layout
        main_layout = AnchorLayout()

        # AnchorLayout для информации о персонаже в верхнем левом углу
        character_info_layout = AnchorLayout(anchor_x='left', anchor_y='top')
        character_info_box = BoxLayout(orientation='vertical', size_hint=(None, None), size=(dp(200), dp(150)))
        # Здесь можно добавить виджет для отображения информации о персонаже
        # self.character_info_widget = CharacterInfoWidget()
        # character_info_box.add_widget(self.character_info_widget)
        character_info_layout.add_widget(character_info_box)

        # AnchorLayout для кнопок меню в центре
        button_layout = AnchorLayout(anchor_x='center', anchor_y='center')

        # Создаем два BoxLayout для двух колонок кнопок.
        column_box = BoxLayout(orientation='horizontal', spacing=dp(5), size_hint=(None, None), size=(dp(410), dp(380)))

        left_anchor = AnchorLayout(anchor_y='center', size_hint=(None, 1), width=dp(200))
        left_button_box = BoxLayout(orientation='vertical', spacing=dp(5), size_hint=(None, None), width=dp(200))
        left_button_box.bind(minimum_height=left_button_box.setter('height'))

        right_scroll = ScrollView(size_hint=(None, 1), width=dp(200))
        right_button_box = BoxLayout(orientation='vertical', spacing=dp(5), size_hint=(None, None), width=dp(200))
        right_button_box.bind(minimum_height=right_button_box.setter('height'))
        right_scroll.add_widget(right_button_box)

        # Ключи для левой колонки
        left_column_keys = [
            'equipment_head', 'equipment_neck', 'equipment_torso',
            'equipment_finger_01', 'equipment_finger_02',
            'equipment_legs', 'equipment_foots'
        ]

        # Кнопки для левой колонки
        for key in left_column_keys:
            item = char_characteristic.get(key)
            button_text = f"{item['item_name'][0].title()} (+ {item['bonus'][0]} {item['characteristic'][0].title()})" \
                if item else 'None'
            btn = Button(text=button_text,
                         size_hint=(None, None),
                         size=(dp(200), dp(50)),
                         background_normal='',
                         background_color=(0.4, 0.4, 0.8, 1),
                         border=(20, 20, 20, 20))
            btn.bind(on_release=lambda instance, k=key: self.on_equipment_button_pressed(k))
            left_button_box.add_widget(btn)
            self.buttons[key] = btn  # Сохраняем кнопку в словарь

        # Добавляем кнопку "Back" в левую колонку после кнопок экипировки
        left_button_box.add_widget(Button(text='Back',
                                          size_hint=(None, None),
                                          size=(dp(200), dp(50)),
                                          background_normal='',
                                          background_color=(0.4, 0.4, 0.8, 1),
                                          border=(20, 20, 20, 20),
                                          on_release=self.go_back))

        # Кнопки для правой колонки (inventory)
        inventory_items = char_characteristic.get('inventory', [])
        for item in inventory_items:
            button_text = f"{item['item_name'][0].title()} (+ {item['bonus'][0]} {item['characteristic'][0].title()})"
            btn = Button(text=button_text,
                         size_hint=(None, None),
                         size=(dp(200), dp(50)),
                         background_normal='',
                         background_color=(0.4, 0.4, 0.8, 1),
                         border=(20, 20, 20, 20))
            btn.bind(on_release=lambda instance, itm=item: self.on_inventory_button_pressed(itm))
            right_button_box.add_widget(btn)

        left_anchor.add_widget(left_button_box)
        column_box.add_widget(left_anchor)
        column_box.add_widget(right_scroll)
        button_layout.add_widget(column_box)

        # Добавляем AnchorLayout для информации о персонаже и кнопок в основной AnchorLayout
        main_layout.add_widget(character_info_layout)
        main_layout.add_widget(button_layout)

        self.add_widget(main_layout)

    def on_equipment_button_pressed(self, key):
        print(f'Equipment button for {key} pressed.')
        # Логика для обработки нажатия кнопок экипировки

    def on_inventory_button_pressed(self, item):
        print(f'Inventory item {item["item_name"][0]} pressed.')
        # Логика для обработки нажатия кнопок инвентаря

    def go_back(self, instance):
        self.manager.current = 'main_kivy'
