"""Тесты shop.py после миграции на GameState (Phase 4 задачи 1.1, commit 4)."""

from state import GameState
from shop import _buy_item, Shop


def _empty_item():
    return {
        'item_name': [], 'item_type': [], 'grade': [],
        'characteristic': [], 'bonus': [], 'quality': [], 'price': [],
    }


# ----- _buy_item -----

def test_buy_item_success_deducts_money_and_appends():
    state = GameState.default_new_game()
    state.money = 100
    state.inventory = []
    item = _empty_item()
    item['item_name'].append('cheeseburger')

    assert _buy_item(state, item, cost=2) is True
    assert state.money == 98
    assert state.inventory == [item]


def test_buy_item_insufficient_money_returns_false_no_mutation():
    state = GameState.default_new_game()
    state.money = 1
    state.inventory = []
    item = _empty_item()

    assert _buy_item(state, item, cost=10) is False
    assert state.money == 1
    assert state.inventory == []


def test_buy_item_exact_balance_succeeds():
    state = GameState.default_new_game()
    state.money = 10
    item = _empty_item()
    assert _buy_item(state, item, cost=10) is True
    assert state.money == 0


def test_buy_item_blocked_when_inventory_full():
    """4.50 — purchase blocked when inventory >= capacity, no mutation."""
    state = GameState.default_new_game()
    state.money = 100
    # Заполняем рюкзак до базовой ёмкости (10) — backpack_skill=0 by default.
    state.inventory = [_empty_item() for _ in range(10)]
    item = _empty_item()
    item['item_name'].append('cheeseburger')

    assert _buy_item(state, item, cost=2) is False
    assert state.money == 100
    assert len(state.inventory) == 10  # без мутации


def test_buy_item_succeeds_with_backpack_skill_extra_slot():
    """4.50 — backpack_skill +1 расширяет ёмкость, покупка проходит на 11-м слоте."""
    state = GameState.default_new_game()
    state.money = 100
    state.gym.backpack_skill = 1  # cap = 11
    state.inventory = [_empty_item() for _ in range(10)]  # 10 < 11
    item = _empty_item()

    assert _buy_item(state, item, cost=5) is True
    assert state.money == 95
    assert len(state.inventory) == 11


# ----- Shop.shop_menu (UI smoke) -----

def test_shop_menu_back_command(monkeypatch, capsys):
    monkeypatch.setattr('builtins.input', lambda *a, **k: '0')
    state = GameState.default_new_game()
    Shop.shop_menu(self=None, state=state)
    out = capsys.readouterr().out
    assert 'Магазин' in out


def test_shop_menu_food_buy_cheeseburger(monkeypatch, capsys):
    state = GameState.default_new_game()
    state.money = 10
    state.inventory = []

    inputs = iter(['1', '0', '0'])  # '1' Чизбургер, '0' назад → '0' выйти
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    Shop.shop_menu_food_and_water(self=None, item=_empty_item(), money='m', state=state)

    assert state.money == 8
    assert len(state.inventory) == 1
    assert state.inventory[0]['item_name'] == ['cheeseburger']


def test_shop_menu_food_insufficient_money(monkeypatch, capsys):
    state = GameState.default_new_game()
    state.money = 1
    state.inventory = []

    # '1' попытка купить (fail) → меню повторяется → '0' назад в shop_menu → '0' выход.
    inputs = iter(['1', '0', '0'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    Shop.shop_menu_food_and_water(self=None, item=_empty_item(), money='m', state=state)
    out = capsys.readouterr().out
    assert state.money == 1
    assert state.inventory == []
    assert 'не достаточно денег' in out.lower()


def test_shop_menu_food_shows_no_effect_warning(monkeypatch, capsys):
    """21.05.2026 — Полиш: warning что расходники без consume mechanic (4.7.1)."""
    state = GameState.default_new_game()
    state.money = 100
    inputs = iter(['0', '0'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    Shop.shop_menu_food_and_water(self=None, item=_empty_item(), money='m', state=state)
    out = capsys.readouterr().out
    assert 'без эффекта' in out.lower() or 'БЕЗ ЭФФЕКТА' in out
    assert '4.7.1' in out


def test_shop_menu_shoes_display_uses_flat_stamina_not_percent(monkeypatch, capsys):
    """21.05.2026 — Полиш: shoes показывают «+N к Stamina» (flat), не «+N % шагов»."""
    state = GameState.default_new_game()
    state.money = 100
    # 5 → раздел "Обувь"; 0 → назад из clothes_shoes; 0 → назад из shop_menu_clothes.
    inputs = iter(['5', '0', '0', '0'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    Shop.shop_menu_clothes(self=None, item=_empty_item(), money='m', state=state)
    out = capsys.readouterr().out
    assert 'к Stamina' in out
    assert '% шагов' not in out  # старый misleading текст не должен остаться


def test_shop_menu_clothes_buy_shoes(monkeypatch, capsys):
    state = GameState.default_new_game()
    state.money = 25
    state.inventory = []

    # 5 → раздел "Обувь"; 1 → C-Grade за 25 $; 0 → назад из clothes_shoes;
    # 0 → назад из shop_menu_clothes (через рекурсивный заход).
    inputs = iter(['5', '1', '0', '0', '0'])
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    Shop.shop_menu_clothes(self=None, item=_empty_item(), money='m', state=state)

    assert state.money == 0
    assert len(state.inventory) == 1
    shoe = state.inventory[0]
    assert shoe['item_type'] == ['shoes']
    assert shoe['grade'] == ['c-grade']
    assert shoe['bonus'] == [1]
