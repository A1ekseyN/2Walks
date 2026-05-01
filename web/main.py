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
from characteristics import game, init_game_state
from equipment_bonus import (
    equipment_energy_max_bonus,
    equipment_luck_bonus,
    equipment_speed_skill_bonus,
    equipment_stamina_bonus,
)
from functions import bonus_percentage, total_bonus_steps
from google_sheets_db import StepsLogRepo
from level import CharLevel
from locations import icon_loc
from skill_bonus import stamina_skill_bonus_def
from web.sync import get_last_reload, try_reload_state


VERSION = "0.2.0i"
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
                       steps_form_open: bool = False) -> dict:
    """Собирает все данные, нужные dashboard и status-fragment шаблонам.

    `steps_error` / `steps_form_open` — флаги для отрисовки формы ввода шагов:
    при ошибке валидации/Sheets форма остаётся открытой с подсказкой.
    """
    state = game.state
    if state is None:
        raise RuntimeError("game.state не инициализирован — должен быть вызван init_game_state() в lifespan.")

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

    return {
        "request": request,
        "version": VERSION,
        "state": state,
        "icon_loc": icon_loc(state),
        # Last reload status — UI показывает badge при ok=False (4.54.0).
        "last_reload": get_last_reload(),
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
