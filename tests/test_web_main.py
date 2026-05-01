"""Тесты FastAPI скелета и dashboard (задачи 4.48.0 + 4.48.1).

Используется ``fastapi.testclient.TestClient`` — он автоматически вызывает
lifespan на входе/выходе из контекста. Перед TestClient мы инициализируем
``game.state`` через ``init_game_state(GameState.default_new_game())``;
повторный вызов в lifespan — no-op (idempotent), Sheets не дёргается.
"""

from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from characteristics import game, init_game_state
from state import GameState
from web.main import VERSION, app


def _setup_state(state=None):
    """Сбросить container и заполнить дефолтным state — так lifespan не пойдёт в Sheets."""
    game.state = None
    init_game_state(state if state is not None else GameState.default_new_game())


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


def test_dashboard_includes_htmx_polling_attributes():
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/")
    body = response.text
    assert 'hx-get="/status"' in body
    assert 'hx-trigger="every 15s"' in body


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
    state.steps.can_use = 4500
    state.energy = 30
    state.money = 250
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert "4,500" in body  # steps.can_use formatted
    assert "30" in body
    assert "250" in body


# ----- Active sessions -----

def test_active_training_renders_with_data_end_ts():
    state = GameState.default_new_game()
    state.training.active = True
    state.training.skill_name = "stamina"
    state.training.time_end = datetime(2026, 5, 1, 18, 0, 0)
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
    state.work.end = datetime(2026, 5, 1, 19, 0, 0)
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
