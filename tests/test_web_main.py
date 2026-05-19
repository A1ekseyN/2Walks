"""Тесты FastAPI скелета и dashboard (задачи 4.48.0 + 4.48.1 + 4.54.0).

Используется ``fastapi.testclient.TestClient`` — он автоматически вызывает
lifespan на входе/выходе из контекста. Перед TestClient мы инициализируем
``game.state`` через ``init_game_state(GameState.default_new_game())``;
повторный вызов в lifespan — no-op (idempotent), Sheets не дёргается.

Auto-fixture ``patch_sheets_load`` мокает ``GameStateRepo.load`` для всех
тестов в этом файле — чтобы `GET /` (который через 4.54.0 делает reload)
не ходил в реальный Sheets.
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from characteristics import game, init_game_state
from state import GameState
from web import sync as web_sync
from web.main import VERSION, app


@pytest.fixture(autouse=True)
def patch_sheets_load(monkeypatch):
    """Мокает GameStateRepo.load/save, StepsLogRepo.for_day и save_characteristic
    — чтобы тесты не ходили в реальный Sheets и не писали JSON/CSV на диск во
    время reload + max-merge (4.15) и mutating endpoint'ов (4.48.5+). Тесты,
    которые хотят assert call count или симулировать ошибку, переопределяют
    patch внутри тела теста."""
    from google_sheets_db import GameStateRepo, StepsLogRepo

    def fake_load(self):
        return game.state.to_dict() if game.state is not None else {}

    def fake_save(self, data, user_id=None):
        return None

    def fake_for_day(self, date_str, user_id=None):
        return []  # пустой лог = max-merge no-op

    monkeypatch.setattr(GameStateRepo, "load", fake_load)
    monkeypatch.setattr(GameStateRepo, "save", fake_save)
    # 4.54.2 — load_meta для save_safe (optimistic concurrency). Возвращаем
    # 0.0 чтобы pre-check всегда проходил (state.last_modified default 0.0).
    monkeypatch.setattr(GameStateRepo, "load_meta", lambda self: 0.0)
    monkeypatch.setattr(StepsLogRepo, "for_day", fake_for_day)
    # 4.54.4 — save_characteristic теперь возвращает "OK"/"STALE" и сам делает
    # Sheets через save_safe. Мокаем её через GameStateRepo.save_safe (а не
    # save напрямую) — это позволяет тестам 4.54.6 переопределять save_safe
    # для симуляции STALE и видеть полный flow STALE-обработки.
    # save_safe сам внутри вызывает self.save() на OK — поэтому tracking через
    # saved_to_sheets (которые мокают `save`) продолжает работать.
    def fake_save_characteristic():
        if game.state is None:
            return "OK"
        try:
            status = GameStateRepo().save_safe(
                game.state.to_dict(),
                expected_last_modified=game.state.last_modified,
            )
        except Exception as e:  # noqa: BLE001
            print(f"[save] Sheets sync failed (CSV-only fallback): {e}")
            return "OK"
        if status == "OK":
            game.state.take_snapshot()
        return status
    import characteristics as _ch
    import work as _wm
    monkeypatch.setattr(_ch, "save_characteristic", fake_save_characteristic)
    monkeypatch.setattr(_wm, "save_characteristic", fake_save_characteristic)
    # И в web.sync (persist_state_to_cloud зовёт save_characteristic локально —
    # после переноса helper'а из web/main.py в web/sync.py в 0.2.1b).
    import web.sync as _wsync_mod
    monkeypatch.setattr(_wsync_mod, "save_characteristic", fake_save_characteristic)
    # И в gym (finalizer skill_training_check_done зовёт save_characteristic).
    import gym as _gym
    monkeypatch.setattr(_gym, "save_characteristic", fake_save_characteristic)
    # Сброс кэша last_reload между тестами — чтобы badge от предыдущих
    # тестов не протекал в текущий.
    web_sync._reset_for_tests()


def _setup_state(state=None):
    """Сбросить container и заполнить дефолтным state — так lifespan не пойдёт в Sheets.

    По умолчанию выставляет `date_last_enter` на сегодня — чтобы тесты,
    которые не про rollover, не ловили его в _dashboard_context /
    _apply_new_steps / try_reload_state. Тесты rollover'а явно перезаписывают
    эту дату на прошлую."""
    if state is None:
        state = GameState.default_new_game()
    if state.date_last_enter == '':
        state.date_last_enter = str(datetime.now().date())
    game.state = None
    init_game_state(state)


# ----- /healthz -----

def test_healthz_returns_ok_status():
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["state_loaded"] is True
    assert body["version"] == VERSION


def test_lifespan_initializes_state_idempotent():
    """Если state уже стоит до TestClient — lifespan не пересоздаёт его."""
    _setup_state()
    pre_state = game.state
    with TestClient(app):
        assert game.state is pre_state


def test_unknown_route_returns_404():
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/this-does-not-exist")
    assert response.status_code == 404


# ----- GET / (dashboard) -----

def test_dashboard_returns_html():
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    body = response.text
    assert "2Walks" in body
    assert VERSION in body


def test_dashboard_contains_main_sections():
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/")
    body = response.text
    assert "Stats" in body
    assert "Steps" in body
    assert "Energy" in body
    assert "Money" in body
    assert "Инвентарь" in body
    assert "Экипировка" in body


def test_dashboard_does_not_have_htmx_polling_on_status_bar():
    """HTMX polling намеренно отключён в 0.2.0j — цифры обновляются только при
    F5 / submit формы. Таймеры активных сессий двигаются JS на клиенте.
    Endpoint GET /status оставлен для будущего использования (4.54.0.1)."""
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/")
    body = response.text
    # Извлекаем wrapper #status-bar и проверяем что у него нет HTMX-атрибутов
    # для авто-полинга.
    import re
    match = re.search(r'<div id="status-bar"([^>]*)>', body)
    assert match, '#status-bar wrapper not found'
    attrs = match.group(1)
    assert 'hx-get' not in attrs
    assert 'hx-trigger' not in attrs


def test_dashboard_loads_pico_and_htmx_cdn():
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/")
    body = response.text
    assert "@picocss/pico" in body
    assert "htmx.org" in body


def test_dashboard_format_remaining_js_constants_match_python():
    """0.2.1i / задача 2.10: JS `formatRemaining` использует те же константы
    что Python `format_timedelta` (365 дней год, 30 дней месяц, 7 дней неделя)
    и те же суффиксы (г / мес / нед / д). Если конста разойдутся, CLI и web
    покажут разные значения для одного и того же state."""
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/")
    body = response.text
    # Константы должны быть в JS-коде.
    assert "_SEC_YEAR = 365 * 24 * 3600" in body
    assert "_SEC_MONTH = 30 * 24 * 3600" in body
    assert "_SEC_WEEK = 7 * 24 * 3600" in body
    assert "_SEC_DAY = 24 * 3600" in body
    # Суффиксы (внутри template-литералов).
    assert "${y}г" in body
    assert "${mo}мес" in body
    assert "${w}нед" in body
    assert "${d}д" in body


def test_dashboard_shows_location_icon_and_name():
    state = GameState.default_new_game()
    state.loc = "gym"
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/")
    body = response.text
    # Icon + capitalized location name.
    assert "🏋" in body  # gym icon (без variation selector U+FE0F — Pico может не отрендерить совсем точно)
    assert "Gym" in body


# ----- GET /status (HTMX fragment) -----

def test_status_fragment_returns_html_without_full_page_wrapper():
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/status")
    assert response.status_code == 200
    body = response.text
    # Это fragment — не должно быть <html>/<body> обёрток.
    assert "<html" not in body.lower()
    assert "<body" not in body.lower()
    # Но содержание секций есть.
    assert "Stats" in body
    assert "Инвентарь" in body


def test_status_fragment_contains_core_stats():
    state = GameState.default_new_game()
    state.steps.today = 5000
    state.steps.used = 500  # → can_use = 5000 - 500 + 0 (нет бонусов в default) = 4500
    state.energy = 30
    state.money = 250
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # save_game_date_last_enter в _dashboard_context всегда пересчитывает
    # can_use = today - used + bonuses; для default state бонусы = 0 → 4500.
    assert "4,500" in body
    assert "30" in body
    assert "250" in body


# ----- Active sessions -----

def test_active_training_renders_with_data_end_ts():
    state = GameState.default_new_game()
    state.training.active = True
    state.training.skill_name = "stamina"
    # End в будущем — skill_training_check_done не должен финализировать.
    state.training.time_end = datetime.now() + timedelta(minutes=10)
    state.training.timestamp = (datetime.now() - timedelta(minutes=2)).timestamp()
    state.gym.stamina = 4
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert "Тренировка" in body
    assert "Stamina" in body
    assert "data-end-ts=" in body
    # Целевой уровень: 4 + 1 = 5
    assert "уровень 5" in body


def test_active_work_renders_with_data_end_ts():
    state = GameState.default_new_game()
    state.work.active = True
    state.work.work_type = "factory"
    state.work.salary = 5
    state.work.hours = 4
    # end в будущем — work_check_done не должна закрывать смену.
    state.work.end = datetime.now() + timedelta(hours=1)
    state.work.start = datetime.now() - timedelta(hours=1)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert "Работа" in body
    assert "Factory" in body
    # После 0.2.4a (4.23) — earnings_boost обёртка + format_money: "20.00 $".
    # earnings_boost=0 (default) → effective_salary = base = 5, total = 5*4 = 20.00.
    assert "20.00 $" in body
    assert "data-end-ts=" in body


def test_active_adventure_in_progress_shows_timer():
    state = GameState.default_new_game()
    state.adventure.active = True
    state.adventure.name = "walk_easy"
    # end_ts в будущем — приключение ещё идёт
    state.adventure.end_ts = datetime.now().timestamp() + 600
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert "Walk_Easy" in body
    assert "data-end-ts=" in body
    assert "Adventure finished" not in body


def test_finished_adventure_auto_finalizes_on_render():
    """4.48.3 — end_ts < now → render авто-финализирует приключение (active=False).
    Старого «Adventure finished / claim drop in CLI» сообщения больше нет —
    drop_notification banner (если был дроп) заменяет необходимость claim'а."""
    state = GameState.default_new_game()
    state.adventure.active = True
    state.adventure.name = "walk_15k"
    state.adventure.end_ts = datetime.now().timestamp() - 60  # 1 минуту назад
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # State финализирован — adventure inactive.
    assert state.adventure.active is False
    # Старое сообщение «claim drop in CLI» убрано.
    assert "claim drop" not in body
    # Active session timer не показывается (нечему).
    assert "data-end-ts=" not in body


def test_no_active_sessions_section_omitted():
    """Если все сессии неактивны — секция 'Активные сессии' не рендерится."""
    state = GameState.default_new_game()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert "Активные сессии" not in body


# ----- Inventory / Equipment -----

def test_empty_inventory_shows_placeholder():
    state = GameState.default_new_game()
    state.inventory = []
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert "пусто" in body


def test_inventory_renders_items():
    state = GameState.default_new_game()
    state.inventory = [
        {
            'item_name': ['ring'],
            'item_type': ['ring'],
            'grade': ['s-grade'],
            'characteristic': ['luck'],
            'bonus': [4],
            'quality': [85.5],
            'price': [171],
        }
    ]
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert "Ring" in body
    assert "s-grade" in body
    assert "+4" in body
    assert "Luck" in body
    # 4.48.6 — price теперь через format_money (с trader skill applied).
    # Trader skill=0 (default) → sell_price=171.0 → "171.00 $".
    assert "171.00 $" in body


def test_equipment_empty_slot_shows_placeholder():
    state = GameState.default_new_game()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Несколько слотов пустые — все выводятся
    assert "Голова" in body
    assert "Ступни" in body
    # И содержат маркер пустоты в равном кол-ве (7 слотов = 7 placeholder'ов).
    assert body.count("— пусто —") >= 7  # +1 если inventory тоже пуст


def test_equipment_filled_slot_shows_item_details():
    state = GameState.default_new_game()
    state.equipment.head = {
        'item_name': ['helmet'],
        'item_type': ['helmet'],
        'grade': ['a-grade'],
        'characteristic': ['stamina'],
        'bonus': [3],
        'quality': [88.0],
        'price': [132],
    }
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert "Helmet" in body
    assert "a-grade" in body
    assert "+3" in body
    assert "Stamina" in body


# ----- Progress bars (active sessions) -----

def test_active_work_renders_progress_bar_without_percent():
    """Work — таймер до конца смены + прогресс-бар (вернулся в 0.2.1v по запросу
    пользователя). Без % текста — только сам бар."""
    state = GameState.default_new_game()
    state.work.active = True
    state.work.work_type = "factory"
    state.work.salary = 5
    state.work.hours = 4
    state.work.start = datetime.now() - timedelta(hours=1)
    state.work.end = datetime.now() + timedelta(hours=1)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Таймер на месте.
    assert "data-end-ts=" in body
    # Прогресс-бар Work присутствует (training/adventure не активны — это
    # единственный <progress> в active sessions).
    assert "data-progress-start-ts=" in body
    assert "<progress" in body
    # Подписи "% Завершено" нет — work без процентного текста, в отличие от
    # training/adventure.
    assert "Завершено" not in body


def test_active_training_renders_progress_bar():
    state = GameState.default_new_game()
    state.training.active = True
    state.training.skill_name = "stamina"
    state.training.timestamp = (datetime.now() - timedelta(minutes=5)).timestamp()
    state.training.time_end = datetime.now() + timedelta(minutes=5)
    state.gym.stamina = 4
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert "<progress" in body
    # ~50% прогресса.
    import re
    match = re.search(r'<progress[^>]*data-progress-start-ts[^>]*value="([0-9]+\.[0-9]+)"', body)
    assert match
    pct = float(match.group(1))
    assert 30 <= pct <= 70


def test_active_adventure_renders_progress_bar():
    state = GameState.default_new_game()
    state.adventure.active = True
    state.adventure.name = "walk_easy"
    state.adventure.start_ts = (datetime.now() - timedelta(minutes=5)).timestamp()
    state.adventure.end_ts = (datetime.now() + timedelta(minutes=5)).timestamp()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert "<progress" in body
    assert "data-progress-start-ts=" in body
    # Не помечено как finished, прогресс ~50%.
    assert "✓ Завершено" not in body
    import re
    match = re.search(r'<progress[^>]*data-progress-start-ts[^>]*value="([0-9]+\.[0-9]+)"', body)
    assert match
    pct = float(match.group(1))
    assert 30 <= pct <= 70


def test_finished_work_auto_finalized_in_dashboard_context():
    """Work с end в прошлом → auto-finalize в _dashboard_context: зарплата
    зачислена, work очищен, прогресс-бар работы НЕ рендерится. См. также
    test_dashboard_auto_finalizes_expired_work_session ниже."""
    state = GameState.default_new_game()
    state.work.active = True
    state.work.work_type = "factory"
    state.work.salary = 5
    state.work.hours = 4
    state.work.start = datetime.now() - timedelta(hours=2)
    state.work.end = datetime.now() - timedelta(seconds=1)
    pre_money = state.money
    _setup_state(state)

    with TestClient(app) as client:
        response = client.get("/status")

    body = response.text
    # Зарплата зачислена.
    assert state.money == pre_money + 20  # 5 * 4
    # Work очищен — нет завершённого progress bar.
    assert state.work.active is False
    assert "✓ Завершено" not in body


def test_finished_adventure_finalized_no_progress_bar_remains():
    """4.48.3 — Adventure с end в прошлом → авто-финализация → progress bar
    исчезает (active=False, ветка active-sessions не рендерится). Старого
    `value="100.00"` / «✓ Завершено» / «claim drop» сообщений больше нет."""
    state = GameState.default_new_game()
    state.adventure.active = True
    state.adventure.name = "walk_easy"
    state.adventure.start_ts = (datetime.now() - timedelta(hours=1)).timestamp()
    state.adventure.end_ts = (datetime.now() - timedelta(seconds=1)).timestamp()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # State финализирован.
    assert state.adventure.active is False
    # Старые маркеры финализации убраны (заменены drop_notification banner'ом
    # либо тихим финализом если не было дропа).
    assert "claim drop" not in body
    assert "Adventure finished" not in body


def test_no_active_session_renders_no_progress_bars():
    state = GameState.default_new_game()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Прогресс-бары секции "Активные сессии" не рендерятся (Level прогресс — только обычный прогресс-бар).
    assert "data-progress-start-ts=" not in body


# ----- Sync (task 4.54.0) -----

def test_get_root_triggers_sheets_reload(monkeypatch):
    """GET / должен дёргать GameStateRepo.load() (свежие данные из Sheets)."""
    from google_sheets_db import GameStateRepo
    calls = []

    def counting_load(self):
        calls.append(1)
        return game.state.to_dict() if game.state else {}

    monkeypatch.setattr(GameStateRepo, "load", counting_load)
    _setup_state()

    with TestClient(app) as client:
        client.get("/")

    assert len(calls) == 1


def test_get_status_does_not_trigger_sheets_reload(monkeypatch):
    """GET /status (HTMX-полинг) — НЕ дёргает Sheets, рендерит из памяти."""
    from google_sheets_db import GameStateRepo
    calls = []

    def counting_load(self):
        calls.append(1)
        return game.state.to_dict() if game.state else {}

    monkeypatch.setattr(GameStateRepo, "load", counting_load)
    _setup_state()

    with TestClient(app) as client:
        client.get("/status")

    assert calls == []


def test_get_root_with_sheets_error_returns_200_and_shows_badge(monkeypatch):
    """Сетевая ошибка во время reload — возвращаем 200 + кэшированный state + badge."""
    from google_sheets_db import GameStateRepo

    def failing_load(self):
        raise RuntimeError("Network down")

    monkeypatch.setattr(GameStateRepo, "load", failing_load)
    _setup_state()

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    body = response.text
    assert "Cloud sync failed" in body
    assert "Network down" in body
    # state остался кэшированным — основной контент рендерится.
    assert "Stats" in body


def test_dashboard_no_badge_when_reload_succeeds():
    """Успешный reload — badge не должен показываться."""
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/")
    body = response.text
    assert "Cloud sync failed" not in body


def test_status_fragment_does_not_show_reload_badge():
    """Badge показывается только в полной странице (dashboard), не в HTMX-фрагменте."""
    _setup_state()
    with TestClient(app) as client:
        # Сначала вызвать reload, чтобы last_reload был заполнен (даже успешный).
        client.get("/")
        response = client.get("/status")
    # Fragment не содержит badge даже после reload.
    assert "Cloud sync failed" not in response.text


def test_dashboard_no_polling_intervals_present():
    """Полная защита от регрессии: ни 15s, ни 60s polling интервалов на
    странице (HTMX-полинг отключён в 0.2.0j)."""
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/")
    body = response.text
    assert 'hx-trigger="every 15s"' not in body
    assert 'hx-trigger="every 60s"' not in body
    # Любой "every Ns" pattern.
    import re
    assert not re.search(r'hx-trigger="every \d+s"', body)


# ----- Steps input (task 4.48.2) -----

def test_api_steps_valid_value_applies_and_logs(monkeypatch):
    from google_sheets_db import StepsLogRepo
    appended = []
    monkeypatch.setattr(StepsLogRepo, "append",
                        lambda self, ts, steps, source, user_id="alex":
                        appended.append((ts, steps, source)))

    state = GameState.default_new_game()
    state.steps.today = 1000
    state.steps.used = 200
    _setup_state(state)

    with TestClient(app) as client:
        response = client.post("/api/steps", json={"steps": 5000})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["applied"] is True
    assert body["steps_today"] == 5000
    assert state.steps.today == 5000
    # can_use = today - used + bonuses; bonuses = 0 для default state.
    assert state.steps.can_use == 5000 - 200
    assert len(appended) == 1
    assert appended[0][1] == 5000
    assert appended[0][2] == "web"


def test_api_steps_below_today_is_rejected_no_log(monkeypatch):
    from google_sheets_db import StepsLogRepo
    appended = []
    monkeypatch.setattr(StepsLogRepo, "append",
                        lambda self, ts, steps, source, user_id="alex":
                        appended.append((ts, steps, source)))

    state = GameState.default_new_game()
    state.steps.today = 5000
    _setup_state(state)

    with TestClient(app) as client:
        response = client.post("/api/steps", json={"steps": 4000})

    assert response.status_code == 422
    body = response.json()
    assert body["applied"] is False
    assert "должно быть больше" in body["error"]
    assert state.steps.today == 5000  # state не изменён
    assert appended == []  # log не вызван


def test_api_steps_equal_to_today_is_rejected():
    state = GameState.default_new_game()
    state.steps.today = 5000
    _setup_state(state)

    with TestClient(app) as client:
        response = client.post("/api/steps", json={"steps": 5000})

    assert response.status_code == 422
    assert state.steps.today == 5000


def test_api_steps_negative_value_rejected_by_pydantic():
    _setup_state()
    with TestClient(app) as client:
        response = client.post("/api/steps", json={"steps": -1})
    assert response.status_code == 422


def test_api_steps_non_int_rejected():
    _setup_state()
    with TestClient(app) as client:
        response = client.post("/api/steps", json={"steps": "hello"})
    assert response.status_code == 422


def test_api_steps_sheets_error_returns_503_state_unchanged(monkeypatch):
    from google_sheets_db import StepsLogRepo
    def failing_append(self, ts, steps, source, user_id="alex"):
        raise RuntimeError("Network down")
    monkeypatch.setattr(StepsLogRepo, "append", failing_append)

    state = GameState.default_new_game()
    state.steps.today = 1000
    _setup_state(state)

    with TestClient(app) as client:
        response = client.post("/api/steps", json={"steps": 5000})

    assert response.status_code == 503
    body = response.json()
    assert body["ok"] is False
    assert "Sheets unavailable" in body["error"]
    assert state.steps.today == 1000  # state НЕ изменён при Sheets-ошибке


def test_api_steps_with_explicit_ts_and_source(monkeypatch):
    from google_sheets_db import StepsLogRepo
    appended = []
    monkeypatch.setattr(StepsLogRepo, "append",
                        lambda self, ts, steps, source, user_id="alex":
                        appended.append((ts, steps, source)))

    _setup_state()
    with TestClient(app) as client:
        response = client.post("/api/steps", json={
            "steps": 7000,
            "ts": 1746125425.5,
            "source": "auto",
        })

    assert response.status_code == 200
    assert appended[0] == (1746125425.5, 7000, "auto")


# ----- /web/steps (HTML form) -----

def test_web_steps_valid_returns_html_fragment_with_updated_value(monkeypatch):
    from google_sheets_db import StepsLogRepo
    monkeypatch.setattr(StepsLogRepo, "append",
                        lambda self, ts, steps, source, user_id="alex": None)

    state = GameState.default_new_game()
    state.steps.today = 1000
    state.steps.used = 0
    _setup_state(state)

    with TestClient(app) as client:
        response = client.post("/web/steps", data={"steps": "8500"})

    assert response.status_code == 200
    body = response.text
    # Fragment, не полная страница.
    assert "<html" not in body.lower()
    assert "Stats" in body
    # Новый steps.today применён → can_use = 8500 - 0 = 8500.
    assert "8,500" in body
    # Форма закрыта (не form-visible).
    assert 'class="form-visible"' not in body


def test_web_steps_invalid_value_keeps_form_open_with_error_message(monkeypatch):
    from google_sheets_db import StepsLogRepo
    appended = []
    monkeypatch.setattr(StepsLogRepo, "append",
                        lambda self, ts, steps, source, user_id="alex":
                        appended.append((ts, steps, source)))

    state = GameState.default_new_game()
    state.steps.today = 5000
    _setup_state(state)

    with TestClient(app) as client:
        response = client.post("/web/steps", data={"steps": "3000"})

    # Возвращаем 200 с ошибкой в теле — для HTMX swap.
    assert response.status_code == 200
    body = response.text
    assert "должно быть больше" in body
    # form-visible маркер есть.
    assert "form-visible" in body
    # Log не вызван.
    assert appended == []


def test_dashboard_includes_steps_form_with_min_attribute():
    state = GameState.default_new_game()
    state.steps.today = 1500
    _setup_state(state)

    with TestClient(app) as client:
        response = client.get("/")

    body = response.text
    # Форма + клиентская валидация min=today+1.
    assert 'name="steps"' in body
    assert 'min="1501"' in body
    assert 'hx-post="/web/steps"' in body
    # Кнопка Применить и Отмена.
    assert "Применить" in body
    assert "Отмена" in body


def test_dashboard_steps_form_hidden_by_default():
    """form-visible класс отсутствует на свежем dashboard'е."""
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/")
    body = response.text
    # Класс form-visible отсутствует — форма скрыта (CSS hide).
    assert 'class="form-visible"' not in body


# ----- Section ordering -----

def test_equipment_section_appears_before_inventory():
    """Экипировка идёт раньше инвентаря на странице."""
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    eq_pos = body.find('id="equipment"')
    inv_pos = body.find('id="inventory"')
    assert eq_pos > 0 and inv_pos > 0
    assert eq_pos < inv_pos


# ----- Collapsible sections (0.2.0j follow-up) -----

def test_inventory_uses_details_element():
    """Инвентарь обёрнут в <details><summary>, по умолчанию свёрнут."""
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Внутри #inventory есть <details> и <summary>.
    inv_start = body.find('id="inventory"')
    inv_section = body[inv_start:inv_start + 2000]
    # После 0.2.4d (4.50.2) details может рендериться с пустым `open` атрибутом
    # ({% if pending_drop_view.active %}open{% endif %} → "<details >") когда
    # pending=None — поэтому regex на тег без open.
    import re
    assert re.search(r'<details\s*>', inv_section) is not None
    assert "<summary>" in inv_section
    # Свернут по умолчанию (нет open атрибута).
    assert "<details open" not in inv_section


def test_equipment_uses_details_element():
    """Экипировка обёрнута в <details><summary>, по умолчанию свёрнута."""
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    eq_start = body.find('id="equipment"')
    eq_section = body[eq_start:eq_start + 2000]
    assert "<details>" in eq_section
    assert "<summary>" in eq_section
    assert "<details open" not in eq_section


def test_inventory_summary_shows_count():
    """Summary инвентаря показывает счётчик (N/cap). cap = 10 (base) после 0.2.4b."""
    state = GameState.default_new_game()
    state.inventory = [
        {"item_name": ["x"], "item_type": ["ring"], "grade": ["a-grade"],
         "characteristic": ["luck"], "bonus": [3], "quality": [80.0], "price": [120]},
        {"item_name": ["y"], "item_type": ["helmet"], "grade": ["b-grade"],
         "characteristic": ["stamina"], "bonus": [2], "quality": [70.0], "price": [70]},
    ]
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Summary содержит "(2/10)" сразу после "Инвентарь</strong>".
    assert "Инвентарь</strong> (2/10)" in body


def test_equipment_summary_shows_worn_count():
    """Summary экипировки показывает (N/7)."""
    state = GameState.default_new_game()
    state.equipment.head = {
        "item_name": ["helmet"], "item_type": ["helmet"], "grade": ["a-grade"],
        "characteristic": ["stamina"], "bonus": [3], "quality": [80.0], "price": [120],
    }
    state.equipment.neck = {
        "item_name": ["necklace"], "item_type": ["necklace"], "grade": ["b-grade"],
        "characteristic": ["luck"], "bonus": [2], "quality": [70.0], "price": [70],
    }
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # 2 надетых из 7 → "(2/7)".
    assert "(2/7)" in body


def test_equipment_summary_shows_only_nonzero_bonuses():
    """Summary экипировки показывает только не-нулевые бонусы (stamina выше 0
    видно, energy_max/speed/luck с +0 — спрятаны)."""
    state = GameState.default_new_game()
    state.equipment.head = {
        "item_name": ["helmet"], "item_type": ["helmet"], "grade": ["a-grade"],
        "characteristic": ["stamina"], "bonus": [5], "quality": [80.0], "price": [120],
    }
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Найдём summary блока экипировки.
    eq_start = body.find('id="equipment"')
    summary_start = body.find("<summary>", eq_start)
    summary_end = body.find("</summary>", summary_start)
    summary = body[summary_start:summary_end]
    # stamina ненулевой → отображается с +5.
    assert "stamina +5" in summary
    # Остальные нулевые → скрыты.
    assert "energy_max" not in summary
    assert "speed" not in summary
    assert "luck" not in summary


def test_equipment_summary_no_bonuses_block_when_all_zero():
    """Если ни одного бонуса нет — <small> с "·" префиксом не рендерится в summary."""
    state = GameState.default_new_game()
    # Никакой экипировки → все 4 бонуса = 0.
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Найдём summary блока экипировки.
    eq_start = body.find('id="equipment"')
    summary_start = body.find("<summary>", eq_start)
    summary_end = body.find("</summary>", summary_start)
    summary = body[summary_start:summary_end]
    assert "stamina" not in summary
    assert "energy_max" not in summary
    assert "speed" not in summary
    assert "luck" not in summary
    assert "·" not in summary  # никаких разделителей не осталось


def test_equipment_summary_shows_multiple_nonzero_bonuses():
    """При нескольких ненулевых — все они показаны в summary."""
    state = GameState.default_new_game()
    state.equipment.head = {
        "item_name": ["helmet"], "item_type": ["helmet"], "grade": ["a-grade"],
        "characteristic": ["stamina"], "bonus": [3], "quality": [80.0], "price": [120],
    }
    state.equipment.neck = {
        "item_name": ["necklace"], "item_type": ["necklace"], "grade": ["a-grade"],
        "characteristic": ["luck"], "bonus": [4], "quality": [80.0], "price": [120],
    }
    state.equipment.foots = {
        "item_name": ["shoes"], "item_type": ["shoes"], "grade": ["b-grade"],
        "characteristic": ["speed_skill"], "bonus": [2], "quality": [70.0], "price": [70],
    }
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    eq_start = body.find('id="equipment"')
    summary_start = body.find("<summary>", eq_start)
    summary_end = body.find("</summary>", summary_start)
    summary = body[summary_start:summary_end]
    assert "stamina +3" in summary
    assert "luck +4" in summary
    assert "speed +2" in summary
    # energy_max нулевой → скрыт.
    assert "energy_max" not in summary


def test_bonuses_section_uses_details_collapsed_by_default():
    """Бонусы Steps + Energy перенесены в отдельный <details> блок, свёрнут."""
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    bon_start = body.find('id="bonuses"')
    assert bon_start > 0, "section id=bonuses missing"
    bon_section = body[bon_start:bon_start + 2000]
    assert "<details>" in bon_section
    assert "<summary>" in bon_section
    assert "<details open" not in bon_section


def test_bonuses_section_contains_steps_breakdown():
    state = GameState.default_new_game()
    state.steps.today = 10000
    state.gym.stamina = 5
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    bon_start = body.find('id="bonuses"')
    bon_section = body[bon_start:bon_start + 2000]
    # Внутри секции бонусов: stamina/equipment/daily/level + всего/percent.
    assert "stamina" in bon_section
    assert "equipment" in bon_section
    assert "daily" in bon_section
    assert "level" in bon_section
    assert "Всего:" in bon_section
    assert "%" in bon_section


def test_bonuses_section_contains_energy_breakdown():
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    bon_start = body.find('id="bonuses"')
    bon_section = body[bon_start:bon_start + 2000]
    # Energy block внутри секции бонусов.
    assert "🔋" in bon_section
    assert "Energy" in bon_section


def test_total_used_moved_into_bonuses_section():
    """`Total used: N шагов` перенесено из Stats в свёрнутый блок Бонусы."""
    state = GameState.default_new_game()
    state.steps.total_used = 123456
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Total used должен быть только внутри секции id="bonuses".
    bon_start = body.find('id="bonuses"')
    assert bon_start > 0
    bon_end = body.find('</section>', bon_start)
    bon_section = body[bon_start:bon_end]
    assert "Total used: 123,456" in bon_section
    # И НЕ должен быть ранее по странице (например, в Stats).
    pre_bonuses = body[:bon_start]
    assert "Total used:" not in pre_bonuses


def test_steps_section_no_longer_inline_bonus_line():
    """После переноса в <details> — старая строка 'Bonus 🏃: ...' удалена из стартового
    блока Steps в Stats."""
    state = GameState.default_new_game()
    state.steps.today = 5000
    state.gym.stamina = 5
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Inline-бонус "Bonus 🏃: stamina +X · equipment +Y..." больше не появляется
    # вне details. Внутри details строка ещё есть (там детали показаны).
    # Проверяем по уникальной фразе "Bonus 🏃" — она была в исходной inline-строке.
    assert "Bonus 🏃:" not in body


def test_energy_section_no_longer_inline_bonus_line():
    """После переноса в <details> — строка 'Equipment +X · daily +Y · level +Z'
    под Energy больше не отображается inline."""
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Извлекаем кусок между Energy stat-row и Money stat-row — там не должно
    # быть отдельной "Equipment +N · daily +M · level +K" строки.
    energy_pos = body.find("🔋")
    money_pos = body.find("💰")
    assert 0 < energy_pos < money_pos
    between = body[energy_pos:money_pos]
    # В этом куске нет полного шаблона строки бонусов (она перенесена в <details>).
    import re
    assert not re.search(r"Equipment\s*\+\d+\s*·\s*daily\s*\+\d+\s*·\s*level\s*\+\d+", between)


def test_inventory_items_still_in_dom_when_collapsed():
    """Содержимое <details> остаётся в DOM даже когда блок свёрнут — это
    важно для accessibility и поиска. Браузер только скрывает визуально."""
    state = GameState.default_new_game()
    state.inventory = [{
        "item_name": ["uniqitem"], "item_type": ["ring"], "grade": ["s-grade"],
        "characteristic": ["luck"], "bonus": [4], "quality": [85.0], "price": [170],
    }]
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Item в DOM несмотря на свёрнутость.
    assert "Ring" in body
    assert "s-grade" in body
    assert "+4" in body


# ----- Work UI (task 4.48.5) -----

def _state_for_work(steps_can_use=8000, energy=80):
    """Подготовленный state с достаточными ресурсами для всех вакансий
    (factory @500/7 = 16 ч / 11 ч; cap 8 → 8 ч). Для forwarder (@5000/30)
    хватит на 1 ч (8000/5000=1, 80/30=2 → min 1)."""
    state = GameState.default_new_game()
    state.steps.today = steps_can_use
    state.steps.can_use = steps_can_use
    state.energy = energy
    return state


def test_web_work_section_renders_in_status_fragment():
    """В фрагменте присутствует секция id='work' с обёрткой <details>."""
    state = _state_for_work()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert 'id="work"' in body
    work_pos = body.find('id="work"')
    work_section = body[work_pos:work_pos + 4000]
    assert "<details" in work_section
    assert "<summary>" in work_section


def test_web_work_section_collapsed_when_not_active():
    """Не работаешь → блок Work свёрнут (нет open атрибута)."""
    _setup_state(_state_for_work())
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    work_pos = body.find('id="work"')
    work_section = body[work_pos:work_pos + 4000]
    # <details> без open (Jinja может оставить пробел после имени тега).
    assert "<details" in work_section
    assert "<details open" not in work_section


def test_web_work_section_collapsed_even_when_active():
    """Работаешь → блок Work всё равно свёрнут по умолчанию. Игрок сам
    разворачивает, чтобы увидеть форму '+часов' и не путать со step-формой."""
    state = _state_for_work()
    state.work.active = True
    state.work.work_type = "watchman"
    state.work.salary = 2
    state.work.hours = 3
    state.work.start = datetime.now() - timedelta(hours=1)
    state.work.end = datetime.now() + timedelta(hours=2)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    work_pos = body.find('id="work"')
    work_section = body[work_pos:work_pos + 4000]
    assert "<details open" not in work_section
    # Но контент формы add_hours всё равно в DOM (для accessibility).
    assert 'hx-post="/web/work/add_hours"' in work_section


def test_web_work_renders_all_4_vacancies_when_not_active():
    """Меню вакансий: 4 формы старта смены, по одной на каждую вакансию."""
    _setup_state(_state_for_work())
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Все 4 названия вакансий присутствуют.
    assert "Сторож" in body
    assert "Завод" in body
    assert "Курьер" in body
    assert "Экспедитор" in body
    # И 4 формы со старт-ендпоинтом.
    assert body.count('hx-post="/web/work/start"') == 4


def test_web_work_renders_add_hours_form_when_active():
    """Уже работаешь → нет меню вакансий, есть форма '+часов'."""
    state = _state_for_work()
    state.work.active = True
    state.work.work_type = "factory"
    state.work.salary = 5
    state.work.hours = 2
    state.work.start = datetime.now() - timedelta(hours=1)
    state.work.end = datetime.now() + timedelta(hours=1)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert 'hx-post="/web/work/add_hours"' in body
    # И нет старта смены — посреди смены нельзя сменить вакансию.
    assert 'hx-post="/web/work/start"' not in body


def test_web_work_max_hours_button_count_caps_at_8():
    """Cap = 8 кнопок даже если ресурсов хватает на 100 часов."""
    state = _state_for_work(steps_can_use=10_000_000, energy=10000)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # У watchman (@200 шагов/4 эн) с такими ресурсами max должно быть >> 8 — но cap 8.
    # Считаем кнопки в первой watchman-форме: hidden input value="watchman" + 8 hours-button'ов.
    work_pos = body.find('id="work"')
    work_section = body[work_pos:work_pos + 8000]
    # Найти watchman article (hidden input value="watchman")
    watchman_form_start = work_section.find('value="watchman"')
    assert watchman_form_start > 0
    # До </form>
    form_end = work_section.find('</form>', watchman_form_start)
    watchman_form = work_section[watchman_form_start:form_end]
    # Кнопки 1ч..8ч — ровно 8 штук, не больше.
    import re
    btns = re.findall(r'name="hours" value="(\d+)"', watchman_form)
    assert btns == ["1", "2", "3", "4", "5", "6", "7", "8"]


def test_web_work_no_button_when_not_enough_resources():
    """Forwarder требует 5000 шагов/30 эн в час. Если шагов/энергии впритык на 0
    часов — нет ни одной кнопки запуска для forwarder."""
    state = _state_for_work(steps_can_use=100, energy=10)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Forwarder в DOM, но без кнопок.
    work_pos = body.find('id="work"')
    work_section = body[work_pos:work_pos + 8000]
    forwarder_pos = work_section.find('Экспедитор')
    assert forwarder_pos > 0
    # До конца article (или следующего article).
    article_end = work_section.find('</article>', forwarder_pos)
    forwarder_block = work_section[forwarder_pos:article_end]
    # Нет hidden input forwarder → форма не сгенерирована (max_hours=0).
    assert 'value="forwarder"' not in forwarder_block
    assert "не хватает" in forwarder_block


def test_web_work_start_with_valid_params_starts_session():
    state = _state_for_work()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/web/work/start", data={"work_type": "watchman", "hours": "2"})
    assert response.status_code == 200
    # state.work.active теперь True.
    assert state.work.active is True
    assert state.work.work_type == "watchman"
    assert state.work.hours == 2
    # И фрагмент содержит форму add_hours (т.к. работаем).
    body = response.text
    assert 'hx-post="/web/work/add_hours"' in body


def test_web_work_start_with_insufficient_resources_returns_error():
    """Forwarder требует 5000 шагов/30 эн в час; на 2 часа = 10к шагов/60 эн.
    State.steps=8000 — не хватает."""
    state = _state_for_work(steps_can_use=8000, energy=80)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/web/work/start", data={"work_type": "forwarder", "hours": "2"})
    assert response.status_code == 200  # фрагмент с error
    assert state.work.active is False  # не запустилось
    body = response.text
    assert "❌" in body
    assert "Не хватает ресурсов" in body


def test_web_work_start_with_invalid_work_type_returns_error():
    state = _state_for_work()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/web/work/start", data={"work_type": "ceo", "hours": "1"})
    assert response.status_code == 200
    assert state.work.active is False
    body = response.text
    assert "Неизвестная вакансия" in body


def test_web_work_start_when_already_working_rejects():
    """Старт новой смены поверх активной — отвергается."""
    state = _state_for_work()
    state.work.active = True
    state.work.work_type = "watchman"
    state.work.salary = 2
    state.work.hours = 1
    state.work.start = datetime.now() - timedelta(minutes=30)
    state.work.end = datetime.now() + timedelta(hours=1)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/web/work/start", data={"work_type": "factory", "hours": "1"})
    assert response.status_code == 200
    # work_type не сменился.
    assert state.work.work_type == "watchman"
    body = response.text
    assert "Уже работаешь" in body


def test_web_work_add_hours_when_active_extends_session():
    state = _state_for_work()
    state.work.active = True
    state.work.work_type = "watchman"
    state.work.salary = 2
    state.work.hours = 1
    state.work.start = datetime.now() - timedelta(minutes=30)
    state.work.end = datetime.now() + timedelta(hours=1)
    _setup_state(state)
    pre_hours = state.work.hours
    with TestClient(app) as client:
        response = client.post("/web/work/add_hours", data={"hours": "2"})
    assert response.status_code == 200
    # Часы увеличились.
    assert state.work.hours == pre_hours + 2


def test_web_work_add_hours_when_not_active_returns_error():
    state = _state_for_work()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/web/work/add_hours", data={"hours": "1"})
    assert response.status_code == 200
    body = response.text
    assert "не работаешь" in body.lower()
    assert state.work.active is False


# ----- /api/work/* (JSON) -----

def test_api_work_start_with_valid_params():
    state = _state_for_work()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/work/start", json={"work_type": "watchman", "hours": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["work"]["active"] is True
    assert body["work"]["work_type"] == "watchman"
    assert body["work"]["hours"] == 2
    assert body["work"]["salary"] == 2
    assert body["work"]["start_ts"] is not None
    assert body["work"]["end_ts"] is not None


def test_api_work_start_with_invalid_hours_pydantic_422():
    """Pydantic ловит hours=0/9 до того, как доходит до handler'а."""
    _setup_state(_state_for_work())
    with TestClient(app) as client:
        r1 = client.post("/api/work/start", json={"work_type": "watchman", "hours": 0})
        r2 = client.post("/api/work/start", json={"work_type": "watchman", "hours": 9})
    assert r1.status_code == 422
    assert r2.status_code == 422


def test_api_work_start_with_unknown_work_type_returns_422():
    _setup_state(_state_for_work())
    with TestClient(app) as client:
        response = client.post("/api/work/start", json={"work_type": "ceo", "hours": 1})
    assert response.status_code == 422
    body = response.json()
    assert body["ok"] is False
    assert "Неизвестная вакансия" in body["error"]


def test_api_work_start_with_insufficient_resources_returns_422():
    state = _state_for_work(steps_can_use=8000, energy=80)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/work/start", json={"work_type": "forwarder", "hours": 2})
    assert response.status_code == 422
    body = response.json()
    assert body["ok"] is False
    assert "Не хватает ресурсов" in body["error"]


def test_api_work_start_when_already_working_returns_409():
    state = _state_for_work()
    state.work.active = True
    state.work.work_type = "watchman"
    state.work.salary = 2
    state.work.hours = 1
    state.work.start = datetime.now() - timedelta(minutes=30)
    state.work.end = datetime.now() + timedelta(hours=1)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/work/start", json={"work_type": "factory", "hours": 1})
    assert response.status_code == 409
    body = response.json()
    assert body["ok"] is False
    assert body["work"]["work_type"] == "watchman"


def test_api_work_add_hours_when_active():
    state = _state_for_work()
    state.work.active = True
    state.work.work_type = "watchman"
    state.work.salary = 2
    state.work.hours = 1
    state.work.start = datetime.now() - timedelta(minutes=30)
    state.work.end = datetime.now() + timedelta(hours=1)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/work/add_hours", json={"hours": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["work"]["hours"] == 3


def test_api_work_add_hours_when_not_active_returns_409():
    _setup_state(_state_for_work())
    with TestClient(app) as client:
        response = client.post("/api/work/add_hours", json={"hours": 2})
    assert response.status_code == 409
    body = response.json()
    assert body["ok"] is False


# ----- Auto-finalize (work_check_done в _dashboard_context) -----

def test_dashboard_auto_finalizes_expired_work_session():
    """Если state.work.end в прошлом, заход на /status (или GET /) должен
    автоматически закрыть смену через work_check_done() и зачислить зарплату."""
    state = _state_for_work()
    state.work.active = True
    state.work.work_type = "watchman"
    state.work.salary = 2
    state.work.hours = 4
    state.work.start = datetime.now() - timedelta(hours=2)
    state.work.end = datetime.now() - timedelta(seconds=1)
    pre_money = state.money
    _setup_state(state)

    with TestClient(app) as client:
        response = client.get("/status")

    assert response.status_code == 200
    # Зарплата зачислена: 2 $ × 4 ч = 8 $.
    assert state.money == pre_money + 8
    # Смена очищена.
    assert state.work.active is False
    assert state.work.work_type is None
    assert state.work.hours == 0


def test_dashboard_does_not_finalize_active_unfinished_work():
    """Если work.end в будущем — work_check_done не трогает state."""
    state = _state_for_work()
    state.work.active = True
    state.work.work_type = "watchman"
    state.work.salary = 2
    state.work.hours = 4
    state.work.start = datetime.now() - timedelta(minutes=10)
    state.work.end = datetime.now() + timedelta(hours=1)
    pre_money = state.money
    _setup_state(state)

    with TestClient(app) as client:
        response = client.get("/status")

    assert response.status_code == 200
    assert state.work.active is True
    assert state.money == pre_money  # ничего не зачислено


# ----- Section ordering for Work -----

def test_web_work_start_persists_state_to_cloud(monkeypatch):
    """REGRESSION: после успешного /web/work/start state должен попасть в
    Sheets+CSV+JSON. Иначе (как было до фикса) у игрока в браузере крутится
    таймер, но при рестарте uvicorn'а или CLI-чтении смены нет.

    После 4.54.4: autouse fixture's fake_save_characteristic вызывает
    GameStateRepo.save → tracking через saved_to_sheets достаточен.
    """
    from google_sheets_db import GameStateRepo
    saved_to_sheets = []

    monkeypatch.setattr(GameStateRepo, "save",
                        lambda self, data, user_id=None: saved_to_sheets.append(data))

    _setup_state(_state_for_work())
    with TestClient(app) as client:
        response = client.post("/web/work/start", data={"work_type": "watchman", "hours": "1"})

    assert response.status_code == 200
    assert len(saved_to_sheets) == 1, "GameStateRepo.save (Sheets) должен быть вызван"
    # И snapshot (плоский legacy-формат) содержит активную смену.
    snapshot = saved_to_sheets[0]
    assert snapshot["working"] is True
    assert snapshot["work"] == "watchman"


def test_web_work_add_hours_persists_state_to_cloud(monkeypatch):
    """REGRESSION: успешный add_hours тоже должен синкать state в облако."""
    from google_sheets_db import GameStateRepo
    saved_to_sheets = []
    monkeypatch.setattr(GameStateRepo, "save",
                        lambda self, data, user_id=None: saved_to_sheets.append(data))

    state = _state_for_work()
    state.work.active = True
    state.work.work_type = "watchman"
    state.work.salary = 2
    state.work.hours = 1
    state.work.start = datetime.now() - timedelta(minutes=30)
    state.work.end = datetime.now() + timedelta(hours=1)
    _setup_state(state)

    with TestClient(app) as client:
        response = client.post("/web/work/add_hours", data={"hours": "1"})

    assert response.status_code == 200
    assert len(saved_to_sheets) == 1
    assert saved_to_sheets[0]["working_hours"] == 2


def test_api_work_start_persists_state_to_cloud(monkeypatch):
    from google_sheets_db import GameStateRepo
    saved_to_sheets = []
    monkeypatch.setattr(GameStateRepo, "save",
                        lambda self, data, user_id=None: saved_to_sheets.append(data))

    _setup_state(_state_for_work())
    with TestClient(app) as client:
        response = client.post("/api/work/start", json={"work_type": "watchman", "hours": 1})

    assert response.status_code == 200
    assert len(saved_to_sheets) == 1
    assert saved_to_sheets[0]["working"] is True


def test_web_work_failed_validation_does_not_persist(monkeypatch):
    """Если ресурсов не хватает / unknown work_type → state не мутирован,
    persist НЕ вызван (нет смысла писать неизменённый state в Sheets).

    После 4.54.4: tracking через GameStateRepo.save (autouse fixture'а
    fake_save_characteristic зовёт его, если бы persist отработал)."""
    from google_sheets_db import GameStateRepo
    saved_to_sheets = []
    monkeypatch.setattr(GameStateRepo, "save",
                        lambda self, data, user_id=None: saved_to_sheets.append(data))

    _setup_state(_state_for_work())
    with TestClient(app) as client:
        # Unknown work_type → 422-валидация Python.
        client.post("/web/work/start", data={"work_type": "ceo", "hours": "1"})

    assert saved_to_sheets == []


def test_web_work_persists_even_if_sheets_save_fails(monkeypatch, capsys):
    """Sheets save fail → не блокирует endpoint, state остаётся мутирован
    локально (CSV/JSON синкнулся первым), uvicorn пишет в лог про fail."""
    from google_sheets_db import GameStateRepo
    def failing_save(self, data, user_id=None):
        raise RuntimeError("Sheets API quota exceeded")
    monkeypatch.setattr(GameStateRepo, "save", failing_save)

    _setup_state(_state_for_work())
    with TestClient(app) as client:
        response = client.post("/web/work/start", data={"work_type": "watchman", "hours": "1"})

    # Endpoint всё равно отвечает 200.
    assert response.status_code == 200
    # State в RAM мутирован — смена активна.
    assert game.state.work.active is True
    # В лог записано про Sheets-fail (4.54.4 — теперь "Sheets sync failed (CSV-only fallback)").
    captured = capsys.readouterr()
    assert "Sheets sync failed" in captured.out or "Sheets save failed" in captured.out


def test_work_section_appears_after_active_sessions():
    """Order: Stats → (Active sessions if active) → Work → Бонусы → ...

    Исторически Work был выше Active sessions, но в 0.2.1c follow-up
    переставлены — игроку важнее видеть текущий таймер прямо под Stats."""
    state = _state_for_work()
    # Чтобы Active sessions точно отрисовалась, добавим тренировку.
    state.training.active = True
    state.training.skill_name = "stamina"
    state.training.timestamp = (datetime.now() - timedelta(minutes=5)).timestamp()
    state.training.time_end = datetime.now() + timedelta(minutes=5)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    stats_pos = body.find('id="stats"')
    active_pos = body.find('id="active-sessions"')
    work_pos = body.find('id="work"')
    bonuses_pos = body.find('id="bonuses"')
    assert 0 < stats_pos < active_pos < work_pos < bonuses_pos


# ----- Day rollover в web (task 4.54.0.2) -----

def test_try_reload_state_triggers_rollover_when_date_is_stale(monkeypatch):
    """try_reload_state после успешного reload зовёт save_game_date_last_enter
    — это переносит state на сегодня, обнуляет today/used и persist'ит."""
    from web import sync as web_sync_mod
    from google_sheets_db import GameStateRepo

    # state с вчерашней датой (yesterday) — rollover должен сработать.
    state = GameState.default_new_game()
    state.date_last_enter = '2020-01-01'  # давно в прошлом
    state.steps.today = 8000
    state.steps.used = 200
    _setup_state(state)
    # Sheets возвращает то же самое (мокнуто в autouse-фикстуре).

    persist_calls = []
    monkeypatch.setattr(web_sync_mod, "persist_state_to_cloud",
                        lambda: persist_calls.append(1))

    status = web_sync_mod.try_reload_state()

    assert status.ok is True
    # Rollover применён.
    assert state.date_last_enter == str(datetime.now().date())
    assert state.steps.today == 0
    assert state.steps.used == 0
    # И persist вызван.
    assert len(persist_calls) == 1


def test_try_reload_state_no_rollover_no_persist_when_date_current(monkeypatch):
    """Если в state уже сегодняшняя дата — save_game_date_last_enter no-op,
    persist НЕ зовётся (нет смысла писать неизменённый state)."""
    from web import sync as web_sync_mod

    state = GameState.default_new_game()
    state.date_last_enter = str(datetime.now().date())
    state.steps.today = 8000
    _setup_state(state)

    persist_calls = []
    monkeypatch.setattr(web_sync_mod, "persist_state_to_cloud",
                        lambda: persist_calls.append(1))

    status = web_sync_mod.try_reload_state()

    assert status.ok is True
    # Дата та же, today не сбросился.
    assert state.steps.today == 8000
    assert persist_calls == []


def test_try_reload_state_persists_yesterday_steps_correctly():
    """При rollover today→yesterday копируется и daily_bonus считается по
    10k+ за вчера. Если вчера было 12k — daily_bonus +1."""
    state = GameState.default_new_game()
    state.date_last_enter = '2020-01-01'
    state.steps.today = 12000
    state.steps.daily_bonus = 0
    _setup_state(state)

    web_sync.try_reload_state()

    assert state.steps.yesterday == 12000
    assert state.steps.daily_bonus == 1
    assert state.steps.today == 0


def test_apply_new_steps_works_after_midnight_rollover(monkeypatch):
    """Кейс игрока: вкладка живёт с вчера (state.steps.today=8000), наступила
    полночь, игрок утром вводит 800 шагов с свежего браслета. Без rollover
    в _apply_new_steps валидация (steps > today) отклонит ввод. С rollover'ом
    today обнулится и 800 будет принято."""
    from google_sheets_db import StepsLogRepo
    appended = []
    monkeypatch.setattr(StepsLogRepo, "append",
                        lambda self, ts, steps, source, user_id="alex":
                        appended.append((ts, steps, source)))

    state = GameState.default_new_game()
    state.date_last_enter = '2020-01-01'  # вчера / любая прошлая дата
    state.steps.today = 8000
    state.steps.used = 200
    _setup_state(state)

    with TestClient(app) as client:
        response = client.post("/api/steps", json={"steps": 800})

    assert response.status_code == 200
    body = response.json()
    assert body["applied"] is True
    assert body["steps_today"] == 800
    # Date обновлена на сегодня.
    assert state.date_last_enter == str(datetime.now().date())
    # Лог получил 800.
    assert appended[0][1] == 800


def test_apply_new_steps_persists_after_rollover(monkeypatch):
    """После rollover'а в _apply_new_steps state.work тоже должен попасть в
    Sheets — это страховка для случая, когда первое действие на новый день
    идёт через POST /api/steps без предварительного GET / (например iPhone
    Shortcut)."""
    from web import sync as web_sync_mod

    persist_calls = []
    monkeypatch.setattr(web_sync_mod, "persist_state_to_cloud",
                        lambda: persist_calls.append(1))
    # web.main.persist_state_to_cloud — это import-скопированная ссылка.
    import web.main as wm
    monkeypatch.setattr(wm, "persist_state_to_cloud",
                        lambda: persist_calls.append(1))

    state = GameState.default_new_game()
    state.date_last_enter = '2020-01-01'
    state.steps.today = 8000
    _setup_state(state)

    with TestClient(app) as client:
        client.post("/api/steps", json={"steps": 500})

    # Persist вызван хотя бы один раз — после rollover'а в _apply_new_steps.
    assert len(persist_calls) >= 1


def test_dashboard_context_triggers_rollover_too(monkeypatch):
    """Defense-in-depth: GET /status (не зовёт try_reload_state, но всё ещё
    рендерит dashboard) — _dashboard_context должен сам триггернуть
    rollover."""
    state = GameState.default_new_game()
    state.date_last_enter = '2020-01-01'
    state.steps.today = 8000
    _setup_state(state)

    with TestClient(app) as client:
        client.get("/status")

    assert state.date_last_enter == str(datetime.now().date())
    assert state.steps.today == 0


def test_dashboard_after_rollover_form_min_is_1():
    """После rollover state.steps.today=0, форма должна позволять ввести
    с min=1 (today+1). До фикса валидация требовала min=8001."""
    state = GameState.default_new_game()
    state.date_last_enter = '2020-01-01'
    state.steps.today = 8000
    _setup_state(state)

    with TestClient(app) as client:
        response = client.get("/")

    body = response.text
    assert 'min="1"' in body
    # Старый stale "8001" не мелькает.
    assert 'min="8001"' not in body


def test_rollover_does_not_clear_active_work_session():
    """Активная смена через midnight остаётся как есть — таймер просто
    продолжает идти на новый день. CLI делает то же самое (rollover не
    трогает state.work)."""
    state = _state_for_work()
    state.date_last_enter = '2020-01-01'
    state.work.active = True
    state.work.work_type = "watchman"
    state.work.salary = 2
    state.work.hours = 4
    state.work.start = datetime.now() - timedelta(minutes=30)
    state.work.end = datetime.now() + timedelta(hours=2)  # таймер ещё идёт
    _setup_state(state)

    with TestClient(app) as client:
        client.get("/")

    # Steps сбросились (rollover), но work не тронут.
    assert state.steps.today == 0
    assert state.work.active is True
    assert state.work.work_type == "watchman"
    assert state.work.hours == 4


# ----- Hour buttons content (0.2.1c) -----
# Кнопки выбора часов должны содержать pre-computed totals по формуле
# `Nh · 🏃 N*steps · 🔋 N*energy · 💰 N*salary`. Расчёт в Python через
# _build_hour_options.

def test_hour_buttons_show_pre_computed_totals_for_watchman():
    """Watchman: 200 шагов/ч, 4 эн/ч, 2 $/ч. Кнопка 1h → 200/4/2; кнопка 2h → 400/8/4."""
    state = _state_for_work(steps_can_use=8000, energy=80)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Найдём watchman-форму.
    work_pos = body.find('id="work"')
    work_section = body[work_pos:work_pos + 12000]
    watchman_pos = work_section.find('value="watchman"')
    assert watchman_pos > 0
    form_end = work_section.find('</form>', watchman_pos)
    form = work_section[watchman_pos:form_end]
    # Кнопка 1h: "1h · 🏃 200 · 🔋 4 · 💰 2"
    # Default state без speed-бонусов → real_time = h * 60 минут.
    assert "1h 🕑 1h · 🏃 -200 · 🔋 -4 · 💰 +2" in form
    # Кнопка 2h: умножается на 2.
    assert "2h 🕑 2h · 🏃 -400 · 🔋 -8 · 💰 +4" in form
    # Кнопка 3h.
    assert "3h 🕑 3h · 🏃 -600 · 🔋 -12 · 💰 +6" in form


def test_hour_buttons_show_pre_computed_totals_for_factory():
    """Factory: 500 шагов/ч, 7 эн/ч, 5 $/ч."""
    state = _state_for_work(steps_can_use=8000, energy=80)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    work_pos = body.find('id="work"')
    work_section = body[work_pos:work_pos + 12000]
    factory_pos = work_section.find('value="factory"')
    assert factory_pos > 0
    form_end = work_section.find('</form>', factory_pos)
    form = work_section[factory_pos:form_end]
    assert "1h 🕑 1h · 🏃 -500 · 🔋 -7 · 💰 +5" in form
    assert "2h 🕑 2h · 🏃 -1000 · 🔋 -14 · 💰 +10" in form


def test_add_hours_buttons_show_pre_computed_totals():
    """Когда уже работаешь — кнопки add_hours тоже показывают полную формулу
    относительно текущей вакансии."""
    state = _state_for_work(steps_can_use=8000, energy=80)
    state.work.active = True
    state.work.work_type = "watchman"
    state.work.salary = 2
    state.work.hours = 1
    state.work.start = datetime.now() - timedelta(minutes=30)
    state.work.end = datetime.now() + timedelta(hours=1)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Меню вакансий не показывается.
    assert 'hx-post="/web/work/start"' not in body
    # А add_hours форма содержит формулу.
    assert "+1h 🕑 1h · 🏃 -200 · 🔋 -4 · 💰 +2" in body
    assert "+2h 🕑 2h · 🏃 -400 · 🔋 -8 · 💰 +4" in body


def test_hour_options_python_helper_zero_max_hours_returns_empty():
    """_build_hour_options(state, req, 0) → пустой список (нет кнопок при
    нулевых ресурсах)."""
    from web.main import _build_hour_options
    req = {'steps': 200, 'energy': 4, 'salary': 2}
    state = GameState.default_new_game()
    assert _build_hour_options(state, req, 0) == []


def test_hour_options_python_helper_max_8():
    """_build_hour_options(state, req, 8) → 8 записей с правильно умноженными
    значениями + real_time с учётом speed-бонусов."""
    from web.main import _build_hour_options
    req = {'steps': 1000, 'energy': 10, 'salary': 10}
    state = GameState.default_new_game()  # без бонусов → real_time = h*60 мин
    options = _build_hour_options(state, req, 8)
    assert len(options) == 8
    # Первая запись.
    assert options[0] == {"h": 1, "steps": 1000, "energy": 10, "salary": 10, "real_time": "1h"}
    # Восьмая.
    assert options[7] == {"h": 8, "steps": 8000, "energy": 80, "salary": 80, "real_time": "8h"}


def test_hour_options_real_time_with_speed_bonus():
    """Speed-бонус 25% (gym.speed_skill=25) → 1h работы = 45 минут реальных."""
    from web.main import _build_hour_options
    req = {'steps': 200, 'energy': 4, 'salary': 2}
    state = GameState.default_new_game()
    state.gym.speed_skill = 25  # 25% бонус
    options = _build_hour_options(state, req, 3)
    # 1h * 60 * (1 - 0.25) = 45 мин → "45m"
    assert options[0]["real_time"] == "45m"
    # 2h * 60 * 0.75 = 90 мин → "1h 30m"
    assert options[1]["real_time"] == "1h 30m"
    # 3h * 60 * 0.75 = 135 мин → "2h 15m"
    assert options[2]["real_time"] == "2h 15m"


def test_hour_options_real_time_with_full_speed_bonus():
    """100% speed-бонус → real_time = 0 минут (edge case, нереалистично, но
    логика должна обрабатывать корректно: 0m)."""
    from web.main import _build_hour_options
    req = {'steps': 200, 'energy': 4, 'salary': 2}
    state = GameState.default_new_game()
    state.gym.speed_skill = 100
    options = _build_hour_options(state, req, 1)
    assert options[0]["real_time"] == "0m"


def test_energy_regenerates_in_dashboard_context():
    """Energy с устаревшим stamp → после GET /status energy выросла на 1+
    и stamp обновлён. Без бонусов interval=60s."""
    state = GameState.default_new_game()
    state.energy = 30
    state.energy_max = 65
    # Stamp 3 минуты назад → +3 единицы при interval=60s.
    state.energy_time_stamp = datetime.now().timestamp() - 180
    _setup_state(state)

    with TestClient(app) as client:
        client.get("/status")

    # 30 + 3 = 33, не больше max=65.
    assert state.energy == 33
    # Stamp синкнут: остаток = 0 (180 % 60 == 0) → stamp = now.
    assert abs(state.energy_time_stamp - datetime.now().timestamp()) < 2


def test_energy_clamped_to_max_in_dashboard_context():
    """Energy уже на max → state не растёт, stamp синкается к now (защита
    от баг 2.2.2 — бесплатной энергии после максимума).

    После 0.2.1g (4.48.4.1) energy_max — computed value: задаём через
    state.gym.energy_max_skill (было `state.energy_max = 65` напрямую)."""
    state = GameState.default_new_game()
    state.gym.energy_max_skill = 15  # 50 + 15 = 65 max
    state.energy = 65
    state.energy_time_stamp = datetime.now().timestamp() - 1000  # давно
    _setup_state(state)

    with TestClient(app) as client:
        client.get("/status")

    assert state.energy == 65
    # Stamp подтянулся к now.
    assert abs(state.energy_time_stamp - datetime.now().timestamp()) < 2


def test_energy_data_attrs_in_dom():
    """В DOM-фрагменте есть все 4 data-атрибута для JS-таймера.

    После 0.2.1g — `data-energy-max` берётся из `compute_energy_max(state)`
    (context var `energy_max_now`), не из stale-поля `state.energy_max`."""
    state = GameState.default_new_game()
    state.gym.energy_max_skill = 15  # 50 + 15 = 65
    state.energy = 30
    state.energy_time_stamp = datetime.now().timestamp()
    _setup_state(state)

    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text

    assert 'data-energy="30"' in body
    assert 'data-energy-max="65"' in body
    assert 'data-energy-stamp=' in body
    assert 'data-energy-interval=' in body


def test_energy_regen_does_not_trigger_persist(monkeypatch):
    """Регенерация энергии не должна писать в Sheets/CSV — иначе каждый
    F5 будет триггерить persist (дорого, без необходимости). Persist'ится
    только при rollover/work-mutation."""
    from web import sync as web_sync_mod

    persist_calls = []
    monkeypatch.setattr(web_sync_mod, "persist_state_to_cloud",
                        lambda: persist_calls.append(1))

    state = GameState.default_new_game()
    state.energy = 30
    state.energy_max = 65
    state.energy_time_stamp = datetime.now().timestamp() - 180
    _setup_state(state)

    with TestClient(app) as client:
        client.get("/status")

    # Energy выросла, но persist не вызывался.
    assert state.energy == 33
    assert persist_calls == []


def test_energy_interval_with_regen_bonus():
    """0.2.4i (task 4.21) — energy_regen_skill 25% → interval = 60 * 0.75 = 45 сек.
    Speed-skill больше не влияет на regen (раньше до 0.2.4i — влиял через
    speed_skill_equipment_and_level_bonus)."""
    state = GameState.default_new_game()
    state.energy = 30
    state.energy_max = 65
    state.gym.energy_regen_skill = 25  # 25% бонус к regen
    # Stamp 90 сек назад → 90 // 45 = 2 → +2 энергии.
    state.energy_time_stamp = datetime.now().timestamp() - 90
    _setup_state(state)

    with TestClient(app) as client:
        response = client.get("/status")

    assert state.energy == 32
    # И data-energy-interval = 45 в DOM.
    body = response.text
    assert 'data-energy-interval="45"' in body


def test_energy_interval_speed_skill_does_not_affect_regen():
    """0.2.4i (task 4.21) — speed_skill больше НЕ влияет на regen.
    interval = 60 даже при speed_skill=50 (если energy_regen_skill=0)."""
    state = GameState.default_new_game()
    state.gym.speed_skill = 50  # speed=50, regen=0
    _setup_state(state)

    with TestClient(app) as client:
        response = client.get("/status")

    body = response.text
    assert 'data-energy-interval="60"' in body  # speed_skill игнорируется


def test_format_real_time_helper():
    """_format_real_time правильно выводит часы / минуты / комбинацию."""
    from web.main import _format_real_time
    assert _format_real_time(0) == "0m"
    assert _format_real_time(45) == "45m"
    assert _format_real_time(60) == "1h"
    assert _format_real_time(90) == "1h 30m"
    assert _format_real_time(120) == "2h"
    assert _format_real_time(135) == "2h 15m"
    assert _format_real_time(480) == "8h"


# ----- Skill allocation (task 4.48.8 / 0.2.1d) -----

def test_skills_section_hidden_when_no_points():
    """Если up_skills=0, секция id='skills' не рендерится в фрагменте."""
    state = GameState.default_new_game()
    state.char_level.up_skills = 0
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert 'id="skills"' not in body


def test_skills_section_visible_when_points_available():
    """up_skills > 0 → секция id='skills' с 4 кнопками навыков."""
    state = GameState.default_new_game()
    state.char_level.up_skills = 2
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert 'id="skills"' in body
    # 4 кнопки.
    assert 'value="stamina"' in body
    assert 'value="energy_max"' in body
    assert 'value="speed"' in body
    assert 'value="luck"' in body
    # Счётчик доступных очков.
    assert "доступно: 2" in body
    # hx-confirm на каждой кнопке (защита от misclick).
    assert 'hx-confirm=' in body
    # Свёрнут по умолчанию.
    skills_pos = body.find('id="skills"')
    skills_section = body[skills_pos:skills_pos + 4000]
    assert "<details>" in skills_section
    assert "<details open" not in skills_section


def test_skills_section_shows_current_skill_levels():
    """Каждая кнопка показывает текущий уровень навыка `(текущий: +N)`."""
    state = GameState.default_new_game()
    state.char_level.up_skills = 1
    state.char_level.skill_stamina = 5
    state.char_level.skill_speed = 3
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert "Stamina (текущий: +5)" in body
    assert "Speed (текущий: +3)" in body
    # Energy / Luck = 0.
    assert "Energy Max (текущий: +0)" in body
    assert "Luck (текущий: +0)" in body


def test_skills_section_appears_between_stats_and_active_sessions():
    """Order: Stats → Skills → Active sessions → Работа → Бонусы → ..."""
    state = GameState.default_new_game()
    state.char_level.up_skills = 1
    state.training.active = True
    state.training.skill_name = "stamina"
    state.training.timestamp = (datetime.now() - timedelta(minutes=5)).timestamp()
    state.training.time_end = datetime.now() + timedelta(minutes=5)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    stats_pos = body.find('id="stats"')
    skills_pos = body.find('id="skills"')
    active_pos = body.find('id="active-sessions"')
    work_pos = body.find('id="work"')
    assert 0 < stats_pos < skills_pos < active_pos < work_pos


# ----- /web/level/allocate (Form) -----

def test_web_level_allocate_with_valid_skill_decrements_points():
    state = GameState.default_new_game()
    state.char_level.up_skills = 3
    state.char_level.skill_stamina = 2
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/web/level/allocate", data={"skill": "stamina"})
    assert response.status_code == 200
    assert state.char_level.up_skills == 2
    assert state.char_level.skill_stamina == 3


def test_web_level_allocate_with_unknown_skill_returns_error():
    state = GameState.default_new_game()
    state.char_level.up_skills = 1
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/web/level/allocate", data={"skill": "ceo"})
    assert response.status_code == 200
    body = response.text
    assert "Неизвестный навык" in body
    assert state.char_level.up_skills == 1  # state не мутирован


def test_web_level_allocate_when_no_points_returns_error():
    state = GameState.default_new_game()
    state.char_level.up_skills = 0
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/web/level/allocate", data={"skill": "stamina"})
    assert response.status_code == 200
    body = response.text
    assert "Нет доступных очков" in body
    assert state.char_level.skill_stamina == 0


def test_web_level_allocate_persists_state(monkeypatch):
    """Каждое распределение очка → persist (CSV+JSON+Sheets), как для work."""
    from google_sheets_db import GameStateRepo
    saved_to_sheets = []
    monkeypatch.setattr(GameStateRepo, "save",
                        lambda self, data, user_id=None: saved_to_sheets.append(data))

    state = GameState.default_new_game()
    state.char_level.up_skills = 1
    _setup_state(state)
    with TestClient(app) as client:
        client.post("/web/level/allocate", data={"skill": "luck"})
    assert len(saved_to_sheets) == 1
    assert saved_to_sheets[0]["lvl_up_skill_luck"] == 1
    assert saved_to_sheets[0]["char_level_up_skills"] == 0


def test_web_level_allocate_invalid_skill_does_not_persist(monkeypatch):
    """Невалидный skill → state не мутирован, persist не вызван."""
    from google_sheets_db import GameStateRepo
    saved_to_sheets = []
    monkeypatch.setattr(GameStateRepo, "save",
                        lambda self, data, user_id=None: saved_to_sheets.append(data))

    state = GameState.default_new_game()
    state.char_level.up_skills = 1
    _setup_state(state)
    with TestClient(app) as client:
        client.post("/web/level/allocate", data={"skill": "ceo"})
    assert saved_to_sheets == []


# ----- /api/level/allocate (JSON) -----

def test_api_level_allocate_with_valid_skill():
    state = GameState.default_new_game()
    state.char_level.up_skills = 2
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/level/allocate", json={"skill": "speed"})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["char_level"]["up_skills"] == 1
    assert body["char_level"]["skill_speed"] == 1


def test_api_level_allocate_unknown_skill_returns_422():
    state = GameState.default_new_game()
    state.char_level.up_skills = 1
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/level/allocate", json={"skill": "ceo"})
    assert response.status_code == 422
    body = response.json()
    assert body["ok"] is False


def test_api_level_allocate_no_points_returns_422():
    state = GameState.default_new_game()
    state.char_level.up_skills = 0
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/level/allocate", json={"skill": "stamina"})
    assert response.status_code == 422
    body = response.json()
    assert body["ok"] is False
    assert "Нет доступных очков" in body["error"]


# ----- _validate_and_apply_skill_allocation helper -----

def test_validate_skill_allocation_success():
    from web.main import _validate_and_apply_skill_allocation
    state = GameState.default_new_game()
    state.char_level.up_skills = 1
    state.char_level.skill_stamina = 4
    err = _validate_and_apply_skill_allocation(state, "stamina")
    assert err is None
    assert state.char_level.skill_stamina == 5
    assert state.char_level.up_skills == 0


def test_validate_skill_allocation_no_points():
    from web.main import _validate_and_apply_skill_allocation
    state = GameState.default_new_game()
    state.char_level.up_skills = 0
    err = _validate_and_apply_skill_allocation(state, "stamina")
    assert err is not None
    assert "Нет доступных" in err


def test_validate_skill_allocation_unknown_skill():
    from web.main import _validate_and_apply_skill_allocation
    state = GameState.default_new_game()
    state.char_level.up_skills = 1
    err = _validate_and_apply_skill_allocation(state, "ceo")
    assert err is not None
    assert "Неизвестный навык" in err
    assert state.char_level.up_skills == 1  # не тронут


# ----- Level-up auto-detection in _dashboard_context (4.48.8 prerequisite) -----

def test_dashboard_context_triggers_level_up_when_threshold_crossed(monkeypatch):
    """Web должен сам апать уровень при прохождении порога total_used_steps —
    иначе web-only игрок никогда не получит up_skills."""
    from google_sheets_db import GameStateRepo
    saved_to_sheets = []
    monkeypatch.setattr(GameStateRepo, "save",
                        lambda self, data, user_id=None: saved_to_sheets.append(data))

    state = GameState.default_new_game()
    state.char_level.level = 0
    state.char_level.up_skills = 0
    state.steps.total_used = 15000  # выше первого порога 10000 → level=1
    _setup_state(state)

    with TestClient(app) as client:
        client.get("/status")

    # Level апнулся, +1 очко.
    assert state.char_level.level == 1
    assert state.char_level.up_skills == 1
    # Persist вызван (level изменился).
    assert len(saved_to_sheets) == 1


def test_dashboard_context_no_level_up_no_persist(monkeypatch):
    """Если total_used не пересекает порог — level не апается, persist не зовётся."""
    from google_sheets_db import GameStateRepo
    saved_to_sheets = []
    monkeypatch.setattr(GameStateRepo, "save",
                        lambda self, data, user_id=None: saved_to_sheets.append(data))

    state = GameState.default_new_game()
    state.char_level.level = 1
    state.char_level.up_skills = 0
    state.steps.total_used = 15000  # уже учтено в level=1
    _setup_state(state)

    with TestClient(app) as client:
        client.get("/status")

    assert state.char_level.level == 1
    assert state.char_level.up_skills == 0
    assert saved_to_sheets == []


# ----- Gym skill training (task 4.48.4 / 0.2.1e) -----

def _state_for_gym(steps=10000, energy=20, money=200):
    """State с ресурсами достаточными для прокачки большинства навыков 1-го уровня.

    energy_time_stamp выставлен в now, чтобы energy_time_charge в
    _dashboard_context не регенерировал энергию обратно в max между
    мутацией и рендером ответа."""
    state = GameState.default_new_game()
    state.steps.today = steps
    state.steps.can_use = steps
    state.energy = energy
    state.money = money
    state.energy_time_stamp = datetime.now().timestamp()
    return state


def test_gym_section_renders_in_status_fragment():
    """В фрагменте присутствует <section id='gym'> с <details>."""
    _setup_state(_state_for_gym())
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert 'id="gym"' in body
    gym_pos = body.find('id="gym"')
    gym_section = body[gym_pos:gym_pos + 8000]
    assert "<details" in gym_section
    assert "<summary>" in gym_section


def test_gym_section_collapsed_by_default():
    _setup_state(_state_for_gym())
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    gym_pos = body.find('id="gym"')
    gym_section = body[gym_pos:gym_pos + 8000]
    assert "<details>" in gym_section
    assert "<details open" not in gym_section


def test_gym_section_renders_8_skills():
    """Меню Gym показывает все 8 навыков (включая energy_max — но он
    помечен как недоступный для старта)."""
    _setup_state(_state_for_gym())
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # 7 working skills via hidden form input value.
    assert 'value="stamina"' in body
    assert 'value="speed_skill"' in body
    assert 'value="luck_skill"' in body
    assert 'value="move_optimization_adventure"' in body
    assert 'value="move_optimization_gym"' in body
    assert 'value="move_optimization_work"' in body
    assert 'value="neatness_in_using_things"' in body
    # energy_max — отображается, но помечен недоступным (нет form-button).
    assert "Energy Max" in body
    # Все 8 заголовков навыков.
    assert "Stamina" in body
    assert "Speed" in body
    assert "Luck" in body


def test_gym_section_shows_costs_and_time():
    """Кнопка stamina (level 0 → 1): cost из skill_training_table[1] = 1000 шагов / 5 эн / 10 $ / 5 мин."""
    _setup_state(_state_for_gym())
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Стоимость в формате `🏃 -1000 · 🔋 -5 · 💰 -10 · 🕑 5m`.
    assert "🏃 -1000" in body
    assert "🔋 -5" in body
    assert "💰 -10" in body
    assert "🕑 5m" in body


def test_gym_section_disabled_button_when_not_enough_resources():
    """Если на первый уровень не хватает (например, очень мало шагов) —
    кнопка отображается с disabled и текстом 'Не хватает: 🏃 N'."""
    _setup_state(_state_for_gym(steps=100, energy=5, money=10))  # шагов меньше 1000
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # disabled-кнопка для stamina.
    assert "disabled" in body
    assert "Не хватает" in body


def test_gym_skills_use_nested_details():
    """4.48.4 follow-up: каждый навык обёрнут в собственный nested
    <details>, свёрнут по умолчанию — игрок раскрывает только нужные."""
    _setup_state(_state_for_gym())
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    gym_pos = body.find('id="gym"')
    # Следующая секция после Gym = Bank (с 0.2.4w / 4.48.9), затем Bonuses.
    next_section_pos = body.find('id="bank"', gym_pos)
    gym_section = body[gym_pos:next_section_pos]
    # Внутри Gym-блока — nested <details> по одному на каждый навык
    # (после 0.2.4j / 4.22 — 20 навыков: + 3 energy_optimization_* после move_opt).
    import re
    details_tags = re.findall(r'<details(?:\s[^>]*)?>', gym_section)
    # 1 внешний + 20 nested = 21.
    assert len(details_tags) == 21
    # Ни один не должен быть `open`.
    for tag in details_tags:
        assert "open" not in tag, f"details unexpectedly open: {tag}"


def test_gym_skill_summary_shows_minimal_info():
    """Summary каждого навыка содержит только имя, level → next, описание."""
    _setup_state(_state_for_gym())
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Summary stamina — компактная строка.
    assert "🏃 <strong>Stamina</strong>" in body
    assert "(0 → 1)" in body  # default state.gym.stamina = 0
    assert "+1 % к общему кол-во шагов" in body


def test_gym_section_no_intro_text():
    """4.48.4 follow-up: введение 'Выбери навык для прокачки...' убрано —
    список навыков самодостаточный."""
    _setup_state(_state_for_gym())
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    gym_pos = body.find('id="gym"')
    gym_section = body[gym_pos:gym_pos + 16000]
    assert "Выбери навык для прокачки" not in gym_section


def test_gym_section_when_training_active_no_start_buttons():
    """Если идёт тренировка — нет form с /web/gym/start, есть подсказка."""
    state = _state_for_gym()
    state.training.active = True
    state.training.skill_name = "stamina"
    state.training.timestamp = (datetime.now() - timedelta(minutes=2)).timestamp()
    state.training.time_end = datetime.now() + timedelta(minutes=10)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Меню стартов скрыто.
    assert 'hx-post="/web/gym/start"' not in body
    # Внутри блока есть подсказка.
    gym_pos = body.find('id="gym"')
    gym_section = body[gym_pos:gym_pos + 8000]
    assert "Идёт прокачка" in gym_section


def test_gym_section_after_training_appears_in_active_sessions():
    """Активная тренировка отображается в Active sessions блоке (existing render)."""
    state = _state_for_gym()
    state.training.active = True
    state.training.skill_name = "speed_skill"
    state.gym.speed_skill = 2
    state.training.timestamp = (datetime.now() - timedelta(minutes=2)).timestamp()
    state.training.time_end = datetime.now() + timedelta(minutes=10)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Active sessions section
    active_pos = body.find('id="active-sessions"')
    assert active_pos > 0
    active_section = body[active_pos:active_pos + 4000]
    assert "Тренировка" in active_section
    assert "Speed_Skill" in active_section


# ----- /web/gym/start (Form) -----

def test_web_gym_start_with_valid_skill():
    state = _state_for_gym()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/web/gym/start", data={"skill_name": "stamina"})
    assert response.status_code == 200
    # state.training активна.
    assert state.training.active is True
    assert state.training.skill_name == "stamina"
    # Ресурсы списаны (1000 шагов / 5 эн / 10 $ для level 1).
    assert state.steps.used == 1000
    assert state.energy == 20 - 5
    assert state.money == 200 - 10


def test_web_gym_start_with_unknown_skill():
    _setup_state(_state_for_gym())
    with TestClient(app) as client:
        response = client.post("/web/gym/start", data={"skill_name": "ceo"})
    assert response.status_code == 200
    body = response.text
    assert "Неизвестный навык" in body


def test_web_gym_start_with_energy_max_skill_works():
    """После 0.2.1g (4.48.4.1) — energy_max_skill теперь обычный навык,
    прокачка работает как для других skills. Стартуем с level=0 → level 1
    стоит 1000/5/10, что покрывают дефолтные ресурсы _state_for_gym."""
    state = _state_for_gym()
    # state.gym.energy_max_skill = 0 (default) → next level 1 → cost 1000/5/10.
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/web/gym/start", data={"skill_name": "energy_max_skill"})
    assert response.status_code == 200
    # Тренировка стартанула — state.training активен.
    assert state.training.active is True
    assert state.training.skill_name == "energy_max_skill"


def test_web_gym_start_with_old_energy_max_key_returns_error():
    """Старый ключ 'energy_max' (без _skill) теперь не валидный — ошибка."""
    _setup_state(_state_for_gym())
    with TestClient(app) as client:
        response = client.post("/web/gym/start", data={"skill_name": "energy_max"})
    assert response.status_code == 200
    body = response.text
    assert "Неизвестный навык" in body


def test_web_gym_start_when_already_training_rejects():
    state = _state_for_gym()
    state.training.active = True
    state.training.skill_name = "luck_skill"
    state.training.timestamp = (datetime.now() - timedelta(minutes=1)).timestamp()
    state.training.time_end = datetime.now() + timedelta(minutes=10)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/web/gym/start", data={"skill_name": "stamina"})
    assert response.status_code == 200
    body = response.text
    assert "уже идёт" in body.lower()
    # state.training.skill_name не сменился.
    assert state.training.skill_name == "luck_skill"


def test_web_gym_start_when_not_enough_resources():
    _setup_state(_state_for_gym(steps=100))
    with TestClient(app) as client:
        response = client.post("/web/gym/start", data={"skill_name": "stamina"})
    assert response.status_code == 200
    body = response.text
    assert "Не хватает 🏃" in body


def test_web_gym_start_persists_state(monkeypatch):
    """Старт тренировки → persist (CSV+JSON+Sheets)."""
    from google_sheets_db import GameStateRepo
    saved_to_sheets = []
    monkeypatch.setattr(GameStateRepo, "save",
                        lambda self, data, user_id=None: saved_to_sheets.append(data))

    _setup_state(_state_for_gym())
    with TestClient(app) as client:
        client.post("/web/gym/start", data={"skill_name": "speed_skill"})
    assert len(saved_to_sheets) == 1
    assert saved_to_sheets[0]["skill_training"] is True
    assert saved_to_sheets[0]["skill_training_name"] == "speed_skill"


# ----- /api/gym/start (JSON) -----

def test_api_gym_start_with_valid_skill():
    _setup_state(_state_for_gym())
    with TestClient(app) as client:
        response = client.post("/api/gym/start", json={"skill_name": "stamina"})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["training"]["active"] is True
    assert body["training"]["skill_name"] == "stamina"


def test_api_gym_start_unknown_skill_returns_422():
    _setup_state(_state_for_gym())
    with TestClient(app) as client:
        response = client.post("/api/gym/start", json={"skill_name": "ceo"})
    assert response.status_code == 422


def test_api_gym_start_when_already_training_returns_409():
    state = _state_for_gym()
    state.training.active = True
    state.training.skill_name = "luck_skill"
    state.training.timestamp = (datetime.now() - timedelta(minutes=1)).timestamp()
    state.training.time_end = datetime.now() + timedelta(minutes=10)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/gym/start", json={"skill_name": "stamina"})
    assert response.status_code == 409


def test_api_gym_start_when_not_enough_resources_returns_422():
    _setup_state(_state_for_gym(steps=100))
    with TestClient(app) as client:
        response = client.post("/api/gym/start", json={"skill_name": "stamina"})
    assert response.status_code == 422


# ----- Auto-finalize training in _dashboard_context -----

def test_dashboard_auto_finalizes_expired_training():
    """state.training.time_end < now → skill_training_check_done в
    _dashboard_context апает skill уровень и обнуляет training."""
    state = _state_for_gym()
    state.training.active = True
    state.training.skill_name = "stamina"
    state.training.timestamp = (datetime.now() - timedelta(minutes=20)).timestamp()
    state.training.time_end = datetime.now() - timedelta(seconds=1)
    state.gym.stamina = 4  # → должен стать 5
    _setup_state(state)

    with TestClient(app) as client:
        client.get("/status")

    assert state.gym.stamina == 5
    assert state.training.active is False
    assert state.training.skill_name is None


def test_dashboard_does_not_finalize_active_unfinished_training():
    state = _state_for_gym()
    state.training.active = True
    state.training.skill_name = "speed_skill"
    state.gym.speed_skill = 1
    state.training.timestamp = (datetime.now() - timedelta(minutes=1)).timestamp()
    state.training.time_end = datetime.now() + timedelta(minutes=10)
    _setup_state(state)

    with TestClient(app) as client:
        client.get("/status")

    assert state.training.active is True
    assert state.gym.speed_skill == 1


# ----- _build_gym_skills helper -----

def test_build_gym_skills_returns_all_entries():
    from web.main import _build_gym_skills
    state = _state_for_gym()
    skills = _build_gym_skills(state)
    keys = [s["key"] for s in skills]
    # После 0.2.1g (4.48.4.1) — ключ 'energy_max' переименован в 'energy_max_skill'.
    # После 0.2.2 (4.49.1.0) — добавлен banking_interest_rate (9-й навык).
    # После 0.2.2 (4.49.2.0) — добавлены loan_capacity + loan_interest_reduction.
    # После 0.2.3 (4.27) — добавлен inspiration. После 0.2.3a (4.20) — добавлен
    # money_saving; reorder: money_saving поднят на позицию 9. После 0.2.4a (4.23)
    # — добавлен earnings_boost рядом с money_saving (позиция 10), остальные
    # money/loan/inspiration сдвинуты на одну вниз. После 0.2.4b (4.50.0) —
    # добавлен backpack_skill в самый низ. После 0.2.4h (4.28) — добавлен
    # trader в money trilogy (позиция 11), bank/inspiration/backpack
    # сдвинуты на одну вниз. После 0.2.4i (4.21) — добавлен
    # energy_regen_skill сразу после energy_max_skill (позиция 3),
    # все остальные сдвинуты на одну вниз. После 0.2.4j (4.22) —
    # добавлены 3 energy_optimization_* (adventure/gym/work) после
    # move_optimization_*, остальные сдвинуты ещё на 3 вниз.
    assert keys == [
        "stamina", "energy_max_skill", "energy_regen_skill",
        "speed_skill", "luck_skill",
        "move_optimization_adventure", "move_optimization_gym",
        "move_optimization_work",
        "energy_optimization_adventure", "energy_optimization_gym",
        "energy_optimization_work",
        "neatness_in_using_things",
        "money_saving", "earnings_boost", "trader",
        "banking_interest_rate", "loan_capacity", "loan_interest_reduction",
        "inspiration",
        "backpack_skill",
    ]


def test_build_gym_skills_energy_max_skill_now_available():
    """После 0.2.1g — energy_max_skill больше не помечен available=False."""
    from web.main import _build_gym_skills
    state = _state_for_gym()
    skills = _build_gym_skills(state)
    energy_max = next(s for s in skills if s["key"] == "energy_max_skill")
    assert energy_max["available"] is True
    assert energy_max["unavailable_reason"] is None


def test_build_gym_skills_can_afford_flag():
    """С 10к шагов + 20 эн + 200 $ должно хватать на stamina (1000/5/10),
    но не на higher-cost навыки. На stamina can_afford=True, на forwarder-style
    высокие пороги нет (но в gym нет такого, все начальные стоимости одинаковы)."""
    from web.main import _build_gym_skills
    state = _state_for_gym()
    skills = _build_gym_skills(state)
    stamina = next(s for s in skills if s["key"] == "stamina")
    assert stamina["can_afford"] is True
    assert stamina["missing"] == {}


def test_build_gym_skills_missing_resources_listed():
    from web.main import _build_gym_skills
    state = _state_for_gym(steps=100, energy=2, money=5)
    skills = _build_gym_skills(state)
    stamina = next(s for s in skills if s["key"] == "stamina")
    assert stamina["can_afford"] is False
    assert stamina["missing"]["steps"] == 900   # 1000 - 100
    assert stamina["missing"]["energy"] == 3    # 5 - 2
    assert stamina["missing"]["money"] == 5     # 10 - 5


def test_validate_and_apply_training_unknown_skill():
    from web.main import _validate_and_apply_training
    state = _state_for_gym()
    err = _validate_and_apply_training(state, "ceo")
    assert err is not None
    assert "Неизвестный" in err


def test_validate_and_apply_training_already_active():
    from web.main import _validate_and_apply_training
    state = _state_for_gym()
    state.training.active = True
    state.training.skill_name = "luck_skill"
    state.training.time_end = datetime.now() + timedelta(minutes=10)
    err = _validate_and_apply_training(state, "stamina")
    assert err is not None
    assert "уже идёт" in err.lower()


def test_validate_and_apply_training_success():
    from web.main import _validate_and_apply_training
    state = _state_for_gym()
    err = _validate_and_apply_training(state, "luck_skill")
    assert err is None
    assert state.training.active is True
    assert state.training.skill_name == "luck_skill"


def test_dashboard_context_provides_work_add_hour_options_when_active():
    """В _dashboard_context'е при активной смене work_add_hour_options
    содержит pre-computed данные для текущей вакансии."""
    state = _state_for_work(steps_can_use=4000, energy=40)
    state.work.active = True
    state.work.work_type = "watchman"  # 200 ш/ч, 4 эн/ч, 2 $/ч
    state.work.salary = 2
    state.work.hours = 1
    state.work.start = datetime.now() - timedelta(minutes=30)
    state.work.end = datetime.now() + timedelta(hours=1)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # max_hours = min(4000/200, 40/4, 8) = min(20, 10, 8) = 8 → 8 кнопок.
    import re
    btns = re.findall(r'name="hours" value="(\d+)"', body)
    assert btns == ["1", "2", "3", "4", "5", "6", "7", "8"]
    # Последняя кнопка — 8h, формула *8.
    assert "+8h 🕑 8h · 🏃 -1600 · 🔋 -32 · 💰 +16" in body


# ===== 4.50.2 — Pending drop UI + endpoints =====

def _make_pending_item(item_type='ring', grade='a-grade', characteristic='luck',
                       bonus=3, quality=80.0, price=120):
    return {
        'item_name': [item_type], 'item_type': [item_type], 'grade': [grade],
        'characteristic': [characteristic], 'bonus': [bonus],
        'quality': [quality], 'price': [price],
    }


def _state_with_pending_and_full_inventory():
    """State с full inventory (10 предметов) + pending=ring."""
    state = GameState.default_new_game()
    state.money = 100.0
    state.inventory = [_make_pending_item(grade='c-grade', bonus=1, price=25)
                       for _ in range(10)]
    state.pending_drop = _make_pending_item(price=120)
    return state


def test_pending_drop_view_inactive_when_no_pending():
    """_build_pending_drop_view: pending=None → active=False."""
    from web.main import _build_pending_drop_view
    state = GameState.default_new_game()
    view = _build_pending_drop_view(state)
    assert view == {"active": False, "item": None}


def test_pending_drop_view_parses_item_fields():
    """_build_pending_drop_view: pending=item → flat parsed dict."""
    from web.main import _build_pending_drop_view
    state = GameState.default_new_game()
    state.pending_drop = _make_pending_item()
    view = _build_pending_drop_view(state)
    assert view["active"] is True
    assert view["item"] == {
        "type": "ring", "grade": "a-grade", "characteristic": "luck",
        "bonus": 3, "quality": 80.0, "price": 120,
    }


def test_dashboard_renders_pending_banner_when_active():
    """GET /status с активным pending → баннер «Найдена находка» в HTML."""
    _setup_state(_state_with_pending_and_full_inventory())
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert 'id="pending-drop"' in body
    assert "Найдена находка" in body
    # Кнопка sell-new с ценой
    assert "💰 Продать находку (120 $)" in body
    assert 'hx-post="/web/drop/sell_new"' in body
    assert 'hx-post="/web/drop/skip"' in body


def test_dashboard_no_banner_when_pending_none():
    """Без pending — баннер отсутствует."""
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert 'id="pending-drop"' not in body


def test_inventory_section_auto_opens_when_pending_active():
    """При active pending инвентарь раскрывается автоматически (open атрибут)."""
    _setup_state(_state_with_pending_and_full_inventory())
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    inv_start = body.find('id="inventory"')
    inv_section = body[inv_start:inv_start + 3000]
    assert "<details open" in inv_section


def test_inventory_renders_sell_keep_buttons_when_pending():
    """Каждый предмет инвентаря рядом получает кнопку «Продать + взять находку»."""
    _setup_state(_state_with_pending_and_full_inventory())
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # 10 кнопок sell-existing.
    import re
    forms = re.findall(r'hx-post="/web/drop/sell_existing"', body)
    assert len(forms) == 10
    # Hidden index input от 0 до 9.
    indices = re.findall(r'name="index" value="(\d+)"', body)
    assert indices == [str(i) for i in range(10)]


def test_inventory_no_sell_keep_buttons_without_pending():
    """Без pending sell-existing кнопок нет."""
    state = GameState.default_new_game()
    state.inventory = [_make_pending_item()]
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert 'hx-post="/web/drop/sell_existing"' not in body


# ----- POST /web/drop/* endpoints -----

def test_post_web_drop_sell_new_resolves_and_returns_fragment():
    """sell_new: pending продан за price, money += price, баннер исчезает."""
    state = _state_with_pending_and_full_inventory()
    initial_money = state.money
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/web/drop/sell_new")
    assert response.status_code == 200
    assert state.pending_drop is None
    assert state.money == initial_money + 120
    # Pending banner ушёл из обновлённого fragment.
    assert 'id="pending-drop"' not in response.text


def test_post_web_drop_sell_existing_swaps_item():
    """sell_existing: index=0 → item[0] продан, pending в инвентаре."""
    state = _state_with_pending_and_full_inventory()
    initial_money = state.money
    pending = state.pending_drop
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/web/drop/sell_existing", data={"index": 0})
    assert response.status_code == 200
    assert state.pending_drop is None
    assert state.money == initial_money + 25  # price проданного c-grade
    assert state.inventory[-1] is pending     # pending в конце инвентаря
    assert len(state.inventory) == 10
    assert 'id="pending-drop"' not in response.text


def test_post_web_drop_sell_existing_invalid_index_returns_error():
    """Out-of-range индекс → drop_error в баннере, pending не тронут."""
    state = _state_with_pending_and_full_inventory()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/web/drop/sell_existing", data={"index": 999})
    assert response.status_code == 200
    assert state.pending_drop is not None  # без мутации
    assert "Неверный индекс" in response.text


def test_post_web_drop_skip_keeps_pending():
    """skip: pending остаётся, fragment просто перерисовался."""
    state = _state_with_pending_and_full_inventory()
    pending = state.pending_drop
    initial_inv_len = len(state.inventory)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/web/drop/skip")
    assert response.status_code == 200
    assert state.pending_drop is pending
    assert len(state.inventory) == initial_inv_len
    # Banner всё ещё показан.
    assert 'id="pending-drop"' in response.text


# ----- POST /api/drop/* endpoints -----

def test_post_api_drop_sell_new_returns_json():
    """JSON sell_new: ok=True, money обновлён, pending=None."""
    state = _state_with_pending_and_full_inventory()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/drop/sell_new")
    data = response.json()
    assert data == {
        "ok": True,
        "money": 220.0,             # 100 + 120
        "inventory_size": 10,
        "pending_drop": None,
    }


def test_post_api_drop_sell_existing_returns_json():
    """JSON sell_existing: ok=True, inventory_size=10, money обновлён."""
    state = _state_with_pending_and_full_inventory()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/drop/sell_existing", json={"index": 0})
    data = response.json()
    assert data["ok"] is True
    assert data["money"] == 125.0  # 100 + 25 c-grade
    assert data["inventory_size"] == 10
    assert data["pending_drop"] is None


def test_post_api_drop_sell_existing_invalid_index():
    """JSON sell_existing с out-of-range index → 422 + error."""
    state = _state_with_pending_and_full_inventory()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/drop/sell_existing", json={"index": 999})
    assert response.status_code == 422
    assert "Неверный индекс" in response.json()["error"]


def test_post_api_drop_sell_new_no_pending():
    """JSON sell_new при pending=None → 422 + error."""
    _setup_state()  # default state — pending=None
    with TestClient(app) as client:
        response = client.post("/api/drop/sell_new")
    assert response.status_code == 422
    assert "Нет активной находки" in response.json()["error"]


# ----- Auto-collect on render (4.50.2 hook in _dashboard_context) -----

def test_auto_collect_fires_in_dashboard_when_room_freed():
    """Pending существует но cap расширилась через backpack_skill (например игрок
    прокачал в gym): _dashboard_context вызывает auto_collect_pending_drop и
    pending переезжает в инвентарь без UI prompt'а."""
    state = GameState.default_new_game()
    state.inventory = [_make_pending_item(grade='c-grade') for _ in range(10)]
    state.pending_drop = _make_pending_item(grade='a-grade')
    state.gym.backpack_skill = 1  # cap=11 → есть место
    _setup_state(state)

    with TestClient(app) as client:
        response = client.get("/status")
    # auto_collect должен сработать в _dashboard_context.
    assert state.pending_drop is None
    assert len(state.inventory) == 11
    assert 'id="pending-drop"' not in response.text


# ----- 4.54.6 — Web STALE response (Form + JSON) -----

def test_web_work_start_returns_stale_fragment_on_concurrent_save(monkeypatch):
    """POST /web/work/start при save_safe STALE → HTML fragment с auto-reload скриптом."""
    from google_sheets_db import GameStateRepo

    # Mock save_safe → STALE (concurrent write detected).
    monkeypatch.setattr(GameStateRepo, "save_safe",
                        lambda self, sd, expected_last_modified: "STALE")
    # И load для diff в _stale_response.
    # autouse fixture уже мокает load для returning {} dict.

    _setup_state(_state_for_work())
    with TestClient(app) as client:
        response = client.post("/web/work/start", data={"work_type": "watchman", "hours": "1"})

    assert response.status_code == 200
    assert 'stale-toast' in response.text
    assert 'Перезагружаю' in response.text
    assert 'window.location.reload' in response.text


def test_api_work_start_returns_409_with_stale_flag(monkeypatch):
    """POST /api/work/start при STALE → 409 + {ok: False, stale: True, diff}."""
    from google_sheets_db import GameStateRepo

    monkeypatch.setattr(GameStateRepo, "save_safe",
                        lambda self, sd, expected_last_modified: "STALE")

    _setup_state(_state_for_work())
    with TestClient(app) as client:
        response = client.post("/api/work/start", json={"work_type": "watchman", "hours": 1})

    assert response.status_code == 409
    payload = response.json()
    assert payload["ok"] is False
    assert payload["stale"] is True
    assert "diff" in payload


def test_web_gym_start_returns_stale_fragment(monkeypatch):
    """POST /web/gym/start при STALE → stale fragment."""
    from google_sheets_db import GameStateRepo

    monkeypatch.setattr(GameStateRepo, "save_safe",
                        lambda self, sd, expected_last_modified: "STALE")

    state = GameState.default_new_game()
    state.steps.today = 5000
    state.steps.can_use = 5000
    state.energy = 50
    state.money = 1000.0
    _setup_state(state)

    with TestClient(app) as client:
        response = client.post("/web/gym/start", data={"skill_name": "stamina"})

    assert response.status_code == 200
    assert 'stale-toast' in response.text


def test_web_level_allocate_returns_stale_fragment(monkeypatch):
    """POST /web/level/allocate при STALE → stale fragment."""
    from google_sheets_db import GameStateRepo

    monkeypatch.setattr(GameStateRepo, "save_safe",
                        lambda self, sd, expected_last_modified: "STALE")

    state = GameState.default_new_game()
    state.char_level.up_skills = 1
    _setup_state(state)

    with TestClient(app) as client:
        response = client.post("/web/level/allocate", data={"skill": "stamina"})

    assert response.status_code == 200
    assert 'stale-toast' in response.text


def test_stale_response_logs_sync_conflict_event(monkeypatch):
    """STALE-flow логирует event sync_conflict с source='web' через log_event."""
    from google_sheets_db import GameStateRepo
    import history

    monkeypatch.setattr(GameStateRepo, "save_safe",
                        lambda self, sd, expected_last_modified: "STALE")

    events = []

    def capture_event(event_type, **payload):
        events.append((event_type, payload))

    monkeypatch.setattr(history, "log_event", capture_event)

    _setup_state(_state_for_work())
    with TestClient(app) as client:
        client.post("/web/work/start", data={"work_type": "watchman", "hours": "1"})

    sync_events = [e for e in events if e[0] == 'sync_conflict']
    assert len(sync_events) >= 1
    payload = sync_events[0][1]
    assert payload.get('source') == 'web'
    assert payload.get('endpoint') == 'work'


# ============================================================================
# 4.48.3 — Web: Adventure (start endpoints + auto-finalize + drop notification)
# ============================================================================


def _state_for_adventure(can_use_steps=5000, energy=50):
    """Helper: state с достаточными ресурсами для walk_easy."""
    s = GameState.default_new_game()
    s.steps.today = can_use_steps
    s.steps.can_use = can_use_steps
    s.energy = energy
    s.date_last_enter = str(datetime.now().date())
    return s


# ----- _build_adventure_view (helper) -----

def test_adventure_view_walk_easy_unlocked_by_default():
    """walk_easy всегда unlocked (no unlock entry)."""
    from web.main import _build_adventure_view
    state = _state_for_adventure()
    _setup_state(state)
    view = _build_adventure_view(state)
    walk_easy = next(a for a in view['adventures'] if a['name'] == 'walk_easy')
    assert walk_easy['locked'] is False
    assert walk_easy['unlock_hint'] is None


def test_adventure_view_walk_normal_locked_until_3_walk_easy():
    """walk_normal locked пока не пройдёт walk_easy 3 раза."""
    from web.main import _build_adventure_view
    state = _state_for_adventure()
    state.adventure.counters['walk_easy'] = 2  # недостаточно
    _setup_state(state)
    view = _build_adventure_view(state)
    walk_normal = next(a for a in view['adventures'] if a['name'] == 'walk_normal')
    assert walk_normal['locked'] is True
    assert 'Прогулка вокруг озера' in walk_normal['unlock_hint']
    assert '1 прохож' in walk_normal['unlock_hint']  # 3 - 2 = 1 осталось


def test_adventure_view_walk_normal_unlocked_after_3_walk_easy():
    from web.main import _build_adventure_view
    state = _state_for_adventure()
    state.adventure.counters['walk_easy'] = 3
    _setup_state(state)
    view = _build_adventure_view(state)
    walk_normal = next(a for a in view['adventures'] if a['name'] == 'walk_normal')
    assert walk_normal['locked'] is False


def test_adventure_view_can_afford_reflects_resources():
    from web.main import _build_adventure_view
    state = _state_for_adventure(can_use_steps=5000, energy=50)
    _setup_state(state)
    view = _build_adventure_view(state)
    walk_easy = next(a for a in view['adventures'] if a['name'] == 'walk_easy')
    assert walk_easy['can_afford'] is True


def test_adventure_view_can_afford_false_when_insufficient_steps():
    from web.main import _build_adventure_view
    state = _state_for_adventure(can_use_steps=100, energy=50)
    _setup_state(state)
    view = _build_adventure_view(state)
    walk_easy = next(a for a in view['adventures'] if a['name'] == 'walk_easy')
    assert walk_easy['can_afford'] is False
    assert walk_easy['missing']['steps'] > 0


def test_adventure_view_probabilities_contain_at_least_one_grade():
    """compute_grade_probabilities → пары (grade, percent) для template."""
    from web.main import _build_adventure_view
    state = _state_for_adventure()
    _setup_state(state)
    view = _build_adventure_view(state)
    walk_easy = next(a for a in view['adventures'] if a['name'] == 'walk_easy')
    assert len(walk_easy['probabilities']) >= 1
    grade, pct = walk_easy['probabilities'][0]
    assert '%' in pct


def test_adventure_view_grade_labels_use_full_form():
    """Drop labels — полные формы «X-Grade» / «S+ Grade», не одиночные буквы.
    Игроку понятнее «B-Grade [29%]» чем «B [29%]» (4.48.3 polish после feedback)."""
    from web.main import _build_adventure_view
    state = _state_for_adventure()
    _setup_state(state)
    view = _build_adventure_view(state)
    # walk_easy → C-Grade присутствует.
    walk_easy = next(a for a in view['adventures'] if a['name'] == 'walk_easy')
    grade_labels = [g for g, _ in walk_easy['probabilities']]
    assert 'C-Grade' in grade_labels
    # walk_15k имеет тиры A/B/C/S — проверяем что несколько полных меток.
    state.adventure.counters['walk_hard'] = 3  # unlock walk_15k
    view = _build_adventure_view(state)
    walk_15k = next(a for a in view['adventures'] if a['name'] == 'walk_15k')
    walk_15k_labels = [g for g, _ in walk_15k['probabilities']]
    # walk_15k drops include B и A as minimum.
    assert any('-Grade' in g for g in walk_15k_labels)
    # Никаких одиночных букв.
    for g in walk_15k_labels:
        assert len(g) > 1, f'Label «{g}» — single char, ожидалась полная форма'


def test_adventure_view_s_plus_grade_uses_space_format():
    """S+ → «S+ Grade» (с пробелом, не «S+-Grade» с двойным дашем)."""
    from web.main import _GRADE_LABELS
    assert _GRADE_LABELS['s+grade'] == 'S+ Grade'
    assert _GRADE_LABELS['c-grade'] == 'C-Grade'
    assert _GRADE_LABELS['b-grade'] == 'B-Grade'
    assert _GRADE_LABELS['a-grade'] == 'A-Grade'
    assert _GRADE_LABELS['s-grade'] == 'S-Grade'


def test_adventure_view_active_flag_when_adventure_running():
    from web.main import _build_adventure_view
    state = _state_for_adventure()
    state.adventure.active = True
    state.adventure.name = 'walk_easy'
    state.adventure.end_ts = datetime.now().timestamp() + 600
    _setup_state(state)
    view = _build_adventure_view(state)
    assert view['active'] is True
    assert view['active_name'] == 'walk_easy'


# ----- _validate_and_apply_adventure -----

def test_validate_apply_adventure_rejects_when_already_active():
    from web.main import _validate_and_apply_adventure
    state = _state_for_adventure()
    state.adventure.active = True
    state.adventure.name = 'walk_easy'
    _setup_state(state)
    err = _validate_and_apply_adventure(state, 'walk_normal')
    assert err is not None
    assert 'уже идёт' in err


def test_validate_apply_adventure_rejects_unknown_name():
    from web.main import _validate_and_apply_adventure
    state = _state_for_adventure()
    _setup_state(state)
    err = _validate_and_apply_adventure(state, 'walk_nonexistent')
    assert err is not None
    assert 'Неизвестное' in err


def test_validate_apply_adventure_rejects_locked():
    from web.main import _validate_and_apply_adventure
    state = _state_for_adventure()
    state.adventure.counters['walk_easy'] = 0
    _setup_state(state)
    err = _validate_and_apply_adventure(state, 'walk_normal')
    assert err is not None
    assert 'Заблокировано' in err


def test_validate_apply_adventure_rejects_insufficient_resources():
    from web.main import _validate_and_apply_adventure
    state = _state_for_adventure(can_use_steps=10, energy=2)
    _setup_state(state)
    err = _validate_and_apply_adventure(state, 'walk_easy')
    assert err is not None
    assert 'Не хватает ресурсов' in err


def test_validate_apply_adventure_success_sets_state():
    from web.main import _validate_and_apply_adventure
    state = _state_for_adventure()
    _setup_state(state)
    err = _validate_and_apply_adventure(state, 'walk_easy')
    assert err is None
    assert state.adventure.active is True
    assert state.adventure.name == 'walk_easy'
    assert state.adventure.end_ts is not None


# ----- POST /web/adventure/start (Form) -----

def test_web_adventure_start_form_success_returns_fragment():
    state = _state_for_adventure()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/web/adventure/start", data={"adv_name": "walk_easy"})
    assert response.status_code == 200
    assert state.adventure.active is True
    assert state.adventure.name == 'walk_easy'


def test_web_adventure_start_form_locked_shows_error_in_body():
    state = _state_for_adventure()
    state.adventure.counters['walk_easy'] = 0
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/web/adventure/start", data={"adv_name": "walk_normal"})
    assert response.status_code == 200
    assert 'Заблокировано' in response.text
    assert state.adventure.active is False


# ----- POST /api/adventure/start (JSON) -----

def test_api_adventure_start_json_success():
    state = _state_for_adventure()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/adventure/start", json={"adv_name": "walk_easy"})
    assert response.status_code == 200
    payload = response.json()
    assert payload['ok'] is True
    assert payload['adventure']['active'] is True


def test_api_adventure_start_json_already_active_returns_409():
    state = _state_for_adventure()
    state.adventure.active = True
    state.adventure.name = 'walk_easy'
    state.adventure.end_ts = datetime.now().timestamp() + 600
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/adventure/start", json={"adv_name": "walk_normal"})
    assert response.status_code == 409
    payload = response.json()
    assert payload['ok'] is False


def test_api_adventure_start_json_validation_error_returns_422():
    state = _state_for_adventure(can_use_steps=10)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/adventure/start", json={"adv_name": "walk_easy"})
    assert response.status_code == 422
    assert response.json()['ok'] is False


def test_api_adventure_start_json_stale_returns_409(monkeypatch):
    from google_sheets_db import GameStateRepo
    monkeypatch.setattr(GameStateRepo, "save_safe",
                        lambda self, sd, expected_last_modified: "STALE")
    state = _state_for_adventure()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/adventure/start", json={"adv_name": "walk_easy"})
    assert response.status_code == 409
    payload = response.json()
    assert payload.get('stale') is True


# ----- _finalize_adventure_with_drop_capture + drop_notification -----

def test_finalize_does_nothing_when_adventure_not_active():
    from web.main import _finalize_adventure_with_drop_capture
    state = _state_for_adventure()
    state.adventure.active = False
    _setup_state(state)
    _finalize_adventure_with_drop_capture(state)
    assert state.last_adventure_drop is None


def test_finalize_does_nothing_when_end_ts_in_future():
    from web.main import _finalize_adventure_with_drop_capture
    state = _state_for_adventure()
    state.adventure.active = True
    state.adventure.name = 'walk_easy'
    state.adventure.end_ts = datetime.now().timestamp() + 600
    _setup_state(state)
    _finalize_adventure_with_drop_capture(state)
    assert state.adventure.active is True  # still active
    assert state.last_adventure_drop is None


def test_finalize_captures_dropped_item_when_inventory_grows(monkeypatch):
    """adventure_check_done → Drop_Item.item_collect добавляет item в inventory →
    finalize wrapper захватывает его в state.last_adventure_drop."""
    from web.main import _finalize_adventure_with_drop_capture
    from drop import Drop_Item

    state = _state_for_adventure()
    state.adventure.active = True
    state.adventure.name = 'walk_easy'
    state.adventure.end_ts = datetime.now().timestamp() - 1
    _setup_state(state)

    test_item = {
        'item_name': ['helmet'], 'item_type': ['helmet'], 'grade': ['a-grade'],
        'characteristic': ['stamina'], 'bonus': [8],
        'quality': [80.0], 'price': [50],
    }
    def fake_collect(self, hard, state):
        state.inventory.append(test_item)
    monkeypatch.setattr(Drop_Item, "item_collect", fake_collect)

    _finalize_adventure_with_drop_capture(state)

    assert state.adventure.active is False  # finalized
    assert state.last_adventure_drop is test_item


def test_finalize_captures_pending_drop_when_inventory_full(monkeypatch):
    """Inventory полон → drop → pending_drop → finalize захватывает pending."""
    from web.main import _finalize_adventure_with_drop_capture
    from drop import Drop_Item

    state = _state_for_adventure()
    state.adventure.active = True
    state.adventure.name = 'walk_easy'
    state.adventure.end_ts = datetime.now().timestamp() - 1
    _setup_state(state)

    pending_item = {
        'item_name': ['ring'], 'item_type': ['ring'], 'grade': ['b-grade'],
        'characteristic': ['luck'], 'bonus': [3],
        'quality': [50.0], 'price': [20],
    }
    def fake_collect(self, hard, state):
        state.pending_drop = pending_item
    monkeypatch.setattr(Drop_Item, "item_collect", fake_collect)

    _finalize_adventure_with_drop_capture(state)

    assert state.last_adventure_drop is pending_item


def test_drop_notification_banner_renders_when_set():
    state = _state_for_adventure()
    state.last_adventure_drop = {
        'item_name': ['helmet'], 'item_type': ['helmet'], 'grade': ['a-grade'],
        'characteristic': ['stamina'], 'bonus': [8],
        'quality': [80.0], 'price': [50],
    }
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert '🎁' in body
    assert 'Из приключения выпало' in body
    assert 'Helmet' in body


def test_drop_notification_banner_absent_when_none():
    state = _state_for_adventure()
    state.last_adventure_drop = None
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert 'Из приключения выпало' not in body


def test_drop_notification_cleared_after_steps_mutation():
    """Banner исчезает после первого успешного mutation (steps submit)."""
    state = _state_for_adventure()
    state.last_adventure_drop = {
        'item_name': ['helmet'], 'item_type': ['helmet'], 'grade': ['a-grade'],
        'characteristic': ['stamina'], 'bonus': [8],
        'quality': [80.0], 'price': [50],
    }
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/web/steps",
                               data={"steps": str(state.steps.today + 100)})
    assert state.last_adventure_drop is None
    assert 'Из приключения выпало' not in response.text


def test_drop_notification_cleared_after_work_mutation():
    """Banner исчезает после mutation через _persist_and_handle_stale (work_start)."""
    state = _state_for_adventure(can_use_steps=10000, energy=100)
    state.last_adventure_drop = {
        'item_name': ['ring'], 'item_type': ['ring'], 'grade': ['c-grade'],
        'characteristic': ['luck'], 'bonus': [1],
        'quality': [40.0], 'price': [10],
    }
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/web/work/start",
                               data={"work_type": "watchman", "hours": "1"})
    assert state.last_adventure_drop is None
    assert 'Из приключения выпало' not in response.text


# ----- Adventure section rendering -----

def test_adventure_section_shows_locked_with_hint():
    state = _state_for_adventure()
    state.adventure.counters['walk_easy'] = 0
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert '🔒' in body
    assert 'Прогулка вокруг озера' in body
    assert 'Прогулка по району' in body


def test_adventure_section_shows_start_button_for_unlocked_affordable():
    state = _state_for_adventure(can_use_steps=5000, energy=50)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert '▶ Старт' in body
    assert 'walk_easy' in body


def test_adventure_section_shows_summary_when_active():
    state = _state_for_adventure()
    state.adventure.active = True
    state.adventure.name = 'walk_easy'
    state.adventure.end_ts = datetime.now().timestamp() + 600
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert '▶ Старт' not in body
    assert 'идёт' in body


# ============================================================================
# 4.48.6 — Web: Inventory + Equipment (sell / wear / unwear endpoints + views)
# ============================================================================


def _make_inv_item(item_type='ring', grade='a-grade', characteristic='luck',
                   bonus=3, quality=80.0, price=120, item_name=None):
    """Helper: item-dict в legacy list-обёрточном формате (как `_make_item` в test_loadout)."""
    return {
        'item_name': [item_name or item_type],
        'item_type': [item_type],
        'grade': [grade],
        'characteristic': [characteristic],
        'bonus': [bonus],
        'quality': [quality],
        'price': [price],
    }


# ----- _sort_inventory_view -----

def test_sort_inventory_view_default():
    """Default sort = (item_type, characteristic, -bonus)."""
    from web.main import _sort_inventory_view
    inv = [
        _make_inv_item(item_type='ring', bonus=5),
        _make_inv_item(item_type='helmet', bonus=3),
        _make_inv_item(item_type='ring', bonus=10),
    ]
    sorted_pairs = _sort_inventory_view(inv, 'default')
    # helmet < ring alphabetically, ring 10 > ring 5
    assert [p[0] for p in sorted_pairs] == [1, 2, 0]  # helmet, ring-10, ring-5


def test_sort_inventory_view_by_grade():
    """Sort by grade = s+ → s → a → b → c."""
    from web.main import _sort_inventory_view
    inv = [
        _make_inv_item(grade='c-grade'),
        _make_inv_item(grade='s+grade'),
        _make_inv_item(grade='b-grade'),
    ]
    sorted_pairs = _sort_inventory_view(inv, 'grade')
    assert [p[0] for p in sorted_pairs] == [1, 2, 0]  # s+, b, c


def test_sort_inventory_view_by_price_desc():
    from web.main import _sort_inventory_view
    inv = [
        _make_inv_item(price=50),
        _make_inv_item(price=200),
        _make_inv_item(price=100),
    ]
    sorted_pairs = _sort_inventory_view(inv, 'price')
    assert [p[0] for p in sorted_pairs] == [1, 2, 0]  # 200, 100, 50


def test_sort_inventory_view_by_bonus_desc():
    from web.main import _sort_inventory_view
    inv = [
        _make_inv_item(bonus=2),
        _make_inv_item(bonus=8),
        _make_inv_item(bonus=5),
    ]
    sorted_pairs = _sort_inventory_view(inv, 'bonus')
    assert [p[0] for p in sorted_pairs] == [1, 2, 0]


def test_sort_inventory_view_invalid_key_falls_to_default():
    from web.main import _sort_inventory_view
    inv = [_make_inv_item(item_type='ring'), _make_inv_item(item_type='helmet')]
    sorted_pairs = _sort_inventory_view(inv, 'unknown_sort_key')
    # falls to default → helmet first.
    assert [p[0] for p in sorted_pairs] == [1, 0]


def test_sort_inventory_view_preserves_orig_index():
    """orig_index в результате должен соответствовать позиции в исходном inv."""
    from web.main import _sort_inventory_view
    inv = [_make_inv_item(bonus=i) for i in range(5)]
    sorted_pairs = _sort_inventory_view(inv, 'bonus')
    # Bonuses 0,1,2,3,4 → sorted desc → 4,3,2,1,0 → orig_indices 4,3,2,1,0.
    assert [p[0] for p in sorted_pairs] == [4, 3, 2, 1, 0]


# ----- _build_inventory_view -----

def test_inventory_view_includes_sort_metadata():
    from web.main import _build_inventory_view
    state = GameState.default_new_game()
    state.inventory = [_make_inv_item()]
    _setup_state(state)
    view = _build_inventory_view(state, 'grade')
    assert view['current_sort'] == 'grade'
    assert ('default', 'По типу') in view['sort_options']
    assert ('grade', 'По grade (S+ → C)') in view['sort_options']


def test_inventory_view_marks_equipment_items():
    """is_equipment=True для ring/helmet/etc; False для food."""
    from web.main import _build_inventory_view
    state = GameState.default_new_game()
    state.inventory = [
        _make_inv_item(item_type='ring'),
        _make_inv_item(item_type='cheeseburger'),  # food, не equipment
    ]
    _setup_state(state)
    view = _build_inventory_view(state, 'default')
    # default sort: cheeseburger before ring alphabetically.
    items_by_type = {i['item_type']: i for i in view['items']}
    assert items_by_type['ring']['is_equipment'] is True
    assert items_by_type['cheeseburger']['is_equipment'] is False


def test_inventory_view_ring_has_two_eligible_slots():
    from web.main import _build_inventory_view
    state = GameState.default_new_game()
    state.inventory = [_make_inv_item(item_type='ring')]
    _setup_state(state)
    view = _build_inventory_view(state, 'default')
    assert view['items'][0]['eligible_slots'] == ['finger_01', 'finger_02']


def test_inventory_view_non_ring_has_one_eligible_slot():
    from web.main import _build_inventory_view
    state = GameState.default_new_game()
    state.inventory = [_make_inv_item(item_type='helmet')]
    _setup_state(state)
    view = _build_inventory_view(state, 'default')
    assert view['items'][0]['eligible_slots'] == ['head']


def test_inventory_view_applies_trader_to_sell_price():
    """sell_price учитывает trader skill (4.28)."""
    from web.main import _build_inventory_view
    state = GameState.default_new_game()
    state.gym.trader = 50  # +50%
    state.inventory = [_make_inv_item(price=100)]
    _setup_state(state)
    view = _build_inventory_view(state, 'default')
    # 100 * 1.5 = 150
    assert view['items'][0]['sell_price'] == 150.0
    # price_raw остаётся оригинал.
    assert view['items'][0]['price_raw'] == 100


# ----- _build_equipment_view -----

def test_equipment_view_all_seven_slots():
    from web.main import _build_equipment_view
    state = GameState.default_new_game()
    _setup_state(state)
    view = _build_equipment_view(state)
    slot_attrs = [s['slot_attr'] for s in view['slots']]
    assert slot_attrs == ['head', 'neck', 'torso', 'finger_01',
                          'finger_02', 'legs', 'foots']


def test_equipment_view_can_unequip_false_for_empty_slot():
    from web.main import _build_equipment_view
    state = GameState.default_new_game()
    _setup_state(state)
    view = _build_equipment_view(state)
    for slot in view['slots']:
        assert slot['item'] is None
        assert slot['can_unequip'] is False


def test_equipment_view_can_unequip_true_when_item_and_inv_not_full():
    from web.main import _build_equipment_view
    state = GameState.default_new_game()
    state.equipment.head = _make_inv_item(item_type='helmet')
    _setup_state(state)
    view = _build_equipment_view(state)
    head_slot = next(s for s in view['slots'] if s['slot_attr'] == 'head')
    assert head_slot['can_unequip'] is True
    assert head_slot['block_reason'] is None


def test_equipment_view_blocks_unequip_when_inventory_full():
    """Inventory заполнен до cap → can_unequip=False с понятным reason."""
    from web.main import _build_equipment_view
    state = GameState.default_new_game()
    state.equipment.head = _make_inv_item(item_type='helmet')
    state.inventory = [_make_inv_item() for _ in range(10)]  # 10/10 default cap
    _setup_state(state)
    view = _build_equipment_view(state)
    head_slot = next(s for s in view['slots'] if s['slot_attr'] == 'head')
    assert head_slot['can_unequip'] is False
    assert 'Рюкзак полон' in head_slot['block_reason']
    assert view['inventory_full'] is True


# ----- _validate_and_apply_sell -----

def test_validate_sell_rejects_invalid_index():
    from web.main import _validate_and_apply_sell
    state = GameState.default_new_game()
    state.inventory = [_make_inv_item()]
    _setup_state(state)
    assert _validate_and_apply_sell(state, -1) is not None
    assert _validate_and_apply_sell(state, 99) is not None


def test_validate_sell_success_removes_item_and_credits_money():
    from web.main import _validate_and_apply_sell
    state = GameState.default_new_game()
    state.money = 1000.0
    state.inventory = [_make_inv_item(price=100)]
    _setup_state(state)
    err = _validate_and_apply_sell(state, 0)
    assert err is None
    assert len(state.inventory) == 0
    assert state.money > 1000.0  # money increased by sell price (with trader)


# ----- _validate_and_apply_wear -----

def test_validate_wear_non_ring_auto_picks_slot():
    """Для helmet — slot_attr=None разрешён, auto = head."""
    from web.main import _validate_and_apply_wear
    state = GameState.default_new_game()
    state.inventory = [_make_inv_item(item_type='helmet')]
    _setup_state(state)
    err = _validate_and_apply_wear(state, 0, slot_attr=None)
    assert err is None
    assert state.equipment.head is not None


def test_validate_wear_ring_requires_explicit_slot():
    """Для ring slot_attr=None → error (нужно явно finger_01 или finger_02)."""
    from web.main import _validate_and_apply_wear
    state = GameState.default_new_game()
    state.inventory = [_make_inv_item(item_type='ring')]
    _setup_state(state)
    err = _validate_and_apply_wear(state, 0, slot_attr=None)
    assert err is not None
    assert 'явный выбор' in err


def test_validate_wear_ring_to_explicit_finger():
    from web.main import _validate_and_apply_wear
    state = GameState.default_new_game()
    state.inventory = [_make_inv_item(item_type='ring')]
    _setup_state(state)
    err = _validate_and_apply_wear(state, 0, slot_attr='finger_02')
    assert err is None
    assert state.equipment.finger_02 is not None
    assert state.equipment.finger_01 is None


def test_validate_wear_rejects_invalid_slot_for_item_type():
    from web.main import _validate_and_apply_wear
    state = GameState.default_new_game()
    state.inventory = [_make_inv_item(item_type='helmet')]
    _setup_state(state)
    err = _validate_and_apply_wear(state, 0, slot_attr='finger_01')
    assert err is not None
    assert 'не подходит' in err


def test_validate_wear_rejects_non_equipment_item():
    """Food items нельзя надевать."""
    from web.main import _validate_and_apply_wear
    state = GameState.default_new_game()
    state.inventory = [_make_inv_item(item_type='cheeseburger')]
    _setup_state(state)
    err = _validate_and_apply_wear(state, 0)
    assert err is not None
    assert 'не является экипировкой' in err


def test_validate_wear_swap_returns_old_to_inventory():
    """Если slot занят — auto-swap (старый → inventory)."""
    from web.main import _validate_and_apply_wear
    state = GameState.default_new_game()
    old = _make_inv_item(item_type='helmet', bonus=2)
    new = _make_inv_item(item_type='helmet', bonus=8)
    state.equipment.head = old
    state.inventory = [new]
    _setup_state(state)
    err = _validate_and_apply_wear(state, 0)
    assert err is None
    assert state.equipment.head is new
    assert old in state.inventory


# ----- _validate_and_apply_unwear -----

def test_validate_unwear_rejects_invalid_slot():
    from web.main import _validate_and_apply_unwear
    state = GameState.default_new_game()
    _setup_state(state)
    err = _validate_and_apply_unwear(state, 'invalid_slot')
    assert err is not None
    assert 'Неверный слот' in err


def test_validate_unwear_rejects_empty_slot():
    from web.main import _validate_and_apply_unwear
    state = GameState.default_new_game()
    _setup_state(state)
    err = _validate_and_apply_unwear(state, 'head')
    assert err is not None
    assert 'пуст' in err


def test_validate_unwear_rejects_when_inventory_full():
    from web.main import _validate_and_apply_unwear
    state = GameState.default_new_game()
    state.equipment.head = _make_inv_item(item_type='helmet')
    state.inventory = [_make_inv_item() for _ in range(10)]  # at cap
    _setup_state(state)
    err = _validate_and_apply_unwear(state, 'head')
    assert err is not None
    assert 'Рюкзак полон' in err


def test_validate_unwear_success_moves_item_to_inventory():
    from web.main import _validate_and_apply_unwear
    state = GameState.default_new_game()
    helmet = _make_inv_item(item_type='helmet')
    state.equipment.head = helmet
    _setup_state(state)
    err = _validate_and_apply_unwear(state, 'head')
    assert err is None
    assert state.equipment.head is None
    assert helmet in state.inventory


# ----- POST /web/inventory/sell -----

def test_web_inventory_sell_form_success():
    state = GameState.default_new_game()
    state.money = 1000.0
    state.inventory = [_make_inv_item(price=50)]
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/web/inventory/sell",
                               data={"index": "0", "sort": "default"})
    assert response.status_code == 200
    assert len(state.inventory) == 0


def test_api_inventory_sell_json_success():
    state = GameState.default_new_game()
    state.money = 500.0
    state.inventory = [_make_inv_item(price=80)]
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/inventory/sell", json={"index": 0})
    assert response.status_code == 200
    assert response.json()['ok'] is True
    assert len(state.inventory) == 0


def test_api_inventory_sell_invalid_index_returns_422():
    state = GameState.default_new_game()
    state.inventory = []
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/inventory/sell", json={"index": 5})
    assert response.status_code == 422


# ----- POST /web/equipment/wear -----

def test_web_equipment_wear_form_non_ring_success():
    state = GameState.default_new_game()
    state.inventory = [_make_inv_item(item_type='helmet')]
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/web/equipment/wear",
                               data={"inventory_index": "0", "slot_attr": "head",
                                     "sort": "default"})
    assert response.status_code == 200
    assert state.equipment.head is not None


def test_api_equipment_wear_ring_explicit_finger_02():
    state = GameState.default_new_game()
    state.inventory = [_make_inv_item(item_type='ring')]
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/equipment/wear",
                               json={"inventory_index": 0, "slot_attr": "finger_02"})
    assert response.status_code == 200
    assert state.equipment.finger_02 is not None
    assert state.equipment.finger_01 is None


def test_api_equipment_wear_ring_without_slot_returns_422():
    state = GameState.default_new_game()
    state.inventory = [_make_inv_item(item_type='ring')]
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/equipment/wear",
                               json={"inventory_index": 0})
    assert response.status_code == 422


# ----- POST /web/equipment/unwear -----

def test_web_equipment_unwear_form_success():
    state = GameState.default_new_game()
    state.equipment.head = _make_inv_item(item_type='helmet')
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/web/equipment/unwear",
                               data={"slot_attr": "head", "sort": "default"})
    assert response.status_code == 200
    assert state.equipment.head is None


def test_api_equipment_unwear_full_inventory_returns_422():
    state = GameState.default_new_game()
    state.equipment.head = _make_inv_item(item_type='helmet')
    state.inventory = [_make_inv_item() for _ in range(10)]
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/equipment/unwear",
                               json={"slot_attr": "head"})
    assert response.status_code == 422
    assert 'Рюкзак полон' in response.json()['error']


# ----- STALE handling -----

def test_api_inventory_sell_stale_returns_409(monkeypatch):
    from google_sheets_db import GameStateRepo
    monkeypatch.setattr(GameStateRepo, "save_safe",
                        lambda self, sd, expected_last_modified: "STALE")
    state = GameState.default_new_game()
    state.inventory = [_make_inv_item(price=50)]
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/inventory/sell", json={"index": 0})
    assert response.status_code == 409
    assert response.json().get('stale') is True


# ----- Section rendering -----

def test_inventory_section_renders_sort_dropdown_when_not_empty():
    state = GameState.default_new_game()
    state.inventory = [_make_inv_item()]
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert 'name="sort"' in body
    assert 'По типу' in body  # default label
    assert 'По grade' in body


def test_inventory_section_renders_sell_button():
    state = GameState.default_new_game()
    state.inventory = [_make_inv_item(item_type='ring', price=50)]
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert '💰 Продать' in body
    assert '/web/inventory/sell' in body


def test_inventory_section_renders_two_buttons_for_ring():
    """Ring → 2 кнопки 'На палец 1' / 'На палец 2'."""
    state = GameState.default_new_game()
    state.inventory = [_make_inv_item(item_type='ring')]
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert 'На палец 1' in body
    assert 'На палец 2' in body


def test_inventory_section_renders_single_wear_button_for_helmet():
    state = GameState.default_new_game()
    state.inventory = [_make_inv_item(item_type='helmet')]
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Один Wear button для helmet, без 'На палец'.
    assert '🧥 Надеть' in body
    assert 'На палец 1' not in body


def test_equipment_section_renders_unwear_button_when_can():
    state = GameState.default_new_game()
    state.equipment.head = _make_inv_item(item_type='helmet')
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert '🗑 Снять' in body
    assert '/web/equipment/unwear' in body


def test_equipment_section_disables_unwear_when_inventory_full():
    state = GameState.default_new_game()
    state.equipment.head = _make_inv_item(item_type='helmet')
    state.inventory = [_make_inv_item() for _ in range(10)]
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Кнопка показана, но disabled.
    assert 'disabled' in body
    assert 'Рюкзак полон' in body  # warning под кнопками


# ============================================================================
# 4.63.3 — Web UI для optimizer + presets (Phase 3 зонтичной 4.63)
# ============================================================================


# ----- _build_loadout_view -----

def test_loadout_view_includes_four_characteristics():
    from web.main import _build_loadout_view
    state = GameState.default_new_game()
    _setup_state(state)
    view = _build_loadout_view(state)
    keys = [c['key'] for c in view['characteristics']]
    assert keys == ['stamina', 'energy_max', 'speed_skill', 'luck']


def test_loadout_view_current_bonus_reflects_equipment():
    """current_bonus = sum bonuses from equipment по characteristic."""
    from web.main import _build_loadout_view
    state = GameState.default_new_game()
    state.equipment.head = _make_inv_item(characteristic='stamina', bonus=8)
    state.equipment.torso = _make_inv_item(item_type='t-shirt',
                                            characteristic='stamina', bonus=5)
    state.equipment.foots = _make_inv_item(item_type='shoes',
                                            characteristic='luck', bonus=3)
    _setup_state(state)
    view = _build_loadout_view(state)
    by_key = {c['key']: c for c in view['characteristics']}
    assert by_key['stamina']['current_bonus'] == 13
    assert by_key['luck']['current_bonus'] == 3
    assert by_key['energy_max']['current_bonus'] == 0


def test_loadout_view_empty_presets():
    from web.main import _build_loadout_view
    state = GameState.default_new_game()
    _setup_state(state)
    view = _build_loadout_view(state)
    assert view['presets'] == []


def test_loadout_view_presets_summary_with_bonuses():
    from web.main import _build_loadout_view
    from loadout import save_preset
    state = GameState.default_new_game()
    state.equipment.head = _make_inv_item(characteristic='stamina', bonus=8)
    state.equipment.torso = _make_inv_item(item_type='t-shirt',
                                            characteristic='luck', bonus=4)
    _setup_state(state)
    save_preset(state, 'training')
    view = _build_loadout_view(state)
    assert len(view['presets']) == 1
    preset = view['presets'][0]
    assert preset['name'] == 'training'
    assert preset['slots_filled'] == 2
    assert preset['bonuses']['stamina'] == 8
    assert preset['bonuses']['luck'] == 4


# ----- _build_optimize_preview -----

def test_optimize_preview_returns_diff_and_bonus_change():
    from web.main import _build_optimize_preview
    state = GameState.default_new_game()
    state.equipment.head = _make_inv_item(item_type='helmet',
                                            characteristic='energy_max', bonus=3)
    state.inventory = [_make_inv_item(item_type='helmet',
                                       characteristic='energy_max', bonus=10)]
    _setup_state(state)
    preview = _build_optimize_preview(state, 'energy_max')
    assert preview['kind'] == 'optimize'
    assert preview['subject_key'] == 'energy_max'
    assert '🔋' in preview['subject_label']
    # diff должен показывать замену head слота.
    assert any('Голова' in d['slot_label'] for d in preview['diff_items'])
    assert preview['bonus_before'] == 3
    assert preview['bonus_after'] == 10


def test_optimize_preview_empty_diff_when_optimal():
    from web.main import _build_optimize_preview
    state = GameState.default_new_game()
    state.equipment.head = _make_inv_item(item_type='helmet',
                                            characteristic='stamina', bonus=10)
    _setup_state(state)
    preview = _build_optimize_preview(state, 'stamina')
    assert preview['diff_items'] == []
    assert preview['bonus_before'] == preview['bonus_after']


# ----- _build_preset_preview -----

def test_preset_preview_returns_none_for_unknown_name():
    from web.main import _build_preset_preview
    state = GameState.default_new_game()
    _setup_state(state)
    assert _build_preset_preview(state, 'nonexistent') is None


def test_preset_preview_includes_diff_and_warnings_for_lost_items():
    from web.main import _build_preset_preview
    state = GameState.default_new_game()
    # Preset вручную — содержит item которого нет в pool.
    state.equipment_presets['p1'] = {
        'head': {'item_name': ['lost'], 'item_type': ['helmet'], 'grade': ['s-grade'],
                 'characteristic': ['stamina'], 'bonus': [99], 'quality': [100], 'price': [200]},
        'neck': None, 'torso': None, 'finger_01': None, 'finger_02': None,
        'legs': None, 'foots': None,
    }
    _setup_state(state)
    preview = _build_preset_preview(state, 'p1')
    assert preview is not None
    assert preview['kind'] == 'preset'
    assert len(preview['warnings']) == 1  # lost item warning


# ----- _validate_and_apply_optimize -----

def test_validate_optimize_rejects_unknown_characteristic():
    from web.main import _validate_and_apply_optimize
    state = GameState.default_new_game()
    _setup_state(state)
    err = _validate_and_apply_optimize(state, 'unknown_char')
    assert err is not None
    assert 'Неподдерживаемая' in err


def test_validate_optimize_applies_swap_from_inventory():
    from web.main import _validate_and_apply_optimize
    state = GameState.default_new_game()
    # helmet item_type → попадает в head слот (ring item_type попал бы в finger_01/02).
    weak = _make_inv_item(item_type='helmet', characteristic='stamina', bonus=3)
    strong = _make_inv_item(item_type='helmet', characteristic='stamina', bonus=8)
    state.equipment.head = weak
    state.inventory = [strong]
    _setup_state(state)
    err = _validate_and_apply_optimize(state, 'stamina')
    assert err is None
    assert state.equipment.head is strong
    assert weak in state.inventory


# ----- _validate_and_apply_save_preset / load / delete -----

def test_validate_save_preset_success():
    from web.main import _validate_and_apply_save_preset
    state = GameState.default_new_game()
    state.equipment.head = _make_inv_item(bonus=5)
    _setup_state(state)
    err = _validate_and_apply_save_preset(state, 'training')
    assert err is None
    assert 'training' in state.equipment_presets


def test_validate_save_preset_rejects_empty_name():
    from web.main import _validate_and_apply_save_preset
    state = GameState.default_new_game()
    _setup_state(state)
    err = _validate_and_apply_save_preset(state, '   ')
    assert err is not None


def test_validate_load_preset_success():
    from web.main import _validate_and_apply_save_preset, _validate_and_apply_load_preset
    state = GameState.default_new_game()
    h1 = _make_inv_item(characteristic='stamina', bonus=5)
    h2 = _make_inv_item(characteristic='energy_max', bonus=8)
    state.equipment.head = h1
    state.inventory = [h2]
    _setup_state(state)
    _validate_and_apply_save_preset(state, 'stamina_load')
    # Swap to h2.
    state.equipment.head = h2
    state.inventory = [h1]
    # Load → back to h1.
    err = _validate_and_apply_load_preset(state, 'stamina_load')
    assert err is None
    assert state.equipment.head is h1


def test_validate_load_preset_unknown_name():
    from web.main import _validate_and_apply_load_preset
    state = GameState.default_new_game()
    _setup_state(state)
    err = _validate_and_apply_load_preset(state, 'missing')
    assert err is not None
    assert 'не найден' in err


def test_validate_delete_preset_success():
    from web.main import _validate_and_apply_save_preset, _validate_and_apply_delete_preset
    state = GameState.default_new_game()
    _setup_state(state)
    _validate_and_apply_save_preset(state, 'p1')
    err = _validate_and_apply_delete_preset(state, 'p1')
    assert err is None
    assert 'p1' not in state.equipment_presets


# ----- POST /web/loadout/* + /web/preset/* -----

def test_web_loadout_preview_returns_fragment_with_preview_banner():
    state = GameState.default_new_game()
    state.equipment.head = _make_inv_item(characteristic='energy_max', bonus=3)
    state.inventory = [_make_inv_item(characteristic='energy_max', bonus=10)]
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/web/loadout/preview",
                               data={"characteristic": "energy_max"})
    assert response.status_code == 200
    body = response.text
    assert 'Preview оптимизации' in body
    assert '✅ Применить' in body
    assert '❌ Отмена' in body
    # State не мутирован.
    assert state.equipment.head['bonus'] == [3]


def test_web_loadout_optimize_applies_mutation():
    state = GameState.default_new_game()
    state.equipment.head = _make_inv_item(item_type='helmet',
                                            characteristic='stamina', bonus=3)
    state.inventory = [_make_inv_item(item_type='helmet',
                                       characteristic='stamina', bonus=8)]
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/web/loadout/optimize",
                               data={"characteristic": "stamina"})
    assert response.status_code == 200
    assert state.equipment.head['bonus'] == [8]


def test_web_preset_save_creates_preset():
    state = GameState.default_new_game()
    state.equipment.head = _make_inv_item(bonus=5)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/web/preset/save",
                               data={"name": "my_loadout"})
    assert response.status_code == 200
    assert 'my_loadout' in state.equipment_presets


def test_web_preset_delete_removes_preset():
    from loadout import save_preset
    state = GameState.default_new_game()
    state.equipment.head = _make_inv_item(bonus=5)
    _setup_state(state)
    save_preset(state, 'p1')
    with TestClient(app) as client:
        response = client.post("/web/preset/delete",
                               data={"name": "p1"})
    assert response.status_code == 200
    assert 'p1' not in state.equipment_presets


# ----- POST /api/loadout/* + /api/preset/* -----

def test_api_loadout_optimize_success():
    state = GameState.default_new_game()
    state.equipment.head = _make_inv_item(item_type='helmet',
                                            characteristic='energy_max', bonus=3)
    state.inventory = [_make_inv_item(item_type='helmet',
                                       characteristic='energy_max', bonus=10)]
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/loadout/optimize",
                               json={"characteristic": "energy_max"})
    assert response.status_code == 200
    payload = response.json()
    assert payload['ok'] is True
    assert payload['characteristic'] == 'energy_max'
    assert payload['bonus_after'] == 10


def test_api_loadout_optimize_unknown_char_returns_422():
    state = GameState.default_new_game()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/loadout/optimize",
                               json={"characteristic": "unknown"})
    assert response.status_code == 422


def test_api_preset_save_success():
    state = GameState.default_new_game()
    state.equipment.head = _make_inv_item(bonus=5)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/preset/save",
                               json={"name": "training"})
    assert response.status_code == 200
    payload = response.json()
    assert payload['ok'] is True
    assert payload['name'] == 'training'
    assert payload['presets_count'] == 1


def test_api_preset_load_unknown_returns_422():
    state = GameState.default_new_game()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/preset/load",
                               json={"name": "missing"})
    assert response.status_code == 422


def test_api_preset_delete_unknown_returns_422():
    state = GameState.default_new_game()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/preset/delete",
                               json={"name": "missing"})
    assert response.status_code == 422


# ----- STALE handling -----

def test_api_loadout_optimize_stale_returns_409(monkeypatch):
    from google_sheets_db import GameStateRepo
    monkeypatch.setattr(GameStateRepo, "save_safe",
                        lambda self, sd, expected_last_modified: "STALE")
    state = GameState.default_new_game()
    state.equipment.head = _make_inv_item(item_type='helmet',
                                            characteristic='stamina', bonus=3)
    state.inventory = [_make_inv_item(item_type='helmet',
                                       characteristic='stamina', bonus=8)]
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/loadout/optimize",
                               json={"characteristic": "stamina"})
    assert response.status_code == 409
    assert response.json().get('stale') is True


# ----- Section rendering -----

def test_loadout_section_renders_characteristic_dropdown():
    state = GameState.default_new_game()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert 'Auto-Optimizer' in body
    assert 'Stamina' in body
    assert 'Energy Max' in body


def test_loadout_section_renders_save_preset_form():
    state = GameState.default_new_game()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert '💾 Сохранить' in body
    assert '/web/preset/save' in body


def test_loadout_section_shows_no_presets_message_when_empty():
    state = GameState.default_new_game()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert 'нет сохранённых' in body.lower()


def test_loadout_section_renders_preset_with_load_and_delete():
    from loadout import save_preset
    state = GameState.default_new_game()
    state.equipment.head = _make_inv_item(characteristic='stamina', bonus=8)
    _setup_state(state)
    save_preset(state, 'training')
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert 'training' in body
    assert '📥 Preview Load' in body
    assert '🗑 Delete' in body


# ============================================================================
# 4.48.9 — Web: Банк (депозиты + кредиты)
# ============================================================================


def _state_for_bank(money=1000.0, banking=5, loan_capacity=10, loan_reduction=0):
    """Helper: state с unlocked bank skills + money."""
    s = GameState.default_new_game()
    s.money = money
    s.gym.banking_interest_rate = banking
    s.gym.loan_capacity = loan_capacity
    s.gym.loan_interest_reduction = loan_reduction
    s.date_last_enter = str(datetime.now().date())
    return s


# ----- _build_bank_view -----

def test_bank_view_locked_when_no_skills():
    from web.main import _build_bank_view
    state = GameState.default_new_game()  # banking=0, loan_capacity=0
    _setup_state(state)
    view = _build_bank_view(state)
    assert view['can_open_deposit'] is False
    assert view['can_take_loan'] is False
    assert view['locked_reason'] is not None


def test_bank_view_unlocked_when_skills_present():
    from web.main import _build_bank_view
    state = _state_for_bank()
    _setup_state(state)
    view = _build_bank_view(state)
    assert view['can_open_deposit'] is True
    assert view['can_take_loan'] is True
    assert view['locked_reason'] is None


def test_bank_view_rates_reflect_skills():
    from web.main import _build_bank_view
    state = _state_for_bank(banking=10, loan_reduction=20)
    _setup_state(state)
    view = _build_bank_view(state)
    assert view['rate_deposit_pct'] == 10.0  # 0% base + 10/level
    assert view['rate_loan_pct'] == 80.0  # 100% base - 20/level


def test_bank_view_max_loan_amount():
    """max_loan = loan_capacity * 100."""
    from web.main import _build_bank_view
    state = _state_for_bank(loan_capacity=7)
    _setup_state(state)
    view = _build_bank_view(state)
    assert view['max_loan_amount'] == 700
    assert view['loan_available'] == 700  # nothing borrowed


# ----- _validate_and_apply_bank_op -----

def test_bank_op_rejects_unknown_op():
    from web.main import _validate_and_apply_bank_op
    state = _state_for_bank()
    _setup_state(state)
    err = _validate_and_apply_bank_op(state, 'unknown_op', 100)
    assert err is not None
    assert 'Неизвестная' in err


def test_bank_op_deposit_success_moves_money_to_deposit():
    from web.main import _validate_and_apply_bank_op
    state = _state_for_bank(money=500.0)
    _setup_state(state)
    err = _validate_and_apply_bank_op(state, 'deposit', 200)
    assert err is None
    assert state.money == 300.0
    assert state.bank.deposit_amount == 200


def test_bank_op_deposit_rejects_when_skill_zero():
    from web.main import _validate_and_apply_bank_op
    state = GameState.default_new_game()
    state.money = 500.0  # banking=0 still
    _setup_state(state)
    err = _validate_and_apply_bank_op(state, 'deposit', 100)
    assert err is not None
    assert 'Banking Interest Rate' in err


def test_bank_op_deposit_rejects_insufficient_money():
    from web.main import _validate_and_apply_bank_op
    state = _state_for_bank(money=50.0)
    _setup_state(state)
    err = _validate_and_apply_bank_op(state, 'deposit', 100)
    assert err is not None
    assert 'Недостаточно денег' in err


def test_bank_op_deposit_rejects_zero_amount():
    from web.main import _validate_and_apply_bank_op
    state = _state_for_bank()
    _setup_state(state)
    err = _validate_and_apply_bank_op(state, 'deposit', 0)
    assert err is not None
    assert 'положительной' in err


def test_bank_op_deposit_all_moves_wallet_money():
    from web.main import _validate_and_apply_bank_op
    state = _state_for_bank(money=123.45)
    _setup_state(state)
    err = _validate_and_apply_bank_op(state, 'deposit_all')
    assert err is None
    assert state.money == 0
    assert state.bank.deposit_amount == 123.45


def test_bank_op_deposit_all_rejects_empty_wallet():
    from web.main import _validate_and_apply_bank_op
    state = _state_for_bank(money=0.0)
    _setup_state(state)
    err = _validate_and_apply_bank_op(state, 'deposit_all')
    assert err is not None
    assert 'пуст' in err


def test_bank_op_withdraw_success():
    import time as _time
    from web.main import _validate_and_apply_bank_op
    state = _state_for_bank(money=0.0)
    state.bank.deposit_amount = 500.0
    state.bank.deposit_last_interest_ts = _time.time()  # ts=now → accrue=0
    _setup_state(state)
    err = _validate_and_apply_bank_op(state, 'withdraw', 100)
    assert err is None
    assert state.money == 100.0


def test_bank_op_withdraw_rejects_amount_too_large():
    import time as _time
    from web.main import _validate_and_apply_bank_op
    state = _state_for_bank(money=0.0)
    state.bank.deposit_amount = 50.0
    state.bank.deposit_last_interest_ts = _time.time()
    _setup_state(state)
    err = _validate_and_apply_bank_op(state, 'withdraw', 100)
    assert err is not None
    assert 'больше доступного' in err


def test_bank_op_withdraw_all_clears_deposit():
    import time as _time
    import pytest
    from web.main import _validate_and_apply_bank_op
    state = _state_for_bank(money=0.0)
    state.bank.deposit_amount = 250.0
    state.bank.deposit_last_interest_ts = _time.time()
    _setup_state(state)
    err = _validate_and_apply_bank_op(state, 'withdraw_all')
    assert err is None
    # μ-проценты могут добавиться за elapsed между ts и accrue.
    assert state.money == pytest.approx(250.0, abs=0.01)
    assert state.bank.deposit_amount == 0  # withdraw_all всегда чистит


def test_bank_op_take_loan_success():
    from web.main import _validate_and_apply_bank_op
    state = _state_for_bank(money=0.0, loan_capacity=5)
    _setup_state(state)
    err = _validate_and_apply_bank_op(state, 'take_loan', 300)
    assert err is None
    assert state.money == 300.0
    assert state.bank.loan_amount == 300


def test_bank_op_take_loan_rejects_when_no_capacity():
    from web.main import _validate_and_apply_bank_op
    state = GameState.default_new_game()  # loan_capacity=0
    _setup_state(state)
    err = _validate_and_apply_bank_op(state, 'take_loan', 100)
    assert err is not None
    assert 'Loan Capacity' in err


def test_bank_op_take_loan_rejects_when_exceeds_limit():
    from web.main import _validate_and_apply_bank_op
    state = _state_for_bank(loan_capacity=3)  # max=300
    _setup_state(state)
    err = _validate_and_apply_bank_op(state, 'take_loan', 500)
    assert err is not None
    assert 'больше доступного лимита' in err


def test_bank_op_repay_loan_success():
    import time as _time
    import pytest
    from web.main import _validate_and_apply_bank_op
    state = _state_for_bank(money=500.0)
    state.bank.loan_amount = 200.0
    state.bank.loan_last_interest_ts = _time.time()
    _setup_state(state)
    err = _validate_and_apply_bank_op(state, 'repay_loan', 100)
    assert err is None
    assert state.money == 400.0
    # μ-проценты могут накопиться за elapsed между ts и accrue в _repay_loan.
    assert state.bank.loan_amount == pytest.approx(100, abs=0.01)


def test_bank_op_repay_all_clears_loan():
    """repay_all с large money (без проблем с накопленными %% за elapsed)."""
    from web.main import _validate_and_apply_bank_op
    state = _state_for_bank(money=999_999.0)  # достаточно покрыть любые μ-проценты
    state.bank.loan_amount = 200.0
    # ts=now чтобы elapsed=0 → accrue=0.
    import time as _time
    state.bank.loan_last_interest_ts = _time.time()
    _setup_state(state)
    err = _validate_and_apply_bank_op(state, 'repay_all')
    assert err is None
    assert state.bank.loan_amount == 0


def test_bank_op_repay_rejects_no_loan():
    from web.main import _validate_and_apply_bank_op
    state = _state_for_bank()
    _setup_state(state)
    err = _validate_and_apply_bank_op(state, 'repay_loan', 100)
    assert err is not None
    assert 'Нет долга' in err


# ----- POST /web/bank/* -----

def test_web_bank_deposit_form_success():
    """POST через TestClient → render → accrue_deposit добавляет μ-проценты,
    поэтому asserts через `approx` (~1e-9 tolerance)."""
    import pytest
    state = _state_for_bank(money=500.0)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/web/bank/deposit", data={"amount": "200"})
    assert response.status_code == 200
    assert state.bank.deposit_amount == pytest.approx(200, abs=0.001)


def test_web_bank_take_loan_form_success():
    import pytest
    state = _state_for_bank(money=0.0)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/web/bank/take_loan", data={"amount": "300"})
    assert response.status_code == 200
    assert state.bank.loan_amount == pytest.approx(300, abs=0.001)


def test_web_bank_withdraw_all_form():
    state = _state_for_bank(money=0.0)
    state.bank.deposit_amount = 150.0
    import time as _time
    state.bank.deposit_last_interest_ts = _time.time()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/web/bank/withdraw_all")
    assert response.status_code == 200
    assert state.bank.deposit_amount == 0  # withdraw_all точно обнуляет
    assert state.money >= 150.0  # μ-проценты могут добавиться, но не отнять


# ----- POST /api/bank/* -----

def test_api_bank_deposit_json_success():
    state = _state_for_bank(money=500.0)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/bank/deposit", json={"amount": 200})
    assert response.status_code == 200
    payload = response.json()
    assert payload['ok'] is True
    assert payload['money'] == 300.0
    assert payload['deposit'] == 200


def test_api_bank_take_loan_returns_money_loan_state():
    state = _state_for_bank(money=0.0)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/bank/take_loan", json={"amount": 250})
    assert response.status_code == 200
    payload = response.json()
    assert payload['money'] == 250.0
    assert payload['loan'] == 250


def test_api_bank_deposit_insufficient_money_returns_422():
    state = _state_for_bank(money=50.0)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/bank/deposit", json={"amount": 100})
    assert response.status_code == 422


def test_api_bank_deposit_zero_amount_returns_422():
    """Pydantic gt=0 rejects 0."""
    state = _state_for_bank()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/bank/deposit", json={"amount": 0})
    assert response.status_code == 422


def test_api_bank_repay_all_no_loan_returns_422():
    state = _state_for_bank()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/bank/repay_all")
    assert response.status_code == 422


# ----- STALE handling -----

def test_api_bank_deposit_stale_returns_409(monkeypatch):
    from google_sheets_db import GameStateRepo
    monkeypatch.setattr(GameStateRepo, "save_safe",
                        lambda self, sd, expected_last_modified: "STALE")
    state = _state_for_bank(money=500.0)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.post("/api/bank/deposit", json={"amount": 100})
    assert response.status_code == 409
    assert response.json().get('stale') is True


# ----- Section rendering -----

def test_bank_section_renders_summary_for_locked_state():
    state = GameState.default_new_game()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Locked state — summary с замочком + лозунгом про прокачку.
    assert '🏦' in body
    assert '🔒' in body


def test_bank_section_renders_deposit_and_loan_blocks_when_unlocked():
    state = _state_for_bank()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert '💰 Депозит' in body
    assert '💸 Кредит' in body
    assert '/web/bank/deposit' in body
    assert '/web/bank/take_loan' in body


def test_bank_section_hides_withdraw_when_no_deposit():
    """Withdraw кнопки не рендерятся когда депозит=0."""
    state = _state_for_bank()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert '/web/bank/withdraw' not in body


def test_bank_section_hides_repay_when_no_loan():
    state = _state_for_bank()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert '/web/bank/repay' not in body


def test_bank_section_take_loan_hx_confirm_includes_rate():
    """hx-confirm на take_loan должен показывать rate-инфо в тексте."""
    state = _state_for_bank(loan_reduction=20)  # rate 80%
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert 'годовых' in body
    assert '80.0%' in body or '80%' in body

