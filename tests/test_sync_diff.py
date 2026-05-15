"""Тесты sync_diff helpers (4.54.3) — diff между snapshot и current state.

Pure helpers, тестируются без gspread / GameState — на dict-формах напрямую.
"""

from state import GameState
from sync_diff import (
    diff_states,
    format_diff_brief,
    format_diff_cli,
    has_changes,
)


def _empty_diff() -> dict:
    """Snapshot vs identical current → все категории пустые."""
    s = GameState.default_new_game().to_dict()
    return diff_states(s, s)


# ----- has_changes / no-op -----

def test_no_changes_returns_empty_diff():
    d = _empty_diff()
    assert has_changes(d) is False
    assert format_diff_cli(d) == '(нет изменений)'
    assert format_diff_brief(d) == '(нет изменений)'


def test_has_changes_true_when_any_category_non_empty():
    s = GameState.default_new_game().to_dict()
    c = GameState.default_new_game().to_dict()
    c['money'] = 100.0
    d = diff_states(s, c)
    assert has_changes(d) is True


# ----- Money -----

def test_diff_money_positive_delta():
    s = GameState.default_new_game().to_dict()
    c = dict(s, money=1733.20)
    s['money'] = 1133.20

    d = diff_states(s, c)
    assert len(d['money']) == 1
    line = d['money'][0]
    assert '💰' in line
    assert '1,133.20' in line
    assert '1,733.20' in line
    assert '+600.00' in line


def test_diff_money_negative_delta():
    s = GameState.default_new_game().to_dict()
    c = dict(s, money=500.0)
    s['money'] = 1000.0
    d = diff_states(s, c)
    assert any('-500' in line for line in d['money'])


def test_diff_money_under_half_kopek_ignored():
    """Tolerance 0.005 — изменения < полкопейки не показываются."""
    s = GameState.default_new_game().to_dict()
    s['money'] = 100.001
    c = dict(s, money=100.002)
    d = diff_states(s, c)
    assert d['money'] == []


# ----- Steps -----

def test_diff_steps_today_only():
    s = GameState.default_new_game().to_dict()
    c = dict(s, steps_today=3000)
    s['steps_today'] = 2000
    d = diff_states(s, c)
    assert len(d['steps']) == 1
    assert 'today' in d['steps'][0]
    assert '2,000' in d['steps'][0]
    assert '3,000' in d['steps'][0]
    assert '+1,000' in d['steps'][0]


def test_diff_steps_multiple_fields():
    s = GameState.default_new_game().to_dict()
    c = dict(s, steps_today=5000, steps_today_used=1000, steps_total_used=99999)
    d = diff_states(s, c)
    assert len(d['steps']) == 3


# ----- Energy -----

def test_diff_energy_change():
    s = GameState.default_new_game().to_dict()
    s['energy'] = 30
    c = dict(s, energy=50)
    d = diff_states(s, c)
    assert len(d['energy']) == 1
    assert '🔋' in d['energy'][0]
    assert '30' in d['energy'][0]
    assert '50' in d['energy'][0]


# ----- Gym skills -----

def test_diff_gym_single_skill_upgrade():
    s = GameState.default_new_game().to_dict()
    c = dict(s, stamina=5)
    d = diff_states(s, c)
    assert len(d['gym']) == 1
    assert 'Stamina' in d['gym'][0]
    assert '0 → 5' in d['gym'][0]


def test_diff_gym_multiple_skills():
    s = GameState.default_new_game().to_dict()
    c = dict(s, stamina=5, energy_max_skill=3, trader=10)
    d = diff_states(s, c)
    assert len(d['gym']) == 3


def test_diff_gym_no_change_for_unchanged():
    s = GameState.default_new_game().to_dict()
    c = dict(s, stamina=5)
    s['stamina'] = 5
    d = diff_states(s, c)
    assert d['gym'] == []


# ----- Char level -----

def test_diff_char_level_change():
    s = GameState.default_new_game().to_dict()
    c = dict(s, char_level=5, char_level_up_skills=2)
    d = diff_states(s, c)
    assert len(d['char_level']) == 2


def test_diff_char_level_allocation_skill():
    s = GameState.default_new_game().to_dict()
    c = dict(s, lvl_up_skill_stamina=3)
    d = diff_states(s, c)
    assert any('Allocation' in line for line in d['char_level'])


# ----- Work -----

def test_diff_work_session_ended():
    """work.active: True → False — показываем «завершена»."""
    s = GameState.default_new_game().to_dict()
    s['working'] = True
    s['work'] = 'watchman'
    s['working_hours'] = 4
    c = dict(s, working=False, working_hours=0)
    d = diff_states(s, c)
    assert any('завершена' in line for line in d['work'])
    assert any('watchman' in line for line in d['work'])


def test_diff_work_session_started():
    """work.active: False → True — показываем «началась»."""
    s = GameState.default_new_game().to_dict()
    c = dict(s, working=True, work='watchman', working_hours=2)
    d = diff_states(s, c)
    assert any('началась' in line for line in d['work'])


def test_diff_work_hours_extended():
    """Same active=True, но hours изменились (add_hours)."""
    s = GameState.default_new_game().to_dict()
    s['working'] = True
    s['working_hours'] = 2
    c = dict(s, working=True, working_hours=4)
    d = diff_states(s, c)
    assert any('hours' in line.lower() for line in d['work'])


# ----- Training -----

def test_diff_training_session_completed():
    s = GameState.default_new_game().to_dict()
    s['skill_training'] = True
    s['skill_training_name'] = 'stamina'
    c = dict(s, skill_training=False, skill_training_name=None)
    d = diff_states(s, c)
    assert any('завершена' in line for line in d['training'])


# ----- Adventure -----

def test_diff_adventure_completed():
    s = GameState.default_new_game().to_dict()
    s['adventure'] = True
    s['adventure_name'] = 'walk_easy'
    c = dict(s, adventure=False, adventure_name=None)
    d = diff_states(s, c)
    assert any('завершена' in line for line in d['adventure'])


def test_diff_adventure_counters():
    s = GameState.default_new_game().to_dict()
    c = dict(s, adventure_walk_easy_counter=10)
    d = diff_states(s, c)
    assert any('walk_easy' in line for line in d['adventure'])


# ----- Inventory -----

def test_diff_inventory_item_added():
    s = GameState.default_new_game().to_dict()
    item = {'item_type': ['ring'], 'grade': ['s-grade'],
            'characteristic': ['luck'], 'bonus': [4],
            'quality': [80.0], 'price': [160]}
    c = dict(s, inventory=[item])
    d = diff_states(s, c)
    assert len(d['inventory']) == 1
    assert '0 → 1' in d['inventory'][0] or '0 → 1' in d['inventory'][0]


def test_diff_inventory_no_change_same_items():
    """Те же items в инвентаре → нет diff."""
    item = {'item_type': ['ring'], 'grade': ['s-grade'],
            'characteristic': ['luck'], 'bonus': [4],
            'quality': [80.0], 'price': [160]}
    s = GameState.default_new_game().to_dict()
    s['inventory'] = [item]
    c = dict(s, inventory=[dict(item)])  # deep-shallow copy с тем же содержимым
    d = diff_states(s, c)
    assert d['inventory'] == []


# ----- Equipment -----

def test_diff_equipment_item_equipped():
    s = GameState.default_new_game().to_dict()
    item = {'item_type': ['helmet'], 'grade': ['a-grade'],
            'characteristic': ['stamina'], 'bonus': [3],
            'quality': [75.0], 'price': [113]}
    c = dict(s, equipment_head=item)
    d = diff_states(s, c)
    assert len(d['equipment']) == 1
    assert 'Голова' in d['equipment'][0]
    assert 'пусто' in d['equipment'][0]
    assert 'Helmet' in d['equipment'][0]


def test_diff_equipment_item_swapped():
    s = GameState.default_new_game().to_dict()
    old_item = {'item_type': ['helmet'], 'grade': ['a-grade'],
                'characteristic': ['stamina'], 'bonus': [3],
                'quality': [75.0], 'price': [113]}
    new_item = {'item_type': ['helmet'], 'grade': ['s-grade'],
                'characteristic': ['stamina'], 'bonus': [4],
                'quality': [80.0], 'price': [160]}
    s['equipment_head'] = old_item
    c = dict(s, equipment_head=new_item)
    d = diff_states(s, c)
    assert len(d['equipment']) == 1
    assert 'a-grade' in d['equipment'][0]
    assert 's-grade' in d['equipment'][0]


# ----- Bank -----

def test_diff_bank_deposit():
    s = GameState.default_new_game().to_dict()
    c = dict(s, bank_deposit_amount=1000.50)
    d = diff_states(s, c)
    assert any('Депозит' in line for line in d['bank'])
    assert any('1,000.50' in line for line in d['bank'])


# ----- Date rollover -----

def test_diff_date_rollover():
    s = GameState.default_new_game().to_dict()
    s['date_last_enter'] = '2026-05-14'
    c = dict(s, date_last_enter='2026-05-15')
    d = diff_states(s, c)
    assert len(d['date']) == 1
    assert '📅' in d['date'][0]
    assert '2026-05-14' in d['date'][0]
    assert '2026-05-15' in d['date'][0]


# ----- Pending drop -----

def test_diff_pending_drop_appeared():
    s = GameState.default_new_game().to_dict()
    drop = {'item_type': ['ring'], 'grade': ['s+grade'],
            'characteristic': ['luck'], 'bonus': [5],
            'quality': [90.0], 'price': [225]}
    c = dict(s, pending_drop=drop)
    d = diff_states(s, c)
    assert len(d['pending_drop']) == 1
    assert 'появилась' in d['pending_drop'][0]


def test_diff_pending_drop_resolved():
    drop = {'item_type': ['ring'], 'grade': ['s-grade'],
            'characteristic': ['luck'], 'bonus': [4],
            'quality': [70.0], 'price': [140]}
    s = GameState.default_new_game().to_dict()
    s['pending_drop'] = drop
    c = dict(s, pending_drop=None)
    d = diff_states(s, c)
    assert len(d['pending_drop']) == 1
    assert 'разрешена' in d['pending_drop'][0]


# ----- format_diff_cli -----

def test_format_cli_renders_all_changes():
    s = GameState.default_new_game().to_dict()
    c = dict(s, money=600.0, stamina=5, char_level=2,
             date_last_enter='2026-05-15')
    s['date_last_enter'] = '2026-05-14'
    out = format_diff_cli(diff_states(s, c))
    assert 'Изменения с сервера:' in out
    assert '💰' in out
    assert 'Stamina' in out
    assert '📈' in out  # char_level icon
    assert '📅' in out


# ----- format_diff_brief -----

def test_format_brief_money_with_sign():
    s = GameState.default_new_game().to_dict()
    c = dict(s, money=600.0)
    out = format_diff_brief(diff_states(s, c))
    assert '💰' in out
    assert '+600' in out  # subset of '+600.00'


def test_format_brief_skill_count():
    s = GameState.default_new_game().to_dict()
    c = dict(s, stamina=5, energy_max_skill=3, trader=10)
    out = format_diff_brief(diff_states(s, c))
    assert '🏋 +3 skills' in out


def test_format_brief_work_changed():
    s = GameState.default_new_game().to_dict()
    s['working'] = True
    c = dict(s, working=False)
    out = format_diff_brief(diff_states(s, c))
    assert '🏭' in out


def test_format_brief_multiple_categories():
    s = GameState.default_new_game().to_dict()
    s['date_last_enter'] = '2026-05-14'
    c = dict(s, money=600.0, stamina=5, working=True,
             date_last_enter='2026-05-15')
    out = format_diff_brief(diff_states(s, c))
    parts = out.split(' / ')
    assert any('💰' in p for p in parts)
    assert any('🏋' in p for p in parts)
    assert any('🏭' in p for p in parts)
    assert any('📅' in p for p in parts)
