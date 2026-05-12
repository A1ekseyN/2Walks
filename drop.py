"""Drop_Item — генерация дропа после Adventure.

Все методы и `current_luck(state)` принимают state явно — `luck_chr` больше не
кэшируется на уровне модуля (раньше был side-effect bug: фиксировался при импорте
и не учитывал прокачку удачи).
"""

from random import randint
from typing import Any

from bonus import inventory_full
from equipment_bonus import equipment_luck_bonus
from state import GameState


# Вероятности выпадения (баланс — отдельная задача 4.19 / 3.2.2).
drop_percent_gl = 80
drop_percent_item_c = 75
drop_percent_item_b = 60
drop_percent_item_a = 45
drop_percent_item_s = 30
drop_percent_item_s_ = 15  # s_ = s+ Grade (base, walk_20k)

# Per-adventure overrides для S+ threshold (0.2.4g balance — follow-up
# задачи 4.29-replacement). Базовый `drop_percent_item_s_=15` остаётся для
# walk_20k (где s+ — редкий бонус среди 3 тиров). На endgame'е повышен
# чтобы walk_30k не выглядел бесполезным относительно walk_25k:
#   - до 0.2.4g: walk_25k P(S+)=14%, walk_30k P(S+)=15.5% (luck=12) —
#     практически одинаково при цене +20% шагов/энергии/времени.
#   - после 0.2.4g: walk_25k S+=20 → 18.2%, walk_30k S+=35 → 36.2% —
#     четкое позиционирование walk_30k как endgame walk «специально за S+».
drop_percent_item_s_walk_25k = 20
drop_percent_item_s_walk_30k = 35


def current_luck(state: GameState) -> int:
    """Текущая удача = luck_skill (gym) + equipment + level. Pure (без побочных эффектов)."""
    return state.gym.luck_skill + equipment_luck_bonus(state) + state.char_level.skill_luck


def compute_grade_probabilities(adventure_name: str, state: GameState) -> dict[str, float]:
    """4.29-replacement (0.2.4f) — аналитическая вероятность каждого грейда
    для приключения с учётом current_luck. Pure (без рандома).

    Returns: `{'c-grade': 0.60, 'b-grade': 0.0, ..., 'nothing': 0.40}` —
    ключ 'nothing' = вероятность miss'а (не выпал ни один грейд).

    Формула: пусть N = 100 - luck (clamp ≥ 1). Тиры — упорядоченный список
    `[(grade_i, threshold_i)]` из `adventure_data_table[adv]['drops']`. На
    каждый дроп drop.py делает один gate-roll `i ~ U[1, N]` + по одному
    конкурентному ролу на каждый тир `R_i ~ U[1, N]`. Тир `i` выигрывает
    если `R_i ≤ threshold_i` И `R_i < R_j ∀ j ≠ i`.

        P(gate) = min(drop_percent_gl, N) / N
        P(tier i wins | gate) = Σ_{r=1}^{min(T_i, N)} (1/N) · ((N-r)/N)^{n-1}
        P(grade_i) = P(gate) · P(tier i wins | gate)

    где n — количество тиеров.

    Sanity (luck=0, N=100):
        walk_easy   → c-grade 60.00%, nothing 40.00%
        walk_normal → c-grade 37.20%, b-grade 33.36%, nothing 29.44%
        walk_30k    → s+grade 11.94%, nothing 88.06%
    """
    # Lazy import чтобы избежать circular (adventure_data.py импортирует
    # constants из drop.py — наш caller — а если бы drop импортил adventure_data
    # на module-level, был бы цикл).
    from adventure_data import adventure_data_table

    luck = current_luck(state)
    N = max(1, 100 - luck)  # clamp: при luck≥100 защита от деления на ноль

    adv = adventure_data_table.get(adventure_name)
    if adv is None:
        return {'nothing': 1.0}
    # adventure_data_table[..]['drops']: list[tuple[str, int]] — гарантировано
    # схемой adventure_data.py, но dict-значения внутри adv общие (через `object`),
    # т.к. в одной таблице мешаются 'steps': int / 'drops': list. Annotate явно
    # и cast'им — без этого mypy ругается на len() и iteration.
    drops_raw: Any = adv.get('drops')
    if not drops_raw:
        return {'nothing': 1.0}
    tiers: list[tuple[str, int]] = drops_raw
    n_tiers = len(tiers)
    n_competitors = n_tiers - 1
    p_gate = min(drop_percent_gl, N) / N

    result: dict[str, float] = {}
    total = 0.0
    for grade, threshold in tiers:
        k = min(threshold, N)
        if k <= 0:
            p_grade = 0.0
        else:
            # Σ_{r=1}^{k} (1/N) · ((N-r)/N)^{n-1}
            acc = 0.0
            for r in range(1, k + 1):
                acc += ((N - r) / N) ** n_competitors
            p_grade = acc / N
        p = p_gate * p_grade
        result[grade] = p
        total += p

    result['nothing'] = max(0.0, 1.0 - total)
    return result


class Drop_Item:
    """Генерация случайного item после Adventure. Все методы статичны по сути."""

    def one_item_random_grade(self, hard, state: GameState):
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
                # 0.2.4g — per-adventure override (см. константы выше).
                elif s_ < s and s_ <= drop_percent_item_s_walk_25k:
                    return 's+grade'

        elif hard == 'walk_30k':
            i = randint(1, 100 - luck)
            if i <= drop_percent_gl:
                s_ = randint(1, 100 - luck)
                # 0.2.4g — per-adventure override, endgame bonus (см. выше).
                if s_ <= drop_percent_item_s_walk_30k:
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

    def item_type(self, state: GameState):
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

    def characteristic_type(self, state: GameState):
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

    def item_quality(self, state: GameState):
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

    def item_collect(self, hard, state: GameState):
        """Собирает item из подразделов. Если все поля валидны — кладёт в state.inventory."""
        item: dict[str, list] = {
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
            from history import log_event

            # 4.50.1 — три ветки в зависимости от заполненности инвентаря и
            # наличия pending. Базовая логика appendа осталась только в (1).
            # Лог-события: 'drop' / 'drop_pending' / 'drop_force_sold' —
            # позволяют отличать на дашборде истории сценарий (4.6.2).
            if not inventory_full(state):
                # (1) Обычный drop — есть место, кладём в инвентарь.
                state.inventory.append(item)
                log_event('drop',
                          adventure=hard,
                          item_type=item['item_type'][0],
                          grade=item['grade'][0],
                          characteristic=item['characteristic'][0],
                          bonus=item['bonus'][0],
                          quality=item['quality'][0],
                          price=item['price'][0])
            elif state.pending_drop is None:
                # (2) Рюкзак полон, pending свободен — копим находку в pending.
                # Игрок resolve'ит при следующем заходе в Inventory (A3 flow):
                # одноразовое info-уведомление здесь + persistent badge в menu.
                state.pending_drop = item
                print('🎒 Инвентарь полон. Находка ждёт решения — '
                      'открой Инвентарь чтобы продать что-то старое или эту находку.')
                log_event('drop_pending',
                          adventure=hard,
                          item_type=item['item_type'][0],
                          grade=item['grade'][0],
                          characteristic=item['characteristic'][0],
                          bonus=item['bonus'][0],
                          quality=item['quality'][0],
                          price=item['price'][0])
            else:
                # (3) Рюкзак полон + pending уже занят — forced sale (вариант D-iii):
                # новая находка авто-продаётся за base price, money += price.
                # Pending остаётся прежним; не теряем уже найденное.
                price = item['price'][0]
                state.money += price
                print(f'🎒 Инвентарь и слот находок заняты. '
                      f'Находка автоматически продана за {price} $.')
                log_event('drop_force_sold',
                          adventure=hard,
                          item_type=item['item_type'][0],
                          grade=item['grade'][0],
                          characteristic=item['characteristic'][0],
                          bonus=item['bonus'][0],
                          quality=item['quality'][0],
                          price=price)
            return item
        print('--- Ничего не выпало ---\n')
        return None
