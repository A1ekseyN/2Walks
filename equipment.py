"""Управление экипировкой персонажа — отображение слотов, надевание / снятие.

Чистая логика (`_equip_from_inventory`, `_unequip`) выделена для тестируемости —
UI-обёртки в Equipment.* остаются с input/print.

Auto-Optimizer (4.63.1) — отдельный модуль `loadout.py`, UI handler здесь
(`Equipment.optimize_loadout_menu`).
"""

from typing import Optional

from bonus import backpack_capacity, inventory_full
from inventory import inventory_view
from state import GameState


# Маппинг legacy-ключа слота ('equipment_head') → атрибут state.equipment.
_SLOT_ATTR = {
    'equipment_head': 'head',
    'equipment_neck': 'neck',
    'equipment_torso': 'torso',
    'equipment_finger_01': 'finger_01',
    'equipment_finger_02': 'finger_02',
    'equipment_legs': 'legs',
    'equipment_foots': 'foots',
    'equipment_back': 'back',  # 4.51 — рюкзак
}


# ----- Чистая логика -----

def _equip_from_inventory(state: GameState, slot_attr: str, inventory_index: int) -> tuple[dict, Optional[dict]]:
    """Надеть предмет из inventory[index] на слот state.equipment.<slot_attr>.

    Если слот занят — старый предмет возвращается в inventory.
    Возвращает (new_item, prev_item).
    """
    new_item = state.inventory[inventory_index]
    prev_item = getattr(state.equipment, slot_attr)
    setattr(state.equipment, slot_attr, new_item)
    del state.inventory[inventory_index]
    if prev_item is not None:
        state.inventory.append(prev_item)
    # 4.6 — log_event надевания экипировки. _first() безопасно достаёт из
    # list-обёртки legacy item-формата (рефакторинг в 1.6).
    from history import log_event
    log_event('item_equipped',
              slot=slot_attr,
              item_type=_first(new_item.get('item_type')),
              grade=_first(new_item.get('grade')),
              characteristic=_first(new_item.get('characteristic')),
              bonus=_first(new_item.get('bonus')),
              replaced=prev_item is not None)
    return new_item, prev_item


def _unequip(state: GameState, slot_attr: str) -> Optional[dict]:
    """Снять предмет со слота — возвращается в inventory.

    Возвращает снятый предмет или None, если слот был пуст ИЛИ если рюкзак
    полон (4.50). Унеquip — это +1 предмет в инвентарь, поэтому требует
    свободный слот; UI должен пред-проверять `inventory_full(state)` чтобы
    различить «слот пуст» и «рюкзак полон».

    `_equip_from_inventory` (swap) — net-zero (один уходит в инвентарь, другой
    выходит) и в check'е не нуждается.
    """
    item: Optional[dict] = getattr(state.equipment, slot_attr)
    if item is None:
        return None
    if inventory_full(state):
        return None
    setattr(state.equipment, slot_attr, None)
    state.inventory.append(item)
    # 4.6 — log_event снятия экипировки.
    from history import log_event
    log_event('item_unequipped',
              slot=slot_attr,
              item_type=_first(item.get('item_type')),
              grade=_first(item.get('grade')))
    return item


def _first(values):
    """Безопасно достать первый элемент list-обёртки item-поля. None если пусто."""
    if not values:
        return None
    return values[0]


# ----- UI-обёртки -----

class Equipment:
    """Отображение и смена экипировки. Все методы фактически статические — `self`
    в них не используется (вызовы передают `self=None`)."""

    def equipment_view(self, state: GameState) -> None:
        eq = state.equipment

        print('\n--- 🎒 Экипировка персонажа 🎒 ---')
        if all(slot is None for slot in (
            eq.head, eq.neck, eq.torso, eq.finger_01, eq.finger_02, eq.legs, eq.foots, eq.back
        )):
            print('\nНа персонаже нет вещей: ')

        # 4.61 — 6 однотипных строк через helper. broken=0% → 🔨 СЛОМАН +0 bonus.
        slots_display = [
            ('1. Голова:           ', eq.head,      'Нет одежды'),
            ('2. Шея:              ', eq.neck,      'Нет одежды'),
            ('3. Торс:             ', eq.torso,     'Нет одежды'),
            ('4. Палец левой руки: ', eq.finger_01, 'Нет кольца'),
            ('5. Палец правой руки:', eq.finger_02, 'Нет кольца'),
            ('6. Ступни:           ', eq.foots,     'Нет обуви'),
        ]
        for label, item, empty_msg in slots_display:
            if item is None:
                print(f'{label} {empty_msg}')
                continue
            qual = item["quality"][0]
            is_broken = qual == 0
            bonus_display = '+0' if is_broken else f'+ {item["bonus"][0]}'
            broken_marker = '🔨 СЛОМАН ' if is_broken else ''
            print(f'{label} {broken_marker}{item["item_name"][0].title()} {item["grade"][0].title()}: '
                  f'{bonus_display} {item["characteristic"][0].title()} '
                  f'(Quality: {qual:,.2f})')

        # 4.51 — Рюкзак (слот 'back'): спец-формат «+N слотов» (от грейда, не bonus).
        from bonus import BACKPACK_GRADE_SLOTS
        if eq.back is None:
            print('7. Спина (рюкзак):     Нет рюкзака')
        else:
            bp = eq.back
            qual = bp["quality"][0]
            is_broken = qual == 0
            grade = bp["grade"][0]
            slots = 0 if is_broken else BACKPACK_GRADE_SLOTS.get(grade, 0)
            broken_marker = '🔨 СЛОМАН ' if is_broken else ''
            print(f'7. Спина (рюкзак):     {broken_marker}{bp["item_name"][0].title()} {grade.title()}: '
                  f'+{slots} слотов (Quality: {qual:,.2f})')

        print('\n8. 🎯 Оптимизировать loadout (auto-equip)')
        print('9. 💼 Управление preset\'ами экипировки')
        print('0. Назад')
        Equipment.equipment_change(self, state)

    def equipment_change(self, state: GameState) -> None:
        slot_map = {
            '1': ('голова',           'helmet',   'equipment_head'),
            '2': ('шея',              'necklace', 'equipment_neck'),
            '3': ('торс',             't-shirt',  'equipment_torso'),
            '4': ('палец левой руки', 'ring',     'equipment_finger_01'),
            '5': ('палец правой руки', 'ring',     'equipment_finger_02'),
            '6': ('ступни',           'shoes',    'equipment_foots'),
            '7': ('спина',            'backpack', 'equipment_back'),  # 4.51
        }
        # Цикл retry на невалиде (1.5.2 — 0.2.1h, было: рекурсивный self-call).
        while True:
            ask = input('\nВыберите слот, в котором хотите заменить одежду или экипировку: \n>>> ')
            if ask in slot_map:
                item_name, item_type, item_slot = slot_map[ask]
                Equipment.equipment_change_item_in_slot(self, item_name, item_type, item_slot, state)
                return
            if ask == '8':
                Equipment.optimize_loadout_menu(self, state)
                return
            if ask == '9':
                Equipment.preset_menu(self, state)
                return
            if ask == '0':
                return

    def equipment_change_item_in_slot(self, item_name: str, item_type: str,
                                       item_slot: str, state: GameState) -> None:
        slot_attr = _SLOT_ATTR[item_slot]
        cnt = 0
        list_cnt = []

        current_in_slot = getattr(state.equipment, slot_attr)
        if current_in_slot is None:
            print(f'\n{item_name.title()} - ничего не надето.')
        else:
            print(f'\nНа {item_name} у персонажа надето: '
                  f'\n- {current_in_slot["item_name"][0].title()} {current_in_slot["grade"][0].title()}: + {current_in_slot["bonus"][0]} {current_in_slot["characteristic"][0].title()} (Quality: {current_in_slot["quality"][0]:,.2f})')

        print(f'\nВ инвентаре имеются предметы, которые можно экипировать: ')

        state.inventory = sorted(
            state.inventory,
            key=lambda x: (x['item_type'], x['characteristic'], x['bonus']),
            reverse=True,
        )

        for i in state.inventory:
            cnt += 1
            if i["item_type"][0] == item_type:
                print(f'{cnt}. {i["item_name"][0].title()} {i["grade"][0]}: + {i["bonus"][0]} {i["characteristic"][0].title()} (Quality: {i["quality"][0]:,.2f})')
                list_cnt.append(cnt)

        print('\n0. Назад'
              '\n99. Снять предмет экипировки')

        Equipment.change_item_in_slot(self, item_name, item_type, item_slot, list_cnt, state)

    def change_item_in_slot(self, item_name: str, item_type: str, item_slot: str,
                             list_cnt: list[int], state: GameState) -> None:
        slot_attr = _SLOT_ATTR[item_slot]
        # Цикл retry на ValueError / невалидном индексе (1.5.2 — 0.2.1h).
        while True:
            try:
                index = int(input('\n>>> '))
            except ValueError:
                print('\nПроизошла ошибка при выборе экипировки. Введите число.')
                Equipment.equipment_change_item_in_slot(self, item_name, item_type, item_slot, state)
                return

            if index in list_cnt:
                chosen = state.inventory[index - 1]
                print(f'\nВы выбрали предмет:'
                      f'\n- {chosen["item_name"][0].title()} {chosen["grade"][0].title()}: + {chosen["bonus"][0]} {chosen["characteristic"][0].title()} (Quality: {chosen["quality"][0]:,.2f}).')
                ask = input('\nНадеть элемент экипировки на персонажа: \n1. Да\n0. Назад \n>>> ')
                if ask == '1':
                    new_item, prev_item = _equip_from_inventory(state, slot_attr, index - 1)
                    print('\nВы надели предмет на персонажа: ')
                    print(f'- {new_item["item_name"][0].title()} {new_item["grade"][0].title()}: + {new_item["bonus"][0]} {new_item["characteristic"][0].title()} (Quality: {new_item["quality"][0]:,.2f})')
                    if prev_item is not None:
                        print('\nВы заменили один предмет экипировки на другой.')
                    Equipment.equipment_view(self=None, state=state)
                    return
                Equipment.equipment_change_item_in_slot(self, item_name, item_type, item_slot, state)
                return

            if index == 0:
                Equipment.equipment_view(self=None, state=state)
                return
            if index == 99:
                # 4.50 — пред-проверка inventory_full чтобы UI показал корректное
                # сообщение (без unequip — `_unequip` ловит full и возвращает None).
                if inventory_full(state):
                    print(f'\nРюкзак полон ({len(state.inventory)}/{backpack_capacity(state)}). '
                          f'Сначала продай предмет — снять экипировку некуда.')
                    return
                removed = _unequip(state, slot_attr)
                if removed is not None:
                    print(f'\nВы сняли предмет экипировки: '
                          f'\n- {removed["item_name"][0].title()} {removed["grade"][0].title()}: + {removed["bonus"][0]} {removed["characteristic"][0].title()} (Quality: {removed["quality"][0]})')
                return
            print('\nПопробуйте еще раз ввести число: ')

    def inventory_view(self, state: GameState) -> None:
        cap = backpack_capacity(state)
        print(f'\nВ инвентаре находится {len(state.inventory)}/{cap} предметов: ')
        inventory_view(state)

    # ----- 4.63.1 Auto-Optimizer (CLI menu) -----

    # Human-friendly labels для 4 optimizable characteristics. Порядок здесь
    # = порядок отображения в menu (1-4).
    _OPT_CHAR_DISPLAY: tuple[tuple[str, str, str], ...] = (
        ('stamina',     '🏃', 'Stamina'),
        ('energy_max',  '🔋', 'Energy Max'),
        ('speed_skill', '⚡', 'Speed'),
        ('luck',        '🍀', 'Luck'),
    )

    # Slot labels для отображения diff'а — match'ат equipment_view.
    _SLOT_LABELS: dict[str, str] = {
        'head':       'Голова           ',
        'neck':       'Шея              ',
        'torso':      'Торс             ',
        'finger_01':  'Палец лев. руки  ',
        'finger_02':  'Палец прав. руки ',
        'legs':       'Ноги             ',
        'foots':      'Ступни           ',
        'back':       'Спина (рюкзак)   ',
    }

    def optimize_loadout_menu(self, state: GameState) -> None:
        """4.63.1 — UI handler для Auto-Optimizer.

        Flow: выбор characteristic (1-4) → preview diff → confirm `yes` →
        apply. Persist НЕ делается (следует существующему equipment pattern:
        wear/unwear тоже не зовут save_characteristic — игрок жмёт `s`).
        """
        from loadout import (
            apply_loadout,
            find_optimal_loadout,
            preview_loadout_diff,
            total_bonus,
        )

        print('\n--- 🎯 Auto-Optimizer экипировки ---')
        print('Под какую characteristic оптимизировать?')
        for i, (_char, icon, label) in enumerate(Equipment._OPT_CHAR_DISPLAY, start=1):
            print(f'{i}. {icon} {label}')
        print('0. Назад')

        while True:
            ask = input('>>> ').strip()
            if ask == '0':
                return
            if ask in {'1', '2', '3', '4'}:
                char, icon, label = Equipment._OPT_CHAR_DISPLAY[int(ask) - 1]
                Equipment._optimize_for_characteristic(state, char, icon, label)
                return
            print('Неверный выбор. Введи 1-4 или 0.')

    @staticmethod
    def _optimize_for_characteristic(state: GameState, characteristic: str,
                                      icon: str, label: str) -> None:
        """Compute optimal, show diff, confirm, apply."""
        from history import log_event
        from loadout import (
            apply_loadout,
            find_optimal_loadout,
            preview_loadout_diff,
            total_bonus,
        )

        bonus_before = total_bonus(state, characteristic)
        target = find_optimal_loadout(state, characteristic)
        diff = preview_loadout_diff(state, target)

        if not diff:
            print(f'\n✅ Текущий loadout уже оптимален для {icon} {label} '
                  f'(+{bonus_before}). Изменения не нужны.')
            return

        # Preview: показать какие слоты меняются.
        print(f'\nОптимизация под {icon} {label}:')
        for slot, old_item, new_item in diff:
            slot_label = Equipment._SLOT_LABELS.get(slot, slot)
            old_str = Equipment._format_item_short(old_item, characteristic)
            new_str = Equipment._format_item_short(new_item, characteristic)
            print(f'  {slot_label} : {old_str}  →  {new_str}')

        # Compute bonus_after (рассчитываем «как было бы после apply»).
        bonus_after = sum(
            (new_item.get('bonus', [0])[0] if new_item is not None
             and (new_item.get('characteristic') or [None])[0] == characteristic
             else 0)
            for slot, _old, new_item in diff
        )
        # Добавить bonus из неизменившихся слотов (где new == old).
        for slot in Equipment._SLOT_LABELS:
            cur = getattr(state.equipment, slot)
            if any(s == slot for s, _, _ in diff):
                continue  # уже учтён в bonus_after
            if cur is not None and (cur.get('characteristic') or [None])[0] == characteristic:
                bonus_after += cur.get('bonus', [0])[0]

        print(f'\nИтого: {icon} {label} был +{bonus_before}, станет +{bonus_after} '
              f'(дельта: {bonus_after - bonus_before:+d}).')

        confirm = input('\nПрименить? (yes/no): ').strip().lower()
        if confirm not in ('yes', 'y', 'да', 'д'):
            print('Отменено. Loadout не изменён.')
            return

        success, warnings = apply_loadout(state, target)
        if not success:
            print('\n❌ Не удалось применить:')
            for w in warnings:
                print(f'  - {w}')
            return

        print(f'\n✅ Loadout применён. {icon} {label}: +{total_bonus(state, characteristic)}.')
        for w in warnings:
            print(f'⚠ {w}')

        log_event('loadout_optimized',
                  characteristic=characteristic,
                  slots_changed=len(diff),
                  bonus_before=bonus_before,
                  bonus_after=total_bonus(state, characteristic),
                  warnings_count=len(warnings))

    @staticmethod
    def _format_item_short(item: Optional[dict], characteristic: str) -> str:
        """Однострочное описание item для diff'а: 'helmet a (+8)' или '(пусто)'."""
        if item is None:
            return '(пусто)'
        item_type = (item.get('item_type') or ['?'])[0]
        grade = (item.get('grade') or ['?'])[0]
        # Bonus для искомой characteristic; если item не имеет её — bonus=0
        # (но он попал в target — значит имеет).
        chars = item.get('characteristic') or []
        bonuses = item.get('bonus') or []
        bonus_val = 0
        try:
            idx = chars.index(characteristic)
            bonus_val = bonuses[idx]
        except (ValueError, IndexError):
            pass
        return f'{item_type} {grade} (+{bonus_val})'

    # ----- 4.63.2 Equipment Presets (CLI menu) -----

    def preset_menu(self, state: GameState) -> None:
        """4.63.2 — UI handler для управления preset'ами.

        Submenu: list + 4 действия (save / load / delete / back). Save
        требует имя; overwrite уже существующего preset'а — с confirm.
        Load показывает diff + confirm перед apply. Delete тоже с confirm.
        """
        from loadout import (
            apply_loadout,
            delete_preset,
            list_presets,
            preview_loadout_diff,
            resolve_preset_to_loadout,
            save_preset,
        )

        while True:
            presets = list_presets(state)
            print('\n--- 💼 Equipment Presets ---')
            if not presets:
                print('Пока нет сохранённых preset\'ов.')
            else:
                print(f'Сохранённых preset\'ов: {len(presets)}')
                for i, (name, snapshot) in enumerate(presets, start=1):
                    summary = Equipment._format_preset_summary(snapshot)
                    print(f'  {i}. "{name}" — {summary}')

            print('\ns. 💾 Сохранить текущую экипировку как preset')
            print('l. 📥 Загрузить preset')
            print('d. 🗑  Удалить preset')
            print('0. Назад')

            ask = input('>>> ').strip().lower()
            if ask == '0':
                return
            if ask == 's':
                Equipment._do_save_preset(state)
                continue
            if ask == 'l':
                Equipment._do_load_preset(state)
                continue
            if ask == 'd':
                Equipment._do_delete_preset(state)
                continue
            print('Неверный выбор. Введи s / l / d / 0.')

    @staticmethod
    def _format_preset_summary(snapshot: dict[str, Optional[dict]]) -> str:
        """Однострочное summary preset'а: «5 слотов: 🏃+15 🔋+22 ⚡+5 🍀+3»."""
        filled = sum(1 for v in snapshot.values() if v is not None)
        # Суммы по 4 базовым characteristic.
        totals = {'stamina': 0, 'energy_max': 0, 'speed_skill': 0, 'luck': 0}
        for item in snapshot.values():
            if item is None:
                continue
            chars = item.get('characteristic') or []
            bonuses = item.get('bonus') or []
            for char, bonus in zip(chars, bonuses):
                if char in totals:
                    totals[char] += int(bonus)
        icons = {'stamina': '🏃', 'energy_max': '🔋',
                 'speed_skill': '⚡', 'luck': '🍀'}
        bonus_parts = [f'{icons[c]}+{v}' for c, v in totals.items() if v > 0]
        bonus_str = ' '.join(bonus_parts) if bonus_parts else '(без бонусов)'
        return f'{filled} слотов: {bonus_str}'

    @staticmethod
    def _do_save_preset(state: GameState) -> None:
        """Save current equipment as named preset. Overwrite с confirm."""
        from history import log_event
        from loadout import save_preset

        name = input('\nВведи имя preset\'а (или пусто для отмены): ').strip()
        if not name:
            print('Отменено.')
            return
        if name in state.equipment_presets:
            confirm = input(f'Preset "{name}" уже существует. Перезаписать? (yes/no): ').strip().lower()
            if confirm not in ('yes', 'y', 'да', 'д'):
                print('Отменено. Существующий preset не изменён.')
                return
        success, message = save_preset(state, name)
        print(message)
        if success:
            log_event('preset_saved',
                      name=name,
                      slots_filled=sum(1 for v in state.equipment_presets[name].values()
                                        if v is not None))

    @staticmethod
    def _do_load_preset(state: GameState) -> None:
        """Load preset → preview diff → confirm → apply."""
        from history import log_event
        from loadout import (
            apply_loadout,
            preview_loadout_diff,
            resolve_preset_to_loadout,
        )

        if not state.equipment_presets:
            print('Нет сохранённых preset\'ов.')
            return
        name = input('Введи имя preset\'а для загрузки (или пусто для отмены): ').strip()
        if not name:
            print('Отменено.')
            return

        target, resolve_warnings = resolve_preset_to_loadout(state, name)
        if target is None:
            # Preset не найден — resolve_warnings содержит сообщение.
            for w in resolve_warnings:
                print(w)
            return

        # Show resolve warnings (lost items) сразу — игрок должен знать что
        # часть preset'а недоступна ДО confirm.
        for w in resolve_warnings:
            print(f'⚠ {w}')

        diff = preview_loadout_diff(state, target)
        if not diff:
            print(f'\n✅ Текущая экипировка уже соответствует preset "{name}". Изменения не нужны.')
            return

        print(f'\nИзменения при загрузке preset "{name}":')
        for slot, old_item, new_item in diff:
            slot_label = Equipment._SLOT_LABELS.get(slot, slot)
            old_str = Equipment._format_item_for_preset_diff(old_item)
            new_str = Equipment._format_item_for_preset_diff(new_item)
            print(f'  {slot_label} : {old_str}  →  {new_str}')

        confirm = input('\nПрименить preset? (yes/no): ').strip().lower()
        if confirm not in ('yes', 'y', 'да', 'д'):
            print('Отменено. Loadout не изменён.')
            return

        success, apply_warnings = apply_loadout(state, target)
        if not success:
            print('\n❌ Не удалось применить:')
            for w in apply_warnings:
                print(f'  - {w}')
            return

        print(f'\n✅ Preset "{name}" применён. Изменено слотов: {len(diff)}.')
        for w in apply_warnings:
            print(f'⚠ {w}')

        log_event('preset_applied',
                  name=name,
                  slots_changed=len(diff),
                  lost_items_count=len(resolve_warnings),
                  apply_warnings_count=len(apply_warnings))

    @staticmethod
    def _do_delete_preset(state: GameState) -> None:
        """Delete preset by name с confirm."""
        from history import log_event
        from loadout import delete_preset

        if not state.equipment_presets:
            print('Нет сохранённых preset\'ов.')
            return
        name = input('Введи имя preset\'а для удаления (или пусто для отмены): ').strip()
        if not name:
            print('Отменено.')
            return
        if name not in state.equipment_presets:
            print(f'Preset "{name}" не найден.')
            return
        confirm = input(f'Удалить preset "{name}"? (yes/no): ').strip().lower()
        if confirm not in ('yes', 'y', 'да', 'д'):
            print('Отменено.')
            return
        success, message = delete_preset(state, name)
        print(message)
        if success:
            log_event('preset_deleted', name=name)

    @staticmethod
    def _format_item_for_preset_diff(item: Optional[dict]) -> str:
        """Описание item для diff'а в preset load: 'helmet a (+8 stamina)' или '(пусто)'."""
        if item is None:
            return '(пусто)'
        item_type = (item.get('item_type') or ['?'])[0]
        grade = (item.get('grade') or ['?'])[0]
        char = (item.get('characteristic') or ['?'])[0]
        bonus = (item.get('bonus') or [0])[0]
        return f'{item_type} {grade} (+{bonus} {char})'
