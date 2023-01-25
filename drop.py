from random import randint
from characteristics import char_characteristic

drop_percent_gl = 80
drop_percent_item_c = 75
drop_percent_item_b = 60
drop_percent_item_a = 45

#luck_chr = 0  # Шанс удачи персонажа
luck_chr = char_characteristic['luck_skill']


class Drop_Item():
    # Клас для генерации рандомной item, после прохождения приключения.

    def one_item_random_grade(self):
        # 1 item generation
        i = randint(1, 100 - luck_chr)
        if i <= drop_percent_gl:  # Определение выпал item или нет.
            c = randint(1, 100 - luck_chr)
            if c <= drop_percent_item_c:
                grade = 'C-Grade'
                return grade
            else:
                return None
        else:
            return None

    def item_bonus_value(item, grade):
        if grade[0] == 'C-Grade':
            return 1

    def item_type(self):
        # Определение типа предмена (Ring, Necklace)
        ring = randint(1, 100 + luck_chr)
        necklace = randint(1, 100 + luck_chr)
        if ring > necklace:
            item_type = 'Ring'
        elif necklace > ring:
            item_type = 'Necklace'
        else:
            return None
        return item_type

    def characteristic_type(self):
        # Определение типа характеристик item
        stamina = randint(1, 100 + luck_chr)
        energy_max = randint(1, 100 + luck_chr)
        speed_skill = randint(1, 100 + luck_chr)
        luck = randint(1, 100 + luck_chr)

        if stamina > energy_max and stamina > speed_skill and stamina > luck:
            chr = 'stamina'
        elif energy_max > stamina and energy_max > speed_skill and energy_max > luck:
            chr = 'energy_max'
        elif speed_skill > stamina and speed_skill > energy_max and speed_skill > luck:
            chr = 'speed_skill'
        elif luck > stamina and luck > energy_max and luck > speed_skill:
            chr = 'luck'
        else:
            return None
        return chr

    def item_quality(self):
        # Определение качества предмета
        q = randint(20 + luck_chr, 100)
        return q

    def item_collect(self):
        # Собираем предмет из разных подразделов.
        global char_characteristic
        item = {
            'item_type': [],
            'grade': [],
            'characteristic': [],
            'bonus': [],
            'quality': [],
        }

        item['item_type'].append(Drop_Item.item_type(self))
        item['grade'].append(Drop_Item.one_item_random_grade(self))
        item['characteristic'].append(Drop_Item.characteristic_type(self))
        item['bonus'].append(Drop_Item.item_bonus_value(self, grade=item['grade']))
        item['quality'].append(Drop_Item.item_quality(self))

        if item['item_type'][0] != None and item['grade'][0] != None and item['characteristic'][0] != None and item['quality'][0] != None:
            print(f'\nВыпал предмет: '
                  f'\n- {item["grade"][0]}: {item["item_type"][0]} (+ {item["bonus"][0]} {item["characteristic"][0]} (Качество: {item["quality"][0]})). ')
            return char_characteristic['inventory'].append(item)
#            return item
        else:
            return print('\n--- Ничего не выпало ---.')


#Drop_Item.item_collect(self=None)
