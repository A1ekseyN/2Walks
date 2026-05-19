"""FastAPI 2Walks web — задачи 4.48.0 + 4.48.1.

Запуск локально для разработки:
    source .venv/bin/activate && uvicorn web.main:app --reload --host 127.0.0.1 --port 8008

Запуск с переменными окружения для VPS (отдельная задача 4.48.0.1):
    WEB_HOST=0.0.0.0 WEB_PORT=8008 uvicorn web.main:app

Endpoints:
- ``GET /healthz`` — health-check (smoke + future load balancer).
- ``GET /`` — dashboard read-only (stats / location / active sessions / inventory / equipment).
- ``GET /status`` — HTML-фрагмент того же содержимого dashboard'а; HTMX обновляет
  его каждые 15 секунд через ``hx-get="/status" hx-trigger="every 15s"``.

CLI (``python game.py``) и web (``uvicorn``) — отдельные процессы. В MVP
запускаем что-то одно за раз; sync resolution — задача 4.54.
"""

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from bonus import (
    apply_earnings_boost,
    apply_money_saving,
    apply_move_optimization_gym,
    backpack_capacity,
    daily_steps_bonus,
    equipment_bonus_stamina_steps,
    level_steps_bonus,
)
from characteristics import game, init_game_state
from skill_training_data import skill_training_table
from gym import (
    Skill_Training,
    _apply_speed_bonus,
    skill_training_check_done,
)
from equipment_bonus import (
    equipment_energy_max_bonus,
    equipment_luck_bonus,
    equipment_speed_skill_bonus,
    equipment_stamina_bonus,
)
from functions import bonus_percentage, energy_time_charge, save_game_date_last_enter, total_bonus_steps
from functions_02 import format_hours, format_minutes, format_money
from skill_bonus import speed_skill_equipment_and_level_bonus
from google_sheets_db import StepsLogRepo
from inventory import Wear_Equipped_Items
from level import CharLevel
from locations import icon_loc
from skill_bonus import stamina_skill_bonus_def
from web.sync import get_last_reload, persist_state_to_cloud, try_reload_state
from work import Work, _speed_bonus_pct, work_check_done


from version import VERSION

# UI-метаданные для вакансий (key — атрибут в Work.work_requirements).
_WORK_DISPLAY = {
    "watchman":     {"title": "Сторож",     "icon": "🛡"},
    "factory":      {"title": "Завод",      "icon": "🏭"},
    "courier_foot": {"title": "Курьер",     "icon": "🚲"},
    "forwarder":    {"title": "Экспедитор", "icon": "🚚"},
}


def _max_work_hours(state, requirements: dict) -> int:
    """Сколько часов работы покрывают текущие ресурсы (cap 8).

    Since 0.2.4j (task 4.22) — energy cap учитывает `apply_energy_optimization_work`
    (total approach): loop ищет максимальное h при котором optimized total ≤
    state.energy. Без этого max_hours был бы консервативным.
    """
    from bonus import apply_energy_optimization_work
    steps_cap = state.steps.can_use // requirements['steps'] if requirements['steps'] > 0 else 0
    per_hour_energy = requirements['energy']
    if per_hour_energy > 0:
        # Loop по убыванию (max 8 итераций).
        energy_cap = 0
        for h in range(8, 0, -1):
            if apply_energy_optimization_work(per_hour_energy * h, state) <= state.energy:
                energy_cap = h
                break
    else:
        energy_cap = 8
    return int(min(steps_cap, energy_cap, 8))


def _format_real_time(minutes: int) -> str:
    """Форматирует целое число минут в `Xh Ym` / `Xh` / `Ym`.

    Примеры: 60 → "1h", 90 → "1h 30m", 45 → "45m", 0 → "0m"."""
    h_part, m_part = divmod(int(minutes), 60)
    if h_part == 0:
        return f"{m_part}m"
    if m_part == 0:
        return f"{h_part}h"
    return f"{h_part}h {m_part}m"


def _build_hour_options(state, req: dict, max_hours: int) -> list:
    """Список pre-computed данных для кнопок выбора часов работы.

    Каждая запись — dict `{h, steps, energy, salary, real_time}` где
    steps/energy/salary уже умножены на h, а `real_time` — реальное
    время смены с учётом speed-бонуса (как в work.py:check_requirements:
    `raw_duration - raw_duration * speed_bonus_pct / 100`).

    Salary — после `apply_earnings_boost` (4.23): игрок видит итоговую
    сумму с бонусом в кнопках web Gym, а не базовую цифру.

    Шаблон рендерит формат
    `{h}h 🕑 {real_time} · 🏃 -{steps} · 🔋 -{energy} · 💰 +{salary}` без
    арифметики в Jinja (4.48.5 follow-up — pre-compute в Python).
    """
    from bonus import apply_energy_optimization_work
    speed_bonus_pct = _speed_bonus_pct(state)
    effective_salary = apply_earnings_boost(req['salary'], state)
    return [
        {
            "h": h,
            "steps": h * req['steps'],
            # 0.2.4j (task 4.22) — apply_energy_optimization_work на TOTAL
            # (per_hour × h), не per-hour. Это убирает плато на low-base работах.
            "energy": apply_energy_optimization_work(h * req['energy'], state),
            "salary": round(h * effective_salary, 2),
            "real_time": _format_real_time(round(h * 60 * (1 - speed_bonus_pct / 100))),
        }
        for h in range(1, max_hours + 1)
    ]


def _build_work_vacancies(state) -> list:
    """Собирает данные для меню выбора вакансии (не работаешь).

    salary_per_hour — итоговая ставка с учётом earnings_boost (4.23).
    """
    work_helper = Work(state)
    vacancies = []
    for key, req in work_helper.work_requirements.items():
        meta = _WORK_DISPLAY.get(key, {"title": key.title(), "icon": "🏭"})
        max_hours = _max_work_hours(state, req)
        vacancies.append({
            "key": key,
            "title": meta["title"],
            "icon": meta["icon"],
            "steps_per_hour": req['steps'],
            "energy_per_hour": req['energy'],
            "salary_per_hour": apply_earnings_boost(req['salary'], state),
            "max_hours": max_hours,
            "hour_options": _build_hour_options(state, req, max_hours),
        })
    return vacancies


# 4.54.6 — Sentinel marker для STALE-конфликта. Validators возвращают это
# вместо обычной ошибки, endpoint'ы детектят и рендерят stale-fragment с
# auto-reload через 2 сек. Сама строка никогда не показывается игроку —
# чисто internal signal.
STALE_MARKER = "__STALE__"


def _persist_and_handle_stale(endpoint: str = "") -> Optional[str]:
    """4.54.6 — wraps persist_state_to_cloud, на STALE возвращает brief diff.

    Returns:
    - None — OK, продолжаем обычный flow.
    - brief diff string — STALE, caller возвращает stale-fragment.

    Логирует `log_event('sync_conflict', source='web', diff=..., endpoint=...)`.

    4.48.3 — На успешный persist сбрасывает `state.last_adventure_drop`
    («🎁 Находка» banner). Реализует «исчезает после любого mutation» поведение.
    """
    status = persist_state_to_cloud()
    if status != "STALE":
        # 4.48.3 — clear adventure drop notification на успешный mutation.
        if game.state is not None:
            game.state.last_adventure_drop = None
        return None
    # Build brief diff для toast.
    from google_sheets_db import GameStateRepo
    from sync_diff import diff_states, format_diff_brief, has_changes
    try:
        fresh = GameStateRepo().load()
    except Exception:  # noqa: BLE001
        fresh = {}
    snapshot = game.state.last_loaded_snapshot or {} if game.state else {}
    diff = diff_states(snapshot, fresh)
    brief = format_diff_brief(diff) if has_changes(diff) else "состояние обновилось"
    from history import log_event
    log_event('sync_conflict', source='web', diff=brief, endpoint=endpoint)
    return brief


def _stale_response() -> HTMLResponse:
    """4.54.6 — HTML fragment для HTMX swap при STALE.

    Самостоятельно вычисляет brief diff (вне зависимости от того кто и где
    обнаружил STALE) — fresh load Sheets vs `state.last_loaded_snapshot`,
    через `sync_diff.format_diff_brief`. Содержит toast с diff'ом и JS-
    таймером `window.location.reload()` через 2 сек.

    Используется всеми web mutation endpoint'ами при STALE_MARKER от
    validator'ов. Double-load неэффективен (validator уже загружал для
    log_event), но STALE — rare event, оптимизация не критична.
    """
    from google_sheets_db import GameStateRepo
    from sync_diff import diff_states, format_diff_brief, has_changes
    try:
        fresh = GameStateRepo().load()
    except Exception:  # noqa: BLE001
        fresh = {}
    snapshot = game.state.last_loaded_snapshot or {} if game.state else {}
    diff = diff_states(snapshot, fresh)
    brief = format_diff_brief(diff) if has_changes(diff) else "состояние обновилось"
    html = (
        f'<div id="status-bar" class="stale-toast" '
        f'style="padding:1rem; background:#ffd2d2; '
        f'border:2px solid #d33; border-radius:.5rem; '
        f'color:#600; font-weight:bold;">'
        f'⚠️ Состояние обновлено извне: {brief}. Перезагружаю...'
        f'</div>'
        f'<script>setTimeout(function(){{window.location.reload();}}, 2000);</script>'
    )
    return HTMLResponse(html)


def _stale_json_response() -> JSONResponse:
    """4.54.6 — JSON-вариант STALE response для API endpoint'ов.

    Возвращает 409 Conflict с brief diff. JSON-клиенты (curl / iPhone Shortcut)
    интерпретируют stale=true как «попробуйте позже» — ретрай не делаем
    автоматически, чтобы не залить serverr.
    """
    from google_sheets_db import GameStateRepo
    from sync_diff import diff_states, format_diff_brief, has_changes
    try:
        fresh = GameStateRepo().load()
    except Exception:  # noqa: BLE001
        fresh = {}
    snapshot = game.state.last_loaded_snapshot or {} if game.state else {}
    diff = diff_states(snapshot, fresh)
    brief = format_diff_brief(diff) if has_changes(diff) else "состояние обновилось"
    return JSONResponse(
        {"ok": False, "stale": True, "diff": brief,
         "error": "External state update detected — reload required."},
        status_code=409,
    )


def _validate_and_apply_work(state, work_type: str, hours: int) -> Optional[str]:
    """Валидирует work_type/hours, применяет смену через Work.check_requirements
    + Wear_Equipped_Items.decrease_durability. На успехе синкает state в
    Sheets+CSV+JSON через _persist_state_to_cloud(). Возвращает текст ошибки
    или None.

    Используется тремя endpoint'ами (web/api start + add_hours)."""
    if work_type not in _WORK_DISPLAY:
        return f"Неизвестная вакансия: {work_type}"
    if not (1 <= hours <= 8):
        return f"Часы должны быть в диапазоне 1-8 (было: {hours})"

    work_helper = Work(state)
    req = work_helper.work_requirements[work_type]
    max_hours = _max_work_hours(state, req)
    if hours > max_hours:
        return (f"Не хватает ресурсов: максимум {max_hours} ч "
                f"(нужно {hours * req['steps']} 🏃 + {hours * req['energy']} 🔋)")

    # Work.check_requirements делает try_spend + start_work.
    if not work_helper.check_requirements(work_type, hours):
        return "Не удалось списать ресурсы (race condition?)"
    # Износ экипировки — как в CLI (Work.ask_hours делает это после check_requirements).
    Wear_Equipped_Items(state).decrease_durability(hours * req['steps'])
    # Persist: state.work теперь active=True, но без записи в Sheets/CSV
    # игрок потеряет смену при рестарте uvicorn'а или при reload через 4.54.0.
    # 4.54.6 — STALE marker propagation для optimistic concurrency.
    stale = _persist_and_handle_stale(endpoint='work')
    if stale:
        return STALE_MARKER
    return None


# Skill allocation (4.48.8) — отображаемые навыки и эффект.
_SKILL_DISPLAY = {
    "stamina":      {"title": "Stamina",      "icon": "🏃",   "effect": "+1 % к общему количеству шагов"},
    "energy_max":   {"title": "Energy Max",   "icon": "🔋",   "effect": "+1 ед. к общему запасу энергии"},
    "speed":        {"title": "Speed",        "icon": "⚡",   "effect": "+1 % к скорости активностей"},
    "energy_regen": {"title": "Energy Regen", "icon": "🔋⚡", "effect": "+1 % к скорости регенерации энергии"},
    "luck":         {"title": "Luck",         "icon": "🍀",   "effect": "+1 % к удаче дропа"},
}


def _validate_and_apply_skill_allocation(state, skill: str) -> Optional[str]:
    """Валидирует skill, инкрементирует выбранный char_level.skill_<X> на +1
    и декрементирует up_skills. На успехе persist. Возвращает текст ошибки
    или None.

    Используется двумя endpoint'ами (web/api allocate)."""
    if skill not in _SKILL_DISPLAY:
        return f"Неизвестный навык: {skill}"
    if state.char_level.up_skills < 1:
        return "Нет доступных очков навыков для распределения."

    # Атрибут в state.char_level именуется `skill_<key>` для всех 4.
    attr = f"skill_{skill}"
    new_level = getattr(state.char_level, attr) + 1
    setattr(state.char_level, attr, new_level)
    state.char_level.up_skills -= 1
    # 4.6 — log_event распределения очка навыка через web.
    from history import log_event
    log_event('skill_alloc', skill=skill, new_level=new_level)
    stale = _persist_and_handle_stale(endpoint='skill_alloc')
    if stale:
        return STALE_MARKER
    return None


# Gym skill training (4.48.4) — UI-метаданные.
# `field` — атрибут в state.gym, через который читается current level. Для
# 'energy_max_skill' field теперь корректно совпадает с именем (после унификации
# в 0.2.1g / 4.48.4.1 — старый ключ 'energy_max' переименован в 'energy_max_skill').
_GYM_SKILL_DISPLAY: dict[str, dict[str, Any]] = {
    "stamina": {
        "title": "Stamina", "icon": "🏃",
        "field": "stamina",
        "effect": "+1 % к общему кол-во шагов",
        "available": True,
    },
    "energy_max_skill": {
        "title": "Energy Max", "icon": "🔋",
        "field": "energy_max_skill",
        "effect": "+1 ед. к макс энергии",
        "available": True,
    },
    "energy_regen_skill": {
        "title": "Регенерация энергии", "icon": "🔋⚡",
        "field": "energy_regen_skill",
        "effect": "+1 % к скорости регенерации энергии",
        "available": True,
    },
    "speed_skill": {
        "title": "Speed", "icon": "⚡",
        "field": "speed_skill",
        "effect": "+1 % к скорости активностей",
        "available": True,
    },
    "luck_skill": {
        "title": "Luck", "icon": "🍀",
        "field": "luck_skill",
        "effect": "+1 % к удаче дропа",
        "available": True,
    },
    "move_optimization_adventure": {
        "title": "Move Optimization (Adventure)", "icon": "🗺️",
        "field": "move_optimization_adventure",
        "effect": "-1 % шагов на приключения",
        "available": True,
    },
    "move_optimization_gym": {
        "title": "Move Optimization (Gym)", "icon": "🏋",
        "field": "move_optimization_gym",
        "effect": "-1 % шагов на тренировки",
        "available": True,
    },
    "move_optimization_work": {
        "title": "Move Optimization (Work)", "icon": "🏭",
        "field": "move_optimization_work",
        "effect": "-1 % шагов на работу",
        "available": True,
    },
    "energy_optimization_adventure": {
        "title": "Экономия энергии в Adventure", "icon": "🗺️⚡",
        "field": "energy_optimization_adventure",
        "effect": "-1 % энергии на приключения (мин 1)",
        "available": True,
    },
    "energy_optimization_gym": {
        "title": "Экономия энергии в Gym", "icon": "🏋⚡",
        "field": "energy_optimization_gym",
        "effect": "-1 % энергии на тренировки (мин 1)",
        "available": True,
    },
    "energy_optimization_work": {
        "title": "Экономия энергии в Work", "icon": "🏭⚡",
        "field": "energy_optimization_work",
        "effect": "-1 % энергии на смену, применяется к total (мин 1)",
        "available": True,
    },
    "neatness_in_using_things": {
        "title": "Neatness", "icon": "🧰",
        "field": "neatness_in_using_things",
        "effect": "-1 % износ экипировки",
        "available": True,
    },
    "money_saving": {
        "title": "Экономия денег", "icon": "🏷",
        "field": "money_saving",
        "effect": "−1 % к стоимости трат (Спортзал, Магазин)",
        "available": True,
    },
    "earnings_boost": {
        "title": "Бонус к зарплате", "icon": "💵",
        "field": "earnings_boost",
        "effect": "+1 % к зарплате на работе",
        "available": True,
    },
    "trader": {
        "title": "Торговец", "icon": "💎",
        "field": "trader",
        "effect": "+1 % к цене продажи предметов",
        "available": True,
    },
    "banking_interest_rate": {
        "title": "Банковская ставка", "icon": "🏦",
        "field": "banking_interest_rate",
        "effect": "+1 % к годовой ставке депозита",
        "available": True,
    },
    "loan_capacity": {
        "title": "Кредитный лимит", "icon": "💳",
        "field": "loan_capacity",
        "effect": "+100 $ к максимальной сумме кредита",
        "available": True,
    },
    "loan_interest_reduction": {
        "title": "Снижение ставки по кредиту", "icon": "📉",
        "field": "loan_interest_reduction",
        "effect": "−1 % к годовой ставке кредита",
        "available": True,
    },
    "inspiration": {
        "title": "Обучение", "icon": "📚",
        "field": "inspiration",
        "effect": "+1 % к опыту персонажа за потраченные шаги",
        "available": True,
    },
    "backpack_skill": {
        "title": "Размер инвентаря", "icon": "🎒",
        "field": "backpack_skill",
        "effect": "+1 слот к рюкзаку (база 10)",
        "available": True,
    },
}


def _build_gym_skills(state) -> list:
    """Pre-computed список 8 gym-навыков для UI прокачки.

    Каждая запись — dict `{key, title, icon, effect, current_level, next_level,
    cost: {steps, energy, money, time, real_time}, can_afford, missing,
    available, unavailable_reason}`. Стоимость берётся из
    `skill_training_table[next_level]` с поправкой move_optimization_gym
    (steps) и speed-бонусом (real_time).
    """
    options = []
    for key, meta in _GYM_SKILL_DISPLAY.items():
        current = getattr(state.gym, meta["field"])
        next_level = current + 1

        # Cost lookup. skill_training_table может не содержать высоких уровней —
        # тогда стартовать нельзя, missing.cost = True.
        cost_raw = skill_training_table.get(next_level)
        if cost_raw is None:
            options.append({
                "key": key,
                "title": meta["title"],
                "icon": meta["icon"],
                "effect": meta["effect"],
                "current_level": current,
                "next_level": next_level,
                "cost": None,
                "can_afford": False,
                "missing": {"max_level": True},
                "available": False,
                "unavailable_reason": "Достигнут максимум по таблице.",
            })
            continue

        from bonus import apply_energy_optimization_gym
        steps_needed = apply_move_optimization_gym(cost_raw["steps"], state)
        energy_needed = apply_energy_optimization_gym(cost_raw["energy"], state)  # 4.22
        money_needed = apply_money_saving(cost_raw["money"], state)  # 4.20 — float после скидки
        real_minutes = round(_apply_speed_bonus(cost_raw["time"], state))

        missing = {}
        if state.steps.can_use < steps_needed:
            missing["steps"] = steps_needed - state.steps.can_use
        if state.energy < energy_needed:
            missing["energy"] = energy_needed - state.energy
        if state.money < money_needed:
            missing["money"] = money_needed - state.money

        options.append({
            "key": key,
            "title": meta["title"],
            "icon": meta["icon"],
            "effect": meta["effect"],
            "current_level": current,
            "next_level": next_level,
            "cost": {
                "steps": steps_needed,
                "energy": energy_needed,
                "money": money_needed,
                "time": cost_raw["time"],
                "real_time": _format_real_time(real_minutes),
            },
            "can_afford": not missing,
            "missing": missing,
            "available": meta["available"],
            "unavailable_reason": meta.get("unavailable_reason"),
        })
    return options


def _validate_and_apply_training(state, skill_name: str) -> Optional[str]:
    """Валидирует skill_name + наличие активной тренировки + ресурсы. На успехе
    стартует тренировку через CLI helper Skill_Training.start_skill_training()
    (try_spend + start_training + Wear_Equipped_Items.decrease_durability),
    зовёт persist_state_to_cloud(). Возвращает текст ошибки или None."""
    if skill_name not in _GYM_SKILL_DISPLAY:
        return f"Неизвестный навык: {skill_name}"
    meta = _GYM_SKILL_DISPLAY[skill_name]
    if not meta.get("available", True):
        reason: str = meta.get("unavailable_reason", f"Навык '{skill_name}' недоступен.")
        return reason
    if state.training.active:
        return "Тренировка уже идёт — дождись окончания текущей."

    # Pre-flight check ресурсов до try_spend, чтобы вернуть осмысленный текст.
    field = meta["field"]
    current = getattr(state.gym, field)
    next_level = current + 1
    cost_raw = skill_training_table.get(next_level)
    if cost_raw is None:
        return f"Навык '{skill_name}' достиг максимума по таблице (lvl {current})."

    from bonus import apply_energy_optimization_gym
    steps_needed = apply_move_optimization_gym(cost_raw["steps"], state)
    energy_needed = apply_energy_optimization_gym(cost_raw["energy"], state)  # 4.22
    money_needed = apply_money_saving(cost_raw["money"], state)
    if state.steps.can_use < steps_needed:
        return f"Не хватает 🏃: нужно {steps_needed}, есть {state.steps.can_use}."
    if state.energy < energy_needed:
        return f"Не хватает 🔋: нужно {energy_needed}, есть {state.energy}."
    if state.money < money_needed:
        return f"Не хватает 💰: нужно {format_money(money_needed)}, есть {format_money(state.money)}."

    # Старт через существующий CLI helper. Skill_Training.check_requirements
    # печатает в stdout (CLI noise — допустимо в uvicorn логе) и при недостаче
    # рекурсивно вызывает gym_menu (который заблокируется на input()).
    # Поэтому мы сами проверили ресурсы выше и сразу вызываем start_skill_training.
    state.training.skill_name = skill_name  # CLI делает это в gym_menu до Skill_Training
    skill_training = Skill_Training(state=state, name=skill_name)
    skill_training.start_skill_training()
    Wear_Equipped_Items(state).decrease_durability(steps_needed)
    stale = _persist_and_handle_stale(endpoint='gym_start')
    if stale:
        return STALE_MARKER
    return None


def _build_pending_drop_view(state) -> dict:
    """4.50.2 — Pre-computed данные для pending-drop баннера (web).

    Распаковывает list-обёртки legacy item-формата (item['grade'][0] и т.д.)
    в плоский dict для удобного рендера в Jinja. Если pending=None — возвращает
    `{active: False, item: None}`. Bench: вызывается из `_dashboard_context`
    на каждом рендере, выполнение копеечное.
    """
    if state.pending_drop is None:
        return {"active": False, "item": None}
    p = state.pending_drop

    def _first(values):
        if not values:
            return None
        return values[0]

    item = {
        "type": _first(p.get("item_type")),
        "grade": _first(p.get("grade")),
        "characteristic": _first(p.get("characteristic")),
        "bonus": _first(p.get("bonus")),
        "quality": _first(p.get("quality")),
        "price": _first(p.get("price")) or 0,
    }
    return {"active": True, "item": item}


def _build_skill_options(state) -> list:
    """Pre-computed данные для UI распределения навыков. Каждая запись — dict
    `{key, title, icon, effect, current}` где current = state.char_level.skill_<key>."""
    return [
        {
            "key": key,
            "title": meta["title"],
            "icon": meta["icon"],
            "effect": meta["effect"],
            "current": getattr(state.char_level, f"skill_{key}"),
        }
        for key, meta in _SKILL_DISPLAY.items()
    ]


TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["format_hours"] = format_hours
templates.env.globals["format_money"] = format_money
templates.env.globals["format_minutes"] = format_minutes


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_game_state()
    yield


app = FastAPI(title="2Walks Web", version=VERSION, lifespan=lifespan)

# Static files (0.2.4l) — apple-touch-icon (180×180 PNG для iOS home-screen),
# CSS / future assets. Mount по пути /static. Файл генерируется через
# scripts/generate_favicon.py (один раз, Pillow — dev-only зависимость).
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


def _compute_progress_pct(start_ts, end_ts, now_ts) -> float:
    """Процент выполнения активной сессии. Защита от деления на ноль / отрицательного.

    Возвращает значение в диапазоне [0, 100]. Если start/end отсутствуют или
    end <= start (не должно быть в нормальной игре, но edge case) — возвращает 0.
    """
    if start_ts is None or end_ts is None or end_ts <= start_ts:
        return 0.0
    return float(max(0.0, min(100.0, (now_ts - start_ts) / (end_ts - start_ts) * 100)))


class StepsAppliedResult:
    """Результат применения новых шагов через `_apply_new_steps()`."""
    def __init__(self, applied: bool, steps_today: int, steps_can_use: int,
                 logged: bool, error: Optional[str] = None):
        self.applied = applied
        self.steps_today = steps_today
        self.steps_can_use = steps_can_use
        self.logged = logged
        self.error = error


def _apply_new_steps(steps_value: int, source: str = "web",
                     ts: Optional[float] = None) -> StepsAppliedResult:
    """Применяет новое значение шагов к state и пишет в steps_log.

    Контракт (4.48.2):
    - Validation: `steps_value > state.steps.today` (строго больше). Иначе
      возвращается applied=False (state не меняется).
    - Sheets log пишется ДО применения к state. Если падает — state не меняется,
      возвращается applied=False + error.
    - При успехе: state.steps.today обновляется, steps.can_use пересчитывается.
    - Day rollover (4.54.0.2): перед валидацией зовём save_game_date_last_enter
      — если игрок открыл страницу вчера и submit'ит сегодня (или вкладка живёт
      через midnight без F5), state.steps.today обнулится и валидация пройдёт.
      Без этого ввод "100 шагов" блокировался stale значением вчерашних 8k.
    - source — 'web' / 'manual' / 'auto' / etc; пишется в steps_log.
    """
    state = game.state
    if state is None:
        return StepsAppliedResult(False, 0, 0, False, "state not initialized")

    # Day rollover (4.54.0.2): если первое действие на новый день идёт через
    # POST /api/steps (например с iPhone Shortcut, без предварительного GET /),
    # state в RAM ещё с вчера. Без этой проверки ввод "100 шагов" отвергся бы
    # как меньше вчерашних. Если rollover фактически произошёл — persist
    # свежий state, чтобы CLI и web видели одно и то же.
    old_date = state.date_last_enter
    save_game_date_last_enter(state)
    if state.date_last_enter != old_date:
        persist_state_to_cloud()

    if steps_value <= state.steps.today:
        return StepsAppliedResult(
            applied=False,
            steps_today=state.steps.today,
            steps_can_use=state.steps.can_use,
            logged=False,
            error=f"Введённое значение должно быть больше текущего ({state.steps.today}).",
        )

    # Пишем в Sheets первым — если упадёт, state не трогаем.
    log_ts = ts if ts is not None else datetime.now().timestamp()
    try:
        StepsLogRepo().append(ts=log_ts, steps=steps_value, source=source)
    except Exception as e:
        return StepsAppliedResult(
            applied=False,
            steps_today=state.steps.today,
            steps_can_use=state.steps.can_use,
            logged=False,
            error=f"Sheets unavailable: {e}",
        )

    # Применяем к state в памяти (max-merge).
    previous = state.steps.today
    state.steps.today = steps_value
    state.steps.can_use = state.steps.today - state.steps.used + total_bonus_steps(state)
    # 4.6 — log_event ввода шагов через web / api.
    from history import log_event
    log_event('steps_set', source=source, value=steps_value, previous=previous)

    # 4.48.3 — clear «🎁 Находка» banner: steps submit это user-mutation,
    # banner должен исчезнуть. Steps не идут через _persist_and_handle_stale
    # (steps_log append-only, без save_safe) — clearing здесь explicit.
    state.last_adventure_drop = None

    return StepsAppliedResult(
        applied=True,
        steps_today=state.steps.today,
        steps_can_use=state.steps.can_use,
        logged=True,
    )


def _dashboard_context(request: Request, steps_error: Optional[str] = None,
                       steps_form_open: bool = False,
                       work_error: Optional[str] = None,
                       skill_error: Optional[str] = None,
                       gym_error: Optional[str] = None,
                       drop_error: Optional[str] = None,
                       adventure_error: Optional[str] = None) -> dict:
    """Собирает все данные, нужные dashboard и status-fragment шаблонам.

    `steps_error` / `steps_form_open` — флаги для отрисовки формы ввода шагов:
    при ошибке валидации/Sheets форма остаётся открытой с подсказкой.

    `work_error` — текст ошибки от валидации Work-формы (показывается прямо
    в блоке Work). При None — никаких сообщений.

    `skill_error` — аналогично для блока Skills (4.48.8).
    """
    state = game.state
    if state is None:
        raise RuntimeError("game.state не инициализирован — должен быть вызван init_game_state() в lifespan.")

    # Day rollover (4.54.0.2). Defense-in-depth: основной триггер —
    # try_reload_state на GET /, но если вкладка живёт через midnight и
    # делает только submit формы (которые не зовут try_reload_state), без
    # этой проверки рендер показал бы вчерашние today/used/daily_bonus.
    # save_game_date_last_enter idempotent: на тот же день no-op.
    save_game_date_last_enter(state)

    # Energy regen (0.2.1c follow-up). Каждый рендер пересчитываем энергию
    # по той же формуле, что в CLI (functions.energy_time_charge). Persist
    # в Sheets/CSV не делаем — энергия меняется часто, дёргать Sheets на
    # каждый F5 бессмысленно. При следующей mutation (work start / steps)
    # persist подтянет актуальный state. Если uvicorn рестартанётся —
    # state.energy_time_stamp из Sheets всё ещё валидный, на первый
    # рендер energy_time_charge досчитает прирост за пропущенное время.
    energy_time_charge(state)

    # Level-up detection (0.2.1d / 4.48.8). В CLI update_level() вызывается
    # из status_bar на каждом тике; в web без этой проверки уровень не
    # апается даже после прохождения порога total_used. Web-only игрок
    # никогда не увидел бы очков навыков. Persist если level фактически
    # изменился — иначе CLI после рестарта не увидит новый level (и start_*
    # mutation тоже подхватит, но это требует от игрока что-то сделать).
    char_level = CharLevel(state)
    pre_level = state.char_level.level
    char_level.update_level()
    if state.char_level.level != pre_level:
        persist_state_to_cloud()

    # Auto-finalize тренировки навыка (4.48.4 / 0.2.1e). Если state.training.end
    # < now — повышает уровень навыка на +1 и сбрасывает state.training.
    # save_characteristic вызывается внутри skill_training_check_done.
    # GameStateRepo.save отдельно не зовём — на следующее web-mutation
    # snapshot подтянется. Но если game_state Sheets важен, persist здесь
    # нужен — для согласованности с work_check_done (который тоже без persist
    # в Sheets, только save_characteristic локально). Остаётся та же
    # известная проблема double-claim race (см. TASKS 4.48.5.1).
    skill_training_check_done(state)

    # Auto-finalize работы по таймеру: каждый рендер dashboard'а / fragment'а
    # проверяет state.work.end и если время вышло — начисляет зарплату и
    # обнуляет смену. Так web-сценарий не требует отдельного "Claim"-клика
    # (CLI делает то же самое в main loop'е).
    work_check_done(state)

    # 4.48.3 — Auto-finalize приключения по таймеру + захват дропа для
    # «🎁 Находка» banner'а. Wrapper-helper детектит transition
    # active=True→False через delta inventory/pending_drop и пишет item в
    # state.last_adventure_drop (runtime-only). Banner живёт сквозь F5,
    # очищается в _persist_and_handle_stale на любом успешном mutation.
    _finalize_adventure_with_drop_capture(state)

    # 4.50.2 — Auto-collect pending drop если место освободилось (продажа
    # предмета / прокачка backpack_skill / снятие экипировки) с момента
    # последнего рендера. Симметрично CLI main loop'у в game.py.
    # Persist обязателен: иначе после перезагрузки CLI вытащит stale snapshot
    # и pending воскреснет. Помещаем ПОСЛЕ всех auto-finalize'ов чтобы любое
    # освобождение слота из них (work / training не освобождают, но для
    # будущих расширений) тоже попало под этот хук.
    from bonus import auto_collect_pending_drop
    if auto_collect_pending_drop(state) is not None:
        persist_state_to_cloud()

    # Параметры для JS-таймера энергии в _status_fragment.html (data-attrs).
    # JS раз в 60 сек обновляет цифру, считая `min(energy + floor((now-stamp)/interval), max)`.
    # 0.2.4i (task 4.21) — interval теперь зависит от energy_regen_skill, не speed_skill.
    from bonus import energy_regen_interval
    energy_interval_sec = energy_regen_interval(60, state)
    # Computed energy_max (4.48.4.1 / 0.2.1g) — теперь не читается из state-кэша,
    # вычисляется из источников каждый рендер.
    from bonus import compute_energy_max
    energy_max_now = compute_energy_max(state)

    # char_level уже создан выше (для update_level call) — переиспользуем.
    now_ts = datetime.now().timestamp()

    # Active sessions — конвертируем datetime в Unix timestamp для JS-таймера и progress-bar.
    training_start_ts = state.training.timestamp if state.training.active and state.training.timestamp else None
    training_end_ts = state.training.time_end.timestamp() if state.training.active and state.training.time_end else None
    work_start_ts = state.work.start.timestamp() if state.work.active and state.work.start else None
    work_end_ts = state.work.end.timestamp() if state.work.active and state.work.end else None
    # 4.23 — earnings_boost preview для активной смены. salary в state базовая,
    # эффективная вычисляется на лету (recompute — реагирует на прокачку skill).
    work_effective_salary = apply_earnings_boost(state.work.salary, state) if state.work.active else 0.0
    work_effective_total = round(work_effective_salary * state.work.hours, 2) if state.work.active else 0.0
    # Adventure start_ts/end_ts уже хранятся как float timestamps.
    adv_start_ts = state.adventure.start_ts if state.adventure.active and state.adventure.start_ts else None
    adv_end_ts = state.adventure.end_ts if state.adventure.active and state.adventure.end_ts else None

    adventure_finished = (
        state.adventure.active
        and adv_end_ts is not None
        and adv_end_ts <= now_ts
    )

    # Initial server-side значения прогресс-баров (клиент будет двигать раз в секунду).
    # Work progress вернулся в 0.2.1v (запрос пользователя) — без подписи %, чисто бар.
    training_progress = _compute_progress_pct(training_start_ts, training_end_ts, now_ts)
    work_progress = _compute_progress_pct(work_start_ts, work_end_ts, now_ts)
    adv_progress = _compute_progress_pct(adv_start_ts, adv_end_ts, now_ts)

    # Уровень навыка для текущей тренировки — для отображения "до какого уровня".
    training_skill_target = None
    if state.training.active and state.training.skill_name:
        try:
            training_skill_target = getattr(state.gym, state.training.skill_name) + 1
        except AttributeError:
            training_skill_target = None

    # Кол-во занятых слотов экипировки (для summary `(N/7)`).
    equipment_slots_list = [
        state.equipment.head, state.equipment.neck, state.equipment.torso,
        state.equipment.finger_01, state.equipment.finger_02,
        state.equipment.legs, state.equipment.foots,
    ]
    equipment_worn = sum(1 for s in equipment_slots_list if s is not None)

    # Skill allocation (4.48.8): pre-computed список навыков для UI.
    # Блок видим только если up_skills > 0 (управляется в шаблоне).
    skill_options = _build_skill_options(state)

    # Gym skill training (4.48.4 / 0.2.1e): pre-computed список 8 навыков.
    gym_skills = _build_gym_skills(state)

    # Work UI: либо меню вакансий (когда не работаешь), либо форма "+N часов"
    # (когда уже работаешь). Расчёт max_hours и pre-computed hour_options
    # делаем в Python — Jinja остаётся тонким слоем рендера. Cap = 8 часов
    # (как в CLI Work.ask_hours).
    if state.work.active and state.work.work_type:
        work_vacancies = []
        work_helper = Work(state)
        cur_req = work_helper.work_requirements.get(state.work.work_type)
        work_max_add_hours = _max_work_hours(state, cur_req) if cur_req else 0
        work_add_hour_options = _build_hour_options(state, cur_req, work_max_add_hours) if cur_req else []
    else:
        work_vacancies = _build_work_vacancies(state)
        work_max_add_hours = 0
        work_add_hour_options = []

    return {
        "request": request,
        "version": VERSION,
        "state": state,
        "icon_loc": icon_loc(state),
        # Last reload status — UI показывает badge при ok=False (4.54.0).
        "last_reload": get_last_reload(),
        # Equipment counters (для свёрнутого summary блока).
        "equipment_worn": equipment_worn,
        "equipment_total_slots": 7,
        # 4.50 — Capacity inventory (N/cap). cap = 10 + state.gym.backpack_skill.
        "inventory_capacity": backpack_capacity(state),
        # Steps + bonuses
        "stamina_bonus_steps": stamina_skill_bonus_def(state),
        "equipment_stamina_steps": equipment_bonus_stamina_steps(state),
        "daily_steps_bonus": daily_steps_bonus(state),
        "level_steps_bonus": level_steps_bonus(state),
        "total_bonus_steps": total_bonus_steps(state),
        "max_steps": state.steps.today + total_bonus_steps(state),
        "bonus_pct": bonus_percentage(state),
        # Energy + equipment bonuses
        "equipment_stamina_bonus": equipment_stamina_bonus(state),
        "equipment_energy_max_bonus": equipment_energy_max_bonus(state),
        "equipment_speed_skill_bonus": equipment_speed_skill_bonus(state),
        "equipment_luck_bonus": equipment_luck_bonus(state),
        # Level
        "char_level": char_level.level,
        "char_level_progress": char_level.progress_to_next_level(),
        "char_level_up_skills": state.char_level.up_skills,
        # Active sessions
        "training_start_ts": training_start_ts,
        "training_end_ts": training_end_ts,
        "training_progress": training_progress,
        "training_skill_target": training_skill_target,
        "work_start_ts": work_start_ts,
        "work_end_ts": work_end_ts,
        "work_effective_salary": work_effective_salary,
        "work_effective_total": work_effective_total,
        "work_progress": work_progress,
        "adv_start_ts": adv_start_ts,
        "adv_end_ts": adv_end_ts,
        "adv_progress": adv_progress,
        "adventure_finished": adventure_finished,
        # Now (для server-side rendering первоначального countdown — клиент потом
        # пересчитывает на JS).
        "now_ts": now_ts,
        # Steps form state (4.48.2): error message + open/closed flag.
        "steps_error": steps_error,
        "steps_form_open": steps_form_open,
        # Energy regen (0.2.1c) — параметры для JS-таймера на клиенте.
        "energy_time_stamp": state.energy_time_stamp,
        "energy_interval_sec": energy_interval_sec,
        "energy_max_now": energy_max_now,
        # Skill allocation (4.48.8): список навыков с current-значениями.
        # Блок рендерится только если up_skills > 0 (state.char_level.up_skills).
        "skill_options": skill_options,
        "skill_error": skill_error,
        # Gym skill training (4.48.4 / 0.2.1e): список 8 навыков с pre-computed cost.
        "gym_skills": gym_skills,
        "gym_error": gym_error,
        # Work UI (4.48.5): меню вакансий или форма "+часы".
        "work_vacancies": work_vacancies,
        "work_max_add_hours": work_max_add_hours,
        "work_add_hour_options": work_add_hour_options,
        "work_error": work_error,
        # 4.50.2 — Pending drop UI: баннер + inline кнопки в инвентаре.
        # `active` = True если есть невыпавшая находка, `item` = parsed dict.
        "pending_drop_view": _build_pending_drop_view(state),
        "drop_error": drop_error,
        # 4.48.3 — Adventure section: list прогулок (locked/unlocked + costs + drop %).
        "adventure_view": _build_adventure_view(state),
        "adventure_error": adventure_error,
        # 4.48.3 — «🎁 Находка» banner: runtime-only state.last_adventure_drop.
        # Set в _finalize_adventure_with_drop_capture, cleared на mutation.
        "drop_notification": state.last_adventure_drop,
    }


@app.get("/healthz")
async def healthz():
    """Health-check для smoke и future load balancer / monitoring."""
    return JSONResponse({
        "status": "ok",
        "state_loaded": game.state is not None,
        "version": VERSION,
    })


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Главная страница — read-only dashboard.

    На каждом GET / (заход / F5 / pull-to-refresh) подтягиваем свежий state
    из Sheets через `try_reload_state()`. При сетевой ошибке оставляем
    кэшированный state — UI покажет badge на основе `last_reload.ok` (4.54.0).
    """
    try_reload_state()
    context = _dashboard_context(request)
    # Новый сигнатура Starlette 1.0+: TemplateResponse(request, name, context).
    return templates.TemplateResponse(request, "dashboard.html", context)


@app.get("/status", response_class=HTMLResponse)
async def status_fragment(request: Request):
    """HTML-фрагмент для HTMX-полинга (каждые 60 сек). Тот же контент, без
    обёртки с <html>, чтобы HTMX мог подставить через innerHTML.

    НЕ зовёт `try_reload_state()` — рендерит из памяти. Это сохраняет дешёвый
    polling: 1 заход в Sheets на F5, 0 заходов на каждый автообновление (4.54.0).
    """
    context = _dashboard_context(request)
    return templates.TemplateResponse(request, "_status_fragment.html", context)


# ----------------------------------------------------------------------------
# Steps input — задача 4.48.2.
#
# Два endpoint'а с общим helper `_apply_new_steps()`:
#  - POST /api/steps (JSON) — для curl / iPhone Shortcut / любого не-HTMX клиента.
#  - POST /web/steps (form-data → HTML fragment) — для HTMX-формы на dashboard.
# ----------------------------------------------------------------------------


class StepsRequest(BaseModel):
    """Body для POST /api/steps."""
    steps: int = Field(..., ge=0, description="Абсолютное значение шагов за сегодня (с браслета).")
    ts: Optional[float] = Field(default=None, description="Unix timestamp; default = server now.")
    source: str = Field(default="web", description="manual / web / auto / etc.")


@app.post("/api/steps")
async def api_steps(payload: StepsRequest):
    """JSON endpoint для ввода шагов. Применяет max-merge, пишет в steps_log.

    Возвращает 200 + {ok, applied, steps_today, steps_can_use, logged} при
    успехе или валидационном ignore (steps <= today). Возвращает 503 при
    Sheets-ошибке. Возвращает 422 от Pydantic при невалидном теле.
    """
    result = _apply_new_steps(payload.steps, source=payload.source, ts=payload.ts)

    if result.applied:
        return JSONResponse({
            "ok": True,
            "applied": True,
            "steps_today": result.steps_today,
            "steps_can_use": result.steps_can_use,
            "logged": result.logged,
        })

    # not applied → либо валидация (steps <= today), либо Sheets fail.
    if result.error and "Sheets unavailable" in result.error:
        return JSONResponse(
            {"ok": False, "applied": False, "error": result.error},
            status_code=503,
        )
    # Иначе — валидация (например, value <= today).
    return JSONResponse(
        {
            "ok": False,
            "applied": False,
            "steps_today": result.steps_today,
            "error": result.error,
        },
        status_code=422,
    )


@app.post("/web/steps", response_class=HTMLResponse)
async def web_steps(request: Request, steps: int = Form(...)):
    """Form-data endpoint для HTMX-формы на dashboard. Возвращает обновлённый
    `_status_fragment.html`. При ошибке — фрагмент с сообщением и открытой
    формой; при успехе — фрагмент с закрытой формой и обновлёнными числами.
    """
    result = _apply_new_steps(steps, source="web")
    context = _dashboard_context(
        request,
        steps_error=result.error if not result.applied else None,
        steps_form_open=not result.applied,
    )
    return templates.TemplateResponse(request, "_status_fragment.html", context)


# ----------------------------------------------------------------------------
# Work — задача 4.48.5.
#
# Четыре endpoint'а с общим helper `_validate_and_apply_work()`:
#  - POST /web/work/start (Form: work_type, hours) → HTML fragment.
#  - POST /web/work/add_hours (Form: hours) → HTML fragment, work_type из state.
#  - POST /api/work/start (JSON) — для curl / future iPhone Shortcut.
#  - POST /api/work/add_hours (JSON) — то же, но через JSON.
#
# Финализация смены (зачисление зарплаты, очистка state.work) делается в
# `_dashboard_context()` через `work_check_done(state)` — каждый GET / POST
# проверит state.work.end и закроет смену, если время вышло.
# ----------------------------------------------------------------------------


class WorkStartRequest(BaseModel):
    """Body для POST /api/work/start."""
    work_type: str = Field(..., description="Ключ вакансии: watchman / factory / courier_foot / forwarder.")
    hours: int = Field(..., ge=1, le=8, description="Кол-во рабочих часов (1-8).")


class WorkAddHoursRequest(BaseModel):
    """Body для POST /api/work/add_hours."""
    hours: int = Field(..., ge=1, le=8, description="Сколько часов добавить (1-8).")


def _work_state_snapshot(state) -> dict:
    """Минимальный snapshot state.work для JSON-ответа."""
    return {
        "active": state.work.active,
        "work_type": state.work.work_type,
        "hours": state.work.hours,
        "salary": state.work.salary,
        "start_ts": state.work.start.timestamp() if state.work.start else None,
        "end_ts": state.work.end.timestamp() if state.work.end else None,
    }


@app.post("/web/work/start", response_class=HTMLResponse)
async def web_work_start(request: Request,
                         work_type: str = Form(...),
                         hours: int = Form(...)):
    """Form-data старт смены. Возвращает обновлённый `_status_fragment.html`.

    Если уже работаешь — игнорируем (нельзя сменить вакансию посреди смены,
    как в CLI). Если ресурсов не хватает — фрагмент с work_error.
    """
    state = game.state
    if state is None:
        raise HTTPException(status_code=503, detail="state not initialized")

    if state.work.active:
        # Стартовать новую смену поверх активной нельзя — UI должен был
        # показать форму "+часы", но кто-то всё равно дёрнул POST /start.
        context = _dashboard_context(
            request,
            work_error="Уже работаешь — заверши смену или используй форму 'Добавить часы'.",
        )
    else:
        err = _validate_and_apply_work(state, work_type, hours)
        # 4.54.6 — STALE → специальный fragment с auto-reload.
        if err == STALE_MARKER:
            return _stale_response()
        context = _dashboard_context(request, work_error=err)
    return templates.TemplateResponse(request, "_status_fragment.html", context)


@app.post("/web/work/add_hours", response_class=HTMLResponse)
async def web_work_add_hours(request: Request, hours: int = Form(...)):
    """Form-data добавление часов к активной смене. Берёт work_type из state."""
    state = game.state
    if state is None:
        raise HTTPException(status_code=503, detail="state not initialized")

    if not state.work.active or not state.work.work_type:
        context = _dashboard_context(
            request,
            work_error="Сейчас не работаешь — выбери вакансию.",
        )
    else:
        err = _validate_and_apply_work(state, state.work.work_type, hours)
        if err == STALE_MARKER:
            return _stale_response()
        context = _dashboard_context(request, work_error=err)
    return templates.TemplateResponse(request, "_status_fragment.html", context)


@app.post("/api/work/start")
async def api_work_start(payload: WorkStartRequest):
    """JSON старт смены. Возвращает 200+work snapshot или 422 с error."""
    state = game.state
    if state is None:
        return JSONResponse({"ok": False, "error": "state not initialized"}, status_code=503)

    # work_check_done вызывается ТОЛЬКО в _dashboard_context (не в API).
    # JSON-клиент явно вызывает start — авто-финализация ему не нужна.
    if state.work.active:
        return JSONResponse(
            {"ok": False, "error": "Already working — нельзя сменить вакансию посреди смены.",
             "work": _work_state_snapshot(state)},
            status_code=409,
        )

    err = _validate_and_apply_work(state, payload.work_type, payload.hours)
    if err == STALE_MARKER:
        return _stale_json_response()
    if err is not None:
        return JSONResponse({"ok": False, "error": err}, status_code=422)
    return JSONResponse({"ok": True, "work": _work_state_snapshot(state)})


@app.post("/api/work/add_hours")
async def api_work_add_hours(payload: WorkAddHoursRequest):
    """JSON добавление часов к активной смене."""
    state = game.state
    if state is None:
        return JSONResponse({"ok": False, "error": "state not initialized"}, status_code=503)

    if not state.work.active or not state.work.work_type:
        return JSONResponse(
            {"ok": False, "error": "Not working — нет активной смены."},
            status_code=409,
        )

    err = _validate_and_apply_work(state, state.work.work_type, payload.hours)
    if err == STALE_MARKER:
        return _stale_json_response()
    if err is not None:
        return JSONResponse({"ok": False, "error": err}, status_code=422)
    return JSONResponse({"ok": True, "work": _work_state_snapshot(state)})


# ----------------------------------------------------------------------------
# Skill allocation — задача 4.48.8.
#
# 2 endpoint'а: POST /web/level/allocate (Form → HTML fragment) и
# POST /api/level/allocate (JSON). Подтверждение делается на клиенте
# через `hx-confirm` HTMX-атрибут (нативный browser confirm) — игрок
# подтверждает каждый клик прежде чем уходит запрос на сервер.
# ----------------------------------------------------------------------------


class SkillAllocateRequest(BaseModel):
    """Body для POST /api/level/allocate."""
    skill: str = Field(..., description="stamina / energy_max / speed / energy_regen / luck")


def _char_level_snapshot(state) -> dict:
    """Минимальный snapshot char_level для JSON-ответа."""
    cl = state.char_level
    return {
        "level": cl.level,
        "up_skills": cl.up_skills,
        "skill_stamina": cl.skill_stamina,
        "skill_energy_max": cl.skill_energy_max,
        "skill_speed": cl.skill_speed,
        "skill_energy_regen": cl.skill_energy_regen,  # 0.2.4i (task 4.21)
        "skill_luck": cl.skill_luck,
    }


@app.post("/web/level/allocate", response_class=HTMLResponse)
async def web_level_allocate(request: Request, skill: str = Form(...)):
    """Form-data распределение +1 очка на выбранный навык."""
    state = game.state
    if state is None:
        raise HTTPException(status_code=503, detail="state not initialized")

    err = _validate_and_apply_skill_allocation(state, skill)
    if err == STALE_MARKER:
        return _stale_response()
    context = _dashboard_context(request, skill_error=err)
    return templates.TemplateResponse(request, "_status_fragment.html", context)


@app.post("/api/level/allocate")
async def api_level_allocate(payload: SkillAllocateRequest):
    """JSON распределение +1 очка."""
    state = game.state
    if state is None:
        return JSONResponse({"ok": False, "error": "state not initialized"}, status_code=503)

    err = _validate_and_apply_skill_allocation(state, payload.skill)
    if err == STALE_MARKER:
        return _stale_json_response()
    if err is not None:
        return JSONResponse({"ok": False, "error": err}, status_code=422)
    return JSONResponse({"ok": True, "char_level": _char_level_snapshot(state)})


# ----------------------------------------------------------------------------
# Gym skill training — задача 4.48.4 (0.2.1e).
#
# 2 endpoint'а: POST /web/gym/start (Form → HTML fragment) и
# POST /api/gym/start (JSON через GymStartRequest). Подтверждение на клиенте
# через `hx-confirm` HTMX-атрибут — игрок подтверждает старт прежде чем
# уходит запрос. Auto-finalize тренировки делает skill_training_check_done
# в _dashboard_context.
# ----------------------------------------------------------------------------


class GymStartRequest(BaseModel):
    """Body для POST /api/gym/start."""
    skill_name: str = Field(..., description="stamina / speed_skill / luck_skill / move_optimization_* / neatness_in_using_things")


def _training_snapshot(state) -> dict:
    """Минимальный snapshot state.training для JSON-ответа."""
    t = state.training
    return {
        "active": t.active,
        "skill_name": t.skill_name,
        "time_end_ts": t.time_end.timestamp() if t.time_end else None,
        "timestamp": t.timestamp,
    }


@app.post("/web/gym/start", response_class=HTMLResponse)
async def web_gym_start(request: Request, skill_name: str = Form(...)):
    """Form-data старт тренировки навыка. Возвращает обновлённый
    `_status_fragment.html`."""
    state = game.state
    if state is None:
        raise HTTPException(status_code=503, detail="state not initialized")

    err = _validate_and_apply_training(state, skill_name)
    if err == STALE_MARKER:
        return _stale_response()
    context = _dashboard_context(request, gym_error=err)
    return templates.TemplateResponse(request, "_status_fragment.html", context)


@app.post("/api/gym/start")
async def api_gym_start(payload: GymStartRequest):
    """JSON старт тренировки навыка."""
    state = game.state
    if state is None:
        return JSONResponse({"ok": False, "error": "state not initialized"}, status_code=503)

    if state.training.active:
        return JSONResponse(
            {"ok": False, "error": "Training already active.",
             "training": _training_snapshot(state)},
            status_code=409,
        )

    err = _validate_and_apply_training(state, payload.skill_name)
    if err == STALE_MARKER:
        return _stale_json_response()
    if err is not None:
        return JSONResponse({"ok": False, "error": err}, status_code=422)
    return JSONResponse({"ok": True, "training": _training_snapshot(state)})


# ============================================================================
# 4.48.3 — Web: Adventure (старт прогулки + auto-finalize + drop notification)
#
# Дизайн (зафиксировано 19.05.2026):
# - 7 прогулок с прогрессивной разблокировкой (3 прохождения предыдущего тира)
# - Locked = greyed-out карточки с progress hint
# - Drop probabilities через drop.compute_grade_probabilities (учитывает luck)
# - Drop notification: «🎁 Находка» banner — runtime-only state.last_adventure_drop,
#   set в _finalize_adventure_with_drop_capture (через delta inventory/pending),
#   cleared на следующем успешном mutation (steps/work/gym/drop/skill_alloc).
#   Banner переживает F5, исчезает после первого клика игрока.
# - Auto-finalize: _finalize_adventure_with_drop_capture(state) в _dashboard_context
#   (рядом с work_check_done / skill_training_check_done).
# - One adventure at a time (как Work/Gym, гарантируется state.adventure.active flag).
# ============================================================================


# Human-friendly labels для UI. Порядок = порядок отображения в section.
_ADVENTURE_DISPLAY: tuple[tuple[str, str], ...] = (
    ('walk_easy',   'Прогулка вокруг озера'),
    ('walk_normal', 'Прогулка по району'),
    ('walk_hard',   'Прогулка в лес'),
    ('walk_15k',    'Прогулка 15к шагов'),
    ('walk_20k',    'Прогулка 20к шагов'),
    ('walk_25k',    'Прогулка 25к шагов'),
    ('walk_30k',    'Прогулка 30к шагов'),
)

# Unlock prerequisites: adv_name → (required_counter_key, required_count, prereq_label).
# walk_easy всегда unlocked (no entry в dict).
_ADVENTURE_UNLOCK: dict[str, tuple[str, int, str]] = {
    'walk_normal': ('walk_easy', 3, 'Прогулка вокруг озера'),
    'walk_hard':   ('walk_normal', 3, 'Прогулка по району'),
    'walk_15k':    ('walk_hard', 3, 'Прогулка в лес'),
    'walk_20k':    ('walk_15k', 3, 'Прогулка 15к шагов'),
    'walk_25k':    ('walk_20k', 3, 'Прогулка 20к шагов'),
    'walk_30k':    ('walk_25k', 3, 'Прогулка 25к шагов'),
}

# Human-readable labels для drop probability display. Полные формы вместо
# одиночных букв — игроку понятнее «B-Grade [29%]» чем «B [29%]». Consistent
# с CLI _format_reward output. Для S+ используется «S+ Grade» с пробелом
# (визуально лучше чем «S+-Grade» c двойным дашем).
_GRADE_LABELS: dict[str, str] = {
    'c-grade':  'C-Grade',
    'b-grade':  'B-Grade',
    'a-grade':  'A-Grade',
    's-grade':  'S-Grade',
    's+grade':  'S+ Grade',
}


class AdventureStartRequest(BaseModel):
    """Body для POST /api/adventure/start."""
    adv_name: str = Field(..., description="walk_easy / walk_normal / ... / walk_30k")


def _adventure_snapshot(state) -> dict:
    """Минимальный snapshot state.adventure для JSON-ответа."""
    a = state.adventure
    return {
        "active": a.active,
        "name": a.name,
        "start_ts": a.start_ts,
        "end_ts": a.end_ts,
    }


def _build_adventure_view(state) -> dict:
    """Pre-compute UI данные для Adventure-секции.

    Returns dict:
    - `active`: bool — активна ли прогулка сейчас (если да — меню стартов скрыто)
    - `active_name`: str | None — для inline summary в details summary
    - `adventures`: list[dict] — 7 элементов, каждый:
        - name (key), label (human), locked (bool), unlock_hint (str|None),
        - cost: {steps, energy, time_minutes}, can_afford (bool), missing dict,
        - probabilities: list[(grade_label, percent_str)] — для отображения %
    """
    from adventure import Adventure
    from adventure_data import adventure_data_table
    from drop import compute_grade_probabilities

    is_active = state.adventure.active
    active_name = state.adventure.name if is_active else None

    adv_helper = Adventure(adventure_data_table, state)

    items: list[dict] = []
    for name, label in _ADVENTURE_DISPLAY:
        # Locked check.
        locked = False
        unlock_hint = None
        if name in _ADVENTURE_UNLOCK:
            prereq_key, prereq_count, prereq_label = _ADVENTURE_UNLOCK[name]
            current_count = state.adventure.counters.get(prereq_key, 0)
            if current_count < prereq_count:
                locked = True
                remaining = prereq_count - current_count
                unlock_hint = f'Нужно ещё {remaining} прохождений «{prereq_label}»'

        # Cost (адаптированный под move_opt + energy_opt skills).
        adv_data = next(
            (adv['data'] for adv in adv_helper.adventures.values() if adv['name'] == name),
            None,
        )
        if adv_data is None:
            # На случай отсутствия в adv_helper — skip.
            continue
        base_steps = adv_data['steps']
        base_energy = adv_data['energy']
        # Time — финальная длительность с учётом speed_skill bonus.
        from skill_bonus import speed_skill_equipment_and_level_bonus
        final_time_min = speed_skill_equipment_and_level_bonus(adv_data['time'], state)

        can_afford = (
            state.steps.can_use >= base_steps
            and state.energy >= base_energy
        )
        missing = {
            'steps': max(0, base_steps - state.steps.can_use),
            'energy': max(0, base_energy - state.energy),
        }

        # Drop probabilities (учитывает current luck).
        # Формат: list[(grade_label_human, percent_str)] для template.
        # Skip 'nothing' и грейды с p<0.0001 — чтобы не показывать «C-Grade 0.00%».
        # Labels — полные формы «X-Grade» / «S+ Grade» (consistent с CLI).
        probs = compute_grade_probabilities(name, state)
        prob_pairs: list[tuple[str, str]] = []
        for grade, p in probs.items():
            if grade == 'nothing' or p < 0.0001:
                continue
            label_human = _GRADE_LABELS.get(grade, grade.upper())
            prob_pairs.append((label_human, f'{p * 100:.2f}%'))

        items.append({
            'name': name,
            'label': label,
            'locked': locked,
            'unlock_hint': unlock_hint,
            'cost_steps': base_steps,
            'cost_energy': base_energy,
            'cost_time_min': final_time_min,
            'can_afford': can_afford,
            'missing': missing,
            'probabilities': prob_pairs,
        })

    return {
        'active': is_active,
        'active_name': active_name,
        'adventures': items,
    }


def _finalize_adventure_with_drop_capture(state) -> None:
    """Wrapper вокруг Adventure.adventure_check_done, который при transition
    `active=True → False` (т.е. финализация на этом render'е) захватывает
    дроп через delta inventory/pending_drop → пишет в state.last_adventure_drop.

    Если active=False с самого начала — no-op (не сбрасывает существующий
    notification — чтобы banner переживал F5 после finalize'а).

    Если active=True но end_ts ещё не наступил — тоже no-op (CLI helper
    напечатает «Персонаж находится в Приключении» но не финализирует —
    нас интересует только финал).
    """
    if not state.adventure.active:
        return
    end_ts = state.adventure.end_ts
    if end_ts is None or end_ts > datetime.now().timestamp():
        return  # ещё не время

    # Capture pre-state.
    inv_len_before = len(state.inventory)
    pending_before = state.pending_drop

    # Делегируем существующему helper'у.
    from adventure import Adventure
    Adventure.adventure_check_done(self=None, state=state)

    # Capture what dropped.
    if len(state.inventory) > inv_len_before:
        # Normal drop — last item.
        state.last_adventure_drop = state.inventory[-1]
    elif state.pending_drop is not None and pending_before is None:
        # Full inventory → captured как pending.
        state.last_adventure_drop = state.pending_drop
    # else: no drop (либо roll missed, либо forced sale — для simplicity
    # forced sale не показываем, money-delta видна в Stats).


def _validate_and_apply_adventure(state, adv_name: str) -> Optional[str]:
    """Валидирует adv_name (включая unlock), стартует через Adventure._enter_adventure
    + decrease_durability. На успехе persist. Возвращает текст ошибки или None.

    Используется двумя endpoint'ами (web/api start)."""
    if state.adventure.active:
        return 'Приключение уже идёт — дождись завершения текущего.'
    # Validate adv_name.
    valid_names = {name for name, _ in _ADVENTURE_DISPLAY}
    if adv_name not in valid_names:
        return f'Неизвестное приключение: {adv_name}'
    # Check unlock.
    if adv_name in _ADVENTURE_UNLOCK:
        prereq_key, prereq_count, prereq_label = _ADVENTURE_UNLOCK[adv_name]
        if state.adventure.counters.get(prereq_key, 0) < prereq_count:
            remaining = prereq_count - state.adventure.counters.get(prereq_key, 0)
            return f'Заблокировано: нужно ещё {remaining} прохождений «{prereq_label}»'

    # Compute cost via adventure helper (учитывает move_opt + energy_opt skills).
    from adventure import Adventure
    from adventure_data import adventure_data_table
    adv_helper = Adventure(adventure_data_table, state)
    adv_data = next(
        (adv['data'] for adv in adv_helper.adventures.values() if adv['name'] == adv_name),
        None,
    )
    if adv_data is None:
        return f'Ошибка получения данных приключения: {adv_name}'

    # Pre-flight resources check.
    if state.steps.can_use < adv_data['steps'] or state.energy < adv_data['energy']:
        return (f'Не хватает ресурсов: нужно {adv_data["steps"]} 🏃 + '
                f'{adv_data["energy"]} 🔋 (есть {state.steps.can_use} 🏃 + {state.energy} 🔋).')

    # Final time с учётом speed_skill bonus.
    from skill_bonus import speed_skill_equipment_and_level_bonus
    final_time_min = speed_skill_equipment_and_level_bonus(adv_data['time'], state)

    # Spend + start (через actions.try_spend + actions.start_adventure).
    from actions import try_spend, start_adventure as actions_start_adventure
    if not try_spend(state, steps=adv_data['steps'], energy=adv_data['energy']):
        return 'Не удалось списать ресурсы (race condition?)'
    now_ts = datetime.now().timestamp()
    actions_start_adventure(
        state,
        name=adv_name,
        start_ts=now_ts,
        end_ts=now_ts + (final_time_min * 60),
    )

    # Износ экипировки — как в CLI Adventure._enter_adventure.
    from inventory import Wear_Equipped_Items
    Wear_Equipped_Items(state).decrease_durability(adv_data['steps'])

    # log_event как в CLI.
    from history import log_event
    log_event('adventure_start', name=adv_name,
              cost_steps=adv_data['steps'], cost_energy=adv_data['energy'],
              duration_minutes=final_time_min)

    stale = _persist_and_handle_stale(endpoint='adventure_start')
    if stale:
        return STALE_MARKER
    return None


@app.post("/web/adventure/start", response_class=HTMLResponse)
async def web_adventure_start(request: Request, adv_name: str = Form(...)):
    """Form-data старт приключения. Возвращает обновлённый _status_fragment.html."""
    state = game.state
    if state is None:
        raise HTTPException(status_code=503, detail="state not initialized")

    err = _validate_and_apply_adventure(state, adv_name)
    if err == STALE_MARKER:
        return _stale_response()
    context = _dashboard_context(request, adventure_error=err)
    return templates.TemplateResponse(request, "_status_fragment.html", context)


@app.post("/api/adventure/start")
async def api_adventure_start(payload: AdventureStartRequest):
    """JSON старт приключения."""
    state = game.state
    if state is None:
        return JSONResponse({"ok": False, "error": "state not initialized"}, status_code=503)

    if state.adventure.active:
        return JSONResponse(
            {"ok": False, "error": "Adventure already active.",
             "adventure": _adventure_snapshot(state)},
            status_code=409,
        )

    err = _validate_and_apply_adventure(state, payload.adv_name)
    if err == STALE_MARKER:
        return _stale_json_response()
    if err is not None:
        return JSONResponse({"ok": False, "error": err}, status_code=422)
    return JSONResponse({"ok": True, "adventure": _adventure_snapshot(state)})


# ===== 4.50.2 — Pending drop resolve (web) =====

class DropSellExistingRequest(BaseModel):
    """Body для POST /api/drop/sell_existing — индекс предмета в state.inventory.

    Индекс **0-based по списку state.inventory** (не по отсортированной view).
    Web-форма передаёт реальный индекс из исходного списка через `value=`
    атрибут кнопки — sort применяется только в template на отображение.
    """
    index: int = Field(..., ge=0, description="0-based индекс предмета в state.inventory")


def _validate_and_apply_drop_sell_existing(state, index: int) -> Optional[str]:
    """Resolve pending: продать предмет инвентаря по индексу + положить pending.

    Возвращает None при успехе, текст ошибки иначе. На успех — persist.
    """
    if state.pending_drop is None:
        return "Нет активной находки для resolve."
    if not (0 <= index < len(state.inventory)):
        return f"Неверный индекс предмета: {index} (инвентарь: {len(state.inventory)} предметов)."
    from inventory import _resolve_pending_drop_sell_existing
    _resolve_pending_drop_sell_existing(state, index)
    stale = _persist_and_handle_stale(endpoint='drop_sell_existing')
    if stale:
        return STALE_MARKER
    return None


def _validate_and_apply_drop_sell_new(state) -> Optional[str]:
    """Resolve pending: продать саму находку за base price.

    Возвращает None при успехе, текст ошибки иначе. На успех — persist.
    """
    if state.pending_drop is None:
        return "Нет активной находки для resolve."
    from inventory import _resolve_pending_drop_sell_new
    _resolve_pending_drop_sell_new(state)
    stale = _persist_and_handle_stale(endpoint='drop_sell_new')
    if stale:
        return STALE_MARKER
    return None


@app.post("/web/drop/sell_existing", response_class=HTMLResponse)
async def web_drop_sell_existing(request: Request, index: int = Form(...)):
    """Form-data resolve: продать предмет №index, положить pending."""
    state = game.state
    if state is None:
        raise HTTPException(status_code=503, detail="state not initialized")

    err = _validate_and_apply_drop_sell_existing(state, index)
    if err == STALE_MARKER:
        return _stale_response()
    context = _dashboard_context(request, drop_error=err)
    return templates.TemplateResponse(request, "_status_fragment.html", context)


@app.post("/web/drop/sell_new", response_class=HTMLResponse)
async def web_drop_sell_new(request: Request):
    """Form-data resolve: продать находку за base price."""
    state = game.state
    if state is None:
        raise HTTPException(status_code=503, detail="state not initialized")

    err = _validate_and_apply_drop_sell_new(state)
    if err == STALE_MARKER:
        return _stale_response()
    context = _dashboard_context(request, drop_error=err)
    return templates.TemplateResponse(request, "_status_fragment.html", context)


@app.post("/web/drop/skip", response_class=HTMLResponse)
async def web_drop_skip(request: Request):
    """Form-data skip: pending остаётся, баннер появится снова на следующем
    рендере. По сути — просто re-render, но симметрично CLI flow и явный
    «отложить» для UI. Никаких мутаций / persist."""
    state = game.state
    if state is None:
        raise HTTPException(status_code=503, detail="state not initialized")
    context = _dashboard_context(request)
    return templates.TemplateResponse(request, "_status_fragment.html", context)


def _pending_drop_snapshot(state) -> Optional[dict]:
    """Минимальный JSON-snapshot pending_drop для API ответа."""
    if state.pending_drop is None:
        return None
    p = state.pending_drop

    def _first(values):
        return values[0] if values else None

    return {
        "type": _first(p.get("item_type")),
        "grade": _first(p.get("grade")),
        "characteristic": _first(p.get("characteristic")),
        "bonus": _first(p.get("bonus")),
        "quality": _first(p.get("quality")),
        "price": _first(p.get("price")),
    }


@app.post("/api/drop/sell_existing")
async def api_drop_sell_existing(payload: DropSellExistingRequest):
    """JSON resolve: продать предмет №index, положить pending."""
    state = game.state
    if state is None:
        return JSONResponse({"ok": False, "error": "state not initialized"}, status_code=503)

    err = _validate_and_apply_drop_sell_existing(state, payload.index)
    if err == STALE_MARKER:
        return _stale_json_response()
    if err is not None:
        return JSONResponse({"ok": False, "error": err}, status_code=422)
    return JSONResponse({
        "ok": True,
        "money": state.money,
        "inventory_size": len(state.inventory),
        "pending_drop": _pending_drop_snapshot(state),
    })


@app.post("/api/drop/sell_new")
async def api_drop_sell_new():
    """JSON resolve: продать находку за base price."""
    state = game.state
    if state is None:
        return JSONResponse({"ok": False, "error": "state not initialized"}, status_code=503)

    err = _validate_and_apply_drop_sell_new(state)
    if err == STALE_MARKER:
        return _stale_json_response()
    if err is not None:
        return JSONResponse({"ok": False, "error": err}, status_code=422)
    return JSONResponse({
        "ok": True,
        "money": state.money,
        "inventory_size": len(state.inventory),
        "pending_drop": _pending_drop_snapshot(state),
    })
