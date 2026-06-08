"""Тесты forge.py — Кузница (4.59).

4.59.0 — skeleton-меню с 5 пунктами. UI-smoke тесты.
4.59.1 — Repair: pure helpers (cost / max / candidates / apply) + UI flow.
4.60   — Forge skills: forge_steps_saving / forge_money_saving (экономия
         на repair+craft) + forge_repair_quality (множитель восстановления).
4.59.4 — Таймеры на Repair/Crafting + навык forge_speed + capture-in-session.
"""

import pytest

from state import GameState
from forge import (
    craft_item,
    craft_duration,
    crafting_cost,
    crafting_cost_effective,
    find_craftable_groups,
    forge_check_done,
    forge_menu,
    max_repair_percent,
    repair_candidates,
    repair_cost,
    repair_cost_effective,
    repair_duration,
    repair_item,
    start_craft_session,
    start_repair_session,
)
from bonus import (
    apply_forge_money_saving,
    apply_forge_speed,
    apply_forge_steps_saving,
    forge_repair_multiplier,
)


def _make_item(item_type='helmet', grade='a-grade', quality=50.0,
               characteristic='speed', bonus=10) -> dict:
    """Helper для построения item-dict (list-обёртки legacy формата)."""
    return {
        'item_type': [item_type],
        'item_name': [item_type],
        'grade': [grade],
        'characteristic': [characteristic],
        'bonus': [bonus],
        'quality': [quality],
        'price': [int(quality * 1.5)],
    }


def test_forge_menu_exit_by_zero(monkeypatch, capsys):
    """'0' выходит из меню сразу. Шапка отрисовалась."""
    state = GameState.default_new_game()
    monkeypatch.setattr('builtins.input', lambda *a, **k: '0')

    forge_menu(state)

    out = capsys.readouterr().out
    assert '🔨 Кузница' in out
    assert 'Отремонтировать предмет' in out
    assert 'Улучшить Grade предмета' in out
    assert 'Сделать дырку' in out
    assert 'Вставить камень' in out
    assert 'Объединить камни' in out


def test_forge_menu_shows_resources_in_header(monkeypatch, capsys):
    """Шапка показывает Steps / Energy / Money игрока."""
    state = GameState.default_new_game()
    state.money = 1234.56
    state.steps.can_use = 5000
    state.energy = 42
    monkeypatch.setattr('builtins.input', lambda *a, **k: '0')

    forge_menu(state)

    out = capsys.readouterr().out
    assert '5,000' in out  # steps с thousands separator (симметрично status_bar)
    assert '42' in out  # energy
    assert '1,234.56' in out  # money с format_money


def test_forge_menu_invalid_input_loops_back(monkeypatch, capsys):
    """Невалидный ввод → '\\nНеверный выбор' → continue → '0' выходит."""
    state = GameState.default_new_game()
    inputs = iter(['xyz', '99', '0'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    forge_menu(state)

    out = capsys.readouterr().out
    assert out.count('Неверный выбор') >= 2  # xyz и 99


def test_forge_menu_gem_stubs_deferred(monkeypatch, capsys):
    """Пункты 3, 4, 5 — отложенные gem-stub'ы (4.59.3 deferred)."""
    state = GameState.default_new_game()
    inputs = iter(['3', '4', '5', '0'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    forge_menu(state)

    out = capsys.readouterr().out
    # Все 3 stub'а ссылаются на 4.59.3
    assert out.count('4.59.3') == 3
    assert 'Сделать дырку' in out or 'дырку' in out
    assert 'Вставить камень' in out or 'камень' in out
    assert 'Объединить камни' in out or 'камни' in out


# ----- 4.59.1 Repair: pure helpers -----

def test_repair_cost_linear():
    """1% = 1000ш / 100$ / 10эн; масштабируется линейно."""
    assert repair_cost(1) == (1000, 100, 10)
    assert repair_cost(10) == (10_000, 1_000, 100)
    assert repair_cost(0) == (0, 0, 0)
    assert repair_cost(100) == (100_000, 10_000, 1_000)


def test_max_repair_percent_headroom_only():
    """С неограниченными ресурсами — лимит = 100 - quality."""
    state = GameState.default_new_game()
    state.steps.can_use = 1_000_000
    state.money = 1_000_000.0
    state.energy = 100_000
    item = _make_item(quality=67.5)
    # int(100 - 67.5) = 32 (floor)
    assert max_repair_percent(state, item) == 32


def test_max_repair_percent_by_resources():
    """С ограниченными ресурсами — выбирается минимум по 3 caps + headroom."""
    state = GameState.default_new_game()
    state.steps.can_use = 50_000   # → 50% по шагам
    state.money = 800.0            # → 8% по деньгам (минимум!)
    state.energy = 200             # → 20% по энергии
    item = _make_item(quality=50.0)  # headroom=50
    assert max_repair_percent(state, item) == 8


def test_max_repair_percent_full_quality_returns_zero():
    """Quality=100 → нечего ремонтировать."""
    state = GameState.default_new_game()
    state.steps.can_use = 1_000_000
    state.money = 1_000_000.0
    state.energy = 100_000
    item = _make_item(quality=100.0)
    assert max_repair_percent(state, item) == 0


def test_max_repair_percent_no_quality_field_returns_zero():
    """Предмет без quality (e.g. consumables) — repair неприменим."""
    state = GameState.default_new_game()
    state.steps.can_use = 1_000_000
    item = {'item_type': ['coffee'], 'item_name': ['coffee'], 'price': [10]}
    assert max_repair_percent(state, item) == 0


def test_repair_candidates_skips_full_quality_and_empty_slots():
    """Quality=100 не попадает; пустые слоты пропускаются."""
    state = GameState.default_new_game()
    state.equipment.head = _make_item(item_type='helmet', quality=80.0)
    state.equipment.torso = _make_item(item_type='armor', quality=100.0)  # пропуск
    state.equipment.foots = None  # пропуск
    state.inventory.append(_make_item(item_type='ring', quality=42.0))
    state.inventory.append(_make_item(item_type='boots', quality=100.0))  # пропуск
    # Без quality поля — пропуск
    state.inventory.append({'item_type': ['coffee'], 'price': [10]})

    candidates = repair_candidates(state)
    labels = [label for label, _ in candidates]
    assert len(candidates) == 2
    # Сортировка по quality asc: ring(42) < helmet(80)
    assert 'ring' in labels[0].lower()
    assert 'helmet' in labels[1].lower()


def test_repair_candidates_sort_by_quality_asc():
    """Самые повреждённые (низкий quality) — первые в списке."""
    state = GameState.default_new_game()
    state.equipment.head = _make_item(item_type='helmet', quality=75.0)
    state.equipment.torso = _make_item(item_type='armor', quality=12.0)
    state.equipment.legs = _make_item(item_type='pants', quality=48.0)
    candidates = repair_candidates(state)
    qualities = [item['quality'][0] for _, item in candidates]
    assert qualities == [12.0, 48.0, 75.0]


def test_repair_item_success_mutates_quality_and_price():
    """repair_item: списывает ресурсы, поднимает quality, recalc price."""
    state = GameState.default_new_game()
    state.steps.can_use = 10_000
    state.money = 1_000.0
    state.energy = 100
    item = _make_item(grade='a-grade', quality=50.0)  # price = 75

    ok = repair_item(state, item, 10)
    assert ok is True
    assert item['quality'][0] == 60.0
    # a-grade × quality 60 × 1.5 = 90
    assert item['price'][0] == 90
    # Ресурсы списались
    assert state.steps.can_use == 0
    assert state.money == 0.0
    assert state.energy == 0


def test_repair_item_clamps_at_100():
    """quality + percent > 100 → clamp до 100."""
    state = GameState.default_new_game()
    state.steps.can_use = 50_000
    state.money = 5_000.0
    state.energy = 500
    item = _make_item(quality=95.0)

    # max headroom = 5, но если каким-то образом передали больше —
    # max_repair_percent заблокирует. Проверяем clamp при exact match.
    ok = repair_item(state, item, 5)
    assert ok is True
    assert item['quality'][0] == 100.0


def test_repair_item_rejects_above_max():
    """percent > max_repair_percent → False, без мутаций."""
    state = GameState.default_new_game()
    state.steps.can_use = 5_000  # хватит только на 5%
    state.money = 10_000.0
    state.energy = 1_000
    item = _make_item(quality=50.0)
    original_quality = item['quality'][0]

    ok = repair_item(state, item, 10)
    assert ok is False
    assert item['quality'][0] == original_quality
    assert state.steps.can_use == 5_000  # без мутаций


def test_repair_item_rejects_zero_or_negative():
    """percent <= 0 → noop."""
    state = GameState.default_new_game()
    state.steps.can_use = 10_000
    item = _make_item()
    assert repair_item(state, item, 0) is False
    assert repair_item(state, item, -5) is False
    assert state.steps.can_use == 10_000


def test_repair_item_recalc_for_all_grades():
    """recalc price работает для всех grade-multipliers."""
    state = GameState.default_new_game()
    for grade, mul in [('c-grade', 0.5), ('b-grade', 1.0), ('a-grade', 1.5),
                       ('s-grade', 2.0), ('s+grade', 2.5)]:
        state.steps.can_use = 10_000
        state.money = 1_000.0
        state.energy = 100
        item = _make_item(grade=grade, quality=50.0)
        repair_item(state, item, 10)
        assert item['price'][0] == int(60.0 * mul), f'fail for {grade}'


# ----- 4.59.1 Repair: UI flow -----

def test_repair_menu_empty_when_nothing_to_repair(monkeypatch, capsys):
    """Default state — пустой инвентарь, пустые слоты → friendly message."""
    state = GameState.default_new_game()
    inputs = iter(['1', '0'])  # выбрать Repair → выйти
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    forge_menu(state)

    out = capsys.readouterr().out
    assert 'идеальном состоянии' in out or 'нечего ремонтировать' in out


def test_repair_menu_back_to_forge(monkeypatch, capsys):
    """С повреждённым предметом, выбор '0' возвращает в меню Кузницы."""
    state = GameState.default_new_game()
    state.equipment.head = _make_item(quality=50.0)
    inputs = iter(['1', '0', '0'])  # Repair → назад → выйти из Forge
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    forge_menu(state)

    out = capsys.readouterr().out
    assert 'Ремонт предметов' in out


def test_repair_flow_full_success(monkeypatch, capsys):
    """4.59.4 — flow: выбор предмета → ввод % → СТАРТ таймерного ремонта.
    Результат применится в forge_check_done по таймеру (не сразу)."""
    state = GameState.default_new_game()
    state.steps.can_use = 10_000
    state.money = 1_000.0
    state.energy = 100
    state.equipment.head = _make_item(item_type='helmet', grade='a-grade',
                                       quality=50.0)
    # Repair → выбрать предмет 1 → восстановить 10% (после старта меню сразу
    # покажет активную сессию и выйдет — '0' не понадобится)
    inputs = iter(['1', '1', '10'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    forge_menu(state)

    out = capsys.readouterr().out
    assert 'Ремонт начат: +10%' in out
    # Предмет ушёл в кузницу (слот пуст), ресурсы списаны, сессия активна.
    assert state.equipment.head is None
    assert state.steps.can_use == 0
    assert state.forge.active is True
    assert state.forge.op_type == 'repair'
    assert state.forge.payload['item']['quality'][0] == 50.0  # ещё не применено


def test_repair_flow_insufficient_resources_shows_message(monkeypatch, capsys):
    """Если ресурсов не хватает даже на 1% — explicit error message."""
    state = GameState.default_new_game()
    state.steps.can_use = 500  # < 1000
    state.money = 50.0
    state.energy = 5
    state.equipment.head = _make_item(quality=80.0)

    inputs = iter(['1', '1', '0'])  # Repair → выбрать → выйти Forge
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    forge_menu(state)

    out = capsys.readouterr().out
    assert 'Не хватает ресурсов' in out


def test_repair_flow_cancel_at_percent_prompt(monkeypatch, capsys):
    """'0' на prompt процентов → 'Ремонт отменён', state не мутирует."""
    state = GameState.default_new_game()
    state.steps.can_use = 10_000
    state.money = 1_000.0
    state.energy = 100
    state.equipment.head = _make_item(quality=50.0)

    inputs = iter(['1', '1', '0', '0'])  # Repair → item 1 → cancel → exit Forge
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    forge_menu(state)

    out = capsys.readouterr().out
    assert 'отменён' in out
    assert state.equipment.head['quality'][0] == 50.0
    assert state.steps.can_use == 10_000


def test_repair_flow_out_of_range_percent(monkeypatch, capsys):
    """Ввод процентов вне диапазона → 'вне диапазона. Ремонт отменён'."""
    state = GameState.default_new_game()
    state.steps.can_use = 10_000
    state.money = 1_000.0
    state.energy = 100
    state.equipment.head = _make_item(quality=50.0)

    inputs = iter(['1', '1', '99', '0'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    forge_menu(state)

    out = capsys.readouterr().out
    assert 'вне диапазона' in out
    assert state.equipment.head['quality'][0] == 50.0


# ----- 4.59.2 Crafting: pure helpers -----

def test_crafting_cost_linear_by_tier():
    """tier × (1000ш / 100$ / 10эн). s+grade — (0,0,0) cap."""
    assert crafting_cost('c-grade') == (1000, 100, 10)
    assert crafting_cost('b-grade') == (2000, 200, 20)
    assert crafting_cost('a-grade') == (3000, 300, 30)
    assert crafting_cost('s-grade') == (4000, 400, 40)
    assert crafting_cost('s+grade') == (0, 0, 0)


def test_find_craftable_groups_empty_state():
    """Нет предметов → пустой список."""
    state = GameState.default_new_game()
    assert find_craftable_groups(state) == []


def test_find_craftable_groups_single_no_match():
    """1 предмет без пары → пусто."""
    state = GameState.default_new_game()
    state.inventory.append(_make_item('ring', 'b-grade', 50.0, 'luck', 2))
    assert find_craftable_groups(state) == []


def test_find_craftable_groups_pairs_inventory():
    """2 одинаковых в инвентаре → 1 группа с 2 candidates."""
    state = GameState.default_new_game()
    state.inventory.append(_make_item('ring', 'b-grade', 50.0, 'luck', 2))
    state.inventory.append(_make_item('ring', 'b-grade', 80.0, 'luck', 2))
    groups = find_craftable_groups(state)
    assert len(groups) == 1
    g = groups[0]
    assert g['item_type'] == 'ring'
    assert g['characteristic'] == 'luck'
    assert g['grade'] == 'b-grade'
    assert g['next_grade'] == 'a-grade'
    assert g['cost'] == (2000, 200, 20)
    assert len(g['candidates']) == 2


def test_find_craftable_groups_skip_different_characteristics():
    """Same type+grade, different characteristic → НЕ объединяются."""
    state = GameState.default_new_game()
    state.inventory.append(_make_item('ring', 'b-grade', 50.0, 'luck', 2))
    state.inventory.append(_make_item('ring', 'b-grade', 80.0, 'speed', 2))
    assert find_craftable_groups(state) == []


def test_find_craftable_groups_skip_different_grades():
    """Same type+characteristic, different grade → НЕ объединяются."""
    state = GameState.default_new_game()
    state.inventory.append(_make_item('ring', 'b-grade', 50.0, 'luck', 2))
    state.inventory.append(_make_item('ring', 'a-grade', 80.0, 'luck', 3))
    assert find_craftable_groups(state) == []


def test_find_craftable_groups_mixed_equipment_and_inventory():
    """Equipped + inventory одинаковые → объединяются в одну группу."""
    state = GameState.default_new_game()
    state.equipment.finger_01 = _make_item('ring', 'b-grade', 95.0, 'luck', 2)
    state.equipment.finger_02 = _make_item('ring', 'b-grade', 80.0, 'luck', 2)
    state.inventory.append(_make_item('ring', 'b-grade', 60.0, 'luck', 2))
    groups = find_craftable_groups(state)
    assert len(groups) == 1
    assert len(groups[0]['candidates']) == 3
    # 2 из equipment + 1 inventory
    slot_attrs = [meta[2] for meta in groups[0]['candidates']]
    assert slot_attrs.count(None) == 1
    assert sum(1 for s in slot_attrs if s is not None) == 2


def test_find_craftable_groups_splus_cap_no_next():
    """s+grade пара → группа с next_grade=None, cost=(0,0,0)."""
    state = GameState.default_new_game()
    state.inventory.append(_make_item('ring', 's+grade', 90.0, 'luck', 5))
    state.inventory.append(_make_item('ring', 's+grade', 80.0, 'luck', 5))
    groups = find_craftable_groups(state)
    assert len(groups) == 1
    assert groups[0]['next_grade'] is None
    assert groups[0]['cost'] == (0, 0, 0)


def test_find_craftable_groups_sorted_by_grade():
    """Сортировка по grade asc: C → B → A → S → S+."""
    state = GameState.default_new_game()
    state.inventory.extend([
        _make_item('ring', 'a-grade', 50, 'luck', 3),
        _make_item('ring', 'a-grade', 80, 'luck', 3),
        _make_item('helmet', 'c-grade', 50, 'stamina', 1),
        _make_item('helmet', 'c-grade', 80, 'stamina', 1),
    ])
    groups = find_craftable_groups(state)
    assert [g['grade'] for g in groups] == ['c-grade', 'a-grade']


def test_craft_item_success_inventory_only():
    """2 inventory → 1 next-grade item в inventory, ресурсы списаны."""
    state = GameState.default_new_game()
    state.steps.can_use = 5000
    state.money = 500.0
    state.energy = 50
    state.inventory.extend([
        _make_item('ring', 'b-grade', 60.0, 'luck', 2),
        _make_item('ring', 'b-grade', 80.0, 'luck', 2),
    ])
    a, b = state.inventory[0], state.inventory[1]

    result = craft_item(state, a, b)

    assert result is not None
    assert result['grade'][0] == 'a-grade'
    assert result['bonus'][0] == 3  # a-grade bonus value
    assert result['quality'][0] == 70.0  # avg(60, 80)
    assert result['item_type'][0] == 'ring'
    assert result['characteristic'][0] == 'luck'
    # a-grade × 70 × 1.5 = 105
    assert result['price'][0] == 105
    # Source items удалены, новый добавлен
    assert len(state.inventory) == 1
    assert state.inventory[0] is result
    # Resources списаны (b-grade cost 2k/200/20)
    assert state.steps.can_use == 3000
    assert state.money == 300.0
    assert state.energy == 30


def test_craft_item_success_equipped_auto_unequip():
    """2 equipped → оба слота None, новый item в inventory."""
    state = GameState.default_new_game()
    state.steps.can_use = 5000
    state.money = 500.0
    state.energy = 50
    a = _make_item('ring', 'b-grade', 90.0, 'luck', 2)
    b = _make_item('ring', 'b-grade', 70.0, 'luck', 2)
    state.equipment.finger_01 = a
    state.equipment.finger_02 = b

    result = craft_item(state, a, b)

    assert result is not None
    assert result['quality'][0] == 80.0
    assert state.equipment.finger_01 is None
    assert state.equipment.finger_02 is None
    assert len(state.inventory) == 1
    assert state.inventory[0] is result


def test_craft_item_success_mixed_equipped_and_inventory():
    """1 equipped + 1 inventory → equipped слот None, inventory size unchanged
    (удалили 1, добавили 1)."""
    state = GameState.default_new_game()
    state.steps.can_use = 5000
    state.money = 500.0
    state.energy = 50
    a = _make_item('ring', 'b-grade', 90.0, 'luck', 2)
    b = _make_item('ring', 'b-grade', 70.0, 'luck', 2)
    state.equipment.finger_01 = a
    state.inventory.append(b)

    result = craft_item(state, a, b)

    assert result is not None
    assert state.equipment.finger_01 is None
    assert len(state.inventory) == 1
    assert state.inventory[0] is result


def test_craft_item_rejects_splus_cap():
    """s+grade нельзя крафтить → None, без мутаций."""
    state = GameState.default_new_game()
    state.steps.can_use = 10000
    state.money = 1000.0
    state.energy = 100
    a = _make_item('ring', 's+grade', 90.0, 'luck', 5)
    b = _make_item('ring', 's+grade', 80.0, 'luck', 5)
    state.inventory.extend([a, b])

    assert craft_item(state, a, b) is None
    assert len(state.inventory) == 2
    assert state.steps.can_use == 10000


def test_craft_item_rejects_same_object():
    """Item и сам с собой → None (нельзя крафтить из 1 предмета)."""
    state = GameState.default_new_game()
    state.steps.can_use = 5000
    state.money = 500.0
    state.energy = 50
    a = _make_item('ring', 'b-grade', 60.0, 'luck', 2)
    state.inventory.append(a)
    assert craft_item(state, a, a) is None


def test_craft_item_rejects_mismatched_attributes():
    """Разные item_type / characteristic / grade → None."""
    state = GameState.default_new_game()
    state.steps.can_use = 5000
    state.money = 500.0
    state.energy = 50
    a = _make_item('ring', 'b-grade', 60.0, 'luck', 2)
    b = _make_item('helmet', 'b-grade', 80.0, 'luck', 2)
    state.inventory.extend([a, b])
    assert craft_item(state, a, b) is None
    assert len(state.inventory) == 2


def test_craft_item_rejects_insufficient_resources():
    """Не хватает ресурсов → None, без мутаций."""
    state = GameState.default_new_game()
    state.steps.can_use = 500  # < 2000 нужно для B→A
    state.money = 50.0
    state.energy = 5
    a = _make_item('ring', 'b-grade', 60.0, 'luck', 2)
    b = _make_item('ring', 'b-grade', 80.0, 'luck', 2)
    state.inventory.extend([a, b])

    assert craft_item(state, a, b) is None
    assert len(state.inventory) == 2
    assert state.steps.can_use == 500


def test_craft_item_rejects_inventory_overflow():
    """2 equipped + inventory at cap → after craft inv = cap+1 → reject."""
    state = GameState.default_new_game()
    state.steps.can_use = 5000
    state.money = 500.0
    state.energy = 50
    # Default backpack_capacity = 10 + gym.backpack_skill (0) = 10
    for _ in range(10):
        state.inventory.append(_make_item('helmet', 'c-grade', 50, 'stamina', 1))
    a = _make_item('ring', 'b-grade', 90.0, 'luck', 2)
    b = _make_item('ring', 'b-grade', 70.0, 'luck', 2)
    state.equipment.finger_01 = a
    state.equipment.finger_02 = b

    assert craft_item(state, a, b) is None
    assert state.equipment.finger_01 is a  # без мутаций
    assert len(state.inventory) == 10


def test_craft_item_quality_avg_clamped_for_high_grades():
    """Avg quality для всех grade переходов работает корректно."""
    state = GameState.default_new_game()
    state.steps.can_use = 10000
    state.money = 1000.0
    state.energy = 100
    a = _make_item('ring', 'a-grade', 100.0, 'luck', 3)
    b = _make_item('ring', 'a-grade', 50.0, 'luck', 3)
    state.inventory.extend([a, b])

    result = craft_item(state, a, b)
    assert result is not None
    assert result['grade'][0] == 's-grade'
    assert result['bonus'][0] == 4
    assert result['quality'][0] == 75.0
    # s-grade × 75 × 2.0 = 150
    assert result['price'][0] == 150


# ----- 4.59.2 Crafting: UI flow -----

def test_craft_menu_empty_message(monkeypatch, capsys):
    """Нет пар → friendly message + возврат в Forge."""
    state = GameState.default_new_game()
    inputs = iter(['2', '0'])  # Craft → выйти Forge
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    forge_menu(state)

    out = capsys.readouterr().out
    assert 'Нечего улучшать' in out


def test_craft_menu_lists_groups(monkeypatch, capsys):
    """2 группы → обе показаны в списке."""
    state = GameState.default_new_game()
    state.inventory.extend([
        _make_item('ring', 'b-grade', 60, 'luck', 2),
        _make_item('ring', 'b-grade', 80, 'luck', 2),
        _make_item('helmet', 'c-grade', 50, 'stamina', 1),
        _make_item('helmet', 'c-grade', 70, 'stamina', 1),
    ])
    inputs = iter(['2', '0', '0'])  # Craft → назад из групп → выйти Forge
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    forge_menu(state)

    out = capsys.readouterr().out
    assert 'Helmet c-grade stamina' in out
    assert 'Ring b-grade luck' in out


def test_craft_flow_full_success(monkeypatch, capsys):
    """4.59.4 — flow: список → группа → 2 предмета → yes → СТАРТ таймерного
    крафта. Источники уходят в кузницу, результат появится по таймеру."""
    state = GameState.default_new_game()
    state.steps.can_use = 5000
    state.money = 500.0
    state.energy = 50
    state.inventory.extend([
        _make_item('ring', 'b-grade', 60.0, 'luck', 2),
        _make_item('ring', 'b-grade', 80.0, 'luck', 2),
    ])
    # Craft → выбрать группу 1 → выбрать "1,2" → yes (после старта меню покажет
    # активную сессию и выйдет)
    inputs = iter(['2', '1', '1,2', 'yes'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    forge_menu(state)

    out = capsys.readouterr().out
    assert 'Крафт начат' in out
    assert 'a-grade' in out
    # Источники ушли в кузницу (инвентарь пуст), результат в сессии.
    assert len(state.inventory) == 0
    assert state.forge.active is True
    assert state.forge.op_type == 'craft'
    assert state.forge.payload['result']['grade'][0] == 'a-grade'
    assert state.steps.can_use == 3000


def test_craft_flow_cancel_no_yes(monkeypatch, capsys):
    """Любой ввод кроме 'yes' / 'y' → отмена, без мутаций."""
    state = GameState.default_new_game()
    state.steps.can_use = 5000
    state.money = 500.0
    state.energy = 50
    state.inventory.extend([
        _make_item('ring', 'b-grade', 60.0, 'luck', 2),
        _make_item('ring', 'b-grade', 80.0, 'luck', 2),
    ])
    inputs = iter(['2', '1', '1,2', 'no', '0'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    forge_menu(state)

    out = capsys.readouterr().out
    assert 'Крафт отменён' in out
    assert len(state.inventory) == 2
    assert state.steps.can_use == 5000


def test_craft_flow_equipped_warning(monkeypatch, capsys):
    """Equipped sources → warning виден в preview."""
    state = GameState.default_new_game()
    state.steps.can_use = 5000
    state.money = 500.0
    state.energy = 50
    state.equipment.finger_01 = _make_item('ring', 'b-grade', 90.0, 'luck', 2)
    state.equipment.finger_02 = _make_item('ring', 'b-grade', 70.0, 'luck', 2)
    inputs = iter(['2', '1', '1,2', 'no', '0'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    forge_menu(state)

    out = capsys.readouterr().out
    assert 'ВНИМАНИЕ' in out
    assert 'finger_01' in out
    assert 'finger_02' in out
    assert 'останутся пустыми' in out


def test_craft_flow_invalid_index_format(monkeypatch, capsys):
    """Невалидный формат выбора (1 число / range) → 'Неверный формат'."""
    state = GameState.default_new_game()
    state.steps.can_use = 5000
    state.money = 500.0
    state.energy = 50
    state.inventory.extend([
        _make_item('ring', 'b-grade', 60.0, 'luck', 2),
        _make_item('ring', 'b-grade', 80.0, 'luck', 2),
    ])
    inputs = iter(['2', '1', '1', '0'])  # вводим только "1" вместо "1,2"
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    forge_menu(state)

    out = capsys.readouterr().out
    assert 'Неверный формат' in out
    assert len(state.inventory) == 2  # без мутаций


def test_craft_flow_splus_cap_blocks(monkeypatch, capsys):
    """Выбор s+grade группы → блокировка cap message."""
    state = GameState.default_new_game()
    state.inventory.extend([
        _make_item('ring', 's+grade', 90.0, 'luck', 5),
        _make_item('ring', 's+grade', 80.0, 'luck', 5),
    ])
    inputs = iter(['2', '1', '0'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    forge_menu(state)

    out = capsys.readouterr().out
    assert 'cap' in out  # cap mentioned in group line или после выбора


# ===== 4.60 — Forge skills (steps/money saving + repair quality) =====

# ----- bonus.py helpers -----

def test_apply_forge_steps_saving_no_skill_is_identity():
    state = GameState.default_new_game()
    assert state.gym.forge_steps_saving == 0
    assert apply_forge_steps_saving(1000, state) == 1000


def test_apply_forge_steps_saving_linear_per_level():
    state = GameState.default_new_game()
    state.gym.forge_steps_saving = 10  # -10%
    assert apply_forge_steps_saving(1000, state) == 900
    state.gym.forge_steps_saving = 25  # -25%
    assert apply_forge_steps_saving(1000, state) == 750


def test_apply_forge_steps_saving_clamps_at_100():
    state = GameState.default_new_game()
    state.gym.forge_steps_saving = 150  # clamp до 100% → 0
    assert apply_forge_steps_saving(1000, state) == 0


def test_apply_forge_money_saving_no_skill_is_identity():
    state = GameState.default_new_game()
    assert apply_forge_money_saving(100, state) == 100.0


def test_apply_forge_money_saving_linear_per_level():
    state = GameState.default_new_game()
    state.gym.forge_money_saving = 20  # -20%
    assert apply_forge_money_saving(100, state) == 80.0


def test_apply_forge_money_saving_clamps_at_100():
    state = GameState.default_new_game()
    state.gym.forge_money_saving = 100
    assert apply_forge_money_saving(100, state) == 0.0


def test_forge_repair_multiplier_no_skill_is_one():
    state = GameState.default_new_game()
    assert forge_repair_multiplier(state) == 1.0


def test_forge_repair_multiplier_grows_per_level():
    state = GameState.default_new_game()
    state.gym.forge_repair_quality = 10  # ×1.1
    assert forge_repair_multiplier(state) == pytest.approx(1.1)
    state.gym.forge_repair_quality = 50  # ×1.5
    assert forge_repair_multiplier(state) == pytest.approx(1.5)


# ----- effective cost wrappers (repair + craft) -----

def test_repair_cost_effective_applies_steps_and_money_saving():
    state = GameState.default_new_game()
    state.gym.forge_steps_saving = 10  # -10% шагов
    state.gym.forge_money_saving = 20  # -20% денег
    steps, money, energy = repair_cost_effective(10, state)
    assert steps == 9000   # 10_000 × 0.9
    assert money == 800.0  # 1_000 × 0.8
    assert energy == 100   # энергия БЕЗ скидки (по дизайну 4.60)


def test_crafting_cost_effective_applies_savings():
    state = GameState.default_new_game()
    state.gym.forge_steps_saving = 50  # -50% шагов
    state.gym.forge_money_saving = 50  # -50% денег
    # a-grade tier=3 → base (3000, 300, 30)
    steps, money, energy = crafting_cost_effective('a-grade', state)
    assert steps == 1500
    assert money == 150.0
    assert energy == 30  # без скидки


# ----- repair_item: quality multiplier -----

def test_repair_item_quality_boost_restores_more():
    """forge_repair_quality=50 → ×1.5: 10% ремонта восстанавливает 15%."""
    state = GameState.default_new_game()
    state.steps.can_use = 100_000
    state.money = 10_000.0
    state.energy = 1_000
    state.gym.forge_repair_quality = 50  # ×1.5
    item = _make_item(grade='a-grade', quality=50.0)

    ok = repair_item(state, item, 10)
    assert ok is True
    # 50 + 10×1.5 = 65
    assert item['quality'][0] == pytest.approx(65.0)


def test_repair_item_quality_boost_fractional_no_rounding():
    """lvl 10 → ×1.1: 1% восстанавливает 1.1% (дробное, без округления)."""
    state = GameState.default_new_game()
    state.steps.can_use = 100_000
    state.money = 10_000.0
    state.energy = 1_000
    state.gym.forge_repair_quality = 10  # ×1.1
    item = _make_item(quality=50.0)

    ok = repair_item(state, item, 1)
    assert ok is True
    assert item['quality'][0] == pytest.approx(51.1)


def test_repair_item_quality_boost_clamps_at_100():
    """Множитель не пробивает потолок 100."""
    state = GameState.default_new_game()
    state.steps.can_use = 100_000
    state.money = 10_000.0
    state.energy = 1_000
    state.gym.forge_repair_quality = 100  # ×2.0
    item = _make_item(quality=90.0)

    ok = repair_item(state, item, 10)  # 90 + 10×2 = 110 → clamp 100
    assert ok is True
    assert item['quality'][0] == 100.0


def test_repair_item_uses_discounted_cost():
    """forge_steps/money_saving удешевляют сам ремонт."""
    state = GameState.default_new_game()
    state.steps.can_use = 10_000
    state.money = 1_000.0
    state.energy = 100
    state.gym.forge_steps_saving = 50  # -50%
    state.gym.forge_money_saving = 50  # -50%
    item = _make_item(quality=50.0)

    ok = repair_item(state, item, 10)
    assert ok is True
    # 10% ремонта: base (10_000, 1_000, 100) → -50% steps/money
    assert state.steps.can_use == 5_000   # 10_000 - 5_000
    assert state.money == 500.0           # 1_000 - 500
    assert state.energy == 0              # энергия полная


# ----- max_repair_percent: savings raise the cap -----

def test_max_repair_percent_steps_saving_raises_cap():
    """Со скидкой на шаги тех же ресурсов хватает на больший ремонт."""
    state = GameState.default_new_game()
    state.steps.can_use = 10_000   # без скидки → 10%
    state.money = 1_000_000.0
    state.energy = 1_000_000
    item = _make_item(quality=0.0)  # headroom 100

    assert max_repair_percent(state, item) == 10
    state.gym.forge_steps_saving = 50  # -50% → цена 500/1% → 20%
    assert max_repair_percent(state, item) == 20


def test_max_repair_percent_full_steps_saving_only_limited_by_money():
    """forge_steps_saving=100 → шаги бесплатны, кап лимитируется деньгами."""
    state = GameState.default_new_game()
    state.steps.can_use = 0          # без скидки не отремонтировать вообще
    state.money = 500.0              # → 5% по деньгам
    state.energy = 1_000_000
    state.gym.forge_steps_saving = 100  # шаги → 0
    item = _make_item(quality=0.0)

    assert max_repair_percent(state, item) == 5


# ----- Restorer triumph integration (boosted quality counts, no rounding) -----

def test_restorer_count_delta_reads_boosted_to_quality():
    """Restorer count_delta = to_quality - from_quality БЕЗ округления —
    дробный буст от forge_repair_quality зачитывается точно.
    (register_event замокан autouse-фикстурой вне triumph-тестов, поэтому
    проверяем чистый count_delta.)"""
    from triumphs_data import TRIUMPHS
    cd = TRIUMPHS['restorer']['count_delta']
    # 1% ремонта × ×1.1 множитель → to_quality поднят на 1.1
    assert cd({'from_quality': 50.0, 'to_quality': 51.1}) == pytest.approx(1.1)
    # boosted ×1.5: 10% → +15
    assert cd({'from_quality': 50.0, 'to_quality': 65.0}) == pytest.approx(15.0)


# ===== 4.59.4 — Таймеры Repair/Crafting + forge_speed + capture-in-session =====

import time as _time


def _forge_state(steps=1_000_000, money=1_000_000.0, energy=100_000):
    """State с ресурсами + разблокированной Кузницей (forge_speed=0 по умолчанию)."""
    state = GameState.default_new_game()
    state.steps.can_use = steps
    state.money = money
    state.energy = energy
    return state


# ----- duration helpers + forge_speed -----

def test_repair_duration_base():
    """1% = 1 час (3600 сек); линейно по percent (forge_speed=0)."""
    state = _forge_state()
    assert repair_duration(1, state) == 3600
    assert repair_duration(10, state) == 36000


def test_craft_duration_by_source_grade():
    """C/B/A/S = 1/4/8/12 ч (forge_speed=0)."""
    state = _forge_state()
    assert craft_duration('c-grade', state) == 3600
    assert craft_duration('b-grade', state) == 4 * 3600
    assert craft_duration('a-grade', state) == 8 * 3600
    assert craft_duration('s-grade', state) == 12 * 3600


def test_apply_forge_speed_linear_and_clamp():
    state = _forge_state()
    assert apply_forge_speed(36000, state) == 36000          # skill 0
    state.gym.forge_speed = 50
    assert apply_forge_speed(36000, state) == 18000          # -50%
    state.gym.forge_speed = 100
    assert apply_forge_speed(36000, state) == 60             # clamp 60с (не 0)


def test_repair_duration_with_forge_speed():
    state = _forge_state()
    state.gym.forge_speed = 50
    assert repair_duration(10, state) == 18000  # 36000 × 0.5


# ----- start_repair_session (capture) -----

def test_start_repair_session_captures_from_inventory():
    state = _forge_state()
    item = _make_item(item_type='shoes', grade='a-grade', quality=50.0)
    state.inventory.append(item)
    ok = start_repair_session(state, item, 10)
    assert ok is True
    # Предмет ушёл в кузницу (из инвентаря), сессия активна, ресурсы списаны.
    assert item not in state.inventory
    assert state.forge.active is True
    assert state.forge.op_type == 'repair'
    assert state.forge.payload['item'] is item
    assert state.forge.payload['percent'] == 10
    assert state.steps.can_use == 1_000_000 - 10_000


def test_start_repair_session_captures_from_equipment():
    state = _forge_state()
    item = _make_item(item_type='shoes', grade='a-grade', quality=50.0)
    state.equipment.foots = item
    ok = start_repair_session(state, item, 5)
    assert ok is True
    assert state.equipment.foots is None  # снят в кузницу
    assert state.forge.payload['item'] is item


def test_start_repair_session_rejects_when_active():
    state = _forge_state()
    i1 = _make_item(quality=50.0)
    i2 = _make_item(quality=40.0)
    state.inventory.extend([i1, i2])
    assert start_repair_session(state, i1, 5) is True
    # Вторая операция — отказ (одна за раз).
    assert start_repair_session(state, i2, 5) is False
    assert i2 in state.inventory  # не тронут


def test_start_repair_session_rejects_over_max():
    state = _forge_state(steps=3000)  # хватает ~ на 3%
    item = _make_item(quality=10.0)
    state.inventory.append(item)
    assert start_repair_session(state, item, 50) is False
    assert state.forge.active is False
    assert item in state.inventory  # без мутаций


# ----- start_craft_session (capture sources) -----

def test_start_craft_session_captures_sources():
    state = _forge_state()
    a = _make_item('ring', 'b-grade', 60.0, 'luck', 2)
    b = _make_item('ring', 'b-grade', 80.0, 'luck', 2)
    state.inventory.extend([a, b])
    result = start_craft_session(state, a, b)
    assert result is not None
    assert result['grade'][0] == 'a-grade'
    assert result['quality'][0] == 70.0
    # Источники ушли в кузницу, результат в сессии (НЕ в инвентаре).
    assert len(state.inventory) == 0
    assert state.forge.active is True
    assert state.forge.op_type == 'craft'
    assert state.forge.payload['result'] is result
    assert state.forge.payload['to_grade'] == 'a-grade'


def test_start_craft_session_rejects_when_active():
    state = _forge_state()
    a = _make_item('ring', 'b-grade', 60.0, 'luck', 2)
    b = _make_item('ring', 'b-grade', 80.0, 'luck', 2)
    c = _make_item('ring', 'c-grade', 50.0, 'luck', 1)
    d = _make_item('ring', 'c-grade', 50.0, 'luck', 1)
    state.inventory.extend([a, b, c, d])
    assert start_craft_session(state, a, b) is not None
    assert start_craft_session(state, c, d) is None  # одна за раз


# ----- forge_check_done (финализатор) -----

def test_forge_check_done_not_due_noop():
    """Таймер ещё идёт → no-op."""
    state = _forge_state()
    item = _make_item(quality=50.0)
    state.inventory.append(item)
    start_repair_session(state, item, 10)
    assert state.forge.active is True
    forge_check_done(state)  # end_ts в будущем
    assert state.forge.active is True  # не финализировано


def test_forge_check_done_repair_applies(monkeypatch):
    """Таймер истёк → quality применяется (с forge_repair_quality множителем),
    предмет в инвентаре, сессия очищена."""
    monkeypatch.setattr('persistence.save_characteristic', lambda: "OK")
    state = _forge_state()
    state.gym.forge_repair_quality = 50  # ×1.5
    item = _make_item(item_type='shoes', grade='a-grade', quality=50.0)
    state.inventory.append(item)
    start_repair_session(state, item, 10)
    state.forge.end_ts = _time.time() - 1  # таймер истёк
    forge_check_done(state)
    assert state.forge.active is False
    # 50 + 10×1.5 = 65
    assert item['quality'][0] == pytest.approx(65.0)
    assert item in state.inventory


def test_forge_check_done_craft_applies(monkeypatch):
    """Таймер истёк → результат крафта в инвентаре, сессия очищена."""
    monkeypatch.setattr('persistence.save_characteristic', lambda: "OK")
    state = _forge_state()
    a = _make_item('ring', 'b-grade', 60.0, 'luck', 2)
    b = _make_item('ring', 'b-grade', 80.0, 'luck', 2)
    state.inventory.extend([a, b])
    result = start_craft_session(state, a, b)
    state.forge.end_ts = _time.time() - 1
    forge_check_done(state)
    assert state.forge.active is False
    assert len(state.inventory) == 1
    assert state.inventory[0] is result
    assert state.inventory[0]['grade'][0] == 'a-grade'


def test_forge_check_done_repair_pushes_session_event(monkeypatch):
    """4.48.12 — на OK финализации ремонта добавляется уведомление forge_repaired."""
    monkeypatch.setattr('persistence.save_characteristic', lambda: "OK")
    state = _forge_state()
    item = _make_item(item_type='shoes', grade='a-grade', quality=50.0)
    state.inventory.append(item)
    start_repair_session(state, item, 10)
    state.forge.end_ts = _time.time() - 1
    forge_check_done(state)
    evs = [e for e in state.session_events if e['kind'] == 'forge_repaired']
    assert len(evs) == 1
    assert evs[0]['item_type'] == 'shoes'
    assert evs[0]['to_quality'] == pytest.approx(60.0)


def test_forge_check_done_craft_pushes_session_event(monkeypatch):
    """4.48.12 — на OK финализации крафта добавляется уведомление forge_crafted."""
    monkeypatch.setattr('persistence.save_characteristic', lambda: "OK")
    state = _forge_state()
    a = _make_item('ring', 'b-grade', 60.0, 'luck', 2)
    b = _make_item('ring', 'b-grade', 80.0, 'luck', 2)
    state.inventory.extend([a, b])
    start_craft_session(state, a, b)
    state.forge.end_ts = _time.time() - 1
    forge_check_done(state)
    evs = [e for e in state.session_events if e['kind'] == 'forge_crafted']
    assert len(evs) == 1
    assert evs[0]['item_type'] == 'ring'
    assert evs[0]['to_grade'] == 'a-grade'


def test_forge_check_done_stale_no_session_event(monkeypatch):
    """4.48.12 — на STALE-rollback уведомление НЕ добавляется."""
    monkeypatch.setattr('persistence.save_characteristic', lambda: "STALE")
    state = _forge_state()
    item = _make_item(item_type='shoes', grade='a-grade', quality=50.0)
    state.inventory.append(item)
    start_repair_session(state, item, 10)
    state.forge.end_ts = _time.time() - 1
    forge_check_done(state)
    assert state.session_events == []


def test_forge_check_done_stale_rollback(monkeypatch):
    """save STALE → откат: сессия восстановлена, quality не применён."""
    monkeypatch.setattr('persistence.save_characteristic', lambda: "STALE")
    state = _forge_state()
    item = _make_item(item_type='shoes', grade='a-grade', quality=50.0)
    state.inventory.append(item)
    start_repair_session(state, item, 10)
    state.forge.end_ts = _time.time() - 1
    forge_check_done(state)
    # Откат: сессия активна снова, quality НЕ применён, предмет не в инвентаре.
    assert state.forge.active is True
    assert state.forge.op_type == 'repair'
    assert item['quality'][0] == 50.0
    assert item not in state.inventory
    assert state.finalize_stale is True


def test_forge_session_round_trip():
    """ForgeSession переживает to_dict/from_dict."""
    state = _forge_state()
    item = _make_item(quality=50.0)
    state.inventory.append(item)
    start_repair_session(state, item, 10)
    restored = GameState.from_dict(state.to_dict())
    assert restored.forge.active is True
    assert restored.forge.op_type == 'repair'
    assert restored.forge.payload['percent'] == 10
    assert restored.forge.end_ts == state.forge.end_ts


def test_forge_menu_blocks_when_active(monkeypatch, capsys):
    """4.59.4 — при активной сессии меню показывает таймер и выходит
    (новую операцию начать нельзя)."""
    state = _forge_state()
    item = _make_item(item_type='shoes', grade='a-grade', quality=50.0)
    state.inventory.append(item)
    start_repair_session(state, item, 10)
    # Пытаемся войти в меню — input не должен запрашиваться (сразу return).
    monkeypatch.setattr('builtins.input',
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError('меню не должно спрашивать выбор при active')))
    forge_menu(state)
    out = capsys.readouterr().out
    assert 'Идёт ремонт' in out
    assert 'Завершится через' in out
    assert state.forge.active is True
