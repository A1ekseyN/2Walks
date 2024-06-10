from random import randint
from characteristics import char_characteristic
from equipment_bonus import equipment_luck_bonus

drop_percent_gl = 80
drop_percent_item_c = 75
drop_percent_item_b = 60
drop_percent_item_a = 45
drop_percent_item_s = 30
drop_percent_item_s_ = 15       # s_ = s+ Grade

luck_chr = char_characteristic['luck_skill'] + equipment_luck_bonus()


class Drop_Item():
    # Клас для генерации случайного item, после прохождения приключения.
    # Вероятность выпадения item и grade item по формуле, которая рассчитывает на оборот. То есть 1 больше чем 2 или 3.
    def one_item_random_grade(self, hard):
        # One item generation
        if hard == 'walk_easy':
            i = randint(1, 100 - luck_chr)
            if i <= drop_percent_gl:  # Определение выпал item или нет.
                c = randint(1, 100 - luck_chr)
                if c <= drop_percent_item_c:
                    grade = 'c-grade'
                    return grade

        elif hard == 'walk_normal':
            i = randint(1, 100 - luck_chr)
            if i <= drop_percent_gl:   # Определение выпал item или нет.
                c = randint(1, 100 - luck_chr)
                b = randint(1, 100 - luck_chr)
                if c < b and c <= drop_percent_item_c:
                    grade = 'c-grade'
                    return grade
                elif b < c and b <= drop_percent_item_b:
                    grade = 'b-grade'
                    return grade

        elif hard == 'walk_hard':
            # При 10к шагах выпадают вещи: b-grade и a-grade. Нужно протестировать или нужно добавить в этот пул c-grade
            i = randint(1, 100 - luck_chr)
            if i <= drop_percent_gl:    # Определение выпал item или нет.
                c = randint(1, 100 - luck_chr)
                b = randint(1, 100 - luck_chr)
                a = randint(1, 100 - luck_chr)
                # C-Grade or B-Grade or A-Grade
                if c < b and c < a and c <= drop_percent_item_c:
                    grade = 'c-grade'
                    return grade
                elif b < c and b < a and b <= drop_percent_item_b:
                    grade = 'b-grade'
                    return grade
                elif a < c and a < b and a <= drop_percent_item_a:
                    grade = 'a-grade'
                    return grade

        elif hard == 'walk_15k':
            # При 15к шагов выпадают вещи: B, A, S Grade.
            i = randint(1, 100 - luck_chr)
            if i <= drop_percent_gl:    # Определяет выпал предмет или нет
                b = randint(1, 100 - luck_chr)
                a = randint(1, 100 - luck_chr)
                s = randint(1, 100 - luck_chr)
                # B-Grade or A-Grade or S-Grade
                if b < a and b < s and b <= drop_percent_item_b:
                    grade = 'b-grade'
                    return grade
                elif a < b and a < s and a <= drop_percent_item_a:
                    grade = 'a-grade'
                    return grade
                elif s < b and s < a and s <= drop_percent_item_s:
                    grade = 's-grade'
                    return grade

        elif hard == 'walk_25k':
            # При 25к шагов выпадают вещи: S, S+ Grade.
            i = randint(1, 100 - luck_chr)
            if i <= drop_percent_gl:  # Определяет выпал предмет или нет.
                s = randint(1, 100 - luck_chr)
                s_ = randint(1, 100 - luck_chr)
                # S-Grade or S+Grade
                if s < s_ and s <= drop_percent_item_s:
                    grade = 's-grade'
                    return grade
                elif s_ < s and s_ <= drop_percent_item_s_:
                    grade = 's+grade'
                    return grade

        elif hard == 'walk_30k':
            # При 30к шагов выпадают вещи: только S+ Grade.
            i = randint(1, 100 - luck_chr)
            if i <= drop_percent_gl:  # Определяет выпал предмет или нет.
                s_ = randint(1, 100 - luck_chr)
                if s_ <= drop_percent_item_s_:
                    grade = 's+grade'
                    return grade


    def item_bonus_value(item, grade):
        if grade[0] == 'c-grade':
            return 1
        elif grade[0] == 'b-grade':
            return 2
        elif grade[0] == 'a-grade':
            return 3
        elif grade[0] == 's-grade':
            return 4
        elif grade[0] == 's+grade':
            return 5

    def item_type(self):
        # Определение типа предмета (Ring, Necklace)
        ring = randint(1, 100 + luck_chr)
        necklace = randint(1, 100 + luck_chr)
        if ring > necklace:
            item_type = 'ring'
        elif necklace > ring:
            item_type = 'necklace'
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
            characteristic = 'stamina'
        elif energy_max > stamina and energy_max > speed_skill and energy_max > luck:
            characteristic = 'energy_max'
        elif speed_skill > stamina and speed_skill > energy_max and speed_skill > luck:
            characteristic = 'speed_skill'
        elif luck > stamina and luck > energy_max and luck > speed_skill:
            characteristic = 'luck'
        else:
            return None
        return characteristic

    def item_quality(self):
        # Определение качества предмета
        quality = randint(20 + luck_chr, 100)
        return quality

    def item_price(self, grade, quality):
        # Определение цены предмета.
        if grade[0] == 'c-grade':
            price = round(quality[0] * 0.5)
            return price
        elif grade[0] == 'b-grade':
            price = round(quality[0] * 1)
            return price
        elif grade[0] == 'a-grade':
            price = round(quality[0] * 1.5)
            return price
        elif grade[0] == 's-grade':
            price = round(quality[0] * 2)
            return price
        elif grade[0] == 's+grade':
            price = round(quality[0] * 2.5)
            return price

    def item_collect(self, hard):
        # Собираем предмет из разных подразделов.
        global char_characteristic
        item = {
            'item_name': [],
            'item_type': [],
            'grade': [],
            'characteristic': [],
            'bonus': [],
            'quality': [],
            'price': [],
        }

        item['item_type'].append(Drop_Item.item_type(self))
        item['item_name'].append(item['item_type'][0])
        item['grade'].append(Drop_Item.one_item_random_grade(self, hard=hard))
        item['characteristic'].append(Drop_Item.characteristic_type(self))
        item['bonus'].append(Drop_Item.item_bonus_value(self, grade=item['grade']))
        item['quality'].append(Drop_Item.item_quality(self))
        item['price'].append(Drop_Item.item_price(self, grade=item['grade'], quality=item['quality']))

        if item['item_type'][0] != None and item['grade'][0] != None and item['characteristic'][0] != None and item['quality'][0] != None:
#            print(item)
            print(f'\nВыпал предмет: '
                  f'\n- {item["grade"][0]}: {item["item_type"][0].title()} + {item["bonus"][0]} {item["characteristic"][0].title()} (Качество: {item["quality"][0]}) (Цена: {item["price"][0]} $). \n')
            return char_characteristic['inventory'].append(item)
        else:
            return print('--- Ничего не выпало ---\n')

#Drop_Item.item_collect(self=None, hard='walk_20k')
