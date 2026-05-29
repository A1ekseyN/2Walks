"""sync_diff — diff helpers для optimistic concurrency (4.54.3).

Сравнивает `snapshot` (deep-copy `state.to_dict()` в момент load'а — взятый
через `state.take_snapshot()`) с `current` (только что загруженный из Sheets
через `GameStateRepo().load()`) — возвращает структурированный список
изменений «что сервер сделал с момента моего load'а». Используется на STALE:

- CLI (4.54.5) — `format_diff_cli()` multi-line detailed для prompt.
- Web (4.54.6) — `format_diff_brief()` single-line иконками для toast.

Pure helpers без зависимостей от GameState — работают с dict-формой
напрямую (то что отдаёт `state.to_dict()`). Это позволяет тестировать без
конструирования полных GameState.

См. также: `state.GameState.take_snapshot()`, `google_sheets_db.save_safe()`.
"""

from typing import Any

from functions_02 import format_money


# Human-readable названия для Gym skills (key в state.to_dict() → label в UI).
# Те же что используются в Gym menu / web _GYM_SKILL_DISPLAY (по символическому
# смыслу — здесь без иконок, иконку добавляет format_diff_cli).
_GYM_SKILL_LABELS = {
    'stamina': 'Stamina',
    'energy_max_skill': 'Energy Max',
    'energy_regen_skill': 'Energy Regen',
    'speed_skill': 'Speed',
    'luck_skill': 'Luck',
    'move_optimization_adventure': 'Move Opt (Adventure)',
    'move_optimization_gym': 'Move Opt (Gym)',
    'move_optimization_work': 'Move Opt (Work)',
    'energy_optimization_adventure': 'Energy Opt (Adventure)',
    'energy_optimization_gym': 'Energy Opt (Gym)',
    'energy_optimization_work': 'Energy Opt (Work)',
    'neatness_in_using_things': 'Аккуратность',
    'money_saving': 'Money Saving',
    'earnings_boost': 'Earnings Boost',
    'trader': 'Trader',
    'banking_interest_rate': 'Bank Rate',
    'loan_capacity': 'Loan Capacity',
    'loan_interest_reduction': 'Loan Rate Reduction',
    'inspiration': 'Inspiration',
    'backpack_skill': 'Backpack',
    'mechanics': 'Mechanics',
    'it_technologies': 'IT Technologies',
}

_CHAR_LEVEL_SKILL_LABELS = {
    'lvl_up_skill_stamina': 'Stamina',
    'lvl_up_skill_energy_max': 'Energy Max',
    'lvl_up_skill_speed': 'Speed',
    'lvl_up_skill_luck': 'Luck',
    'lvl_up_skill_energy_regen': 'Energy Regen',
}

_EQUIPMENT_SLOT_LABELS = {
    'equipment_head': 'Голова',
    'equipment_neck': 'Шея',
    'equipment_torso': 'Торс',
    'equipment_finger_01': 'Палец 1',
    'equipment_finger_02': 'Палец 2',
    'equipment_legs': 'Ноги',
    'equipment_foots': 'Ступни',
    'equipment_back': 'Спина',  # 4.51 — рюкзак
}

_ADVENTURE_COUNTER_LABELS = {
    'adventure_walk_easy_counter': 'walk_easy',
    'adventure_walk_normal_counter': 'walk_normal',
    'adventure_walk_hard_counter': 'walk_hard',
    'adventure_walk_15k_counter': 'walk_15k',
    'adventure_walk_20k_counter': 'walk_20k',
    'adventure_walk_25k_counter': 'walk_25k',
    'adventure_walk_30k_counter': 'walk_30k',
}


# ---------- Public API ----------

def diff_states(snapshot: dict, current: dict) -> dict[str, list[str]]:
    """Структурированный diff по 13 категориям.

    Returns: `{category: [human_readable_line, ...]}`. Пустые категории
    остаются как `[]` (caller фильтрует). Каждая строка — готовый текст
    для отображения (с иконкой). Не зависит от colorama.
    """
    return {
        'money': _diff_money(snapshot, current),
        'steps': _diff_steps(snapshot, current),
        'energy': _diff_energy(snapshot, current),
        'gym': _diff_gym(snapshot, current),
        'char_level': _diff_char_level(snapshot, current),
        'work': _diff_work(snapshot, current),
        'training': _diff_training(snapshot, current),
        'adventure': _diff_adventure(snapshot, current),
        'inventory': _diff_inventory(snapshot, current),
        'equipment': _diff_equipment(snapshot, current),
        'bank': _diff_bank(snapshot, current),
        'date': _diff_date(snapshot, current),
        'pending_drop': _diff_pending_drop(snapshot, current),
    }


def has_changes(diff: dict[str, list[str]]) -> bool:
    """True если хотя бы одна категория содержит изменения."""
    return any(lines for lines in diff.values())


def format_diff_cli(diff: dict[str, list[str]]) -> str:
    """Multi-line detailed для CLI STALE prompt (4.54.5).

    Каждая строка — `  <line>` (с 2-space indent для prompt'а).
    """
    lines = []
    for category in diff.values():
        for change in category:
            lines.append(f'  {change}')
    if not lines:
        return '(нет изменений)'
    return 'Изменения с сервера:\n' + '\n'.join(lines)


def format_diff_brief(diff: dict[str, list[str]]) -> str:
    """Single-line иконками для web toast (4.54.6).

    Пример: `💰 +600.00 / 🏋 +2 skills / 🏭 смена окончена / 📅 day rollover`.
    """
    parts: list[str] = []
    if diff['money']:
        parts.append(_brief_money(diff['money']))
    n_skills = len(diff['gym']) + len(diff['char_level'])
    if n_skills:
        parts.append(f'🏋 +{n_skills} skill{"s" if n_skills > 1 else ""}')
    if diff['work']:
        parts.append('🏭 work changed')
    if diff['training']:
        parts.append('🎓 training changed')
    if diff['adventure']:
        parts.append('🗺 adventure changed')
    if diff['steps']:
        parts.append('🏃 steps changed')
    if diff['energy']:
        parts.append('🔋 energy changed')
    if diff['inventory']:
        parts.append('🎒 inventory changed')
    if diff['equipment']:
        parts.append('⚔ equipment changed')
    if diff['bank']:
        parts.append('🏛 bank changed')
    if diff['date']:
        parts.append('📅 day rollover')
    if diff['pending_drop']:
        parts.append('🎁 pending drop')
    if not parts:
        return '(нет изменений)'
    return ' / '.join(parts)


# ---------- per-category diffs (internal) ----------

def _fmt_int_delta(old: int, new: int) -> str:
    """`N → M (+/-D)` для целочисленных изменений."""
    delta = new - old
    sign = '+' if delta > 0 else ''
    return f'{old:,} → {new:,} ({sign}{delta:,})'


def _diff_money(s: dict, c: dict) -> list[str]:
    """`💰 Wallet: 1,133.20 → 1,733.20 (+600.00)`. Tolerance 0.005 (полкопейки)."""
    old = float(s.get('money') or 0)
    new = float(c.get('money') or 0)
    if abs(new - old) < 0.005:
        return []
    delta = new - old
    sign = '+' if delta > 0 else ''
    return [f'💰 Wallet: {format_money(old)} → {format_money(new)} '
            f'({sign}{format_money(delta)})']


def _diff_steps(s: dict, c: dict) -> list[str]:
    """Step-related fields (7): today/used/yesterday/can_use/daily_bonus/total_used/xp_bonus."""
    out = []
    for label, key in [('🏃 Сегодня (today)', 'steps_today'),
                       ('🏃 Доступно (can_use)', 'steps_can_use'),
                       ('🏃 Использовано (used)', 'steps_today_used'),
                       ('🏃 Вчера (yesterday)', 'steps_yesterday'),
                       ('🏃 Daily bonus', 'steps_daily_bonus'),
                       ('🏃 Total used', 'steps_total_used')]:
        old = int(s.get(key) or 0)
        new = int(c.get(key) or 0)
        if old != new:
            out.append(f'{label}: {_fmt_int_delta(old, new)}')
    # xp_bonus — float
    old_xp = float(s.get('steps_xp_bonus') or 0)
    new_xp = float(c.get('steps_xp_bonus') or 0)
    if abs(new_xp - old_xp) >= 0.5:
        out.append(f'🏃 XP bonus: {old_xp:,.0f} → {new_xp:,.0f}')
    return out


def _diff_energy(s: dict, c: dict) -> list[str]:
    """`🔋 Energy: 42 → 50`, `🔋 Energy Max: 60 → 65`."""
    out = []
    for label, key in [('🔋 Energy', 'energy'),
                       ('🔋 Energy Max', 'energy_max')]:
        old = int(s.get(key) or 0)
        new = int(c.get(key) or 0)
        if old != new:
            out.append(f'{label}: {_fmt_int_delta(old, new)}')
    return out


def _diff_gym(s: dict, c: dict) -> list[str]:
    """20 Gym skills. Каждый — отдельная строка если значение изменилось."""
    out = []
    for key, label in _GYM_SKILL_LABELS.items():
        old = int(s.get(key) or 0)
        new = int(c.get(key) or 0)
        if old != new:
            out.append(f'🏋 {label}: {old} → {new}')
    return out


def _diff_char_level(s: dict, c: dict) -> list[str]:
    """char_level + up_skills + 5 allocation skills."""
    out = []
    old_lvl = int(s.get('char_level') or 0)
    new_lvl = int(c.get('char_level') or 0)
    if old_lvl != new_lvl:
        out.append(f'📈 Char Level: {old_lvl} → {new_lvl}')
    old_up = int(s.get('char_level_up_skills') or 0)
    new_up = int(c.get('char_level_up_skills') or 0)
    if old_up != new_up:
        out.append(f'📈 Skill points available: {old_up} → {new_up}')
    for key, label in _CHAR_LEVEL_SKILL_LABELS.items():
        old = int(s.get(key) or 0)
        new = int(c.get(key) or 0)
        if old != new:
            out.append(f'📈 Allocation {label}: {old} → {new}')
    return out


def _diff_work(s: dict, c: dict) -> list[str]:
    """Work session — start/end/hours/active/work_type/salary."""
    out = []
    old_active = bool(s.get('working'))
    new_active = bool(c.get('working'))
    if old_active != new_active:
        if old_active and not new_active:
            old_type = s.get('work') or '?'
            old_hours = s.get('working_hours') or 0
            out.append(f'🏭 Work session: завершена (была {old_type}, {old_hours}ч)')
        else:
            new_type = c.get('work') or '?'
            new_hours = c.get('working_hours') or 0
            out.append(f'🏭 Work session: началась ({new_type}, {new_hours}ч)')
    elif new_active:
        old_hours = int(s.get('working_hours') or 0)
        new_hours = int(c.get('working_hours') or 0)
        if old_hours != new_hours:
            out.append(f'🏭 Work hours: {old_hours} → {new_hours}')
    return out


def _diff_training(s: dict, c: dict) -> list[str]:
    """Training session — active flag transition + skill_name."""
    out = []
    old_active = bool(s.get('skill_training'))
    new_active = bool(c.get('skill_training'))
    if old_active != new_active:
        if old_active and not new_active:
            old_name = s.get('skill_training_name') or '?'
            out.append(f'🎓 Training: завершена ({old_name})')
        else:
            new_name = c.get('skill_training_name') or '?'
            out.append(f'🎓 Training: началась ({new_name})')
    return out


def _diff_adventure(s: dict, c: dict) -> list[str]:
    """Adventure session + 7 counters."""
    out = []
    old_active = bool(s.get('adventure'))
    new_active = bool(c.get('adventure'))
    if old_active != new_active:
        if old_active and not new_active:
            old_name = s.get('adventure_name') or '?'
            out.append(f'🗺 Adventure: завершена ({old_name})')
        else:
            new_name = c.get('adventure_name') or '?'
            out.append(f'🗺 Adventure: началась ({new_name})')
    # Counters — сумма всех приключений по типам
    for key, label in _ADVENTURE_COUNTER_LABELS.items():
        old = int(s.get(key) or 0)
        new = int(c.get(key) or 0)
        if old != new:
            out.append(f'🗺 {label}: {_fmt_int_delta(old, new)}')
    return out


def _diff_inventory(s: dict, c: dict) -> list[str]:
    """Inventory — count + сводка по item_type."""
    old: list[dict] = s.get('inventory') or []
    new: list[dict] = c.get('inventory') or []
    if len(old) == len(new):
        # Тот же размер — проверим что состав не изменился (грубо по identity-keys).
        if _inventory_signature(old) == _inventory_signature(new):
            return []
    delta = len(new) - len(old)
    sign = '+' if delta > 0 else ''
    return [f'🎒 Inventory: {len(old)} → {len(new)} item{"s" if len(new) != 1 else ""} '
            f'({sign}{delta})']


def _inventory_signature(items: list[dict]) -> list[tuple]:
    """Sortable signature inventory'я: (item_type, grade, characteristic, quality, price).
    Используется для дешёвой проверки «изменился ли состав» без полной сериализации.
    """
    sig = []
    for item in items:
        try:
            sig.append((
                str(item.get('item_type', [None])[0]),
                str(item.get('grade', [None])[0]),
                str(item.get('characteristic', [None])[0]),
                float(item.get('quality', [0])[0] or 0),
                float(item.get('price', [0])[0] or 0),
            ))
        except (KeyError, IndexError, TypeError, ValueError):
            sig.append(('?', '?', '?', 0.0, 0.0))
    sig.sort()
    return sig


def _diff_equipment(s: dict, c: dict) -> list[str]:
    """7 equipment slots. Каждый swap/unequip/equip — отдельная строка."""
    out = []
    for key, label in _EQUIPMENT_SLOT_LABELS.items():
        old = s.get(key)
        new = c.get(key)
        old_desc = _item_brief(old) if old else 'пусто'
        new_desc = _item_brief(new) if new else 'пусто'
        if old_desc != new_desc:
            out.append(f'⚔ {label}: {old_desc} → {new_desc}')
    return out


def _item_brief(item: Any) -> str:
    """`Ring s-grade luck +4 (q.80)` — короткое описание item'а для diff."""
    if not isinstance(item, dict):
        return str(item)
    try:
        item_type = item.get('item_type', ['?'])[0]
        grade = item.get('grade', ['?'])[0]
        char = item.get('characteristic', ['?'])[0]
        bonus = item.get('bonus', [0])[0]
        quality = item.get('quality', [0])[0]
        return f'{str(item_type).title()} {grade} {char} +{bonus} (q.{round(float(quality), 0):.0f})'
    except (KeyError, IndexError, TypeError):
        return '(item)'


def _diff_bank(s: dict, c: dict) -> list[str]:
    """Bank — deposit_amount, loan_amount (timestamps игнорируем — слишком noisy)."""
    out = []
    for label, key in [('🏛 Депозит', 'bank_deposit_amount'),
                       ('🏛 Кредит', 'bank_loan_amount')]:
        old = float(s.get(key) or 0)
        new = float(c.get(key) or 0)
        if abs(new - old) < 0.005:
            continue
        delta = new - old
        sign = '+' if delta > 0 else ''
        out.append(f'{label}: {format_money(old)} → {format_money(new)} '
                   f'({sign}{format_money(delta)})')
    return out


def _diff_date(s: dict, c: dict) -> list[str]:
    """Day rollover detection."""
    old = s.get('date_last_enter') or ''
    new = c.get('date_last_enter') or ''
    if old != new:
        return [f'📅 Day rollover: {old or "(empty)"} → {new or "(empty)"}']
    return []


def _diff_pending_drop(s: dict, c: dict) -> list[str]:
    """Pending drop — None/dict transition."""
    old = s.get('pending_drop')
    new = c.get('pending_drop')
    if old is None and new is None:
        return []
    if old is None and new is not None:
        return [f'🎁 Pending drop: появилась находка ({_item_brief(new)})']
    if old is not None and new is None:
        return [f'🎁 Pending drop: разрешена (была {_item_brief(old)})']
    # Both not None — possibly changed item
    if _item_brief(old) != _item_brief(new):
        return [f'🎁 Pending drop: {_item_brief(old)} → {_item_brief(new)}']
    return []


# ---------- brief formatters (для format_diff_brief) ----------

def _brief_money(money_lines: list[str]) -> str:
    """Извлекает sign + сумму из `💰 Wallet: X → Y (+/-D)` для brief формата."""
    import re
    for line in money_lines:
        # Ищем (+X.XX) или (-X.XX) или (+X) в строке.
        m = re.search(r'\(([+\-][\d,]+\.?\d*)\)', line)
        if m:
            return f'💰 {m.group(1)}'
    return '💰 changed'
