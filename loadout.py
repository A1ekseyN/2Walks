"""Equipment Auto-Optimizer (task 4.63.1).

Pure helpers — без UI и без зависимостей от Sheets. Решает chicken-and-egg
прогрессию (Stamina lvl 19+ требует 95 эн при energy_max=65 — без переодевания
в +energy_max equipment физически невозможно).

API:
- `find_optimal_loadout(state, characteristic)` — для каждого слота выбирает
  лучший item из пула (equipment + inventory) по указанной characteristic.
- `preview_loadout_diff(state, target)` — список изменений old → new.
- `apply_loadout(state, target)` — атомарно (unwear changed → wear target).

Ring-слоты (finger_01 / finger_02) — особый кейс: один item_type 'ring'
заполняет два слота. Top-2 rings из пула идут в finger_01 (best) и finger_02
(second). Если ring всего один — finger_02 остаётся пустым.

Slot 'legs' существует в Equipment dataclass, но ни один item_type его не
заполняет (legacy / reserved). Optimizer всегда возвращает None для legs.
"""

from typing import Optional

from bonus import backpack_capacity
from equipment import _SLOT_ATTR, _equip_from_inventory, _unequip
from state import GameState


# 4 character'а на equipment items (см. equipment_bonus.equipment_bonus и
# drop.Drop_Item._random_characteristic). Asymmetria с Gym skill'ами:
# `luck` на equipment vs `luck_skill` в state.gym — это legacy naming.
OPTIMIZABLE_CHARACTERISTICS: tuple[str, ...] = (
    'stamina', 'energy_max', 'speed_skill', 'luck',
)

# Маппинг item_type → list of slot_attr (одиночные слоты + ring → 2 пальца).
_ITEM_TYPE_TO_SLOTS: dict[str, list[str]] = {
    'helmet':   ['head'],
    'necklace': ['neck'],
    't-shirt':  ['torso'],
    'ring':     ['finger_01', 'finger_02'],
    'shoes':    ['foots'],
}

# Reverse mapping: slot_attr → item_type. Используется для определения какой
# item_type фитится в слот при apply.
_SLOT_TO_ITEM_TYPE: dict[str, str] = {
    slot: item_type
    for item_type, slots in _ITEM_TYPE_TO_SLOTS.items()
    for slot in slots
}

_RING_SLOTS: tuple[str, ...] = ('finger_01', 'finger_02')


def _bonus_for(item: dict, characteristic: str) -> int:
    """Вытащить bonus value для конкретной characteristic из item-dict'а.

    Future-proof для multi-characteristic items: индексирует bonus[] по
    позиции characteristic[] (если match найден). Возвращает 0 если
    item не имеет этой characteristic.
    """
    chars = item.get('characteristic') or []
    bonuses = item.get('bonus') or []
    try:
        idx = chars.index(characteristic)
        return int(bonuses[idx])
    except (ValueError, IndexError):
        return 0


def _collect_pool(state: GameState) -> list[dict]:
    """Список всех equippable items: currently equipped + inventory.

    Включает только не-None слоты. Inventory копируется по ссылке — items
    остаются shared references (важно для identity-based замены в apply).
    """
    pool: list[dict] = []
    for slot in _SLOT_TO_ITEM_TYPE:
        item = getattr(state.equipment, slot)
        if item is not None:
            pool.append(item)
    pool.extend(state.inventory)
    return pool


def find_optimal_loadout(state: GameState, characteristic: str) -> dict[str, Optional[dict]]:
    """Для каждого слота выбрать item с max bonus по characteristic.

    Returns: dict slot_attr → item (или **current equipped item** если в пуле
    нет items этого slot_type с искомой characteristic — keep-current
    semantics чтобы случайно не снять stamina-helmet при optimize'е под
    energy_max). Включает все 7 слотов Equipment.

    Ring-слоты: top-2 ring'а с искомой characteristic из пула. finger_01 =
    best, finger_02 = second. Если matching ring всего один — finger_01 =
    он, finger_02 = current item (keep). Если matching rings нет — оба
    finger остаются current. Если top-2 X-rings заменяют current non-X
    rings — это intentional aggressive trade-off (игрок видит в preview
    diff и подтверждает yes/no).

    Raises:
        ValueError: если characteristic не в OPTIMIZABLE_CHARACTERISTICS.
    """
    if characteristic not in OPTIMIZABLE_CHARACTERISTICS:
        raise ValueError(
            f'Unsupported characteristic: {characteristic!r}. '
            f'Expected one of: {OPTIMIZABLE_CHARACTERISTICS}'
        )

    pool = _collect_pool(state)
    matching = [item for item in pool if _bonus_for(item, characteristic) > 0]

    # Все 7 слотов — default None (заполним ниже либо matching, либо current).
    result: dict[str, Optional[dict]] = {
        slot: None for slot in ('head', 'neck', 'torso', 'finger_01',
                                 'finger_02', 'legs', 'foots')
    }

    # Non-ring slots: max by bonus для каждого item_type.
    for slot, item_type in _SLOT_TO_ITEM_TYPE.items():
        if item_type == 'ring':
            continue
        candidates = [i for i in matching if (i.get('item_type') or [None])[0] == item_type]
        if candidates:
            result[slot] = max(candidates, key=lambda i: _bonus_for(i, characteristic))

    # Ring slots: top-2 rings → finger_01 (best), finger_02 (second).
    rings = sorted(
        [i for i in matching if (i.get('item_type') or [None])[0] == 'ring'],
        key=lambda i: _bonus_for(i, characteristic),
        reverse=True,
    )
    if rings:
        result['finger_01'] = rings[0]
    if len(rings) >= 2:
        result['finger_02'] = rings[1]

    # Keep-current post-process: слоты где optimizer не нашёл matching item'а —
    # оставляем current equipped (чтобы случайно не unwear'нуть stamina-helmet
    # при optimize'е под energy_max когда energy_max-helmet'ов нет).
    for slot in result:
        if result[slot] is None:
            current = getattr(state.equipment, slot)
            if current is not None:
                result[slot] = current

    return result


def preview_loadout_diff(
    state: GameState,
    target: dict[str, Optional[dict]],
) -> list[tuple[str, Optional[dict], Optional[dict]]]:
    """Diff текущей экипировки и target — для confirmation prompt.

    Returns: list of (slot_attr, old_item, new_item) только для слотов
    где меняется item (identity comparison `is`). Слоты без изменений
    (включая no-op «same item уже в слоте») в результат не попадают.
    """
    diff: list[tuple[str, Optional[dict], Optional[dict]]] = []
    for slot, new_item in target.items():
        old_item = getattr(state.equipment, slot)
        if old_item is new_item:
            continue
        diff.append((slot, old_item, new_item))
    return diff


def total_bonus(state: GameState, characteristic: str) -> int:
    """Сумма bonus по characteristic от всей текущей экипировки.

    Используется для display'а «было X → станет Y» в preview/после apply.
    """
    total = 0
    for slot in _SLOT_TO_ITEM_TYPE:
        item = getattr(state.equipment, slot)
        if item is not None:
            total += _bonus_for(item, characteristic)
    return total


# ---------------------------------------------------------------------------
# 4.63.2 — Equipment Presets (именованные loadout'ы)
# ---------------------------------------------------------------------------

def _snapshot_current_equipment(state: GameState) -> dict[str, Optional[dict]]:
    """Deep-copy текущих equipment слотов для сохранения в preset.

    Items хранятся как dict-копии (не reference) — preset переживает
    последующую продажу original item'а в инвентаре. На apply matching
    выполняется по полям, не по identity (см. `_match_preset_item`).
    """
    import copy
    snapshot: dict[str, Optional[dict]] = {}
    for slot in ('head', 'neck', 'torso', 'finger_01', 'finger_02', 'legs', 'foots'):
        item = getattr(state.equipment, slot)
        snapshot[slot] = copy.deepcopy(item) if item is not None else None
    return snapshot


def _match_preset_item(state: GameState, snapshot_item: dict) -> Optional[dict]:
    """Найти в текущем pool (equipment + inventory) item, который matches
    snapshot из preset'а.

    Identity-критерии (все должны совпасть): item_name, item_type, grade,
    characteristic[0], bonus[0]. Quality и price — НЕ учитываются (могут
    меняться от Repair / wear).

    Returns: matching item (current reference) или None если не найден
    (lost item — продан / crafted / etc.).
    """
    def _key(item: dict) -> tuple:
        name = (item.get('item_name') or [None])[0]
        itype = (item.get('item_type') or [None])[0]
        grade = (item.get('grade') or [None])[0]
        char = (item.get('characteristic') or [None])[0]
        bonus = (item.get('bonus') or [None])[0]
        return (name, itype, grade, char, bonus)

    target_key = _key(snapshot_item)
    for current in _collect_pool(state):
        if _key(current) == target_key:
            return current
    return None


def save_preset(state: GameState, name: str) -> tuple[bool, str]:
    """Сохранить текущую экипировку как preset с заданным именем.

    Перезаписывает существующий preset с тем же именем (caller-side
    должен решить про confirmation prompt).

    Returns: (success, message). Success=False — невалидное имя.
    """
    name = name.strip()
    if not name:
        return False, 'Имя preset не может быть пустым.'
    snapshot = _snapshot_current_equipment(state)
    state.equipment_presets[name] = snapshot
    return True, f'Preset "{name}" сохранён ({sum(1 for v in snapshot.values() if v is not None)} слотов).'


def delete_preset(state: GameState, name: str) -> tuple[bool, str]:
    """Удалить preset по имени.

    Returns: (success, message). Success=False — preset не найден.
    """
    if name not in state.equipment_presets:
        return False, f'Preset "{name}" не найден.'
    del state.equipment_presets[name]
    return True, f'Preset "{name}" удалён.'


def list_presets(state: GameState) -> list[tuple[str, dict[str, Optional[dict]]]]:
    """Список всех preset'ов как (name, snapshot) — отсортирован по name.

    UI слой решает как отображать (имя + summary bonuses + slot count и т.д.).
    """
    return sorted(state.equipment_presets.items(), key=lambda kv: kv[0].lower())


def resolve_preset_to_loadout(
    state: GameState, name: str,
) -> tuple[Optional[dict[str, Optional[dict]]], list[str]]:
    """Конвертировать preset (snapshot items) → target dict для apply_loadout
    (refs на текущие items в equipment+inventory).

    Каждый slot в preset'е резолвится через `_match_preset_item`:
    - found → target[slot] = current matching item (готов к apply_loadout)
    - not found → warning «slot: lost item», target[slot] = current equipped
      (keep-current semantics — не снимать на отсутствие preset item'а).
    - preset_item is None → target[slot] = None (preset явно указал «слот пуст»).

    Returns: (target | None, warnings). None target если preset не существует.
    """
    if name not in state.equipment_presets:
        return None, [f'Preset "{name}" не найден.']
    preset = state.equipment_presets[name]
    target: dict[str, Optional[dict]] = {}
    warnings: list[str] = []
    for slot, snapshot_item in preset.items():
        if snapshot_item is None:
            target[slot] = None
            continue
        matched = _match_preset_item(state, snapshot_item)
        if matched is None:
            item_desc = f'{(snapshot_item.get("item_type") or ["?"])[0]} ' \
                        f'{(snapshot_item.get("grade") or ["?"])[0]} ' \
                        f'(+{(snapshot_item.get("bonus") or [0])[0]} ' \
                        f'{(snapshot_item.get("characteristic") or ["?"])[0]})'
            warnings.append(
                f'Слот {slot}: предмет из preset не найден '
                f'({item_desc}) — оставляю current.'
            )
            target[slot] = getattr(state.equipment, slot)
        else:
            target[slot] = matched
    return target, warnings


def apply_loadout(
    state: GameState,
    target: dict[str, Optional[dict]],
) -> tuple[bool, list[str]]:
    """Атомарно применить target loadout. Two-phase: unwear changed → wear target.

    Capacity check ПЕРЕД началом: на промежуточной фазе все unwear'нутые
    items временно в инвентаре. Если peak_size > backpack_capacity → reject
    без мутаций (returns False + warning).

    Lost item handling (4.63 design Q3 — skip + warning): если target_item
    указан, но к моменту wear не найден в state.inventory (продали /
    crafted / etc.) — слот остаётся пустым, добавляется warning. Apply
    продолжается для остальных слотов.

    Returns: (success, warnings).
    - success=False — ничего не мутировано (capacity check fail или no-op).
    - success=True — мутации применены, warnings перечисляет пропущенные слоты.

    log_event('loadout_applied', ...) — НЕ вызывается здесь (вызывается из
    UI handler'а с дополнительным контекстом characteristic + slots_changed).
    """
    diff = preview_loadout_diff(state, target)
    if not diff:
        return False, ['Текущая экипировка уже оптимальна — изменения не нужны.']

    # Capacity check: peak inventory size = current + (items_to_unequip).
    # items_to_unequip = changes где есть currently_equipped item.
    items_to_unequip = sum(1 for _, old, _ in diff if old is not None)
    peak_inventory_size = len(state.inventory) + items_to_unequip
    cap = backpack_capacity(state)
    if peak_inventory_size > cap:
        return False, [
            f'Невозможно применить: при переодевании инвентарь временно '
            f'переполнится ({peak_inventory_size}/{cap}). Освободи место.'
        ]

    warnings: list[str] = []

    # Phase 1: unwear все changed слоты (текущие items уйдут в inventory).
    for slot, old_item, _new_item in diff:
        if old_item is not None:
            _unequip(state, slot)
            # _unequip может вернуть None если inventory_full на момент вызова,
            # но мы уже проверили peak_size — этот случай исключён.

    # Phase 2: wear target items (находим в inventory по identity).
    for slot, _old_item, new_item in diff:
        if new_item is None:
            continue  # слот оставляем пустым (target явно говорит None)
        # Find target_item in inventory by identity (`is`).
        idx: Optional[int] = None
        for i, inv_item in enumerate(state.inventory):
            if inv_item is new_item:
                idx = i
                break
        if idx is None:
            # Lost item: target_item не найден в inventory к моменту wear.
            # Может быть если apply вызвали с target из старого preset'а.
            warnings.append(
                f'Слот {slot}: предмет из target не найден в инвентаре '
                f'(возможно, продан или утерян).'
            )
            continue
        _equip_from_inventory(state, slot, idx)

    return True, warnings
