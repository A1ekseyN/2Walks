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
from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from bonus import (
    daily_steps_bonus,
    equipment_bonus_stamina_steps,
    level_steps_bonus,
)
from characteristics import game, init_game_state, save_characteristic
from equipment_bonus import (
    equipment_energy_max_bonus,
    equipment_luck_bonus,
    equipment_speed_skill_bonus,
    equipment_stamina_bonus,
)
from functions import bonus_percentage, total_bonus_steps
from google_sheets_db import GameStateRepo, StepsLogRepo
from inventory import Wear_Equipped_Items
from level import CharLevel
from locations import icon_loc
from skill_bonus import stamina_skill_bonus_def
from web.sync import get_last_reload, try_reload_state
from work import Work, work_check_done


VERSION = "0.2.1a"

# UI-метаданные для вакансий (key — атрибут в Work.work_requirements).
_WORK_DISPLAY = {
    "watchman":     {"title": "Сторож",     "icon": "🛡"},
    "factory":      {"title": "Завод",      "icon": "🏭"},
    "courier_foot": {"title": "Курьер",     "icon": "🚲"},
    "forwarder":    {"title": "Экспедитор", "icon": "🚚"},
}


def _max_work_hours(state, requirements: dict) -> int:
    """Сколько часов работы покрывают текущие ресурсы (cap 8)."""
    steps_cap = state.steps.can_use // requirements['steps'] if requirements['steps'] > 0 else 0
    energy_cap = state.energy // requirements['energy'] if requirements['energy'] > 0 else 0
    return int(min(steps_cap, energy_cap, 8))


def _build_work_vacancies(state) -> list:
    """Собирает данные для меню выбора вакансии (не работаешь)."""
    work_helper = Work(state)
    vacancies = []
    for key, req in work_helper.work_requirements.items():
        meta = _WORK_DISPLAY.get(key, {"title": key.title(), "icon": "🏭"})
        vacancies.append({
            "key": key,
            "title": meta["title"],
            "icon": meta["icon"],
            "steps_per_hour": req['steps'],
            "energy_per_hour": req['energy'],
            "salary_per_hour": req['salary'],
            "max_hours": _max_work_hours(state, req),
        })
    return vacancies


def _persist_state_to_cloud() -> None:
    """Локальное сохранение (JSON+CSV) + push в Google Sheets.

    Локальное всегда первым (гарантия offline-mode). Sheets — best-effort:
    если упадёт сетевой, сообщение в лог uvicorn'а, но web-операция не
    отвалится. Пользователь увидит данные на disk'е и при следующем
    действии (или CLI save) Sheets синкнется.

    Применяется после каждой мутирующей web-операции (start/add_hours
    смены). Будущие training/adventure endpoint'ы будут звать тот же helper.
    """
    save_characteristic()
    try:
        GameStateRepo().save(game.state.to_dict())
    except Exception as e:  # noqa: BLE001 — best-effort sync
        print(f"[web] Sheets save failed (state cached locally): {e}")


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
    _persist_state_to_cloud()
    return None
TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_game_state()
    yield


app = FastAPI(title="2Walks Web", version=VERSION, lifespan=lifespan)


def _compute_progress_pct(start_ts, end_ts, now_ts) -> float:
    """Процент выполнения активной сессии. Защита от деления на ноль / отрицательного.

    Возвращает значение в диапазоне [0, 100]. Если start/end отсутствуют или
    end <= start (не должно быть в нормальной игре, но edge case) — возвращает 0.
    """
    if start_ts is None or end_ts is None or end_ts <= start_ts:
        return 0.0
    return max(0.0, min(100.0, (now_ts - start_ts) / (end_ts - start_ts) * 100))


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
    - При успехе: state.steps.today обновляется, steps.can_use пересчитывается
      (без day rollover — это отдельная задача в save_game_date_last_enter).
    - source — 'web' / 'manual' / 'auto' / etc; пишется в steps_log.
    """
    state = game.state
    if state is None:
        return StepsAppliedResult(False, 0, 0, False, "state not initialized")

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
    state.steps.today = steps_value
    state.steps.can_use = state.steps.today - state.steps.used + total_bonus_steps(state)

    return StepsAppliedResult(
        applied=True,
        steps_today=state.steps.today,
        steps_can_use=state.steps.can_use,
        logged=True,
    )


def _dashboard_context(request: Request, steps_error: Optional[str] = None,
                       steps_form_open: bool = False,
                       work_error: Optional[str] = None) -> dict:
    """Собирает все данные, нужные dashboard и status-fragment шаблонам.

    `steps_error` / `steps_form_open` — флаги для отрисовки формы ввода шагов:
    при ошибке валидации/Sheets форма остаётся открытой с подсказкой.

    `work_error` — текст ошибки от валидации Work-формы (показывается прямо
    в блоке Work). При None — никаких сообщений.
    """
    state = game.state
    if state is None:
        raise RuntimeError("game.state не инициализирован — должен быть вызван init_game_state() в lifespan.")

    # Auto-finalize работы по таймеру: каждый рендер dashboard'а / fragment'а
    # проверяет state.work.end и если время вышло — начисляет зарплату и
    # обнуляет смену. Так web-сценарий не требует отдельного "Claim"-клика
    # (CLI делает то же самое в main loop'е). Аналогично появятся вызовы
    # training_finalize / adventure_finalize в задачах 4.48.3 / 4.48.4.
    work_check_done(state)

    char_level = CharLevel(state)
    now_ts = datetime.now().timestamp()

    # Active sessions — конвертируем datetime в Unix timestamp для JS-таймера и progress-bar.
    training_start_ts = state.training.timestamp if state.training.active and state.training.timestamp else None
    training_end_ts = state.training.time_end.timestamp() if state.training.active and state.training.time_end else None
    work_start_ts = state.work.start.timestamp() if state.work.active and state.work.start else None
    work_end_ts = state.work.end.timestamp() if state.work.active and state.work.end else None
    # Adventure start_ts/end_ts уже хранятся как float timestamps.
    adv_start_ts = state.adventure.start_ts if state.adventure.active and state.adventure.start_ts else None
    adv_end_ts = state.adventure.end_ts if state.adventure.active and state.adventure.end_ts else None

    adventure_finished = (
        state.adventure.active
        and adv_end_ts is not None
        and adv_end_ts <= now_ts
    )

    # Initial server-side значения прогресс-баров (клиент будет двигать раз в секунду).
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

    # Work UI: либо меню вакансий (когда не работаешь), либо форма "+N часов"
    # (когда уже работаешь). Расчёт max_hours делаем в Python — Jinja остаётся
    # тонким слоем рендера. Cap = 8 часов (как в CLI Work.ask_hours).
    if state.work.active and state.work.work_type:
        work_vacancies = []
        work_helper = Work(state)
        cur_req = work_helper.work_requirements.get(state.work.work_type)
        work_max_add_hours = _max_work_hours(state, cur_req) if cur_req else 0
    else:
        work_vacancies = _build_work_vacancies(state)
        work_max_add_hours = 0

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
        # Work UI (4.48.5): меню вакансий или форма "+часы".
        "work_vacancies": work_vacancies,
        "work_max_add_hours": work_max_add_hours,
        "work_error": work_error,
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
    if err is not None:
        return JSONResponse({"ok": False, "error": err}, status_code=422)
    return JSONResponse({"ok": True, "work": _work_state_snapshot(state)})
