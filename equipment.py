from operator import itemgetter
from characteristics import char_characteristic
from inventory import inventory_view


class Equipment():
    """Клас для инициализации предметов, одетых на персонаже"""

    def equipment_view(self):
        # Отображение вещей, которые одеты на персонаже.
        print('\n--- 🎒 Экипировка персонажа 🎒 ---')
        if char_characteristic['equipment_head'] == None and char_characteristic['equipment_neck'] == None and \
            char_characteristic['equipment_torso'] == None and char_characteristic['equipment_finger_01'] == None and \
            char_characteristic['equipment_finger_02'] == None and char_characteristic['equipment_legs'] == None and \
            char_characteristic['equipment_foots'] == None:
            print('\nНа персонаже нет вещей: ')

        if char_characteristic['equipment_head'] != None:
            print(f'1. Голова:            {char_characteristic["equipment_head"]["item_name"][0].title()} {char_characteristic["equipment_head"]["grade"][0].title()}: + {char_characteristic["equipment_head"]["bonus"][0]} {char_characteristic["equipment_head"]["characteristic"][0].title()} (Quality: {char_characteristic["equipment_head"]["quality"][0]:,.2f})')
        elif char_characteristic['equipment_head'] == None:
            print('1. Голова:            Нет одежды')

        if char_characteristic['equipment_neck'] != None:
            print(f'2. Шея:               {char_characteristic["equipment_neck"]["item_name"][0].title()} {char_characteristic["equipment_neck"]["grade"][0].title()}: + {char_characteristic["equipment_neck"]["bonus"][0]} {char_characteristic["equipment_neck"]["characteristic"][0].title()} (Quality: {char_characteristic["equipment_neck"]["quality"][0]:,.2f})')
        elif char_characteristic['equipment_neck'] == None:
            print('2. Шея:               Нет одежды')

        if char_characteristic['equipment_torso'] != None:
            print(f'3. Торс:              {char_characteristic["equipment_torso"]["item_name"][0].title()} {char_characteristic["equipment_torso"]["grade"][0].title()}: + {char_characteristic["equipment_torso"]["bonus"][0]} {char_characteristic["equipment_torso"]["characteristic"][0].title()} (Quality: {char_characteristic["equipment_torso"]["quality"][0]:,.2f})')
        elif char_characteristic['equipment_torso'] == None:
            print('3. Торс:              Нет одежды')

        if char_characteristic['equipment_finger_01'] != None:
            print(f'4. Палец левой руки:  {char_characteristic["equipment_finger_01"]["item_name"][0].title()} {char_characteristic["equipment_finger_01"]["grade"][0].title()}: + {char_characteristic["equipment_finger_01"]["bonus"][0]} {char_characteristic["equipment_finger_01"]["characteristic"][0].title()} (Quality: {char_characteristic["equipment_finger_01"]["quality"][0]:,.2f})')
        elif char_characteristic['equipment_finger_01'] == None:
            print('4. Палец левой руки:  Нет кольца')

        if char_characteristic['equipment_finger_02'] != None:
            print(f'5. Палец правой руки: {char_characteristic["equipment_finger_02"]["item_name"][0].title()} {char_characteristic["equipment_finger_02"]["grade"][0].title()}: + {char_characteristic["equipment_finger_02"]["bonus"][0]} {char_characteristic["equipment_finger_02"]["characteristic"][0].title()} (Quality: {char_characteristic["equipment_finger_02"]["quality"][0]:,.2f})')
        elif char_characteristic['equipment_finger_02'] == None:
            print('5. Палец правой руки: Нет кольца')

#        if char_characteristic['equipment_legs'] != None:
#            print(f'6. Ноги:              {char_characteristic["equipment_legs"]["item_name"][0].title()} {char_characteristic["equipment_legs"]["grade"][0].title()}: + {char_characteristic["equipment_legs"]["bonus"][0]} {char_characteristic["equipment_legs"]["characteristic"][0].title()} (Quality: {char_characteristic["equipment_legs"]["quality"][0]:,.2f})')
#        elif char_characteristic['equipment_legs'] == None:
#            print('6. Ноги:              Нет одежды')

        if char_characteristic['equipment_foots'] != None:
            print(f'6. Ступни:            {char_characteristic["equipment_foots"]["item_name"][0].title()} {char_characteristic["equipment_foots"]["grade"][0].title()}: + {char_characteristic["equipment_foots"]["bonus"][0]} {char_characteristic["equipment_foots"]["characteristic"][0].title()} (Quality: {char_characteristic["equipment_foots"]["quality"][0]:,.2f})')
        elif char_characteristic['equipment_foots'] == None:
            print('6. Ступни:            Нет обуви')

        print('0. Назад')
        Equipment.equipment_change(self)

    def equipment_change(self):
        # Меняет одежду на персонаже
        try:
            ask = input('\nВыберите слот, в котором хотите заменить одежду или экипировку: \n>>> ')
            if ask == '1':
                item_name = 'голова'
                item_type = 'helmet'
                item_slot = 'equipment_head'
                Equipment.equipment_change_item_in_slot(self, item_name=item_name, item_type=item_type, item_slot=item_slot)
            elif ask == '2':
                item_name = 'шея'
                item_type = 'necklace'
                item_slot = 'equipment_neck'
                Equipment.equipment_change_item_in_slot(self, item_name=item_name, item_type=item_type, item_slot=item_slot)
            elif ask == '3':
                item_name = 'торс'
                item_type = 't-shirt'
                item_slot = 'equipment_torso'
                Equipment.equipment_change_item_in_slot(self, item_name=item_name, item_type=item_type, item_slot=item_slot)
            elif ask == '4':
                item_name = 'палец левой руки'
                item_type = 'ring'
                item_slot = 'equipment_finger_01'
                Equipment.equipment_change_item_in_slot(self, item_name=item_name, item_type=item_type, item_slot=item_slot)
            elif ask == '5':
                item_name = 'палец правой руки'
                item_type = 'ring'
                item_slot = 'equipment_finger_02'
                Equipment.equipment_change_item_in_slot(self, item_name=item_name, item_type=item_type, item_slot=item_slot)
#            elif ask == '6':
#                item_name = None
#                item_type = None
#                item_slot = None
#                Equipment.equipment_change_item_in_slot(self, item_name=item_name, item_type=item_type, item_slot=item_slot)
            elif ask == '6':
                item_name = 'ступни'
                item_type = 'shoes'
                item_slot = 'equipment_foots'
                Equipment.equipment_change_item_in_slot(self, item_name=item_name, item_type=item_type, item_slot=item_slot)
            elif ask == '0':
                pass
            else:
                Equipment.equipment_change(self)
        except:
            Equipment.equipment_change(self)

    def equipment_change_item_in_slot(self, item_name, item_type, item_slot):
        cnt = 0
        list_cnt = []

        if char_characteristic[item_slot] == None:
            print(f'\n{item_name.title()} - ничего не надето.')
        elif char_characteristic[item_slot] != None:
            print(f'\nНа {item_name} у персонажа надето: '
                  f'\n- {char_characteristic[item_slot]["item_name"][0].title()} {char_characteristic[item_slot]["grade"][0].title()}: + {char_characteristic[item_slot]["bonus"][0]} {char_characteristic[item_slot]["characteristic"][0].title()} (Quality: {char_characteristic[item_slot]["quality"][0]:,.2f})')

        print(f'\nВ инвентаре имеются предметы, которые можно экипировать: ')

        ### Сортировка предметов.
        # Нужно протестировать или она правильно работает. Пока, предварительно работает.
        char_characteristic['inventory'] = sorted(char_characteristic['inventory'],
                                                  key=lambda x: (x['item_type'], x['characteristic'], x['bonus']),
                                                  reverse=True)

        for i in char_characteristic['inventory']:
            cnt += 1
            if i["item_type"][0] == item_type:
                print(f'{cnt}. {i["item_name"][0].title()} {i["grade"][0]}: + {i["bonus"][0]} {i["characteristic"][0].title()} (Quality: {i["quality"][0]:,.2f})')
                list_cnt.append(cnt)

        print('\n0. Назад'
              '\n99. Снять предмет экипировки')

        Equipment.change_item_in_slot(self, item_name, item_type, item_slot, list_cnt=list_cnt)

    def change_item_in_slot(self, item_name, item_type, item_slot, list_cnt):
        # Заменяет или добавляет предмет экипировки.
        try:
            index = int(input('\n>>> '))
            if index in list_cnt:
                print(f'\nВы выбрали предмет:'
                      f'\n- {char_characteristic["inventory"][index - 1]["item_name"][0].title()} {char_characteristic["inventory"][index - 1]["grade"][0].title()}: + {char_characteristic["inventory"][index - 1]["bonus"][0]} {char_characteristic["inventory"][index - 1]["characteristic"][0].title()} (Quality: {char_characteristic["inventory"][index - 1]["quality"][0]:,.2f}).')
                try:
                    ask = input('\nНадеть элемент экипировки на персонажа: \n1. Да\n0. Назад \n>>> ')
                    if ask == '1':
                        temp_item = None
                        if char_characteristic[item_slot] != None:
                            # Проверка или слот свободный
                            temp_item = char_characteristic[item_slot]

                        char_characteristic[item_slot] = char_characteristic['inventory'][index - 1]
                        del char_characteristic['inventory'][index - 1]

                        print('\nВы надели предмет на персонажа: ')
                        print(f'- {char_characteristic[item_slot]["item_name"][0].title()} {char_characteristic[item_slot]["grade"][0].title()}: + {char_characteristic[item_slot]["bonus"][0]} {char_characteristic[item_slot]["characteristic"][0].title()} (Quality: {char_characteristic[item_slot]["quality"][0]:,.2f})')

                        if temp_item:
                            char_characteristic['inventory'].append(temp_item)
                            print('\nВы заменили один предмет экипировки на другой.')

                        Equipment.equipment_view(self=None)
                    else:
                        Equipment.equipment_change_item_in_slot(self, item_name, item_type, item_slot)
                except:
                    print('Ошибка смены части экипировки.')
                    Equipment.change_item_in_slot(self, item_name, item_type, item_slot, list_cnt)

            elif index == 0:
                Equipment.equipment_view(self=None)
            elif index == 99:
                # Снять предмет экипировки.
                print(f'\nВы сняли предмет экипировки: '
                      f'\n- {char_characteristic[item_slot]["item_name"][0].title()} {char_characteristic[item_slot]["grade"][0].title()}: + {char_characteristic[item_slot]["bonus"][0]} {char_characteristic[item_slot]["characteristic"][0].title()} (Quality: {char_characteristic[item_slot]["quality"][0]})')
                char_characteristic['inventory'].append(char_characteristic[item_slot])
                char_characteristic[item_slot] = None
            else:
                print('\nПопробуйте еще раз ввести число: ')
                Equipment.equipment_change_item_in_slot(self, item_name, item_type, item_slot)
        except:
            print('\nПроизошла ошибка при выборе экипировки. Введите число.')
            Equipment.equipment_change_item_in_slot(self, item_name, item_type, item_slot)

    def inventory_view(self):
        print(f'\nВ инвентаре находится {len(char_characteristic["inventory"])} предметов: ')
        inventory_view()

#Equipment.equipment_view(self=None)
