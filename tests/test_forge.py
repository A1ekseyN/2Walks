"""Тесты forge.py — Кузница (4.59).

4.59.0 — skeleton-меню с 5 пунктами. UI-smoke тесты.
4.59.1 — Repair: pure helpers (cost / max / candidates / apply) + UI flow.
"""

from state import GameState
from forge import (
    forge_menu,
    max_repair_percent,
    repair_candidates,
    repair_cost,
    repair_item,
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
    assert '5000' in out  # steps
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


def test_forge_menu_craft_stub(monkeypatch, capsys):
    """Пункт 2 — stub в 4.59.0, не падает."""
    state = GameState.default_new_game()
    inputs = iter(['2', '0'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    forge_menu(state)

    out = capsys.readouterr().out
    assert 'разработке (4.59.2)' in out


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
    """Полный flow: выбор предмета → ввод процентов → ремонт."""
    state = GameState.default_new_game()
    state.steps.can_use = 10_000
    state.money = 1_000.0
    state.energy = 100
    state.equipment.head = _make_item(item_type='helmet', grade='a-grade',
                                       quality=50.0)
    # Repair → выбрать предмет 1 → восстановить 10% → выйти из Forge
    inputs = iter(['1', '1', '10', '0'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    forge_menu(state)

    out = capsys.readouterr().out
    assert 'Ремонт +10%' in out
    assert state.equipment.head['quality'][0] == 60.0
    assert state.steps.can_use == 0


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
