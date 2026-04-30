"""Тесты CharCharacteristicProxy — backward-compat обёртки над GameState (Phase 2 задачи 1.1)."""

from datetime import datetime

import pytest

from state import (
    CharCharacteristicProxy,
    GameState,
    StepsState,
    CharLevel,
    GymSkills,
    AdventureSession,
    Equipment,
)


@pytest.fixture
def state():
    return GameState(
        energy=42,
        energy_max=70,
        money=1500,
        loc='gym',
        steps=StepsState(today=5000, used=200, daily_bonus=3),
        char_level=CharLevel(level=10, skill_stamina=15),
        gym=GymSkills(stamina=20, luck_skill=5),
        adventure=AdventureSession(counters={
            'walk_easy': 5, 'walk_normal': 3, 'walk_hard': 1,
            'walk_15k': 0, 'walk_20k': 0, 'walk_25k': 0, 'walk_30k': 0,
        }),
        equipment=Equipment(head={'item_name': ['cap']}),
        inventory=[{'item_name': ['ring']}],
    )


@pytest.fixture
def proxy(state):
    return CharCharacteristicProxy(state)


# ----- Read access -----

def test_proxy_read_top_level_field(proxy):
    assert proxy['energy'] == 42
    assert proxy['money'] == 1500
    assert proxy['loc'] == 'gym'


def test_proxy_read_nested_steps(proxy):
    assert proxy['steps_today'] == 5000
    assert proxy['steps_today_used'] == 200
    assert proxy['steps_daily_bonus'] == 3


def test_proxy_read_nested_char_level(proxy):
    assert proxy['char_level'] == 10
    assert proxy['lvl_up_skill_stamina'] == 15
    assert proxy['lvl_up_skill_luck'] == 0


def test_proxy_read_nested_gym(proxy):
    assert proxy['stamina'] == 20
    assert proxy['luck_skill'] == 5
    assert proxy['speed_skill'] == 0


def test_proxy_read_adventure_counter(proxy):
    assert proxy['adventure_walk_easy_counter'] == 5
    assert proxy['adventure_walk_normal_counter'] == 3
    assert proxy['adventure_walk_30k_counter'] == 0


def test_proxy_read_equipment_slot(proxy):
    assert proxy['equipment_head'] == {'item_name': ['cap']}
    assert proxy['equipment_foots'] is None


def test_proxy_read_inventory_returns_same_list(proxy, state):
    """Inventory через proxy — та же ссылка, что в state. Мутации `.append` работают."""
    inv = proxy['inventory']
    assert inv is state.inventory
    inv.append({'item_name': ['necklace']})
    assert len(state.inventory) == 2


def test_proxy_read_unknown_key_raises_keyerror(proxy):
    with pytest.raises(KeyError):
        _ = proxy['nonexistent_key']


def test_proxy_get_with_default(proxy):
    assert proxy.get('energy') == 42
    assert proxy.get('nonexistent_key', 'fallback') == 'fallback'
    assert proxy.get('nonexistent_key') is None


def test_proxy_contains(proxy):
    assert 'energy' in proxy
    assert 'steps_today' in proxy
    assert 'adventure_walk_easy_counter' in proxy
    assert 'nonexistent_key' not in proxy


def test_proxy_keys_includes_all_legacy_keys(proxy):
    keys = set(proxy.keys())
    expected_subset = {
        'energy', 'energy_max', 'money', 'loc',
        'steps_today', 'steps_today_used', 'steps_daily_bonus',
        'char_level', 'lvl_up_skill_stamina',
        'stamina', 'luck_skill',
        'inventory',
        'equipment_head', 'equipment_foots',
        'adventure', 'adventure_walk_easy_counter', 'adventure_walk_30k_counter',
    }
    assert expected_subset.issubset(keys)


def test_proxy_items_iterable(proxy):
    items = dict(proxy.items())
    assert items['energy'] == 42
    assert items['steps_today'] == 5000


# ----- Write access -----

def test_proxy_write_top_level(proxy, state):
    proxy['energy'] = 30
    assert state.energy == 30


def test_proxy_write_nested_steps(proxy, state):
    proxy['steps_today'] = 10000
    assert state.steps.today == 10000


def test_proxy_write_nested_char_level(proxy, state):
    proxy['lvl_up_skill_stamina'] = 25
    assert state.char_level.skill_stamina == 25


def test_proxy_write_adventure_counter(proxy, state):
    proxy['adventure_walk_hard_counter'] = 10
    assert state.adventure.counters['walk_hard'] == 10


def test_proxy_write_equipment_slot(proxy, state):
    item = {'item_name': ['gloves']}
    proxy['equipment_torso'] = item
    assert state.equipment.torso == item


def test_proxy_write_inventory_replaces_list(proxy, state):
    new_inv = [{'item_name': ['amulet']}]
    proxy['inventory'] = new_inv
    assert state.inventory is new_inv


def test_proxy_write_unknown_key_raises_keyerror(proxy):
    with pytest.raises(KeyError):
        proxy['nonexistent_key'] = 42


# ----- update() / setdefault() -----

def test_proxy_update_with_dict(proxy, state):
    proxy.update({'energy': 60, 'money': 999, 'steps_today': 8000})
    assert state.energy == 60
    assert state.money == 999
    assert state.steps.today == 8000


def test_proxy_update_with_other_proxy(proxy, state):
    """Эмуляция команды `l` (Load from Cloud) — proxy.update(other_proxy)."""
    other_state = GameState(energy=100, money=5000)
    other_proxy = CharCharacteristicProxy(other_state)
    proxy.update(other_proxy)
    assert state.energy == 100
    assert state.money == 5000


def test_proxy_setdefault_existing_key(proxy, state):
    result = proxy.setdefault('energy', 999)
    assert result == 42
    assert state.energy == 42  # не перезаписан


def test_proxy_setdefault_unknown_key(proxy, state):
    """setdefault для unknown ключа — пытается записать, падает с KeyError."""
    with pytest.raises(KeyError):
        proxy.setdefault('nonexistent_key', 42)


# ----- Round-trip с proxy -----

def test_proxy_to_dict_via_state(proxy, state):
    """Проверка, что после mutations через proxy, state.to_dict() видит изменения."""
    proxy['energy'] = 30
    proxy['steps_today'] = 7777
    proxy['lvl_up_skill_luck'] = 4
    proxy['adventure_walk_15k_counter'] = 2

    d = state.to_dict()
    assert d['energy'] == 30
    assert d['steps_today'] == 7777
    assert d['lvl_up_skill_luck'] == 4
    assert d['adventure_walk_15k_counter'] == 2


def test_proxy_supports_increment_pattern(proxy, state):
    """Поддержка legacy-паттерна `proxy[key] += value`."""
    proxy['energy'] -= 5
    assert state.energy == 37
    proxy['steps_today_used'] += 100
    assert state.steps.used == 300
    proxy['adventure_walk_easy_counter'] += 1
    assert state.adventure.counters['walk_easy'] == 6
