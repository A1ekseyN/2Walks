"""Monte-Carlo симулятор drop-механики (10 000 итераций × 6 сложностей).

Standalone скрипт — запускается как `python drop_test_montecarlo.py`.

NB: внутренние формулы — упрощённый fork drop.py для измерения распределения
по grade'ам (см. TASKS.md 3.2.1 для контекста). Не использовать для логики игры.
"""

from random import randint

from equipment_bonus import equipment_luck_bonus
from state import GameState


drop_percent_gl = 80
drop_percent_item_c = 75
drop_percent_item_b = 60
drop_percent_item_a = 45
drop_percent_item_s = 30
drop_percent_item_s_ = 20  # s_ = s+ Grade


def current_luck(state: GameState) -> int:
    return state.gym.luck_skill + equipment_luck_bonus(state) + state.char_level.skill_luck


class Drop_Item:
    def one_item_random_grade(self, hard, state: GameState):
        luck = current_luck(state)
        i = randint(1, 100 - luck)
        if i > drop_percent_gl:
            return None

        if hard == 'walk_easy':
            c = randint(1, 100 - luck)
            if c <= drop_percent_item_c:
                return 'c-grade'

        elif hard == 'walk_normal':
            c = randint(1, 100 - luck)
            b = randint(1, 100 - luck)
            if c < b and c <= drop_percent_item_c:
                return 'c-grade'
            elif b < c and b <= drop_percent_item_b:
                return 'b-grade'

        elif hard == 'walk_hard':
            c = randint(1, 100 - luck)
            b = randint(1, 100 - luck)
            a = randint(1, 100 - luck)
            if c < b and c < a and c <= drop_percent_item_c:
                return 'c-grade'
            elif b < c and b < a and b <= drop_percent_item_b:
                return 'b-grade'
            elif a < c and a < b and a <= drop_percent_item_a:
                return 'a-grade'

        elif hard == 'walk_15k':
            b = randint(1, 100 - luck)
            a = randint(1, 100 - luck)
            s = randint(1, 100 - luck)
            if b < a and b < s and b <= drop_percent_item_b:
                return 'b-grade'
            elif a < b and a < s and a <= drop_percent_item_a:
                return 'a-grade'
            elif s < b and s < a and s <= drop_percent_item_s:
                return 's-grade'

        elif hard == 'walk_25k':
            s = randint(1, 100 - luck)
            s_ = randint(1, 100 - luck)
            if s < s_ and s <= drop_percent_item_s:
                return 's-grade'
            elif s_ < s and s_ <= drop_percent_item_s_:
                return 's+grade'

        elif hard == 'walk_30k':
            s_ = randint(1, 100 - luck)
            if s_ <= drop_percent_item_s_:
                return 's+grade'
        return None

    def item_bonus_value(self, grade):
        return {
            'c-grade': 1, 'b-grade': 2, 'a-grade': 3, 's-grade': 4, 's+grade': 5,
        }.get(grade, 0)

    def item_type(self, state: GameState):
        luck = current_luck(state)
        ring = randint(1, 100 + luck)
        necklace = randint(1, 100 + luck)
        return 'ring' if ring > necklace else 'necklace'

    def characteristic_type(self, state: GameState):
        luck = current_luck(state)
        return max(
            ('stamina', randint(1, 100 + luck)),
            ('energy_max', randint(1, 100 + luck)),
            ('speed_skill', randint(1, 100 + luck)),
            ('luck', randint(1, 100 + luck)),
            key=lambda x: x[1],
        )[0]

    def item_quality(self, state: GameState):
        return randint(20 + current_luck(state), 100)

    def item_price(self, grade, quality):
        return round(quality * {
            'c-grade': 0.5, 'b-grade': 1, 'a-grade': 1.5, 's-grade': 2, 's+grade': 2.5,
        }.get(grade, 0))

    def item_collect(self, hard, state: GameState):
        item = {
            'item_name': '', 'item_type': '', 'grade': '',
            'characteristic': '', 'bonus': 0, 'quality': 0, 'price': 0,
        }

        item['item_type'] = self.item_type(state)
        item['item_name'] = item['item_type']
        item['grade'] = self.one_item_random_grade(hard, state)
        if not item['grade']:
            print('--- Ничего не выпало ---\n')
            return None

        item['characteristic'] = self.characteristic_type(state)
        item['bonus'] = self.item_bonus_value(item['grade'])
        item['quality'] = self.item_quality(state)
        item['price'] = self.item_price(item['grade'], item['quality'])

        print(f'\nВыпал предмет: '
              f'\n- {item["grade"]}: {item["item_type"].title()} + {item["bonus"]} {item["characteristic"].title()} '
              f'(Качество: {item["quality"]}) (Цена: {item["price"]} $). \n')
        state.inventory.append(item)
        return item


def test_item_generation(state: GameState):
    difficulties = ['walk_easy', 'walk_normal', 'walk_hard', 'walk_15k', 'walk_25k', 'walk_30k']
    results = {d: {'total': 0, 'c-grade': 0, 'b-grade': 0, 'a-grade': 0,
                   's-grade': 0, 's+grade': 0, 'none': 0}
               for d in difficulties}

    for difficulty in difficulties:
        for _ in range(10000):
            item = Drop_Item().item_collect(difficulty, state)
            results[difficulty]['total'] += 1
            if item:
                results[difficulty][item['grade']] += 1
            else:
                results[difficulty]['none'] += 1

    for difficulty, data in results.items():
        print(f'\n{difficulty} results:')
        for grade, count in data.items():
            if grade != 'total':
                percentage = (count / data['total']) * 100
                print(f'  {grade}: {count} ({percentage:.2f}%)')


if __name__ == "__main__":
    from characteristics import init_game_state
    state = init_game_state()
    test_item_generation(state)
    print(f"Luck: {current_luck(state)}")
