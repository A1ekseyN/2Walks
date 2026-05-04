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
    monkeypatch.setattr(StepsLogRepo, "for_day", fake_for_day)
    # Локальный CSV/JSON save_characteristic — патчим прямо в характеристиках
    # И в work (там import-time copy в work_check_done).
    import characteristics as _ch
    import work as _wm
    monkeypatch.setattr(_ch, "save_characteristic", lambda: None)
    monkeypatch.setattr(_wm, "save_characteristic", lambda: None)
    # И в web.sync (persist_state_to_cloud зовёт save_characteristic локально —
    # после переноса helper'а из web/main.py в web/sync.py в 0.2.1b).
    import web.sync as _wsync_mod
    monkeypatch.setattr(_wsync_mod, "save_characteristic", lambda: None)
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
    assert "20 $" in body  # 5 * 4
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


def test_finished_adventure_shows_warning_not_timer():
    """end_ts < now — приключение фактически закончилось, но не финализировано."""
    state = GameState.default_new_game()
    state.adventure.active = True
    state.adventure.name = "walk_15k"
    state.adventure.end_ts = datetime.now().timestamp() - 60  # 1 минуту назад
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert "Adventure finished" in body
    # Таймер на adv не показывается, потому что ветка ушла в "finished"
    # (training/work тоже не активны → data-end-ts отсутствует).
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
    assert "171 $" in body


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

def test_active_work_does_not_render_progress_bar():
    """Work — только таймер до конца смены, без progress bar и без % текста
    (0.2.1c follow-up — упрощение UI)."""
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
    # Прогресс-бар работы убран — но adventure/training-прогресс может ещё быть,
    # так что проверяем что внутри Work-блока нет <progress>. Adventure/training
    # не активны — секции для них не рендерятся.
    # Считаем что весь "data-progress-start-ts" должен отсутствовать.
    assert "data-progress-start-ts=" not in body


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


def test_finished_adventure_shows_progress_100_and_claim_warning():
    """Adventure с end в прошлом → progress 100 + ✓ Завершено + warning о CLI claim."""
    state = GameState.default_new_game()
    state.adventure.active = True
    state.adventure.name = "walk_easy"
    state.adventure.start_ts = (datetime.now() - timedelta(hours=1)).timestamp()
    state.adventure.end_ts = (datetime.now() - timedelta(seconds=1)).timestamp()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert 'value="100.00"' in body
    assert "✓ Завершено" in body
    assert "Adventure finished" in body
    assert "claim drop" in body


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
    assert "<details>" in inv_section
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
    """Summary инвентаря показывает счётчик (N)."""
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
    # Summary содержит "(2)" сразу после "Инвентарь</strong>".
    assert "Инвентарь</strong> (2)" in body


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
    таймер, но при рестарте uvicorn'а или CLI-чтении смены нет."""
    from google_sheets_db import GameStateRepo
    saved_to_sheets = []
    saved_locally = []

    monkeypatch.setattr(GameStateRepo, "save",
                        lambda self, data, user_id=None: saved_to_sheets.append(data))
    import web.sync as ws
    monkeypatch.setattr(ws, "save_characteristic", lambda: saved_locally.append(1))

    _setup_state(_state_for_work())
    with TestClient(app) as client:
        response = client.post("/web/work/start", data={"work_type": "watchman", "hours": "1"})

    assert response.status_code == 200
    assert len(saved_locally) == 1, "save_characteristic (CSV+JSON) должен быть вызван"
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
    persist НЕ вызван (нет смысла писать неизменённый state в Sheets)."""
    from google_sheets_db import GameStateRepo
    saved_to_sheets = []
    monkeypatch.setattr(GameStateRepo, "save",
                        lambda self, data, user_id=None: saved_to_sheets.append(data))
    import web.sync as ws
    saved_locally = []
    monkeypatch.setattr(ws, "save_characteristic", lambda: saved_locally.append(1))

    _setup_state(_state_for_work())
    with TestClient(app) as client:
        # Unknown work_type → 422-валидация Python.
        client.post("/web/work/start", data={"work_type": "ceo", "hours": "1"})

    assert saved_to_sheets == []
    assert saved_locally == []


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
    # В лог записано про Sheets-fail.
    captured = capsys.readouterr()
    assert "Sheets save failed" in captured.out


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
    от баг 2.2.2 — бесплатной энергии после максимума)."""
    state = GameState.default_new_game()
    state.energy = 65
    state.energy_max = 65
    state.energy_time_stamp = datetime.now().timestamp() - 1000  # давно
    _setup_state(state)

    with TestClient(app) as client:
        client.get("/status")

    assert state.energy == 65
    # Stamp подтянулся к now.
    assert abs(state.energy_time_stamp - datetime.now().timestamp()) < 2


def test_energy_data_attrs_in_dom():
    """В DOM-фрагменте есть все 4 data-атрибута для JS-таймера."""
    state = GameState.default_new_game()
    state.energy = 30
    state.energy_max = 65
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


def test_energy_interval_with_speed_bonus():
    """Speed-бонус 25% → interval = 60 * 0.75 = 45 сек на +1 энергии."""
    state = GameState.default_new_game()
    state.energy = 30
    state.energy_max = 65
    state.gym.speed_skill = 25  # 25% бонус
    # Stamp 90 сек назад → 90 // 45 = 2 → +2 энергии.
    state.energy_time_stamp = datetime.now().timestamp() - 90
    _setup_state(state)

    with TestClient(app) as client:
        response = client.get("/status")

    assert state.energy == 32
    # И data-energy-interval = 45 в DOM.
    body = response.text
    assert 'data-energy-interval="45"' in body


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
    """4.48.4 follow-up: каждый из 8 навыков обёрнут в собственный nested
    <details>, свёрнут по умолчанию — игрок раскрывает только нужные."""
    _setup_state(_state_for_gym())
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    gym_pos = body.find('id="gym"')
    next_section_pos = body.find('id="bonuses"', gym_pos)
    gym_section = body[gym_pos:next_section_pos]
    # Внутри Gym-блока есть 8 nested <details> — по одному на каждый навык.
    import re
    details_tags = re.findall(r'<details(?:\s[^>]*)?>', gym_section)
    # 1 внешний + 8 nested = 9.
    assert len(details_tags) == 9
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


def test_web_gym_start_with_energy_max_returns_unavailable():
    """energy_max сейчас не реализован — должен возвращать ошибку."""
    _setup_state(_state_for_gym())
    with TestClient(app) as client:
        response = client.post("/web/gym/start", data={"skill_name": "energy_max"})
    assert response.status_code == 200
    body = response.text
    assert "4.48.4.1" in body or "Особая логика" in body


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

def test_build_gym_skills_returns_8_entries():
    from web.main import _build_gym_skills
    state = _state_for_gym()
    skills = _build_gym_skills(state)
    keys = [s["key"] for s in skills]
    assert keys == [
        "stamina", "energy_max", "speed_skill", "luck_skill",
        "move_optimization_adventure", "move_optimization_gym",
        "move_optimization_work", "neatness_in_using_things",
    ]


def test_build_gym_skills_marks_energy_max_unavailable():
    from web.main import _build_gym_skills
    state = _state_for_gym()
    skills = _build_gym_skills(state)
    energy_max = next(s for s in skills if s["key"] == "energy_max")
    assert energy_max["available"] is False
    assert "4.48.4.1" in energy_max["unavailable_reason"]


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
