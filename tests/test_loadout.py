"""Тесты loadout.py — Equipment Auto-Optimizer (4.63.1).

Покрытие:
- `_bonus_for` — single/multi char, missing, empty.
- `find_optimal_loadout` — пустой пул, single slot, multi slot, rings best-2,
  no candidates для одного слота, не-optimizable characteristic.
- `preview_loadout_diff` — identity (no-op), all change, partial change.
- `total_bonus` — empty equipment, sum across slots, missing characteristic.
- `apply_loadout` — simple swap, ring relocation, capacity check fail,
  lost item, atomic on success, no-op detection.
"""

import pytest

from loadout import (
    OPTIMIZABLE_CHARACTERISTICS,
    _bonus_for,
    _collect_pool,
    apply_loadout,
    find_optimal_loadout,
    preview_loadout_diff,
    total_bonus,
)
from state import GameState


# ---------------------------------------------------------------------------
# Helpers — копируют pattern из test_equipment.py / test_inventory.py.
# ---------------------------------------------------------------------------

def _make_item(item_name='item', item_type='helmet', grade='c-grade',
               characteristic='stamina', bonus=5, quality=80.0, price=50):
    """Конструктор item-dict в legacy list-обёрточном формате."""
    return {
        'item_name': [item_name],
        'item_type': [item_type],
        'grade': [grade],
        'characteristic': [characteristic],
        'bonus': [bonus],
        'quality': [quality],
        'price': [price],
    }


def _state_with_items(equipment: dict[str, dict] | None = None,
                       inventory: list[dict] | None = None) -> GameState:
    """GameState с заданными слотами equipment + inventory."""
    s = GameState.default_new_game()
    if equipment:
        for slot, item in equipment.items():
            setattr(s.equipment, slot, item)
    if inventory:
        s.inventory = list(inventory)
    return s


# ---------------------------------------------------------------------------
# _bonus_for
# ---------------------------------------------------------------------------

def test_bonus_for_single_characteristic_match():
    item = _make_item(characteristic='energy_max', bonus=10)
    assert _bonus_for(item, 'energy_max') == 10


def test_bonus_for_characteristic_mismatch_returns_zero():
    item = _make_item(characteristic='stamina', bonus=10)
    assert _bonus_for(item, 'energy_max') == 0


def test_bonus_for_multi_characteristic_picks_correct_index():
    """Future-proof: multi-char item. characteristic[1] → bonus[1]."""
    item = {
        'item_name': ['ring'], 'item_type': ['ring'], 'grade': ['s-grade'],
        'characteristic': ['stamina', 'energy_max'],
        'bonus': [3, 7],
        'quality': [100.0], 'price': [200],
    }
    assert _bonus_for(item, 'stamina') == 3
    assert _bonus_for(item, 'energy_max') == 7
    assert _bonus_for(item, 'luck') == 0


def test_bonus_for_empty_characteristic_list_returns_zero():
    item = {'characteristic': [], 'bonus': []}
    assert _bonus_for(item, 'stamina') == 0


def test_bonus_for_missing_keys_returns_zero():
    """Robustness — item-dict без characteristic/bonus полей."""
    assert _bonus_for({}, 'stamina') == 0


# ---------------------------------------------------------------------------
# _collect_pool
# ---------------------------------------------------------------------------

def test_collect_pool_combines_equipment_and_inventory():
    item_a = _make_item(item_name='a')
    item_b = _make_item(item_name='b', item_type='ring')
    item_c = _make_item(item_name='c', item_type='shoes')
    s = _state_with_items(
        equipment={'head': item_a, 'finger_01': item_b},
        inventory=[item_c],
    )
    pool = _collect_pool(s)
    assert item_a in pool and item_b in pool and item_c in pool
    assert len(pool) == 3


def test_collect_pool_skips_empty_slots():
    item = _make_item()
    s = _state_with_items(equipment={'head': item})
    pool = _collect_pool(s)
    assert pool == [item]  # все остальные слоты None — игнорируются


# ---------------------------------------------------------------------------
# find_optimal_loadout
# ---------------------------------------------------------------------------

def test_find_optimal_loadout_picks_max_bonus_per_slot():
    """Если в инвентаре есть item лучше чем equipped — optimizer его выбирает."""
    weak_helmet = _make_item(item_name='weak', item_type='helmet',
                              characteristic='stamina', bonus=3)
    strong_helmet = _make_item(item_name='strong', item_type='helmet',
                                characteristic='stamina', bonus=8)
    s = _state_with_items(equipment={'head': weak_helmet},
                          inventory=[strong_helmet])
    result = find_optimal_loadout(s, 'stamina')
    assert result['head'] is strong_helmet


def test_find_optimal_loadout_rings_top_two_assigned_to_two_slots():
    """3 rings в пуле — top-2 идут в finger_01, finger_02. Третий не используется."""
    r1 = _make_item(item_name='r1', item_type='ring',
                    characteristic='luck', bonus=5)
    r2 = _make_item(item_name='r2', item_type='ring',
                    characteristic='luck', bonus=8)
    r3 = _make_item(item_name='r3', item_type='ring',
                    characteristic='luck', bonus=3)
    s = _state_with_items(inventory=[r1, r2, r3])
    result = find_optimal_loadout(s, 'luck')
    assert result['finger_01'] is r2  # best
    assert result['finger_02'] is r1  # second


def test_find_optimal_loadout_single_ring_only_finger_01():
    r1 = _make_item(item_type='ring', characteristic='luck', bonus=5)
    s = _state_with_items(inventory=[r1])
    result = find_optimal_loadout(s, 'luck')
    assert result['finger_01'] is r1
    assert result['finger_02'] is None


def test_find_optimal_loadout_no_candidates_keeps_current_items():
    """В пуле нет items с искомой characteristic — current equipped keep'аются.

    Защищает от случайного снятия stamina-helmet при optimize'е под energy_max
    когда energy_max-helmet'ов в пуле нет. Без keep-current semantics
    optimizer был бы destructive (target[slot]=None → apply unwear).
    """
    item = _make_item(characteristic='stamina', bonus=5)
    s = _state_with_items(equipment={'head': item})
    result = find_optimal_loadout(s, 'luck')  # ищем luck, его нет
    assert result['head'] is item  # current keep — не снимается
    # Слоты без current — остаются None.
    assert result['neck'] is None
    assert result['legs'] is None


def test_find_optimal_loadout_keeps_non_matching_ring_when_only_one_matching():
    """1 X-ring в пуле + current non-X ring во втором пальце → keep non-X."""
    luck_ring = _make_item(item_name='luck', item_type='ring',
                           characteristic='luck', bonus=3)
    energy_ring = _make_item(item_name='energy', item_type='ring',
                              characteristic='energy_max', bonus=8)
    s = _state_with_items(
        equipment={'finger_02': luck_ring},  # luck ring в правом
        inventory=[energy_ring],
    )
    result = find_optimal_loadout(s, 'energy_max')
    assert result['finger_01'] is energy_ring  # best matching → finger_01
    assert result['finger_02'] is luck_ring    # keep current (не None)


def test_find_optimal_loadout_ignores_items_with_zero_bonus_for_char():
    """Item без искомой characteristic не должен попадать в кандидаты."""
    helmet_stamina = _make_item(item_type='helmet', characteristic='stamina', bonus=10)
    helmet_energy = _make_item(item_name='h2', item_type='helmet',
                                characteristic='energy_max', bonus=3)
    s = _state_with_items(inventory=[helmet_stamina, helmet_energy])
    result = find_optimal_loadout(s, 'energy_max')
    assert result['head'] is helmet_energy  # не stamina-helmet


def test_find_optimal_loadout_legs_always_none():
    """Slot 'legs' не имеет матчинг item_type — всегда None."""
    item = _make_item()
    s = _state_with_items(inventory=[item])
    result = find_optimal_loadout(s, 'stamina')
    assert result['legs'] is None
    assert 'legs' in result  # ключ присутствует


def test_find_optimal_loadout_includes_all_seven_slots():
    s = _state_with_items()
    result = find_optimal_loadout(s, 'stamina')
    assert set(result.keys()) == {'head', 'neck', 'torso', 'finger_01',
                                   'finger_02', 'legs', 'foots'}


def test_find_optimal_loadout_raises_on_unsupported_characteristic():
    s = _state_with_items()
    with pytest.raises(ValueError, match='Unsupported characteristic'):
        find_optimal_loadout(s, 'banking_interest_rate')


def test_find_optimal_loadout_supports_all_four_optimizable_chars():
    """Для всех 4 expected characteristics функция не падает."""
    s = _state_with_items()
    for char in OPTIMIZABLE_CHARACTERISTICS:
        result = find_optimal_loadout(s, char)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# preview_loadout_diff
# ---------------------------------------------------------------------------

def test_preview_loadout_diff_returns_empty_when_no_changes():
    item = _make_item()
    s = _state_with_items(equipment={'head': item})
    # Target = identical current state.
    target = {slot: getattr(s.equipment, slot) for slot in
              ('head', 'neck', 'torso', 'finger_01', 'finger_02', 'legs', 'foots')}
    assert preview_loadout_diff(s, target) == []


def test_preview_loadout_diff_lists_only_changed_slots():
    helmet_a = _make_item(item_name='a', item_type='helmet')
    helmet_b = _make_item(item_name='b', item_type='helmet')
    s = _state_with_items(equipment={'head': helmet_a})
    target = {
        'head': helmet_b, 'neck': None, 'torso': None, 'finger_01': None,
        'finger_02': None, 'legs': None, 'foots': None,
    }
    diff = preview_loadout_diff(s, target)
    assert diff == [('head', helmet_a, helmet_b)]


def test_preview_loadout_diff_uses_identity_not_equality():
    """Items с одинаковыми полями но разные объекты считаются разными."""
    item_a = _make_item()
    item_b = _make_item()  # same fields, different object
    s = _state_with_items(equipment={'head': item_a})
    target = {slot: None for slot in ('head', 'neck', 'torso', 'finger_01',
                                       'finger_02', 'legs', 'foots')}
    target['head'] = item_b
    diff = preview_loadout_diff(s, target)
    assert len(diff) == 1  # отличие обнаружено (даже при equal содержимом)


# ---------------------------------------------------------------------------
# total_bonus
# ---------------------------------------------------------------------------

def test_total_bonus_empty_equipment_is_zero():
    s = _state_with_items()
    assert total_bonus(s, 'stamina') == 0


def test_total_bonus_sums_matching_characteristic_across_slots():
    s = _state_with_items(equipment={
        'head': _make_item(item_type='helmet', characteristic='stamina', bonus=5),
        'torso': _make_item(item_type='t-shirt', characteristic='stamina', bonus=10),
        'foots': _make_item(item_type='shoes', characteristic='luck', bonus=7),
    })
    assert total_bonus(s, 'stamina') == 15
    assert total_bonus(s, 'luck') == 7
    assert total_bonus(s, 'energy_max') == 0


# ---------------------------------------------------------------------------
# apply_loadout
# ---------------------------------------------------------------------------

def test_apply_loadout_simple_swap_from_inventory():
    """Item из inventory заменяет equipped, equipped уходит в inventory."""
    weak = _make_item(item_name='weak', item_type='helmet',
                      characteristic='stamina', bonus=3)
    strong = _make_item(item_name='strong', item_type='helmet',
                        characteristic='stamina', bonus=8)
    s = _state_with_items(equipment={'head': weak}, inventory=[strong])

    target = find_optimal_loadout(s, 'stamina')
    success, warnings = apply_loadout(s, target)

    assert success is True
    assert warnings == []
    assert s.equipment.head is strong
    assert weak in s.inventory
    assert strong not in s.inventory


def test_apply_loadout_no_changes_returns_false():
    """Если loadout уже оптимален — no-op + информативный warning."""
    item = _make_item(characteristic='stamina', bonus=10)
    s = _state_with_items(equipment={'head': item})
    target = find_optimal_loadout(s, 'stamina')
    success, warnings = apply_loadout(s, target)
    assert success is False
    assert any('уже оптимальна' in w for w in warnings)


def test_apply_loadout_capacity_check_blocks_overflow():
    """Если unwear фаза переполнит инвентарь — reject без мутаций."""
    s = GameState.default_new_game()
    # equipment.head с item — будет unwear'нут
    equipped = _make_item(item_name='eq', item_type='helmet',
                           characteristic='stamina', bonus=3)
    s.equipment.head = equipped
    # inventory переполнен до cap (10 базовых, без backpack_skill).
    s.inventory = [_make_item(item_name=f'i{i}', characteristic='luck', bonus=1)
                   for i in range(10)]
    # Target пытается надеть НОВЫЙ helmet из inventory.
    better = _make_item(item_name='better', item_type='helmet',
                        characteristic='stamina', bonus=10)
    s.inventory.append(better)  # теперь 11, уже выше cap=10 — невалидный setup
    # Reset to valid setup: 9 inv + 1 better → 10 (at cap).
    s.inventory = s.inventory[:9] + [better]
    target = find_optimal_loadout(s, 'stamina')  # выберет better

    # Apply: unwear equipped → inventory = 11 > cap=10 → reject.
    success, warnings = apply_loadout(s, target)
    assert success is False
    assert any('переполнится' in w for w in warnings)
    # State не изменён.
    assert s.equipment.head is equipped
    assert better in s.inventory


def test_apply_loadout_ring_relocation():
    """Ring переезжает с finger_01 на finger_02 (новый best ring надевается)."""
    r_old = _make_item(item_name='old', item_type='ring',
                       characteristic='luck', bonus=5)
    r_better = _make_item(item_name='better', item_type='ring',
                          characteristic='luck', bonus=8)
    s = _state_with_items(equipment={'finger_01': r_old},
                          inventory=[r_better])

    target = find_optimal_loadout(s, 'luck')
    # best ring = r_better → finger_01, second = r_old → finger_02.
    assert target['finger_01'] is r_better
    assert target['finger_02'] is r_old

    success, warnings = apply_loadout(s, target)
    assert success is True
    assert warnings == []
    assert s.equipment.finger_01 is r_better
    assert s.equipment.finger_02 is r_old
    assert r_better not in s.inventory


def test_apply_loadout_lost_item_skips_with_warning():
    """Target ссылается на item которого нет в inventory к моменту wear → skip."""
    item = _make_item(characteristic='stamina', bonus=5)
    s = _state_with_items()  # пустой equipment + inventory

    # Конструируем target вручную (как preset с устаревшей ссылкой).
    target = {slot: None for slot in ('head', 'neck', 'torso', 'finger_01',
                                       'finger_02', 'legs', 'foots')}
    target['head'] = item  # item НЕ в state.inventory!

    success, warnings = apply_loadout(s, target)
    # success=True потому что diff не пустой (head: None → item), но item
    # не найден → warning + slot остаётся пустым.
    assert success is True
    assert len(warnings) == 1
    assert 'head' in warnings[0]
    assert 'не найден' in warnings[0]
    assert s.equipment.head is None


def test_apply_loadout_full_optimization_atomic():
    """Полная оптимизация 3 слотов из inventory — все применяются за один apply."""
    h_old = _make_item(item_name='h_old', item_type='helmet',
                       characteristic='energy_max', bonus=2)
    h_new = _make_item(item_name='h_new', item_type='helmet',
                       characteristic='energy_max', bonus=10)
    t_new = _make_item(item_name='t_new', item_type='t-shirt',
                       characteristic='energy_max', bonus=8)
    s_new = _make_item(item_name='s_new', item_type='shoes',
                       characteristic='energy_max', bonus=5)
    s = _state_with_items(equipment={'head': h_old},
                          inventory=[h_new, t_new, s_new])

    assert total_bonus(s, 'energy_max') == 2  # before

    target = find_optimal_loadout(s, 'energy_max')
    success, warnings = apply_loadout(s, target)

    assert success is True
    assert warnings == []
    assert s.equipment.head is h_new
    assert s.equipment.torso is t_new
    assert s.equipment.foots is s_new
    assert total_bonus(s, 'energy_max') == 23  # 10 + 8 + 5
    assert h_old in s.inventory  # old equipped item возвращён


# ---------------------------------------------------------------------------
# UI handler: Equipment.optimize_loadout_menu (4.63.1 — CLI integration)
# ---------------------------------------------------------------------------

from equipment import Equipment  # noqa: E402  — после pure-helper тестов


def test_optimize_menu_cancel_returns_without_changes(monkeypatch, capsys):
    """Выбор '0' в characteristic menu — exit без действий."""
    item = _make_item(characteristic='stamina', bonus=5)
    s = _state_with_items(equipment={'head': item})

    monkeypatch.setattr('builtins.input', lambda *a, **k: '0')

    Equipment.optimize_loadout_menu(None, s)

    assert s.equipment.head is item  # unchanged
    out = capsys.readouterr().out
    assert 'Auto-Optimizer' in out


def test_optimize_menu_already_optimal_reports_no_change(monkeypatch, capsys):
    """Loadout уже оптимален — no-op + сообщение."""
    item = _make_item(item_type='helmet', characteristic='energy_max', bonus=10)
    s = _state_with_items(equipment={'head': item})

    monkeypatch.setattr('builtins.input', lambda *a, **k: '2')  # 2 = energy_max

    Equipment.optimize_loadout_menu(None, s)

    out = capsys.readouterr().out
    assert 'уже оптимален' in out
    assert s.equipment.head is item  # без изменений


def test_optimize_menu_user_declines_confirmation(monkeypatch, capsys):
    """Diff показан, но игрок отвечает 'no' — apply не происходит."""
    weak = _make_item(item_name='weak', item_type='helmet',
                      characteristic='stamina', bonus=3)
    strong = _make_item(item_name='strong', item_type='helmet',
                        characteristic='stamina', bonus=8)
    s = _state_with_items(equipment={'head': weak}, inventory=[strong])

    inputs = iter(['1', 'no'])  # 1 = stamina; confirm = no
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    Equipment.optimize_loadout_menu(None, s)

    assert s.equipment.head is weak  # без изменений
    out = capsys.readouterr().out
    assert 'Отменено' in out


def test_optimize_menu_full_flow_applies_and_logs_event(monkeypatch, capsys):
    """yes confirmation → apply → log_event('loadout_optimized', ...)."""
    weak = _make_item(item_name='weak', item_type='helmet',
                      characteristic='stamina', bonus=3)
    strong = _make_item(item_name='strong', item_type='helmet',
                        characteristic='stamina', bonus=8)
    s = _state_with_items(equipment={'head': weak}, inventory=[strong])

    inputs = iter(['1', 'yes'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    events: list[tuple[str, dict]] = []
    import history
    monkeypatch.setattr(history, 'log_event',
                        lambda evt_type, **payload: events.append((evt_type, payload)))

    Equipment.optimize_loadout_menu(None, s)

    # Mutation применена.
    assert s.equipment.head is strong
    assert weak in s.inventory

    out = capsys.readouterr().out
    assert 'Loadout применён' in out
    assert '+8' in out  # новый bonus

    # log_event записан с правильным payload.
    loadout_events = [e for e in events if e[0] == 'loadout_optimized']
    assert len(loadout_events) == 1
    payload = loadout_events[0][1]
    assert payload['characteristic'] == 'stamina'
    assert payload['slots_changed'] == 1
    assert payload['bonus_before'] == 3
    assert payload['bonus_after'] == 8
    assert payload['warnings_count'] == 0


def test_optimize_menu_invalid_input_retries(monkeypatch, capsys):
    """Невалидный ввод — retry loop, не падение."""
    s = _state_with_items()

    inputs = iter(['x', '99', '0'])  # два невалида, потом cancel
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    Equipment.optimize_loadout_menu(None, s)

    out = capsys.readouterr().out
    assert out.count('Неверный выбор') == 2


# ---------------------------------------------------------------------------
# 4.63.2 — Equipment Presets (pure helpers)
# ---------------------------------------------------------------------------

from loadout import (  # noqa: E402
    _match_preset_item,
    _snapshot_current_equipment,
    delete_preset,
    list_presets,
    resolve_preset_to_loadout,
    save_preset,
)


def test_snapshot_current_equipment_copies_all_seven_slots():
    helmet = _make_item(item_type='helmet', characteristic='stamina', bonus=5)
    s = _state_with_items(equipment={'head': helmet})
    snapshot = _snapshot_current_equipment(s)
    assert set(snapshot.keys()) == {'head', 'neck', 'torso', 'finger_01',
                                     'finger_02', 'legs', 'foots'}
    # Deep copy: меняем snapshot, original не страдает.
    snapshot['head']['bonus'][0] = 999
    assert helmet['bonus'][0] == 5  # original unchanged


def test_snapshot_current_equipment_empty_state_returns_all_none():
    s = _state_with_items()
    snapshot = _snapshot_current_equipment(s)
    assert all(v is None for v in snapshot.values())


def test_save_preset_stores_snapshot():
    item = _make_item(characteristic='stamina', bonus=5)
    s = _state_with_items(equipment={'head': item})
    success, msg = save_preset(s, 'training')
    assert success is True
    assert 'сохранён' in msg
    assert 'training' in s.equipment_presets
    assert s.equipment_presets['training']['head'] is not item  # deep copy
    assert s.equipment_presets['training']['head']['bonus'] == [5]


def test_save_preset_rejects_empty_name():
    s = _state_with_items()
    success, msg = save_preset(s, '   ')  # whitespace-only
    assert success is False
    assert 'не может быть пустым' in msg
    assert s.equipment_presets == {}


def test_save_preset_overwrites_existing():
    s = _state_with_items(equipment={'head': _make_item(bonus=3)})
    save_preset(s, 'p1')
    # Меняем equipment, перезаписываем preset.
    s.equipment.head = _make_item(bonus=10)
    save_preset(s, 'p1')
    assert s.equipment_presets['p1']['head']['bonus'] == [10]


def test_save_preset_strips_name():
    s = _state_with_items()
    save_preset(s, '  training  ')
    assert 'training' in s.equipment_presets  # без пробелов


def test_delete_preset_removes_entry():
    s = _state_with_items()
    save_preset(s, 'p1')
    success, msg = delete_preset(s, 'p1')
    assert success is True
    assert 'p1' not in s.equipment_presets


def test_delete_preset_returns_false_if_not_found():
    s = _state_with_items()
    success, msg = delete_preset(s, 'missing')
    assert success is False
    assert 'не найден' in msg


def test_list_presets_returns_sorted_pairs():
    s = _state_with_items()
    save_preset(s, 'zebra')
    save_preset(s, 'alpha')
    save_preset(s, 'mango')
    result = list_presets(s)
    names = [name for name, _ in result]
    assert names == ['alpha', 'mango', 'zebra']  # sorted case-insensitive


def test_list_presets_empty_state_returns_empty_list():
    s = _state_with_items()
    assert list_presets(s) == []


def test_match_preset_item_finds_by_identity_fields():
    """Match по item_name + item_type + grade + characteristic[0] + bonus[0]."""
    item = _make_item(item_name='helm', item_type='helmet', grade='a-grade',
                      characteristic='stamina', bonus=5, quality=80.0)
    s = _state_with_items(inventory=[item])
    # Snapshot с теми же identity-fields но другим quality.
    snapshot = _make_item(item_name='helm', item_type='helmet', grade='a-grade',
                          characteristic='stamina', bonus=5, quality=40.0)
    matched = _match_preset_item(s, snapshot)
    assert matched is item  # quality differs, но identity-fields match


def test_match_preset_item_returns_none_if_not_found():
    s = _state_with_items()
    snapshot = _make_item()
    assert _match_preset_item(s, snapshot) is None


def test_match_preset_item_does_not_match_different_bonus():
    """Same name/type/grade но разный bonus — не match (это разные items по нашей логике)."""
    item = _make_item(bonus=5)
    s = _state_with_items(inventory=[item])
    snapshot = _make_item(bonus=10)
    assert _match_preset_item(s, snapshot) is None


def test_resolve_preset_to_loadout_full_match():
    """Все items preset'а найдены в pool → target собран, warnings пустые."""
    helmet = _make_item(item_name='h', item_type='helmet', bonus=8)
    shoes = _make_item(item_name='s', item_type='shoes', bonus=5)
    s = _state_with_items(equipment={'head': helmet}, inventory=[shoes])
    save_preset(s, 'p1')  # snapshot: head=helmet, foots=None, ...
    # Меняем preset вручную чтобы он указал shoes в foots.
    s.equipment_presets['p1']['foots'] = {
        'item_name': ['s'], 'item_type': ['shoes'], 'grade': ['c-grade'],
        'characteristic': ['stamina'], 'bonus': [5], 'quality': [80.0], 'price': [50],
    }
    target, warnings = resolve_preset_to_loadout(s, 'p1')
    assert target['head'] is helmet
    assert target['foots'] is shoes
    assert warnings == []


def test_resolve_preset_to_loadout_lost_item_warning_keeps_current():
    """Item из preset'а не найден в pool → warning + keep current в этом слоте."""
    current_helmet = _make_item(item_name='current', item_type='helmet', bonus=3)
    s = _state_with_items(equipment={'head': current_helmet})
    # Preset указывает ДРУГОЙ helmet (не существующий в pool).
    s.equipment_presets['p1'] = {
        'head': {'item_name': ['lost'], 'item_type': ['helmet'], 'grade': ['s-grade'],
                 'characteristic': ['stamina'], 'bonus': [99], 'quality': [100], 'price': [200]},
        'neck': None, 'torso': None, 'finger_01': None, 'finger_02': None,
        'legs': None, 'foots': None,
    }
    target, warnings = resolve_preset_to_loadout(s, 'p1')
    assert len(warnings) == 1
    assert 'lost' in warnings[0] or 'не найден' in warnings[0]
    assert target['head'] is current_helmet  # keep current, не lost
    assert target['neck'] is None  # preset явно None


def test_resolve_preset_to_loadout_unknown_preset_returns_none():
    s = _state_with_items()
    target, warnings = resolve_preset_to_loadout(s, 'missing')
    assert target is None
    assert len(warnings) == 1
    assert 'не найден' in warnings[0]


# ---------------------------------------------------------------------------
# 4.63.2 — Equipment Presets (UI handler)
# ---------------------------------------------------------------------------

def test_preset_menu_save_then_exit(monkeypatch, capsys):
    """Save preset с именем 'p1' → exit."""
    s = _state_with_items(equipment={'head': _make_item(bonus=5)})
    inputs = iter(['s', 'p1', '0'])  # save / name / exit
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    Equipment.preset_menu(None, s)

    assert 'p1' in s.equipment_presets
    out = capsys.readouterr().out
    assert 'сохранён' in out


def test_preset_menu_save_overwrite_confirm(monkeypatch, capsys):
    """Save с уже существующим именем → confirm → overwrite."""
    s = _state_with_items(equipment={'head': _make_item(bonus=3)})
    save_preset(s, 'p1')
    # Меняем equipment, save с тем же именем.
    s.equipment.head = _make_item(bonus=8)
    inputs = iter(['s', 'p1', 'yes', '0'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    Equipment.preset_menu(None, s)

    assert s.equipment_presets['p1']['head']['bonus'] == [8]  # overwritten


def test_preset_menu_save_overwrite_decline(monkeypatch, capsys):
    """Save overwrite confirm = no → не перезаписывает."""
    s = _state_with_items(equipment={'head': _make_item(bonus=3)})
    save_preset(s, 'p1')
    s.equipment.head = _make_item(bonus=8)
    inputs = iter(['s', 'p1', 'no', '0'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    Equipment.preset_menu(None, s)

    assert s.equipment_presets['p1']['head']['bonus'] == [3]  # original


def test_preset_menu_load_full_flow_with_log_event(monkeypatch, capsys):
    """Save preset → swap equipment → load preset → confirm → apply + log_event."""
    h1 = _make_item(item_name='h1', item_type='helmet',
                    characteristic='stamina', bonus=5)
    h2 = _make_item(item_name='h2', item_type='helmet',
                    characteristic='energy_max', bonus=8)
    s = _state_with_items(equipment={'head': h1}, inventory=[h2])
    save_preset(s, 'stamina_load')
    # Swap to h2.
    s.equipment.head = h2
    s.inventory = [h1]

    events: list[tuple[str, dict]] = []
    import history
    monkeypatch.setattr(history, 'log_event',
                        lambda evt_type, **payload: events.append((evt_type, payload)))

    inputs = iter(['l', 'stamina_load', 'yes', '0'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    Equipment.preset_menu(None, s)

    # Должен снова h1 в head.
    assert s.equipment.head is h1
    # log_event preset_applied записан.
    applied = [e for e in events if e[0] == 'preset_applied']
    assert len(applied) == 1
    assert applied[0][1]['name'] == 'stamina_load'
    assert applied[0][1]['slots_changed'] == 1


def test_preset_menu_load_unknown_preset_shows_message(monkeypatch, capsys):
    s = _state_with_items()
    save_preset(s, 'existing')
    inputs = iter(['l', 'missing', '0'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    Equipment.preset_menu(None, s)

    out = capsys.readouterr().out
    assert 'не найден' in out


def test_preset_menu_load_no_changes_reports_already_applied(monkeypatch, capsys):
    """Load preset идентичного current loadout → 'уже соответствует'."""
    s = _state_with_items(equipment={'head': _make_item(bonus=5)})
    save_preset(s, 'p1')
    inputs = iter(['l', 'p1', '0'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    Equipment.preset_menu(None, s)

    out = capsys.readouterr().out
    assert 'уже соответствует' in out


def test_preset_menu_delete_confirm(monkeypatch, capsys):
    """Delete preset с confirm 'yes' → удалён + log_event."""
    s = _state_with_items()
    save_preset(s, 'p1')

    events: list[tuple[str, dict]] = []
    import history
    monkeypatch.setattr(history, 'log_event',
                        lambda evt_type, **payload: events.append((evt_type, payload)))

    inputs = iter(['d', 'p1', 'yes', '0'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    Equipment.preset_menu(None, s)

    assert 'p1' not in s.equipment_presets
    deleted = [e for e in events if e[0] == 'preset_deleted']
    assert len(deleted) == 1


def test_preset_menu_delete_decline(monkeypatch, capsys):
    """Delete preset с confirm 'no' → НЕ удалён."""
    s = _state_with_items()
    save_preset(s, 'p1')
    inputs = iter(['d', 'p1', 'no', '0'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    Equipment.preset_menu(None, s)

    assert 'p1' in s.equipment_presets


def test_preset_menu_invalid_input_loops(monkeypatch, capsys):
    """Невалидный command в submenu → retry."""
    s = _state_with_items()
    inputs = iter(['x', '99', '0'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    Equipment.preset_menu(None, s)

    out = capsys.readouterr().out
    assert out.count('Неверный выбор') == 2


def test_preset_menu_empty_state_shows_message(monkeypatch, capsys):
    """Без preset'ов — UI печатает 'Пока нет сохранённых'."""
    s = _state_with_items()
    monkeypatch.setattr('builtins.input', lambda *a, **k: '0')

    Equipment.preset_menu(None, s)

    out = capsys.readouterr().out
    assert 'нет сохранённых' in out.lower()


def test_preset_round_trip_through_state_dict():
    """Presets переживают save/load цикл через to_dict/from_dict."""
    s = _state_with_items(equipment={
        'head': _make_item(item_name='h', characteristic='stamina', bonus=5),
    })
    save_preset(s, 'training')

    # Round-trip.
    d = s.to_dict()
    assert 'equipment_presets' in d
    s2 = GameState.from_dict(d)
    assert 'training' in s2.equipment_presets
    assert s2.equipment_presets['training']['head']['bonus'] == [5]


def test_optimize_menu_apply_failure_capacity_shows_warning(monkeypatch, capsys):
    """Capacity overflow при apply — warning, mutation не происходит."""
    equipped = _make_item(item_name='eq', item_type='helmet',
                           characteristic='stamina', bonus=3)
    better = _make_item(item_name='better', item_type='helmet',
                        characteristic='stamina', bonus=10)
    # Inventory at cap (10) — apply переполнит до 11 на unwear фазе.
    other_items = [_make_item(item_name=f'i{i}', characteristic='luck', bonus=1)
                   for i in range(9)]
    s = _state_with_items(
        equipment={'head': equipped},
        inventory=other_items + [better],  # 10 items, at cap
    )

    inputs = iter(['1', 'yes'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    Equipment.optimize_loadout_menu(None, s)

    out = capsys.readouterr().out
    assert 'Не удалось применить' in out
    assert 'переполнится' in out
    assert s.equipment.head is equipped  # state не изменён
