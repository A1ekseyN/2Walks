"""Drop_Item — генерация дропа после Adventure.

Phase 4 задачи 1.1 (commit 4): методы принимают `state: GameState` (default
`state=None` → characteristics.game_state). Module-level `luck_chr`
(side-effect bug — пересчитывался при импорте, прокачка удачи не учитывалась)
заменён на функцию `current_luck(state)`.

Legacy-вызов `Drop_Item.item_collect(self=None, hard=...)` поддерживается —
state подтягивается через resolve. Удалить `state=None` shim после Phase 5.
"""

from random import randint

from equipment_bonus import equipment_luck_bonus
from state import GameState


# Вероятности выпадения (баланс — отдельная задача 4.19 / 3.2.2).
drop_percent_gl = 80
drop_percent_item_c = 75
drop_percent_item_b = 60
drop_percent_item_a = 45
drop_percent_item_s = 30
drop_percent_item_s_ = 15  # s_ = s+ Grade


def _resolve_state(state):
    if state is None:
        from characteristics import game_state
        return game_state
    return state


def current_luck(state: GameState = None) -> int:
    """Текущая удача = luck_skill (gym) + equipment + level. Pure (без побочных эффектов)."""
    state = _resolve_state(state)
    return state.gym.luck_skill + equipment_luck_bonus(state) + state.char_level.skill_luck


class Drop_Item:
    """Генерация случайного item после Adventure. Все методы статичны по сути."""

    def one_item_random_grade(self, hard, state: GameState = None):
        state = _resolve_state(state)
        luck = current_luck(state)
        if hard == 'walk_easy':
            i = randint(1, 100 - luck)
            if i <= drop_percent_gl:
                c = randint(1, 100 - luck)
                if c <= drop_percent_item_c:
                    return 'c-grade'

        elif hard == 'walk_normal':
            i = randint(1, 100 - luck)
            if i <= drop_percent_gl:
                c = randint(1, 100 - luck)
                b = randint(1, 100 - luck)
                if c < b and c <= drop_percent_item_c:
                    return 'c-grade'
                elif b < c and b <= drop_percent_item_b:
                    return 'b-grade'

        elif hard == 'walk_hard':
            i = randint(1, 100 - luck)
            if i <= drop_percent_gl:
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
            i = randint(1, 100 - luck)
            if i <= drop_percent_gl:
                b = randint(1, 100 - luck)
                a = randint(1, 100 - luck)
                s = randint(1, 100 - luck)
                if b < a and b < s and b <= drop_percent_item_b:
                    return 'b-grade'
                elif a < b and a < s and a <= drop_percent_item_a:
                    return 'a-grade'
                elif s < b and s < a and s <= drop_percent_item_s:
                    return 's-grade'

        elif hard == 'walk_20k':
            i = randint(1, 100 - luck)
            if i <= drop_percent_gl:
                a = randint(1, 100 - luck)
                s = randint(1, 100 - luck)
                s_ = randint(1, 100 - luck)
                if a < s and a < s_ and a <= drop_percent_item_a:
                    return 'a-grade'
                elif s < a and s < s_ and s <= drop_percent_item_s:
                    return 's-grade'
                elif s_ < a and s_ < s and s_ <= drop_percent_item_s_:
                    return 's+grade'

        elif hard == 'walk_25k':
            i = randint(1, 100 - luck)
            if i <= drop_percent_gl:
                s = randint(1, 100 - luck)
                s_ = randint(1, 100 - luck)
                if s < s_ and s <= drop_percent_item_s:
                    return 's-grade'
                elif s_ < s and s_ <= drop_percent_item_s_:
                    return 's+grade'

        elif hard == 'walk_30k':
            i = randint(1, 100 - luck)
            if i <= drop_percent_gl:
                s_ = randint(1, 100 - luck)
                if s_ <= drop_percent_item_s_:
                    return 's+grade'

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

    def item_type(self, state: GameState = None):
        state = _resolve_state(state)
        luck = current_luck(state)
        ring = randint(1, 100 + luck)
        necklace = randint(1, 100 + luck)
        helmet = randint(1, 100 + luck)
        shoes = randint(1, 100 + luck)
        tshirt = randint(1, 100 + luck)

        max_value = max(ring, necklace, helmet, shoes, tshirt)

        if ring == max_value:
            item_type = 'ring'
        elif necklace == max_value:
            item_type = 'necklace'
        elif helmet == max_value:
            item_type = 'helmet'
        elif shoes == max_value:
            item_type = 'shoes'
        elif tshirt == max_value:
            item_type = 't-shirt'
        else:
            return None

        values = [ring, necklace, helmet, shoes, tshirt]
        if values.count(max_value) > 1:
            return None
        return item_type

    def characteristic_type(self, state: GameState = None):
        state = _resolve_state(state)
        luck = current_luck(state)
        stamina = randint(1, 100 + luck)
        energy_max = randint(1, 100 + luck)
        speed_skill = randint(1, 100 + luck)
        luck_v = randint(1, 100 + luck)

        if stamina > energy_max and stamina > speed_skill and stamina > luck_v:
            return 'stamina'
        elif energy_max > stamina and energy_max > speed_skill and energy_max > luck_v:
            return 'energy_max'
        elif speed_skill > stamina and speed_skill > energy_max and speed_skill > luck_v:
            return 'speed_skill'
        elif luck_v > stamina and luck_v > energy_max and luck_v > speed_skill:
            return 'luck'
        return None

    def item_quality(self, state: GameState = None):
        state = _resolve_state(state)
        return randint(20 + current_luck(state), 100)

    def item_price(self, grade, quality):
        if grade[0] == 'c-grade':
            return round(quality[0] * 0.5)
        elif grade[0] == 'b-grade':
            return round(quality[0] * 1)
        elif grade[0] == 'a-grade':
            return round(quality[0] * 1.5)
        elif grade[0] == 's-grade':
            return round(quality[0] * 2)
        elif grade[0] == 's+grade':
            return round(quality[0] * 2.5)

    def item_collect(self, hard, state: GameState = None):
        """Собирает item из подразделов. Если все поля валидны — кладёт в state.inventory."""
        state = _resolve_state(state)
        item = {
            'item_name': [],
            'item_type': [],
            'grade': [],
            'characteristic': [],
            'bonus': [],
            'quality': [],
            'price': [],
        }

        item['item_type'].append(Drop_Item.item_type(self, state))
        item['item_name'].append(item['item_type'][0])
        item['grade'].append(Drop_Item.one_item_random_grade(self, hard=hard, state=state))
        item['characteristic'].append(Drop_Item.characteristic_type(self, state))
        item['bonus'].append(Drop_Item.item_bonus_value(self, grade=item['grade']))
        item['quality'].append(Drop_Item.item_quality(self, state))
        item['price'].append(Drop_Item.item_price(self, grade=item['grade'], quality=item['quality']))

        if (item['item_type'][0] is not None
                and item['grade'][0] is not None
                and item['characteristic'][0] is not None
                and item['quality'][0] is not None):
            print(f'\nВыпал предмет: '
                  f'\n- {item["grade"][0]}: {item["item_type"][0].title()} + {item["bonus"][0]} {item["characteristic"][0].title()} '
                  f'(Качество: {item["quality"][0]}) (Цена: {item["price"][0]} $). \n')
            state.inventory.append(item)
            return item
        print('--- Ничего не выпало ---\n')
        return None
